"""定量校验 height_scanner 测出的**踏步高度**是否等于地形真实高度。

思路（2026-11-02，用户提议"让狗落到楼梯上"）:
  把 env 放在已知 riser 的楼梯上(``--terrain stairs --stair_level 6 --stairs_dir up``
  -> riser 固定 0.16 m), 让狗沿直线前进跨过台阶棱边。当 1.6x1.0 m / 0.1 m 的 17x11
  射线栅格**横跨一条棱边**时, 187 个格子会分成两簇, 两簇的差值就是"扫描仪测到的踏步高度"。
  因为 ``mdp.height_scan = pos_w.z - hit_z - offset`` 里的 offset 是**每格相同**的常数,
  两簇相减时 offset 完全抵消 -> 不必知道 offset 就能得到踏步高度, 直接和 0.16 m 对比。

同时打印 hit_z 的世界高度, 用"最高簇 - 最低簇"独立算一次, 两者应一致。

用法:
  python scripts/diagnose/check_height_scanner_step.py --num_envs 2 --steps 400 --level 6
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "rsl_rl"))

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=2)
parser.add_argument("--steps", type=int, default=400, help="前进步数 (每步 0.02 s)")
parser.add_argument("--level", type=int, default=6, help="楼梯等级 0-9 (riser = 0.02 + lvl/9*0.21)")
parser.add_argument("--speed", type=float, default=0.3, help="直线前进速度 m/s")
parser.add_argument("--riser", type=float, default=0.16, help="预期踏步高度 m (用于对比)")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

import unitree_rl_lab.tasks.locomotion  # noqa: F401,E402
from unitree_rl_lab.tasks.locomotion import mdp  # noqa: E402
from terrain_presets import apply_terrain  # noqa: E402

TASK = "Unitree-GeesunDog-LingsiD30W-Velocity"
TERM = "height_scanner"


def main() -> None:
    cfg = parse_env_cfg(TASK, device=args.device, num_envs=args.num_envs)
    # 已知 riser 的楼梯: 倒金字塔(坑底出生, 向前=上楼), 固定等级
    desc = apply_terrain(cfg, "stairs", stairs_dir="up", stair_level=args.level)
    print(f"\n[terrain] {desc}")
    # 期望踏步高度直接从生成后的地形 cfg 读 (--stair_level 会把范围压成 (h,h)),
    # 避免手写 --riser 与地形不一致 (例如 level 3 实际是 0.09 m)。
    try:
        _sub = cfg.scene.terrain.terrain_generator.sub_terrains["stairs"]
        args.riser = float(_sub.step_height_range[0])
        print(f"[terrain] expected riser (from cfg) = {args.riser:.3f} m")
    except Exception as exc:  # 保底: 用命令行给的 riser
        print(f"[WARN] could not read riser from cfg ({exc}); using --riser {args.riser:.3f}")
    # 纯直线前进命令, 关闭站立 env
    cfg.commands.base_velocity.ranges.lin_vel_x = (args.speed, args.speed)
    cfg.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
    cfg.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)
    cfg.commands.base_velocity.rel_standing_envs = 0.0
    cfg.curriculum = None

    env = gym.make(TASK, cfg=cfg).unwrapped
    env.reset()
    sensor = env.scene.sensors[TERM]
    robot = env.scene["robot"]
    terrain = env.scene.terrain
    n_rays = sensor.data.ray_hits_w.shape[1]
    print(f"[sensor] {n_rays} rays (17x11 grid, 0.1 m, 1.6x1.0 m)")

    action = torch.zeros(env.num_envs, sum(env.action_manager.action_term_dim), device=env.device)
    # 平移扫描: 沿 +x 以 5 cm 步长把机器人从坑中心平移到坑壁, 让 1.6 m 长的栅格跨过第一级棱边。
    # 零动作站立时机器人不会自己走 (实测 spread 恒为 0), 所以必须显式平移才能"让它落到楼梯上"。
    root = robot.data.default_root_state.clone()  # (N, 13) 世界系, 已含 env_origins
    sweep = torch.arange(0.0, 1.61, 0.05, device=env.device)
    best = None
    rows = []  # (off, spread, i, scan, hit_z, base_z)
    for off in sweep:
        pose = root.clone()
        # 关键: z 必须相对"本次地形的坑底"(env_origins.z) 设定, 否则 default_root_state 会把狗
        # 放到坑口顶面(z≈0.6), 射线全部打到平地 -> spread 恒为 0 (踩过的坑)。
        pose[:, 0] = terrain.env_origins[:, 0] + off
        pose[:, 1] = terrain.env_origins[:, 1]
        pose[:, 2] = terrain.env_origins[:, 2] + 0.62
        pose[:, 3] = 1.0
        pose[:, 4] = 0.0
        pose[:, 5] = 0.0
        pose[:, 6] = 0.0
        robot.write_root_pose_to_sim(pose[:, :7])
        robot.write_root_velocity_to_sim(pose[:, 7:])
        env.step(action)  # 让 ray caster 按新位姿刷新
        hit_z = sensor.data.ray_hits_w[:, :, 2]
        base_z = robot.data.root_pos_w[:, 2]
        spread = hit_z.max(dim=1).values - hit_z.min(dim=1).values
        i = int(spread.argmax())
        rows.append((float(off), float(spread[i]), i,
                     (base_z[i].unsqueeze(-1) - hit_z[i] - 0.5).clone(), hit_z[i].clone(),
                     float(base_z[i])))
    print("\n  offset  " + " ".join(f"{r[0]:4.2f}" for r in rows))
    print("  spread  " + " ".join(f"{r[1]:4.2f}" for r in rows))
    # 只跨"一条棱边"的偏移才是单级踏步的测量: spread 应 ≈ riser (0.16)。
    # 跨两级 -> 0.32, 三级 -> 0.48 (实测正是 0.16 的整数倍, 说明扫描仪线性且准确)。
    # 候选窗口按 riser 相对选取 (绝对窗口会在 riser=0.02 时漏掉单级、误选 3 级):
    cands = [r for r in rows if 0.5 * args.riser < r[1] < 1.5 * args.riser]
    if cands:
        best = min(cands, key=lambda r: abs(r[1] - args.riser))
    else:
        best = max(rows, key=lambda r: r[1])
    spread, off, i = best[0], best[1], best[2]
    k = off
    scan, hit_z, base_z = best[3], best[4], best[5]
    print(f"  (最大 spread 出现在 x 偏移 {off:.2f} m 处)")
    # 两簇聚类: 贴近日最小值的是"下一级踏面", 贴近日最大值的是"上一级踏面"。
    # (早先版本用 10% 分位取均值, 当上一级只占少数格子时会被稀释成 0.089 m -> 误判;
    #  紧邻 min/max 的容差聚类才是正确的"两级踏面"估计。)
    # 容差必须远小于 riser, 否则两级会被并成一簇 (riser=0.02 时 tol=0.02 直接把台阶抹平)
    tol = min(0.02, 0.3 * args.riser)
    lo_mask = hit_z < (float(hit_z.min()) + tol)
    hi_mask = hit_z > (float(hit_z.max()) - tol)
    hit_lo, hit_hi = float(hit_z[lo_mask].mean()), float(hit_z[hi_mask].mean())
    scan_lo = float(scan[lo_mask].mean())
    scan_hi = float(scan[hi_mask].mean())
    print(f"\n=== widest-spread frame (grid straddles a step edge): step {k}, env{i}, base_z={base_z:+.3f} ===")
    print(f"  cells: lower step {int(lo_mask.sum())}/{n_rays}, upper step {int(hi_mask.sum())}/{n_rays}")
    print(f"  hit_z  两簇中心: low={hit_lo:+.3f} high={hit_hi:+.3f} -> 踏步高 = {hit_hi - hit_lo:.3f} m")
    print(f"  scan   两簇中心: low={scan_lo:+.3f} high={scan_hi:+.3f} -> 踏步高 = {scan_hi - scan_lo:.3f} m")
    print(f"  (max-min 口径: {float(hit_z.max()) - float(hit_z.min()):.3f} m)")
    print(f"  期望 riser = {args.riser:.3f} m")
    # scan = base_z - hit_z - offset: 地形越高 -> scan 越小, 所以两簇差是负号, 取绝对值再比。
    err_h = abs(abs(hit_hi - hit_lo) - args.riser)
    err_s = abs(abs(scan_hi - scan_lo) - args.riser)
    print(f"  误差: hit_z 口径 {err_h * 1000:.1f} mm, scan 口径 {err_s * 1000:.1f} mm")
    print(f"  pit(env_origins.z)={float(terrain.env_origins[i, 2]):+.3f}  "
          f"dz_vs_pit={base_z - float(terrain.env_origins[i, 2]):+.3f}")
    ok = err_h < 0.02 and err_s < 0.02
    print(f"\n[VERDICT] height_scanner 与地形真实踏步高度"
          f"{'一致 (误差 < 20 mm)' if ok else '不一致 (误差 >= 20 mm)'}")
    sys.stdout.flush()
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()

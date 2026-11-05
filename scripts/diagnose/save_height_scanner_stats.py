"""Post-training: measure & SAVE the height_scanner term's spatial stats per ablation arm.

After each arm finishes training, run this to persist a per-arm record of the height_scanner
(高度扫描传感器) observation term - specifically 高度差 (height diff = max-min), 均值 (mean),
方差 (variance), plus std/min/max and an alive/absent verdict. This is the artifact that shows,
arm by arm, whether the privileged terrain term is present and actually carrying terrain:

  A (baseline)   : height_scanner present                       -> alive, variance > 0
  C (AiryStacked): height_scanner present (stacked with Airy)   -> alive, variance > 0
  B (AiryReplace): height_scanner ABSENT (replaced by Airy BEV) -> present = false
  D (ProprioOnly): height_scanner ABSENT (no external sensing)  -> present = false

WHY fast_terrain: shrink the generator to a 1x2 grid of flat + pyramid_stairs with no curriculum,
so startup takes seconds instead of minutes, while still exposing real terrain relief. A flat
plane alone would give a constant grid (zero variance) and could not distinguish a live term from
a clip-dead one.

Run:
    python scripts/diagnose/save_height_scanner_stats.py --headless --task Unitree-Go2-Velocity
    python scripts/diagnose/save_height_scanner_stats.py --headless --task Unitree-Go2-Velocity-AiryStacked

Output: outputs/height_scanner_stats/<arm>.json  (one file per task suffix)
Exit: 0 = present-and-alive OR absent (expected for B/D); 1 = present-but-clip-dead.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

parser = argparse.ArgumentParser(description="Save height_scanner height_diff/mean/variance per arm")
parser.add_argument("--task", default="Unitree-Go2-Velocity",
                    help="gym task id; A baseline by default, -AiryStacked/-AiryReplace/-ProprioOnly work too")
parser.add_argument("--num_envs", type=int, default=8)
parser.add_argument("--steps", type=int, default=30)
parser.add_argument("--out", default=str(REPO / "outputs" / "height_scanner_stats"))

# NOTE: do not parse_args() here - AppLauncher contributes --headless/--device further down.
from isaaclab.app import AppLauncher  # noqa: E402

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch  # noqa: E402
import gymnasium as gym  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

import unitree_rl_lab.tasks.locomotion  # noqa: F401,E402
from unitree_rl_lab.tasks.locomotion import mdp  # noqa: E402

TERM = "height_scanner"
OUT = Path(args_cli.out)
OUT.mkdir(parents=True, exist_ok=True)


def arm_name(task: str) -> str:
    suffix = task.replace("Unitree-Go2-Velocity", "").lstrip("-")
    return suffix or "A_baseline"


def finish(record: dict, code: int) -> None:
    path = OUT / f"{arm_name(args_cli.task)}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"[SUMMARY] {args_cli.task}: wrote {path}")
    sys.stdout.flush()
    os._exit(code)  # simulation_app.close() HANGS here (C++ kit teardown deadlock); os._exit is reliable


def main() -> int:
    cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs)
    from unitree_rl_lab.utils.offline_assets import patch_command_visualizers
    print(f"[assets] patched {patch_command_visualizers(cfg)} cloud visualizer(s) -> local")
    gen = cfg.scene.terrain.terrain_generator
    if gen is not None:
        gen.num_rows, gen.num_cols = 1, 2
        gen.sub_terrains = {k: v for k, v in gen.sub_terrains.items() if k in ("pyramid_stairs", "flat")}
        gen.curriculum = False
        cfg.scene.terrain.max_init_terrain_level = 0
    cfg.scene.num_envs = min(args_cli.num_envs, 8)

    env = gym.make(args_cli.task, cfg=cfg).unwrapped
    obs, _ = env.reset()
    for _ in range(args_cli.steps):
        action = torch.zeros(env.num_envs, sum(env.action_manager.action_term_dim), device=env.device)
        obs, *_ = env.step(action)

    om = env.observation_manager
    record = {
        "task": args_cli.task,
        "arm": arm_name(args_cli.task),
        "num_envs": int(env.num_envs),
        "steps": args_cli.steps,
    }

    present = any(TERM in om.active_terms[g] for g in om.active_terms)
    if not present:
        record.update(present=False,
                      note="height_scanner not in any obs group (expected for AiryReplace / ProprioOnly)")
        print(f"[STATS] {args_cli.task}: height_scanner ABSENT")
        finish(record, 0)

    group = next(g for g in om.active_terms if TERM in om.active_terms[g])
    names = om.active_terms[group]
    term_cfg = om._group_obs_term_cfgs[group][names.index(TERM)]
    clip = term_cfg.clip
    sensor_cfg = term_cfg.params.get("sensor_cfg", SceneEntityCfg(TERM))
    offset_used = term_cfg.params.get("offset", 0.5)

    raw = mdp.height_scan(env, sensor_cfg, offset=offset_used)
    clipped = raw.clone().clamp(min=clip[0], max=clip[1]) if clip else raw
    f = clipped.reshape(-1).float()

    height_diff = float(f.max() - f.min())
    mean = float(f.mean())
    variance = float(f.var(unbiased=False))
    std = float(f.std(unbiased=False))
    at_upper = float((clipped >= clip[1] - 1e-6).float().mean()) if clip else 0.0
    at_lower = float((clipped <= clip[0] + 1e-6).float().mean()) if clip else 0.0

    sensor = env.scene.sensors[sensor_cfg.name]
    hit_z = sensor.data.ray_hits_w[..., 2]
    fin = torch.isfinite(hit_z).all(dim=-1)
    hit_z = hit_z[fin] if bool(fin.any()) else hit_z.reshape(-1)

    alive = std > 1e-4 and (at_upper + at_lower) < 0.999
    record.update(
        present=True,
        group=group,
        dims=int(raw.shape[-1]),
        clip=list(clip) if clip else None,
        offset_used=offset_used,
        height_diff=round(height_diff, 4),
        mean=round(mean, 4),
        variance=round(variance, 6),
        std=round(std, 5),
        min=round(float(f.min()), 4),
        max=round(float(f.max()), 4),
        frac_at_upper_clip=round(at_upper, 4),
        frac_at_lower_clip=round(at_lower, 4),
        hit_z_range=[round(float(hit_z.min()), 3), round(float(hit_z.max()), 3)],
        alive=alive,
        verdict="ALIVE" if alive else "DEAD(clip-saturated)",
    )
    print(f"[STATS] {args_cli.task} ({record['arm']}): height_diff={height_diff:.4f} "
          f"mean={mean:.4f} variance={variance:.6f} std={std:.5f}")
    print(f"[STATS] clipped=[{f.min():.3f},{f.max():.3f}] at_clip(u={at_upper:.2f},l={at_lower:.2f}) "
          f"hit_z=[{float(hit_z.min()):.3f},{float(hit_z.max()):.3f}] -> {record['verdict']}")
    finish(record, 0 if alive else 1)


if __name__ == "__main__":
    main()

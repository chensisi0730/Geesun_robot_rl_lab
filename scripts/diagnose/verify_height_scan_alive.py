"""Is the height_scanner (高度扫描传感器) observation term ALIVE, or saturated by its clip?

Phase 0 of the height_scanner (高度扫描传感器) benefit evaluation. It builds the real task env,
steps it, and MEASURES the observation term statistics per term. Nothing is hardcoded: every
previous ablation table in this repo was written from *assumed* widths and values, and the measured
truth is different (policy is 57 dims, not 49; critic A is 263, not 936).

WHY THIS SCRIPT EXISTS
----------------------
``mdp.height_scan`` (Isaac Lab ``isaaclab/envs/mdp/observations.py:297``) returns

    height = sensor_pos_w.z - hit_point_z - offset          # offset defaults to 0.5

The task hangs the scanner 20 m above ``base_link`` (``OffsetCfg(pos=(0,0,20))``), so

    sensor_pos_w.z = base_z + 20 ~= 0.61 + 20 = 20.61       (lingsi_d30w standing height)
    hit_point_z    ~= 0 .. 0.23                             (terrain surface / stair riser)
    raw            ~= 19.9 .. 20.1

with ``clip=(-1.0, 5.0)`` -> **every one of the 187 cells is the constant 5.0**. A critic fed 187
constants learns nothing about the terrain, so the A-vs-D ablation measures "187 extra constant
inputs", not the height_scanner benefit. This script decides it empirically.

WHAT IT REPORTS
---------------
* per-term measured widths for every group (the ablation dimension table, measured not assumed)
* RAW term values (pre-clip) and CLIPPED values: min/max/std and the fraction pinned at a clip bound
* the analytic prediction above printed next to the measurement, so a mismatch is visible
* verdict ``SATURATED`` (dead term) / ``ALIVE`` (carries terrain information)
* with ``--offset``, the same statistics recomputed under a candidate offset: a live proof that the
  one-number fix (``offset = 20.5``) revives the term

Run:
    python scripts/diagnose/verify_height_scan_alive.py --headless --num_envs 16
    python scripts/diagnose/verify_height_scan_alive.py --headless --num_envs 16 --offset 20.5
    python scripts/diagnose/verify_height_scan_alive.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryStacked

Exit code: 0 = ALIVE, 1 = SATURATED (so the monitoring daemon can gate on it).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

parser = argparse.ArgumentParser(description="Check the height_scanner obs term is not clip-saturated")
parser.add_argument("--task", default="Unitree-GeesunDog-LingsiD30W-Velocity",
                    help="gym task id; A baseline by default, -AiryStacked/-AiryReplace/-ProprioOnly work too")
parser.add_argument("--num_envs", type=int, default=16, help="keep this small; the terrain mesh BVH dominates VRAM")
parser.add_argument("--steps", type=int, default=30, help="steps to run; terrain height varies with the robot pose")
parser.add_argument("--offset", type=float, default=None,
                    help="recompute the term with this offset (candidate fix, e.g. 20.5) and report it too")
parser.add_argument("--fast_terrain", action="store_true",
                    help="shrink the terrain generator to 1x2 (flat + pyramid_stairs only) so startup takes "
                         "seconds instead of minutes. Stairs stay in the scene, so the grid still varies - "
                         "a flat plane CANNOT prove the term is alive (constant hit_z -> constant output).")
parser.add_argument("--out", type=str, default=str(REPO / "outputs" / "verify_height_scan"))

# NOTE: do not call parse_args() here - AppLauncher contributes --headless/--device further down.
from isaaclab.app import AppLauncher  # noqa: E402

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch  # noqa: E402

import gymnasium as gym  # noqa: E402

from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

import unitree_rl_lab.tasks.locomotion  # noqa: F401,E402  (registers the gym tasks)
from unitree_rl_lab.tasks.locomotion import mdp  # noqa: E402

OUT = Path(args_cli.out)
OUT.mkdir(parents=True, exist_ok=True)

TERM = "height_scanner"
STD_ALIVE = 0.02  # a live terrain grid over stairs varies by centimetres; a constant varies by 0


def stats(t: torch.Tensor) -> dict:
    """min/max/mean/std + unique count of a (N, D) term tensor, flattened."""
    f = t.reshape(-1).float()
    return {
        "min": round(float(f.min()), 4),
        "max": round(float(f.max()), 4),
        "mean": round(float(f.mean()), 4),
        "std": round(float(f.std()), 5),
        "unique": int(torch.unique(f.round(decimals=4)).numel()),
    }


def main() -> int:
    cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs)
    if args_cli.fast_terrain:
        # 4 envs live per terrain cell, so 1x2 = 2 terrains caps the scene at 8 envs. Keeping
        # pyramid_stairs is the whole point: the height grid must vary, or a dead term and a
        # live term look identical.
        gen = cfg.scene.terrain.terrain_generator
        if gen is not None:
            gen.num_rows, gen.num_cols = 1, 2
            gen.sub_terrains = {k: v for k, v in gen.sub_terrains.items()
                                if k in ("pyramid_stairs", "flat")}
            gen.curriculum = False
            cfg.scene.terrain.max_init_terrain_level = 0
        cfg.scene.num_envs = min(args_cli.num_envs, 8)
        print(f"[INFO] fast_terrain: {len(gen.sub_terrains) if gen else 0} sub-terrains, "
              f"{cfg.scene.num_envs} envs", flush=True)
    env = gym.make(args_cli.task, cfg=cfg).unwrapped
    obs, _ = env.reset()
    for _ in range(args_cli.steps):
        action = torch.zeros(env.num_envs, sum(env.action_manager.action_term_dim), device=env.device)
        obs, _r, _te, _tr, _i = env.step(action)

    om = env.observation_manager
    report: dict = {"task": args_cli.task, "num_envs": args_cli.num_envs, "groups": {}}

    # ---- 1) measured per-term widths (the ablation table, measured not assumed) ----------
    for group in om.active_terms:
        names = om.active_terms[group]
        dims = [int(sum(d)) for d in om._group_obs_term_dim[group]]
        report["groups"][group] = {"terms": dict(zip(names, dims)), "total": int(sum(dims))}
        print(f"[DIMS] {group:7s} total={sum(dims):5d}  " + ", ".join(f"{n}={d}" for n, d in zip(names, dims)))

    # ---- 2) the height_scanner term: raw vs clipped ---------------------------------------
    verdict = "ABSENT"
    for group in om.active_terms:
        names = om.active_terms[group]
        if TERM not in names:
            continue
        term_cfg = om._group_obs_term_cfgs[group][names.index(TERM)]
        clip = term_cfg.clip
        sensor_cfg = term_cfg.params.get("sensor_cfg", SceneEntityCfg(TERM))
        offset_used = term_cfg.params.get("offset", 0.5)

        raw = mdp.height_scan(env, sensor_cfg, offset=offset_used)
        clipped = raw.clone().clamp(min=clip[0], max=clip[1]) if clip else raw

        sensor = env.scene.sensors[sensor_cfg.name]
        pos_z = sensor.data.pos_w[:, 2]
        hits = sensor.data.ray_hits_w
        finite = torch.isfinite(hits).all(dim=-1)
        hit_z = hits[..., 2][finite] if bool(finite.any()) else hits[..., 2].reshape(-1)

        at_upper = float((clipped >= clip[1] - 1e-6).float().mean()) if clip else 0.0
        at_lower = float((clipped <= clip[0] + 1e-6).float().mean()) if clip else 0.0

        entry = {
            "group": group,
            "clip": list(clip) if clip else None,
            "offset_used": offset_used,
            "dims": int(raw.shape[-1]),
            "raw": stats(raw),
            "clipped": stats(clipped),
            "frac_at_upper_clip": round(at_upper, 4),
            "frac_at_lower_clip": round(at_lower, 4),
            "sensor_pos_z": [round(float(pos_z.min()), 3), round(float(pos_z.max()), 3)],
            "hit_z": [round(float(hit_z.min()), 3), round(float(hit_z.max()), 3)],
            "analytic_raw_range": [round(float(pos_z.min() - hit_z.max() - offset_used), 3),
                                   round(float(pos_z.max() - hit_z.min() - offset_used), 3)],
        }
        entry["verdict"] = "SATURATED" if entry["clipped"]["std"] < STD_ALIVE else "ALIVE"
        report["groups"][group][TERM] = entry
        verdict = entry["verdict"]

        print(f"[OBS] {group}/{TERM} clip={clip} offset={offset_used} dims={entry['dims']}")
        print(f"      raw     {entry['raw']}")
        print(f"      clipped {entry['clipped']}  at_upper={at_upper:.2f} at_lower={at_lower:.2f}")
        print(f"      sensor_z={entry['sensor_pos_z']} hit_z={entry['hit_z']} "
              f"analytic_raw={entry['analytic_raw_range']}")
        print(f"      [VERDICT] {entry['verdict']}"
              + ("  <- every cell pinned at a clip bound: the term carries NO terrain information"
                 if verdict == "SATURATED" else ""))

        # ---- 3) candidate fix proof: same term, same sensor, different offset ------------
        if args_cli.offset is not None and group == "critic":
            cand = mdp.height_scan(env, sensor_cfg, offset=args_cli.offset)
            cand_clip = cand.clone().clamp(min=-1.0, max=1.0)
            fix = {
                "offset": args_cli.offset,
                "raw": stats(cand),
                "clipped_to_-1_1": stats(cand_clip),
                "expected_formula": "base_z - hit_z - 0.5  (offset = 20.5 cancels the 20 m hang)",
            }
            fix["verdict"] = "ALIVE" if fix["clipped_to_-1_1"]["std"] >= STD_ALIVE else "STILL_DEAD"
            entry["candidate_offset_fix"] = fix
            print(f"[FIX] offset={args_cli.offset} -> clipped {fix['clipped_to_-1_1']} "
                  f"[VERDICT] {fix['verdict']}")

    report["verdict"] = verdict
    (OUT / "stats.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[INFO] wrote {OUT / 'stats.json'}")
    print(f"[SUMMARY] {args_cli.task}: height_scanner term is {verdict}")
    return 0 if verdict == "ALIVE" else 1


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)


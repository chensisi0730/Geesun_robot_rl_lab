"""Smoke test: actually build each Airy ablation env, step it, and measure the observations.

``verify_airy_obs_dims.py`` only inspects *config objects*; it never creates an environment, so it
cannot catch runtime failures: an ObsTerm whose tensor shape disagrees with its clip, a sensor that
receives no data, a LiDAR whose beams all miss, or a BEV grid stuck at zero.

Each config runs in its OWN subprocess (see ``--single``). Building a second ``ManagerBasedRLEnv``
inside one Isaac Sim process tears down the USD stage that the first sensor's ray patterns still
reference, and aborts from C++ with ``UsdExpiredPrimAccessError: Used null prim`` - a Python
try/except cannot catch that, so process isolation is the only reliable route.

Obs widths are MEASURED per term, never hardcoded: a hardcoded expectation would only re-assert
whatever we believed while writing the code (and we did get it wrong - policy is 57, not 49).

Run:  python scripts/diagnose/smoke_env_obs.py --headless --num_envs 64 --steps 50
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CONFIGS = [
    ("A baseline    ", ""),
    ("B airy_replace", "-AiryReplace"),
    ("C airy_stacked", "-AiryStacked"),
    ("D proprio_only", "-ProprioOnly"),
]
BASE_TASK = "Unitree-GeesunDog-LingsiD30W-Velocity"
RESULT_JSON = REPO / "outputs" / "smoke_env_obs_result.json"


def run_single(suffix: str, num_envs: int, steps: int) -> dict:
    """Build one env, step it, and return the measured observation widths."""
    from isaaclab.app import AppLauncher

    # Strip this script's own flags before AppLauncher parses: its ArgumentParser rejects unknown
    # args such as --single / --num_envs / --steps.
    argv = sys.argv[1:]
    for flag in ("--single", "--num_envs", "--steps"):
        if flag in argv:
            k = argv.index(flag)
            del argv[k:k + 2]

    parser = argparse.ArgumentParser()
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args(argv)
    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app

    import time

    import gymnasium as gym
    import torch

    from isaaclab_tasks.utils import parse_env_cfg

    import unitree_rl_lab.tasks.locomotion  # noqa: F401
    from unitree_rl_lab.tasks.locomotion.sensors.airy_bev import airy_bev_grid

    task = BASE_TASK + suffix
    cfg = parse_env_cfg(task, device=args.device, num_envs=num_envs)
    env = gym.make(task, cfg=cfg).unwrapped
    obs, _ = env.reset()

    # --- per-term observation widths straight from the ObservationManager -------------
    # NOTE: the attribute is the private ``_group_obs_term_dim`` (plural ``_dim``, mapping
    # group -> list of per-term dims); there is no public ``group_obs_term_dims`` accessor.
    om = env.observation_manager
    pol_dims = {n: int(sum(d)) for n, d in zip(om.active_terms["policy"], om._group_obs_term_dim["policy"])}
    crit_dims = {n: int(sum(d)) for n, d in zip(om.active_terms["critic"], om._group_obs_term_dim["critic"])}

    # --- does the lidar actually return geometry, and is the BEV grid alive? ----------
    has_airy = hasattr(env.scene, "sensors") and "airy_front" in env.scene.sensors
    hit_str, bev_std, bev_max = "-", float("nan"), float("nan")
    if has_airy:
        d = env.scene.sensors["airy_front"].data
        finite = torch.isfinite(d.ray_hits_w).all(dim=-1)
        hit_str = f"{int(finite.sum())}/{finite.numel()}"

    action = torch.zeros(env.num_envs, sum(env.action_manager.action_term_dim), device=env.device)
    t0 = time.perf_counter()
    for _ in range(steps):
        obs, _r, _te, _tr, _i = env.step(action)
    ms = (time.perf_counter() - t0) / steps * 1000.0

    if has_airy:
        d = env.scene.sensors["airy_front"].data
        g = airy_bev_grid(d.ray_hits_w, d.pos_w, d.quat_w)
        bev_std, bev_max = float(g.std().item()), float(g.max().item())

    out = {
        "task": task,
        "policy_terms": pol_dims,
        "critic_terms": crit_dims,
        "policy_total": int(obs["policy"].shape[-1]),
        "critic_total": int(obs["critic"].shape[-1]),
        "action_dim": int(action.shape[-1]),
        "hits": hit_str,
        "bev_std": bev_std,
        "bev_max": bev_max,
        "ms_per_step": round(ms, 2),
    }
    print("RESULT_JSON " + json.dumps(out), flush=True)
    # Hard-exit instead of simulation_app.close(): tearing the stage down raises inside the
    # simulator's own shutdown path and the process then never terminates, which hangs the parent.
    # The measurement is already complete and written out, so nothing is lost.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def main() -> int:
    # Parent (Isaac Sim not needed here): fan out one subprocess per config.
    if "--single" not in sys.argv:
        p = argparse.ArgumentParser(description="Run the Airy ablation smoke test")
        p.add_argument("--num_envs", type=int, default=64)
        p.add_argument("--steps", type=int, default=50)
        p.add_argument("--headless", action="store_true")
        p.add_argument("--timeout", type=int, default=420,
                       help="per-config subprocess timeout in seconds")
        a, _ = p.parse_known_args()

        results = []
        for label, suffix in CONFIGS:
            print(f"\n=== {label.strip()} (suffix='{suffix}') " + "=" * 30, flush=True)
            cmd = [sys.executable, str(Path(__file__).resolve()), "--headless",
                   "--single", suffix or "NONE",
                   "--num_envs", str(a.num_envs), "--steps", str(a.steps)]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
            except subprocess.TimeoutExpired:
                print(f"  !! TIMEOUT after {a.timeout}s")
                results.append({"task": BASE_TASK + suffix, "error": True})
                continue
            line = next((x for x in proc.stdout.splitlines() if x.startswith("RESULT_JSON ")), None)
            if line is None:
                tail = [x for x in proc.stderr.splitlines() if x.strip()][-6:]
                print("  !! no result. stderr tail:\n     " + "\n     ".join(tail))
                results.append({"task": BASE_TASK + suffix, "error": True})
                continue
            results.append(json.loads(line[len("RESULT_JSON "):]))

        print(f"\n{'config':<16}{'pol':>6}{'crit':>7}{'act':>5}{'hits':>15}"
              f"{'bev_std':>10}{'bev_max':>9}{'ms/step':>9}  verdict")
        print("-" * 86)
        for (label, _), r in zip(CONFIGS, results):
            if r.get("error"):
                print(f"{label:<16}{'--':>6}{'--':>7}{'--':>5}{'--':>15}{'--':>10}"
                      f"{'--':>9}{'--':>9}  CRASH")
                continue
            print(f"{label:<16}{r['policy_total']:>6}{r['critic_total']:>7}{r['action_dim']:>5}"
                  f"{r['hits']:>15}{r['bev_std']:>10.4f}{r['bev_max']:>9.3f}"
                  f"{r['ms_per_step']:>9.2f}  OK")
        RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
        RESULT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\n[SMOKE] per-term widths -> {RESULT_JSON}")
        return 0

    # Child: single config.
    i = sys.argv.index("--single")
    suffix = sys.argv[i + 1]
    n = int(sys.argv[sys.argv.index("--num_envs") + 1]) if "--num_envs" in sys.argv else 64
    s = int(sys.argv[sys.argv.index("--steps") + 1]) if "--steps" in sys.argv else 50
    run_single("" if suffix == "NONE" else suffix, n, s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
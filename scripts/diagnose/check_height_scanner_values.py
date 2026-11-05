"""Is the baseline ``height_scanner`` critic observation ALIVE (terrain) or DEAD (a constant)?

MEASURED FACTS (2026-10-16), which this script exists to prove:

* ``mdp.height_scan`` returns ``sensor.data.pos_w.z - ray_hits_w.z - offset``.
* The 20 m ``OffsetCfg(pos=(0,0,20))`` only raises the ray START. It does NOT enter ``pos_w``:
  ``pos_w z`` measures 0.61 (trunk height) while ``ray_hits_w z`` spans 0.000 .. 0.524.
* Therefore the correct ``offset`` is the DEFAULT 0.5 -> ``0.61 - hit_z - 0.5`` in
  [-0.41, +0.11], which ``clip=(-1.0, 1.0)`` passes through untouched: ALIVE.
* The 2026-10-15 "fix" (``offset=20.5``, assuming ``pos_w = base_z + 20``) instead drove the raw
  value to ~ -19.9 so ALL 187 cells pinned to the clip floor -1.0: DEAD. Any checkpoint trained
  with that offset has a constant 187-dim block and is equivalent to the blind baseline.

The script prints, at the same instant, the value the ObsTerm put into the critic group and the
value the function returns when called by hand with either offset, so the two can be compared.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=8)
parser.add_argument("--steps", type=int, default=20)
parser.add_argument("--update_period", choices=["decim", "dt"], default="decim",
                    help="decim = decimation*dt (0.02 s, current config); dt = every physics step")
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

TASK = "Unitree-Go2-Velocity"
TERM = "height_scanner"


def block_stats(om, obs, group: str, term: str):
    """Slice ``term`` out of the concatenated group observation (public dim API)."""
    names = om.active_terms[group]
    dims = [int(sum(d)) for d in om.group_obs_term_dim[group]]
    i = names.index(term)
    start = sum(dims[:i])
    return obs[group][0, start: start + dims[i]]


def main() -> None:
    cfg = parse_env_cfg(TASK, device=args.device, num_envs=args.num_envs)
    from unitree_rl_lab.utils.offline_assets import patch_command_visualizers
    print(f"[assets] patched {patch_command_visualizers(cfg)} cloud visualizer(s) -> local")
    if args.update_period == "dt":
        cfg.scene.height_scanner.update_period = cfg.sim.dt
        print("\n[cfg] height_scanner.update_period overridden to sim.dt (every physics step)")
    else:
        print(f"\n[cfg] height_scanner.update_period = decimation*dt = "
              f"{cfg.scene.height_scanner.update_period}")
    env = gym.make(TASK, cfg=cfg).unwrapped
    om = env.observation_manager

    obs, _ = env.reset()
    sensor = env.scene.sensors[TERM]
    print("\n=== geometry ===")
    print(f"  sensor pos_w z (env0..2):   {sensor.data.pos_w[:3, 2].tolist()}")
    print(f"  ray_hits_w z  (min/max):    {sensor.data.ray_hits_w[..., 2].min():.3f} / "
          f"{sensor.data.ray_hits_w[..., 2].max():.3f}")
    print(f"  num rays (=17x11 grid):     {sensor.data.ray_hits_w.shape[1]}")

    # Same instant, three ways: the ObsTerm, and the function called by hand with the offset the
    # config uses (0.5, correct) and with the reverted one (20.5, wrong).
    g = om.compute_group("critic")
    if isinstance(g, dict):
        gv = g[TERM]
    else:
        # NOTE: hard-coded slice 76:76+187 only fits the lingsi_d30w layout. Derive the offset
        # from the manager's public dim API so this works for GO2 too (height_scanner sits at
        # off=300 with dim=935 once critic.history_length=5 is enabled).
        _names = om.active_terms["critic"]
        _dims = [int(sum(d)) for d in om.group_obs_term_dim["critic"]]
        _i = _names.index(TERM)
        _s = sum(_dims[:_i])
        gv = g[:, _s: _s + _dims[_i]]
    hand_ok = mdp.height_scan(env, SceneEntityCfg(TERM), offset=0.5)
    hand_bad = mdp.height_scan(env, SceneEntityCfg(TERM), offset=20.5)
    print(f"\n[obs term ]  {[round(v, 3) for v in gv[0, :3].tolist()]}")
    print(f"[hand 0.5 ]  {[round(v, 3) for v in hand_ok[0, :3].tolist()]}   <- config uses this")
    print(f"[hand 20.5]  {[round(v, 3) for v in hand_bad[0, :3].tolist()]}   <- the bad 2026-10-15 fix")

    action = torch.zeros(env.num_envs, sum(env.action_manager.action_term_dim), device=env.device)
    print("\n=== per-step: obs block (env0, first 3 cells) ===")
    for k in range(args.steps):
        obs, _r, _te, _tr, _i = env.step(action)
        if k in (0, 1, 2, 5, args.steps - 1):
            sl = block_stats(om, obs, "critic", TERM)
            fin = torch.isfinite(sensor.data.ray_hits_w).all(-1)
            print(f"  step {k:>3}: obs={[round(v, 3) for v in sl[:3].tolist()]}  "
                  f"finite_hits={int(fin.sum())}/{fin.numel()}")

    b1 = block_stats(om, obs, "critic", TERM)
    raw = mdp.height_scan(env, SceneEntityCfg(TERM), offset=0.5)

    print(f"\n=== all critic terms after {args.steps} steps (env0) ===")
    names = om.active_terms["critic"]
    dims = [int(sum(d)) for d in om.group_obs_term_dim["critic"]]
    off = 0
    for n, dd in zip(names, dims):
        sl = obs["critic"][0, off: off + dd]
        print(f"  {n:<20} dim={dd:>4} off={off:>4}  min={sl.min():+.3f} max={sl.max():+.3f} "
              f"mean={sl.mean():+.3f}")
        off += dd

    print(f"\n=== critic '{TERM}' block after {args.steps} steps (sensor running) ===")
    print(f"  min={b1.min():.3f} max={b1.max():.3f} mean={b1.mean():.3f} std={b1.std():.3f}")
    print(f"  first 8 cells: {[round(v, 3) for v in b1[:8].tolist()]}")
    print(f"  raw (offset=0.5, no clip): min={raw.min():.3f} max={raw.max():.3f} "
          f"mean={raw.mean():.3f} std={raw.std():.3f}")
    print(f"  cells at clip floor (-1):  {int((b1 <= -0.999).sum())}/{b1.numel()}")
    print(f"  cells at clip ceiling (+1):{int((b1 >= 0.999).sum())}/{b1.numel()}")

    # NB: on flat spawn ground all 187 cells of ONE env are legitimately equal (std ~ 0), so the
    # cell-wise std is NOT the right liveness test. Liveness = nothing pinned to a clip bound, and
    # the raw value still varies across envs/terrains. With offset=20.5 this reports 187/187 at the
    # floor -> DEAD; with offset=0.5 it reports 0/187 -> ALIVE.
    at_floor = int((b1 <= -0.999).sum())
    at_ceil = int((b1 >= 0.999).sum())
    alive = (at_floor + at_ceil) == 0 and raw.std() > 1e-6
    print(f"  raw std across envs:       {raw.std():.4f}")
    print(f"\n[VERDICT] height_scanner is {'ALIVE (carries terrain)' if alive else 'DEAD (constant)'}")
    sys.stdout.flush()
    # NB: ``simulation_app.close()`` HANGS here (C++ kit teardown deadlock - same trap documented in
    # the Airy README section), which left earlier runs alive at 99% CPU holding 1.5 GB VRAM.
    # os._exit() skips interpreter teardown entirely and is the only reliable way out.
    os._exit(0 if alive else 1)


if __name__ == "__main__":
    main()

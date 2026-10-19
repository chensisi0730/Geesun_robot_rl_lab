"""Does the height_scanner resolve terrain SPATIALLY (a height map), not just a constant?

Prior runs proved the term is not clip-dead and varies ACROSS environments, but on flat
ground all 187 cells are equal (correct). This script isolates the scanner's footprint
response over real stairs:

  1. sanity-check the pyramid_stairs height-field generator (does it produce z-variation?),
  2. force a SINGLE stairs tile at MAX difficulty (so stairs are unmistakable and can't be
     missed by a random curriculum level that may have flattened them),
  3. hover env0's base at a FIXED world z above the tile (re-set each step so gravity cannot
     drag it down -> base_z constant, so base_z - hit_z varies with the terrain the 187 rays
     land on),
  4. scan (dx,dy) offsets across the whole 8x8 tile to find where the footprint straddles the
     staircase (max spatial std),
  5. dump the 17x11 grid to prove the scanner resolves a height map.

Why hover instead of stand: when the robot STANDS on a uniform step, base_z tracks the step
height, so base_z - hit_z ~ const (the scanner measures terrain RELATIVE to its own base ->
meaningful at edges/slopes, constant on a single step). Hovering with fixed base_z removes
that cancellation and reveals the raw footprint map.
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
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--hover_z", type=float, default=1.0, help="base height above tile origin")
parser.add_argument("--scan", type=int, default=33, help="scan grid resolution per axis")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import numpy as np  # noqa: E402
import torch  # noqa: E402
import gymnasium as gym  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

import unitree_rl_lab.tasks.locomotion  # noqa: F401,E402
from unitree_rl_lab.tasks.locomotion import mdp  # noqa: E402

TASK = "Unitree-GeesunDog-LingsiD30W-Velocity"
TERM = "height_scanner"
NCOLS_X = 17  # GridPatternCfg(resolution=0.1, size=[1.6,1.0]) -> 17 x 11 = 187
NROWS_Y = 11


def get_term_block(om, crit, env_id, term=TERM):
    """Slice the critic 'height_scanner' block for env_id out of the concatenated/dict critic obs."""
    if isinstance(crit, dict):
        return crit[term][env_id]
    names = om.active_terms["critic"]
    dims = [int(sum(d)) for d in om.group_obs_term_dim["critic"]]
    i = names.index(term)
    start = sum(dims[:i])
    return crit[env_id, start : start + dims[i]]


def main() -> None:
    # ---- sanity: does the stairs height-field generator produce z-variation? ----
    try:
        from isaaclab.terrains.height_field.hf_terrains import pyramid_stairs_terrain
        from isaaclab.terrains.height_field.hf_terrains_cfg import HfPyramidStairsTerrainCfg

        scfg = HfPyramidStairsTerrainCfg(
            step_height_range=(0.05, 0.23), step_width=0.3, platform_width=3.0, border_width=1.0, holes=False
        )
        for d in (0.0, 0.5, 1.0):
            mesh = pyramid_stairs_terrain(d, scfg)
            z = mesh.vertices[:, 2]
            print(f"[sanity] pyramid_stairs d={d}: verts={len(z)} zmin={z.min():.3f} zmax={z.max():.3f} zstd={z.std():.3f}")
    except Exception as exc:  # pragma: no cover
        print(f"[sanity] skipped ({exc})")

    cfg = parse_env_cfg(TASK, device=args.device, num_envs=args.num_envs)
    # ---- force a single, maximal stairs tile so we cannot miss it ----
    gen = cfg.scene.terrain.terrain_generator
    gen.sub_terrains = {"pyramid_stairs": gen.sub_terrains["pyramid_stairs"]}
    gen.num_rows = 1
    gen.num_cols = 1
    gen.difficulty_range = (1.0, 1.0)
    cfg.scene.terrain.max_init_terrain_level = 0

    env = gym.make(TASK, cfg=cfg).unwrapped
    om = env.observation_manager
    robot = env.scene["robot"]
    terrain = env.scene.terrain
    origin = np.array(terrain.env_origins[0].cpu().tolist())
    print(f"[tile] single pyramid_stairs origin = {origin}")

    action = torch.zeros(env.num_envs, sum(env.action_manager.action_term_dim), device=env.device)

    def hover(env_id, ox, oy, oz):
        root = robot.data.root_state_w.clone()
        root[env_id, 0] = ox
        root[env_id, 1] = oy
        root[env_id, 2] = oz
        root[env_id, 3] = 1.0  # quat w (identity)
        root[env_id, 4:7] = 0.0
        root[env_id, 7:] = 0.0  # zero all velocities
        eid = torch.tensor([env_id], device=env.device, dtype=torch.long)
        robot.write_root_state_to_sim(root[[env_id]], env_ids=eid)
        env.scene.write_data_to_sim()
        env.step(action)
        return om.compute_group("critic")

    obs0, _ = env.reset()
    # ---- scan offsets to locate the staircase (max spatial std across footprint) ----
    best = None
    for dx in torch.linspace(-4.0, 4.0, args.scan):
        for dy in torch.linspace(-4.0, 4.0, args.scan):
            crit = hover(0, origin[0] + dx.item(), origin[1] + dy.item(), args.hover_z)
            blk = get_term_block(om, crit, 0)
            std = float(blk.std().item())
            if best is None or std > best[0]:
                best = (std, dx.item(), dy.item())
    print(f"[scan] best offset dx={best[1]:.2f} dy={best[2]:.2f} spatial_std={best[0]:.4f}")

    # ---- debug: where did the robot land + what terrain did the rays hit ----
    sensor = env.scene.sensors[TERM]
    crit = hover(0, origin[0] + best[1], origin[1] + best[2], args.hover_z)
    blk = get_term_block(om, crit, 0).cpu().numpy()
    root_xyz = robot.data.root_state_w[0, :3].cpu().numpy()
    hit = sensor.data.ray_hits_w[0]
    print(f"[debug] robot root xyz     = {root_xyz}")
    print(f"[debug] ray_hits_w z range = {float(hit[..., 2].min()):.3f} .. {float(hit[..., 2].max()):.3f}")
    print(f"[debug] sensor pos_w z     = {float(sensor.data.pos_w[0, 2]):.3f}")

    # ---- dump the 17x11 grid at the best spot ----
    raw = mdp.height_scan(env, SceneEntityCfg(TERM), offset=0.5)[0].cpu().numpy()
    grid = blk.reshape(NROWS_Y, NCOLS_X)

    print(f"[obs 17x11 clipped]  (rows = y {NROWS_Y}, cols = x {NCOLS_X}; +1.00 saturates, -1.00 floors)")
    for row in grid:
        print("  " + " ".join(f"{v:+.2f}" for v in row))
    print(f"[stats] obs  min={blk.min():+.3f} max={blk.max():+.3f} std={blk.std():.4f}")
    print(f"[stats] raw  min={raw.min():+.3f} max={raw.max():+.3f} std={raw.std():.4f}")

    resolved = blk.std() > 1e-3 and (blk.min() > -0.999) and (blk.max() < 0.999)
    print(
        "[VERDICT] height_scanner SPATIAL MAP over stairs: "
        + ("RESOLVED (footprint varies across terrain)" if resolved else "FLAT (no spatial variation)")
    )
    sys.stdout.flush()
    os._exit(0 if resolved else 1)


if __name__ == "__main__":
    main()

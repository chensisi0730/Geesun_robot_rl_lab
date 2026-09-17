# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Test a trained policy on flat, play-config, or complex terrain.

This script runs a trained checkpoint and records the robot's walking
performance (average forward velocity, average height, height variance) plus
per-joint applied torque statistics (peak / P99 / RMS) for motor selection.
The terrain is selected with ``--terrain``:

- ``flat`` (default): force a pure flat terrain.
- ``play``: no override, use the task's play environment terrain as configured.
- ``random_rough`` / ``boxes`` / ``stairs``: isolate one trained terrain type.
- ``complex``: force a mixed rough terrain (stairs / boxes / rough),
  with robots spawned on all difficulty rows (worst case for torque stats).

Usage:
    python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity \
        --checkpoint logs/rsl_rl/unitree_go2_velocity/<run>/model_7300.pt --steps 500

    # or automatically load the latest run / latest checkpoint:
    python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity

    # worst-case walking / torque statistics on complex terrain:
    python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity --terrain complex --steps 1000
"""

"""Launch Isaac Sim Simulator first."""

import argparse

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

parser = argparse.ArgumentParser(
    description="Test trained policy on flat / play-config / complex terrain and record torque statistics."
)
parser.add_argument("--task", type=str, default="Unitree-Go2-Velocity", help="Name of the task.")
parser.add_argument(
    "--terrain",
    type=str,
    default="flat",
    choices=["flat", "play", "random_rough", "boxes", "stairs", "complex"],
    help=(
        "Terrain for the test: 'flat' = forced pure flat terrain (default), "
        "'play' = use the task's play env terrain as configured, "
        "'random_rough'/'boxes'/'stairs' = isolate one trained terrain type, "
        "'complex' = forced mixed rough terrain (worst-case walking/torque stats)."
    ),
)
parser.add_argument("--num_envs", type=int, default=64, help="Number of environments to simulate.")
parser.add_argument("--steps", type=int, default=500, help="Number of policy steps to record.")
parser.add_argument("--warmup", type=int, default=50, help="Initial steps discarded to skip settling transient.")
parser.add_argument(
    "--full_command_range",
    action="store_true",
    default=False,
    help="Use the play config's full command limits. Default keeps the stage-1 +/-0.25 m/s linear range.",
)
parser.add_argument(
    "--output", type=str, default=None, help="Output CSV path. Defaults to <checkpoint_dir>/flat_walk_stats.csv."
)
parser.add_argument(
    "--save_raw", action="store_true", default=False, help="Additionally save raw torque samples to .npz."
)
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
# append RSL-RL cli arguments (--experiment_name, --load_run, --checkpoint, ...)
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import csv
import os
import sys

import gymnasium as gym
import numpy as np
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab.envs import ManagerBasedRLEnv
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
from isaaclab_tasks.utils import get_checkpoint_path

import unitree_rl_lab.tasks  # noqa: F401
from unitree_rl_lab.utils.parser_cfg import parse_env_cfg

import isaaclab.terrains as terrain_gen

# Mixed rough terrain matching the GO2 training types and limits.
COMPLEX_TERRAIN_CFG = terrain_gen.TerrainGeneratorCfg(
    size=(8.0, 8.0),
    border_width=20.0,
    num_rows=5,
    num_cols=12,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    difficulty_range=(0.0, 1.0),
    curriculum=True,
    use_cache=False,
    sub_terrains={
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.1),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=0.2, noise_range=(0.01, 0.06), noise_step=0.01, border_width=0.25
        ),
        "boxes": terrain_gen.MeshRandomGridTerrainCfg(
            proportion=0.2, grid_width=0.45, grid_height_range=(0.05, 0.2), platform_width=2.0
        ),
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=0.2,
            step_height_range=(0.05, 0.23),
            step_width=0.3,
            platform_width=3.0,
            border_width=1.0,
            holes=False,
        ),
    },
)


def single_terrain_cfg(mode: str) -> terrain_gen.TerrainGeneratorCfg:
    """Build an isolated test terrain using the same limits as GO2 training."""
    if mode == "random_rough":
        terrain = terrain_gen.HfRandomUniformTerrainCfg(
            proportion=1.0, noise_range=(0.01, 0.06), noise_step=0.01, border_width=0.25
        )
    elif mode == "boxes":
        terrain = terrain_gen.MeshRandomGridTerrainCfg(
            proportion=1.0, grid_width=0.45, grid_height_range=(0.05, 0.2), platform_width=2.0
        )
    elif mode == "stairs":
        terrain = terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=1.0,
            step_height_range=(0.05, 0.23),
            step_width=0.3,
            platform_width=3.0,
            border_width=1.0,
            holes=False,
        )
    else:
        raise ValueError(f"Unsupported terrain: {mode}")
    return terrain_gen.TerrainGeneratorCfg(
        size=(8.0, 8.0),
        border_width=20.0,
        num_rows=5,
        num_cols=4,
        horizontal_scale=0.1,
        vertical_scale=0.005,
        slope_threshold=0.75,
        difficulty_range=(0.0, 1.0),
        curriculum=True,
        use_cache=False,
        sub_terrains={mode: terrain},
    )


def resolve_checkpoint(agent_cfg) -> str:
    """Resolve the checkpoint path from CLI arguments or the latest training run."""
    if args_cli.checkpoint and os.path.isfile(args_cli.checkpoint):
        return os.path.abspath(args_cli.checkpoint)

    log_root_path = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    print(f"[INFO] Loading experiment from directory: {log_root_path}")
    return get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)


def main():
    if args_cli.steps <= args_cli.warmup:
        raise ValueError("--steps must be greater than --warmup")

    # parse configuration (use the play env config: fewer envs, no terrain curriculum)
    env_cfg = parse_env_cfg(
        args_cli.task,
        device=args_cli.device,
        num_envs=args_cli.num_envs,
        use_fabric=not args_cli.disable_fabric,
        entry_point_key="play_env_cfg_entry_point",
    )
    if not args_cli.full_command_range:
        env_cfg.commands.base_velocity.ranges.lin_vel_x = (-0.25, 0.25)
        env_cfg.commands.base_velocity.ranges.lin_vel_y = (-0.25, 0.25)

    # Apply terrain selection (--terrain). 'flat' keeps the original behavior;
    # 'play' leaves the play env cfg terrain untouched; 'complex' forces a mixed
    # rough terrain for worst-case walking / torque statistics.
    if args_cli.terrain == "flat":
        # Override terrain to flat only
        flat_terrain_cfg = terrain_gen.TerrainGeneratorCfg(
            size=(8.0, 8.0),
            border_width=20.0,
            num_rows=2,
            num_cols=1,
            horizontal_scale=0.1,
            vertical_scale=0.005,
            slope_threshold=0.75,
            difficulty_range=(0.0, 0.0),
            use_cache=False,
            sub_terrains={
                "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0),
            },
        )
        env_cfg.scene.terrain.terrain_generator = flat_terrain_cfg
    elif args_cli.terrain == "complex":
        env_cfg.scene.terrain.terrain_generator = COMPLEX_TERRAIN_CFG
        # Spawn each env on a random difficulty row (easiest -> hardest)
        env_cfg.scene.terrain.max_init_terrain_level = COMPLEX_TERRAIN_CFG.num_rows - 1
    elif args_cli.terrain in {"random_rough", "boxes", "stairs"}:
        isolated_cfg = single_terrain_cfg(args_cli.terrain)
        env_cfg.scene.terrain.terrain_generator = isolated_cfg
        env_cfg.scene.terrain.max_init_terrain_level = isolated_cfg.num_rows - 1
    env_cfg.curriculum = None
    # 'play': no override, use the task's play env terrain as configured
    print(f"[INFO] Terrain mode: {args_cli.terrain}")

    agent_cfg = cli_args.parse_rsl_rl_cfg(args_cli.task, args_cli)

    resume_path = resolve_checkpoint(agent_cfg)
    print(f"[INFO]: Loading model checkpoint from: {resume_path}")

    # create isaac environment
    env = gym.make(args_cli.task, cfg=env_cfg)
    assert isinstance(env.unwrapped, ManagerBasedRLEnv), "This script only supports manager-based RL environments."
    # wrap around environment for rsl-rl
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # load previously trained model
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    # robot handle for reading applied torque
    robot = env.unwrapped.scene["robot"]
    joint_names = robot.joint_names
    num_joints = len(joint_names)

    # get initial observation (rsl-rl-lib >= 2.3 returns a tuple)
    result = env.get_observations()
    obs = result[0] if isinstance(result, tuple) else result

    torque_samples: list[torch.Tensor] = []  # each: (num_envs, num_joints)
    position_samples: list[torch.Tensor] = []  # each: (num_envs, 3) for base position
    velocity_samples: list[torch.Tensor] = []  # each: (num_envs, 6) for base velocity
    error_xy_sum = torch.zeros(env.unwrapped.num_envs, device=env.unwrapped.device)
    error_yaw_sum = torch.zeros_like(error_xy_sum)
    failed_once = torch.zeros(env.unwrapped.num_envs, dtype=torch.bool, device=env.unwrapped.device)
    recorded_steps = 0
    print(f"[INFO] Recording {args_cli.steps} steps ({args_cli.warmup} warmup steps discarded) ...")

    for step in range(args_cli.steps):
        with torch.inference_mode():
            actions = policy(obs)
            obs, _, _, _ = env.step(actions)
        if step >= args_cli.warmup:
            torque_samples.append(robot.data.applied_torque.clone())
            root_pos = robot.data.root_pos_w.clone()
            root_pos[:, 2] -= env.unwrapped.scene.env_origins[:, 2]
            position_samples.append(root_pos)
            velocity_samples.append(robot.data.root_lin_vel_w.clone())
            command = env.unwrapped.command_manager.get_command("base_velocity")
            error_xy_sum += torch.linalg.norm(command[:, :2] - robot.data.root_lin_vel_b[:, :2], dim=-1)
            error_yaw_sum += torch.abs(command[:, 2] - robot.data.root_ang_vel_b[:, 2])
            failed_once |= env.unwrapped.reset_terminated
            recorded_steps += 1

    env.close()

    # stack samples: (num_samples, num_joints)
    torques = torch.stack(torque_samples, dim=0).flatten(0, 1).to("cpu")
    positions = torch.stack(position_samples, dim=0).flatten(0, 1).to("cpu")
    velocities = torch.stack(velocity_samples, dim=0).flatten(0, 1).to("cpu")

    abs_torques = torques.abs()

    # per-joint statistics for motor selection
    peak = abs_torques.amax(dim=0)  # max |tau|, use with a 1.5-2.0x safety margin for peak torque
    p99 = torch.stack(
        [torch.quantile(abs_torques[:, j], 0.99) for j in range(num_joints)],
        dim=0,
    )  # 99th percentile of |tau|
    rms = abs_torques.pow(2).mean(dim=0).sqrt()  # RMS, compare against motor continuous/thermal torque

    # print a formatted table
    print(f"\n[INFO] Joint torque statistics over {torques.shape[0]} samples x {num_joints} joints:")
    header = f"{'Joint':<28}{'Peak |tau| [Nm]':>18}{'P99 |tau| [Nm]':>18}{'RMS [Nm]':>14}"
    print(header)
    print("-" * len(header))
    for j, name in enumerate(joint_names):
        print(f"{name:<28}{peak[j].item():>18.3f}{p99[j].item():>18.3f}{rms[j].item():>14.3f}")
    print("-" * len(header))
    pooled_peak = abs_torques.amax().item()
    pooled_p99 = torch.quantile(abs_torques.flatten(), 0.99).item()
    pooled_rms = abs_torques.pow(2).mean().sqrt().item()
    print(f"{'ALL (pooled)':<28}{pooled_peak:>18.3f}{pooled_p99:>18.3f}{pooled_rms:>14.3f}\n")

    # Print walking performance metrics
    print("[INFO] Walking performance metrics:")
    # Calculate average forward velocity (x-direction)
    avg_forward_vel = velocities[:, 0].mean().item()
    # Calculate average height (z-position)
    avg_height = positions[:, 2].mean().item()
    # Calculate height variance (stability)
    height_var = positions[:, 2].var().item()
    per_env_error_xy = error_xy_sum / recorded_steps
    per_env_error_yaw = error_yaw_sum / recorded_steps
    mean_error_xy = per_env_error_xy.mean().item()
    mean_error_yaw = per_env_error_yaw.mean().item()
    success_rate = (
        (~failed_once) & (per_env_error_xy < 0.25) & (per_env_error_yaw < 0.35)
    ).float().mean().item()

    print(f"  Average forward velocity: {avg_forward_vel:.3f} m/s")
    print(f"  Average height: {avg_height:.3f} m")
    print(f"  Height variance: {height_var:.6f} m²")
    print(f"  Mean XY tracking error: {mean_error_xy:.3f} m/s")
    print(f"  Mean yaw tracking error: {mean_error_yaw:.3f} rad/s")
    print(f"  Success rate (no early termination, error limits met): {success_rate:.1%}")
    print(f"  Walking stability: {'Stable' if height_var < 0.01 else 'Unstable'}")

    # save results (default CSV name depends on the terrain mode)
    default_output = f"{args_cli.terrain}_terrain_stats.csv"
    output_path = args_cli.output or os.path.join(os.path.dirname(resume_path), default_output)
    with open(output_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["joint", "peak_abs_torque_Nm", "p99_abs_torque_Nm", "rms_torque_Nm"])
        for j, name in enumerate(joint_names):
            writer.writerow([name, f"{peak[j].item():.4f}", f"{p99[j].item():.4f}", f"{rms[j].item():.4f}"])
        writer.writerow([])
        writer.writerow(["metric", "value"])
        writer.writerow(["terrain_mode", args_cli.terrain])
        writer.writerow(["average_forward_velocity_ms", f"{avg_forward_vel:.4f}"])
        writer.writerow(["average_height_m", f"{avg_height:.4f}"])
        writer.writerow(["height_variance_m2", f"{height_var:.6f}"])
        writer.writerow(["mean_error_xy_ms", f"{mean_error_xy:.4f}"])
        writer.writerow(["mean_error_yaw_rads", f"{mean_error_yaw:.4f}"])
        writer.writerow(["success_rate", f"{success_rate:.4f}"])
    print(f"[INFO] Statistics saved to: {output_path}")

    if args_cli.save_raw:
        raw_path = os.path.splitext(output_path)[0] + "_raw.npz"
        np.savez(
            raw_path,
            torques=torques.numpy(),
            positions=positions.numpy(),
            velocities=velocities.numpy(),
            joint_names=np.array(joint_names),
            checkpoint=resume_path,
        )
        print(f"[INFO] Raw samples saved to: {raw_path}")

    # Isaac Sim (kit) hard-exits on shutdown without flushing Python's stdout
    # buffers, which would silently truncate the table above when stdout is
    # piped (e.g. `conda run`, `| tee`, `> log`). Flush explicitly.
    sys.stdout.flush()
    sys.stderr.flush()


if __name__ == "__main__":
    main()
    # close sim app
    simulation_app.close()

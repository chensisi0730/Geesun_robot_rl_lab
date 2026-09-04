# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Record per-joint applied torque statistics (peak / 99th percentile / RMS) from a trained policy.

This script runs a trained checkpoint in the play environment and logs the actuator applied
torque of every joint at each control step. The statistics are intended as a reference for
motor selection (peak torque, continuous torque, thermal sizing).

Usage:
    python scripts/rsl_rl/record_torque_stats.py --task Unitree-Go2-Velocity \
        --checkpoint logs/rsl_rl/unitree_go2_velocity/<run>/model_7300.pt --steps 500

    # or automatically load the latest run / latest checkpoint:
    python scripts/rsl_rl/record_torque_stats.py --task Unitree-Go2-Velocity
"""

"""Launch Isaac Sim Simulator first."""

import argparse

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

parser = argparse.ArgumentParser(description="Record per-joint torque statistics (max, p99, RMS) for motor selection.")
parser.add_argument("--task", type=str, default="Unitree-Go2-Velocity", help="Name of the task.")
parser.add_argument("--num_envs", type=int, default=64, help="Number of environments to simulate.")
parser.add_argument("--steps", type=int, default=500, help="Number of policy steps to record.")
parser.add_argument("--warmup", type=int, default=50, help="Initial steps discarded to skip settling transient.")
parser.add_argument("--output", type=str, default=None, help="Output CSV path. Defaults to <checkpoint_dir>/torque_stats.csv.")
parser.add_argument("--save_raw", action="store_true", default=False, help="Additionally save raw torque samples to .npz.")
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

import gymnasium as gym
import numpy as np
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab.envs import ManagerBasedRLEnv
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
from isaaclab_tasks.utils import get_checkpoint_path

import unitree_rl_lab.tasks  # noqa: F401
from unitree_rl_lab.utils.parser_cfg import parse_env_cfg


def resolve_checkpoint(agent_cfg) -> str:
    """Resolve the checkpoint path from CLI arguments or the latest training run."""
    if args_cli.checkpoint and os.path.isfile(args_cli.checkpoint):
        return os.path.abspath(args_cli.checkpoint)

    log_root_path = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    print(f"[INFO] Loading experiment from directory: {log_root_path}")
    return get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)


def main():
    # parse configuration (use the play env config: fewer envs, no terrain curriculum)
    env_cfg = parse_env_cfg(
        args_cli.task,
        device=args_cli.device,
        num_envs=args_cli.num_envs,
        use_fabric=not args_cli.disable_fabric,
        entry_point_key="play_env_cfg_entry_point",
    )
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
    print(f"[INFO] Recording {args_cli.steps} steps ({args_cli.warmup} warmup steps discarded) ...")

    for step in range(args_cli.steps):
        with torch.inference_mode():
            actions = policy(obs)
            obs, _, _, _ = env.step(actions)
        if step >= args_cli.warmup:
            torque_samples.append(robot.data.applied_torque.clone())

    env.close()

    # stack samples: (num_samples, num_joints)
    torques = torch.stack(torque_samples, dim=0).flatten(0, 1).to("cpu")
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

    # save results
    output_path = args_cli.output or os.path.join(os.path.dirname(resume_path), "torque_stats.csv")
    with open(output_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["joint", "peak_abs_torque_Nm", "p99_abs_torque_Nm", "rms_torque_Nm"])
        for j, name in enumerate(joint_names):
            writer.writerow([name, f"{peak[j].item():.4f}", f"{p99[j].item():.4f}", f"{rms[j].item():.4f}"])
    print(f"[INFO] Statistics saved to: {output_path}")

    if args_cli.save_raw:
        raw_path = os.path.splitext(output_path)[0] + "_raw.npz"
        np.savez(
            raw_path,
            torques=torques.numpy(),
            joint_names=np.array(joint_names),
            checkpoint=resume_path,
        )
        print(f"[INFO] Raw torque samples saved to: {raw_path}")


if __name__ == "__main__":
    main()
    # close sim app
    simulation_app.close()

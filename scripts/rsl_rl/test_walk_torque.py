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
- ``random_rough`` / ``stairs``: isolate one trained terrain type.
- ``complex``: force a mixed rough terrain (stairs / rough),
  with robots spawned on all difficulty rows (worst case for torque stats).

Usage:
    python scripts/rsl_rl/test_walk_torque.py --task Unitree-Go2-Velocity \
        --checkpoint logs/rsl_rl/unitree_go2_velocity/<run>/model_7300.pt --steps 500

    # or automatically load the latest run / latest checkpoint:
    python scripts/rsl_rl/test_walk_torque.py --task Unitree-Go2-Velocity

    # worst-case walking / torque statistics on complex terrain:
    python scripts/rsl_rl/test_walk_torque.py --task Unitree-Go2-Velocity --terrain complex --steps 1000
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
    choices=["flat", "play", "random_rough", "stairs", "complex"],
    help=(
        "Terrain for the test: 'flat' = forced pure flat terrain (default), "
        "'play' = use the task's play env terrain as configured, "
        "'random_rough'/'stairs' = isolate one trained terrain type, "
        "'complex' = forced mixed rough terrain (worst-case walking/torque stats)."
    ),
)
parser.add_argument("--stair_height", type=float, nargs=2, default=None, metavar=("MIN", "MAX"),
                    help="Override the stair riser height range (m) for the 'stairs'/'complex' presets.")
parser.add_argument(
    "--env_cfg_file",
    type=str,
    default=None,
    help="Replay with a run's saved env cfg snapshot (params/velocity_env_cfg.py) instead of the registered "
    "task cfg. Needed when the task cfg changed after the checkpoint was trained (obs dimensions).",
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
    "--cmd_x",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the linear-x command range (m/s). Highest priority: explicit --cmd_* wins over "
    "--full_command_range, which wins over the default +/-0.25 narrowing. Same semantics as play.py.",
)
parser.add_argument(
    "--cmd_y",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the linear-y command range (m/s). Same priority as --cmd_x.",
)
parser.add_argument(
    "--cmd_z",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the yaw command range (rad/s). Same priority as --cmd_x.",
)
parser.add_argument(
    "--no_standing",
    action="store_true",
    default=False,
    help="Disable the standing envs (rel_standing_envs = 0), so every robot keeps walking. Same as play.py. "
    "Recommended for forward-progress measurements: standing envs dilute forward_ok_fraction.",
)
parser.add_argument(
    "--tb_tag",
    type=str,
    default=None,
    help="Tag prefix for the TensorBoard scalars (Eval/<tb_tag>/...) AND for the default CSV name. "
    "Default = --terrain. Set it when evaluating the same terrain twice (e.g. wheel-locked vs free "
    "wheels): identical tags would overwrite each other.",
)
parser.add_argument(
    "--output", type=str, default=None, help="Output CSV path. Defaults to <checkpoint_dir>/<tag>_terrain_stats.csv."
)
parser.add_argument(
    "--no_tb",
    action="store_true",
    default=False,
    help="Do not write the evaluation scalars to TensorBoard (default: write them into the run's event dir).",
)
parser.add_argument(
    "--tb_dir",
    type=str,
    default=None,
    help=(
        "TensorBoard logdir for the evaluation scalars. Default = the checkpoint's directory, i.e. the "
        "training run dir that already holds events.out.tfevents.* - TensorBoard merges every event file "
        "in one logdir, so the eval curves show up next to the training curves of the same run."
    ),
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

# Shared evaluation terrain presets (评估地形预设) - see scripts/rsl_rl/terrain_presets.py
from snapshot_cfg import load_snapshot_env_cfg
from terrain_presets import apply_terrain


def resolve_checkpoint(agent_cfg) -> str:
    """Resolve the checkpoint path from CLI arguments or the latest training run."""
    if args_cli.checkpoint and os.path.isfile(args_cli.checkpoint):
        return os.path.abspath(args_cli.checkpoint)

    log_root_path = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    print(f"[INFO] Loading experiment from directory: {log_root_path}")
    return get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)


def checkpoint_iteration(resume_path: str) -> int:
    """Iteration number encoded in the checkpoint file name (model_10400.pt -> 10400)."""
    stem = os.path.basename(resume_path)
    if stem.startswith("model_") and stem.endswith(".pt"):
        try:
            return int(stem[len("model_") : -len(".pt")])
        except ValueError:
            pass
    return 0


def log_to_tensorboard(
    resume_path: str,
    terrain: str,
    metrics: dict[str, float],
    joint_names: list[str],
    peak: torch.Tensor,
    p99: torch.Tensor,
    rms: torch.Tensor,
    tb_dir: str | None = None,
) -> str | None:
    """Write the evaluation scalars into the training run's TensorBoard.

    The logdir is the checkpoint's directory, i.e. the run dir the rsl-rl runner already writes
    ``events.out.tfevents.*`` to. TensorBoard merges every event file found in one logdir, so the
    evaluation curves show up next to the training curves of the SAME run, with the checkpoint
    iteration as the x-axis (``model_10400.pt`` -> step 10400).

    The terrain mode is part of the tag (``Eval/<terrain>/...``) so flat / stairs / complex
    numbers never land on one curve. Per-joint torque stats are logged as
    ``Eval/<terrain>/torque_peak|torque_p99|torque_rms/<joint>``.

    Returns the logdir on success, ``None`` when TensorBoard is unavailable or the write failed.
    """
    try:
        from torch.utils.tensorboard import SummaryWriter
    except Exception as exc:  # tensorboard is optional
        print(f"[WARN] TensorBoard not available, skipping TB logging: {exc}")
        return None
    log_dir = tb_dir or os.path.dirname(resume_path)
    if not log_dir:
        print("[WARN] No TensorBoard logdir resolved, skipping TB logging.")
        return None
    step = checkpoint_iteration(resume_path)
    prefix = f"Eval/{terrain}"
    try:
        writer = SummaryWriter(log_dir=log_dir)
        for key, value in metrics.items():
            writer.add_scalar(f"{prefix}/{key}", float(value), step)
        for j, name in enumerate(joint_names):
            writer.add_scalar(f"{prefix}/torque_peak/{name}", float(peak[j]), step)
            writer.add_scalar(f"{prefix}/torque_p99/{name}", float(p99[j]), step)
            writer.add_scalar(f"{prefix}/torque_rms/{name}", float(rms[j]), step)
        writer.add_text(
            f"{prefix}/summary",
            ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()),
            step,
        )
        writer.flush()
        writer.close()
    except Exception as exc:  # TB logging must never kill the evaluation
        print(f"[WARN] TensorBoard logging failed: {exc}")
        return None
    print(f"[INFO] TensorBoard scalars written to {log_dir} (tags '{prefix}/...', step {step})")
    return log_dir


def main():
    if args_cli.steps <= args_cli.warmup:
        raise ValueError("--steps must be greater than --warmup")

    # parse configuration (use the play env config: fewer envs, no terrain curriculum)
    if args_cli.env_cfg_file:
        env_cfg = load_snapshot_env_cfg(
            args_cli.env_cfg_file,
            device=args_cli.device,
            num_envs=args_cli.num_envs,
            use_fabric=not args_cli.disable_fabric,
        )
        print(f"[INFO] Using snapshot env cfg from: {os.path.abspath(args_cli.env_cfg_file)}")
    else:
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
    # explicit --cmd_* has the highest priority (over --full_command_range and the narrowing above)
    for attr, value in (("lin_vel_x", args_cli.cmd_x), ("lin_vel_y", args_cli.cmd_y), ("ang_vel_z", args_cli.cmd_z)):
        if value is not None:
            setattr(env_cfg.commands.base_velocity.ranges, attr, (float(value[0]), float(value[1])))
    if args_cli.no_standing:
        env_cfg.commands.base_velocity.rel_standing_envs = 0.0

    # Apply terrain selection (--terrain) from the shared presets (地形预设). 'flat' keeps the
    # original behavior; 'play' leaves the play env cfg terrain untouched; 'complex' forces a
    # mixed rough terrain for worst-case walking / torque statistics. Sub-terrain (子地形) limits
    # are read from the task's own cfg, so every robot is tested on the limits that fit its asset.
    print(f"[INFO] Terrain mode: {apply_terrain(env_cfg, args_cli.terrain, stair_height=args_cli.stair_height)}")
    env_cfg.curriculum = None

    # diagnostics: print what is actually in effect, so a silently-ignored flag (e.g. a missing
    # env var that should have unlocked the wheels) cannot be mistaken for a real result
    _ranges = env_cfg.commands.base_velocity.ranges
    _wheel_scale = getattr(getattr(env_cfg.actions, "WheelVelocityAction", None), "scale", None)
    print(
        f"[INFO] Effective command ranges: lin_vel_x={tuple(_ranges.lin_vel_x)} lin_vel_y={tuple(_ranges.lin_vel_y)} "
        f"ang_vel_z={tuple(_ranges.ang_vel_z)} | rel_standing_envs={env_cfg.commands.base_velocity.rel_standing_envs} "
        f"| WheelVelocityAction.scale={_wheel_scale} ({'LOCKED' if _wheel_scale == 0.0 else 'free'})"
    )
    print(f"[INFO] Eval tag (TB prefix + CSV name): {args_cli.tb_tag or args_cli.terrain}")

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
    # P0 2026-10-21: progress along commanded x (reject stand-still fake success). Rollback: delete these two lines and the forward_ok AND below.
    fwd_sum = torch.zeros_like(error_xy_sum)
    cmd_abs_x_sum = torch.zeros_like(error_xy_sum)
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
            fwd_sum += torch.sign(command[:, 0]) * robot.data.root_lin_vel_b[:, 0]
            cmd_abs_x_sum += command[:, 0].abs()
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
    # P0 2026-10-21: forward_ok = progress along cmd_x >= 50% of mean |cmd_x| (0>=0 passes for standing-with-zero-cmd).
    per_env_fwd = fwd_sum / recorded_steps
    per_env_cmd_abs_x = cmd_abs_x_sum / recorded_steps
    # 0.7 matches curriculums._episode_forward_ok (2026-10-21 A-cut). Rollback to 0.5.
    # P0-2 2026-10-22: zero-command envs (|cmd_x| <= 0.01) cannot demonstrate progress and
    # must not pass for free (same fix as curriculums._episode_forward_ok).
    forward_ok = (per_env_cmd_abs_x > 1e-2) & (per_env_fwd >= 0.7 * per_env_cmd_abs_x)
    mean_cmd_abs_x = per_env_cmd_abs_x.mean().item()
    mean_fwd_along_cmd = per_env_fwd.mean().item()
    success_rate = (
        (~failed_once)
        & (per_env_error_xy < 0.25)
        & (per_env_error_yaw < 0.35)
        & forward_ok
    ).float().mean().item()

    print(f"  Average forward velocity: {avg_forward_vel:.3f} m/s")
    print(f"  Average height: {avg_height:.3f} m")
    print(f"  Height variance: {height_var:.6f} m²")
    print(f"  Mean XY tracking error: {mean_error_xy:.3f} m/s")
    print(f"  Mean yaw tracking error: {mean_error_yaw:.3f} rad/s")
    print(f"  Mean forward along cmd: {mean_fwd_along_cmd:.3f} m/s (cmd |x| mean {mean_cmd_abs_x:.3f})")
    print(f"  forward_ok fraction: {forward_ok.float().mean().item():.1%}")
    print(f"  Success rate (no early termination, error limits met, forward_ok): {success_rate:.1%}")
    print(f"  Walking stability: {'Stable' if height_var < 0.01 else 'Unstable'}")

    # single source of truth for the summary metrics: CSV rows and TensorBoard scalars
    metrics = {
        "average_forward_velocity_ms": avg_forward_vel,
        "average_height_m": avg_height,
        "height_variance_m2": height_var,
        "mean_error_xy_ms": mean_error_xy,
        "mean_error_yaw_rads": mean_error_yaw,
        "mean_fwd_along_cmd_ms": mean_fwd_along_cmd,
        "mean_cmd_abs_x_ms": mean_cmd_abs_x,
        "forward_ok_fraction": forward_ok.float().mean().item(),
        "success_rate": success_rate,
    }

    # save results (default CSV name depends on the eval tag, so two evaluations of the same
    # terrain - e.g. wheel-locked vs free wheels - do not overwrite each other)
    tag = args_cli.tb_tag or args_cli.terrain
    default_output = f"{tag}_terrain_stats.csv"
    output_path = args_cli.output or os.path.join(os.path.dirname(resume_path), default_output)
    with open(output_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["joint", "peak_abs_torque_Nm", "p99_abs_torque_Nm", "rms_torque_Nm"])
        for j, name in enumerate(joint_names):
            writer.writerow([name, f"{peak[j].item():.4f}", f"{p99[j].item():.4f}", f"{rms[j].item():.4f}"])
        writer.writerow([])
        writer.writerow(["metric", "value"])
        writer.writerow(["terrain_mode", args_cli.terrain])
        writer.writerow(["eval_tag", tag])
        # the evaluation setup, so the CSV is self-describing (command range actually used,
        # wheel lock state) - a silently-ignored CLI/env flag must not look like a result
        writer.writerow(["command_lin_vel_x", f"{tuple(float(v) for v in _ranges.lin_vel_x)}"])
        writer.writerow(["command_lin_vel_y", f"{tuple(float(v) for v in _ranges.lin_vel_y)}"])
        writer.writerow(["command_ang_vel_z", f"{tuple(float(v) for v in _ranges.ang_vel_z)}"])
        writer.writerow(["rel_standing_envs", f"{float(env_cfg.commands.base_velocity.rel_standing_envs)}"])
        writer.writerow(["wheel_locked", str(_wheel_scale == 0.0)])
        for key, value in metrics.items():
            writer.writerow([key, f"{value:.4f}"])
    print(f"[INFO] Statistics saved to: {output_path}")

    # push the same metrics into TensorBoard (same run dir as the training curves)
    if not args_cli.no_tb:
        log_to_tensorboard(
            resume_path,
            tag,
            metrics,
            joint_names,
            peak,
            p99,
            rms,
            tb_dir=args_cli.tb_dir,
        )

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

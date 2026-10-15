from __future__ import annotations

import json
import os
import torch
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def _episode_mean_error(env, env_ids, command_term, metric_name: str) -> torch.Tensor:
    """Return the just-ended episode mean before CommandManager.reset() clears it."""
    sum_name = {
        "error_vel_xy": "_error_xy_sum",
        "error_vel_yaw": "_error_yaw_sum",
    }[metric_name]
    if hasattr(command_term, sum_name) and hasattr(command_term, "_step_count"):
        return getattr(command_term, sum_name)[env_ids] / command_term._step_count[env_ids].clamp_min(1.0)

    # Compatibility with stock IsaacLab, which accumulates error/max_command_step in metrics.
    max_command_step = command_term.cfg.resampling_time_range[1] / env.step_dt
    episode_len = env.episode_length_buf[env_ids].clamp_min(1.0)
    return command_term.metrics[metric_name][env_ids] * max_command_step / episode_len


def _load_terrain_state(env, terrain, state_file: str | None) -> None:
    """Restore per-env terrain levels once per process (rsl-rl checkpoints do not store them).

    Skipped with a warning when the saved ``num_envs`` / ``max_level`` do not match the current
    setup (the env -> terrain-column mapping depends on num_envs, so a partial restore would
    assign levels to the wrong columns).
    """
    if getattr(terrain, "_terrain_state_loaded", False):
        return
    terrain._terrain_state_loaded = True
    if not state_file or not os.path.exists(state_file):
        return
    try:
        with open(state_file) as f:
            saved = json.load(f)
        levels = saved.get("levels")
        if (
            levels is None
            or int(saved.get("num_envs", -1)) != int(env.num_envs)
            or int(saved.get("max_level", -1)) != int(terrain.max_terrain_level)
        ):
            print(
                f"[WARN] terrain-levels state {state_file} does not match this run"
                f" (num_envs/max_level changed); keeping the random initial levels."
            )
            return
        device = terrain.terrain_levels.device
        terrain.terrain_levels[:] = torch.tensor(levels, dtype=torch.long, device=device)
        terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
        print(
            f"[INFO] Restored terrain levels from {state_file}:"
            f" mean={float(terrain.terrain_levels.float().mean()):.2f} (saved at step {saved.get('step')})"
        )
    except Exception as exc:  # a corrupt sidecar must never abort training
        print(f"[WARN] Could not read terrain-levels state {state_file}: {exc!r}")


def _save_terrain_state(env, terrain, state_file: str | None) -> None:
    """Persist per-env terrain levels so a restart does not send every env back to level 0."""
    if not state_file:
        return
    try:
        payload = {
            "levels": [int(x) for x in terrain.terrain_levels.tolist()],
            "num_envs": int(env.num_envs),
            "max_level": int(terrain.max_terrain_level),
            "step": int(env.common_step_counter),
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        path = Path(state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    except Exception as exc:  # never let a failed write abort training
        print(f"[WARN] Could not write terrain-levels state {state_file}: {exc!r}")


def terrain_levels_vel_strict(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    command_name: str = "base_velocity",
    move_up_xy: float = 0.22,
    move_up_yaw: float = 0.30,
    move_down_xy: float = 0.40,
    move_down_yaw: float = 0.45,
    min_x_max_for_move_up: float = 0.0,
    cmd_freeze_windows: int = 0,
    cmd_freeze_level_gain: float = 1.0,
    state_file: str | None = None,
    state_save_interval: int = 1000,
) -> torch.Tensor:
    """Move terrain level using survival and tracking error with a hysteresis band.

    Two optional couplings with the velocity-command curriculum (both OFF by default so the
    GO2 / dog1 campaigns keep their verified behavior; enable per task via CurriculumCfg):

    * ``min_x_max_for_move_up``: terrain levels freeze (both up AND down) until the gated
      command range has reached this x upper bound - a true freeze at the current levels
      while the command curriculum climbs first.
    * ``cmd_freeze_windows``: whenever the mean terrain level has gained
      ``cmd_freeze_level_gain`` since the last freeze, the x command range is frozen (neither
      widened nor narrowed) for this many gated-eval windows - a settle period on the new
      terrain difficulty before the command range keeps widening. Triggered on the *mean*
      level, not per-env level-ups (which happen on almost every episode during a climb).
    """
    terrain = env.scene.terrain
    command_term = env.command_manager.get_term(command_name)
    _load_terrain_state(env, terrain, state_file)
    err_xy = _episode_mean_error(env, env_ids, command_term, "error_vel_xy")
    err_yaw = _episode_mean_error(env, env_ids, command_term, "error_vel_yaw")
    valid = env.episode_length_buf[env_ids] > 0
    time_outs = getattr(env, "reset_time_outs", None)
    survived = torch.ones_like(valid) if time_outs is None else time_outs[env_ids].bool()

    x_max = float(command_term.cfg.ranges.lin_vel_x[1])
    gate_open = x_max >= min_x_max_for_move_up
    move_up = valid & survived & (err_xy < move_up_xy) & (err_yaw < move_up_yaw) & gate_open
    # gate freezes BOTH directions: with only move_up gated, occasional move_down events
    # (falls, error tails) would slowly drain every env to level 0 - the intent is a true
    # freeze of the terrain levels while the command range is still climbing.
    move_down = valid & ((~survived) | (err_xy > move_down_xy) | (err_yaw > move_down_yaw)) & gate_open
    terrain.update_env_origins(env_ids, move_up, move_down & ~move_up)

    if cmd_freeze_windows > 0:
        mean_level = float(torch.mean(terrain.terrain_levels.float()))
        last = getattr(command_term, "_cmd_freeze_last_mean", None)
        if last is None:
            command_term._cmd_freeze_last_mean = mean_level
        elif mean_level - last >= cmd_freeze_level_gain:
            command_term._cmd_freeze_last_mean = mean_level
            command_term._cmd_freeze_windows = cmd_freeze_windows
            print(
                f"[INFO] Terrain mean level {mean_level:.2f} (+{mean_level - last:.2f}): freezing x command"
                f" range for {cmd_freeze_windows} eval windows"
            )

    if state_file:
        step = int(env.common_step_counter)
        last_save = getattr(terrain, "_terrain_state_last_save", -(10**9))
        if step - last_save >= state_save_interval:
            terrain._terrain_state_last_save = step
            _save_terrain_state(env, terrain, state_file)
    return torch.mean(terrain.terrain_levels.float())


def _terrain_columns_by_name(env) -> dict[str, list[int]]:
    """Map generated terrain columns back to sub-terrain names."""
    cfg = env.scene.terrain.cfg.terrain_generator
    if cfg is None:
        return {}
    names = list(cfg.sub_terrains)
    weights = torch.tensor([float(v.proportion) for v in cfg.sub_terrains.values()])
    edges = torch.cumsum(weights / weights.sum(), dim=0)
    result = {name: [] for name in names}
    for column in range(cfg.num_cols):
        sample = column / cfg.num_cols + 0.001
        index = int(torch.searchsorted(edges, torch.tensor(sample), right=True).clamp_max(len(names) - 1))
        result[names[index]].append(column)
    return result


def terrain_performance_by_type(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    command_name: str = "base_velocity",
    success_xy: float = 0.25,
    success_yaw: float = 0.35,
) -> dict[str, torch.Tensor]:
    """Log terrain level, tracking errors and success rate for every terrain type."""
    terrain = env.scene.terrain
    command_term = env.command_manager.get_term(command_name)
    err_xy = _episode_mean_error(env, env_ids, command_term, "error_vel_xy")
    err_yaw = _episode_mean_error(env, env_ids, command_term, "error_vel_yaw")
    valid = env.episode_length_buf[env_ids] > 0
    time_outs = getattr(env, "reset_time_outs", None)
    survived = torch.ones_like(valid) if time_outs is None else time_outs[env_ids].bool()
    result = {}

    for name, columns in _terrain_columns_by_name(env).items():
        all_mask = torch.zeros_like(terrain.terrain_types, dtype=torch.bool)
        reset_mask = torch.zeros_like(valid, dtype=torch.bool)
        for column in columns:
            all_mask |= terrain.terrain_types == column
            reset_mask |= terrain.terrain_types[env_ids] == column
        if torch.any(all_mask):
            result[f"{name}_level"] = torch.mean(terrain.terrain_levels[all_mask].float())
        reset_mask &= valid
        if torch.any(reset_mask):
            success = (
                survived[reset_mask]
                & (err_xy[reset_mask] < success_xy)
                & (err_yaw[reset_mask] < success_yaw)
            )
            result[f"{name}_error_xy"] = torch.mean(err_xy[reset_mask])
            result[f"{name}_error_yaw"] = torch.mean(err_yaw[reset_mask])
            result[f"{name}_success_rate"] = torch.mean(success.float())
    return result


def fixed_lin_vel_cmd_level(env: ManagerBasedRLEnv, env_ids: Sequence[int]) -> torch.Tensor:
    """Keep the legacy scalar tag while the stage-1 command range is frozen."""
    del env_ids
    ranges = env.command_manager.get_term("base_velocity").cfg.ranges
    return torch.tensor(ranges.lin_vel_x[1], device=env.device)


def velocity_command_ranges(env: ManagerBasedRLEnv, env_ids: Sequence[int]) -> dict[str, float]:
    """Expose all current command bounds (lin x/y and yaw) in TensorBoard."""
    del env_ids
    ranges = env.command_manager.get_term("base_velocity").cfg.ranges
    return {
        "x_min": float(ranges.lin_vel_x[0]),
        "x_max": float(ranges.lin_vel_x[1]),
        "y_min": float(ranges.lin_vel_y[0]),
        "y_max": float(ranges.lin_vel_y[1]),
        "z_min": float(ranges.ang_vel_z[0]),
        "z_max": float(ranges.ang_vel_z[1]),
    }


def _ensure_gate_state(command_term) -> None:
    """Lazily attach the rolling-window accumulators used by the gated curricula.

    The linear (xy) and yaw gates are tracked independently so a hard-to-learn yaw command
    cannot freeze the linear-velocity range (and vice versa).
    """
    if not hasattr(command_term, "_gate_total"):
        command_term._gate_total = 0.0
        command_term._gate_survived = 0.0
        command_term._gate_lin_success = 0.0
        command_term._gate_yaw_success = 0.0
        command_term._gate_err_xy = 0.0
        command_term._gate_err_yaw = 0.0
        command_term._gate_streak = 0
        command_term._gate_yaw_streak = 0
        command_term._gate_loaded = False


def _load_gate_state(command_term, state_file: str | None) -> None:
    """Restore the advanced command range once per process (rsl-rl checkpoints do not store it)."""
    _ensure_gate_state(command_term)
    if command_term._gate_loaded:
        return
    command_term._gate_loaded = True
    if not state_file or not os.path.exists(state_file):
        return
    try:
        with open(state_file) as f:
            saved = json.load(f).get("ranges", {})
        if "lin_vel_x" in saved:
            command_term.cfg.ranges.lin_vel_x = tuple(saved["lin_vel_x"])
        if "lin_vel_y" in saved:
            command_term.cfg.ranges.lin_vel_y = tuple(saved["lin_vel_y"])
        if "ang_vel_z" in saved:
            command_term.cfg.ranges.ang_vel_z = tuple(saved["ang_vel_z"])
        print(f"[INFO] Restored gated velocity curriculum ranges from {state_file}: {saved}")
    except Exception as exc:  # a corrupt sidecar must never abort training
        print(f"[WARN] Could not read curriculum state {state_file}: {exc!r}")


def _save_gate_state(command_term, state_file: str | None) -> None:
    """Persist the advanced command range so a crash/resume does not revert the curriculum."""
    if not state_file:
        return
    try:
        ranges = command_term.cfg.ranges
        payload = {
            "ranges": {
                "lin_vel_x": [float(ranges.lin_vel_x[0]), float(ranges.lin_vel_x[1])],
                "lin_vel_y": [float(ranges.lin_vel_y[0]), float(ranges.lin_vel_y[1])],
                "ang_vel_z": [float(ranges.ang_vel_z[0]), float(ranges.ang_vel_z[1])],
            },
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        path = Path(state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    except Exception as exc:  # never let a failed write abort training
        print(f"[WARN] Could not write curriculum state {state_file}: {exc!r}")


def gated_lin_vel_cmd_levels(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    command_name: str = "base_velocity",
    state_file: str | None = None,
    lin_increment: float = 0.05,
    yaw_increment: float = 0.1,
    success_xy: float = 0.25,
    success_yaw: float = 0.35,
    min_success_rate: float = 0.90,
    min_env_steps: int = 12000,
    min_episodes: int = 4000,
    hold: int = 2,
) -> dict[str, float]:
    """Gated curriculum for the linear-velocity (xy) and yaw command ranges.

    Statistics are accumulated over a window that spans at least ``min_env_steps`` environment
    steps (a fixed *training duration* rather than a number of episodes, which would be tiny
    with thousands of parallel envs) and at least ``min_episodes`` finished episodes. An
    episode counts as a success for an axis when the robot survived to ``time_out`` *and* its
    episode-mean tracking error on that axis stayed below the threshold.

    The two axes are gated **independently** (the previous combined gate froze the whole
    curriculum whenever yaw tracking lagged, which is exactly what happened to the fresh Go2
    run):

    * x range widens by ``lin_increment`` after ``hold`` consecutive windows with linear
      success rate / time-out rate >= ``min_success_rate`` and mean ``error_vel_xy`` below
      ``success_xy`` (y range stays frozen, keeping the two linear axes decoupled);
    * yaw range (``ang_vel_z``) widens by ``yaw_increment`` after ``hold`` consecutive windows
      with yaw success rate / time-out rate >= ``min_success_rate`` and mean ``error_vel_yaw``
      below ``success_yaw``.

    The window restarts after every evaluation, which doubles as the settle period after an
    increment. Advancing on tracking + survival (not on raw reward) is what keeps the
    curriculum from outrunning the policy (see ``doc/training_monitoring.md``).

    The current range is persisted to ``state_file`` (when given) because the rsl-rl
    checkpoint does not store command ranges.

    Returns a dict that is logged as ``Curriculum/lin_vel_cmd_levels/<key>``.
    """
    command_term = env.command_manager.get_term(command_name)
    _load_gate_state(command_term, state_file)
    if not hasattr(command_term, "_gate_last_eval"):
        command_term._gate_last_eval = env.common_step_counter

    ranges = command_term.cfg.ranges
    limit_ranges = command_term.cfg.limit_ranges
    if isinstance(env_ids, slice):
        env_ids = torch.arange(env.num_envs, device=env.device)

    err_xy = _episode_mean_error(env, env_ids, command_term, "error_vel_xy")
    err_yaw = _episode_mean_error(env, env_ids, command_term, "error_vel_yaw")
    valid = env.episode_length_buf[env_ids] > 0
    time_outs = getattr(env, "reset_time_outs", None)
    survived = torch.ones_like(valid) if time_outs is None else time_outs[env_ids].bool()
    lin_success = survived & (err_xy < success_xy)
    yaw_success = survived & (err_yaw < success_yaw)

    command_term._gate_total += float(valid.sum().item())
    command_term._gate_survived += float((survived & valid).sum().item())
    command_term._gate_lin_success += float((lin_success & valid).sum().item())
    command_term._gate_yaw_success += float((yaw_success & valid).sum().item())
    command_term._gate_err_xy += float(err_xy[valid].sum().item())
    command_term._gate_err_yaw += float(err_yaw[valid].sum().item())

    elapsed = env.common_step_counter - command_term._gate_last_eval
    if elapsed >= min_env_steps and command_term._gate_total >= float(min_episodes):
        total = command_term._gate_total
        time_out_rate = command_term._gate_survived / total
        lin_rate = command_term._gate_lin_success / total
        yaw_rate = command_term._gate_yaw_success / total
        mean_err_xy = command_term._gate_err_xy / total
        mean_err_yaw = command_term._gate_err_yaw / total

        freeze = int(getattr(command_term, "_cmd_freeze_windows", 0))
        if freeze > 0:
            # terrain level-up freeze (terrain_levels_vel_strict sets _cmd_freeze_windows):
            # the x range holds as-is and the streak restarts after the freeze, so the policy
            # gets clean windows on the new terrain before the range widens again. The yaw
            # gate stays independent and keeps evaluating.
            command_term._cmd_freeze_windows = freeze - 1
            command_term._gate_streak = 0
            print(f"[INFO] x command range frozen ({freeze - 1} eval windows left)")
        elif lin_rate >= min_success_rate and time_out_rate >= min_success_rate and mean_err_xy <= success_xy:
            command_term._gate_streak += 1
        else:
            command_term._gate_streak = 0
        if yaw_rate >= min_success_rate and time_out_rate >= min_success_rate and mean_err_yaw <= success_yaw:
            command_term._gate_yaw_streak += 1
        else:
            command_term._gate_yaw_streak = 0

        advanced = False
        if command_term._gate_streak >= hold:
            ranges.lin_vel_x = (
                max(float(ranges.lin_vel_x[0]) - lin_increment, float(limit_ranges.lin_vel_x[0])),
                min(float(ranges.lin_vel_x[1]) + lin_increment, float(limit_ranges.lin_vel_x[1])),
            )
            command_term._gate_streak = 0
            advanced = True
            print(f"[INFO] Velocity curriculum advanced to lin_vel_x={tuple(ranges.lin_vel_x)}")
        if command_term._gate_yaw_streak >= hold:
            ranges.ang_vel_z = (
                max(float(ranges.ang_vel_z[0]) - yaw_increment, float(limit_ranges.ang_vel_z[0])),
                min(float(ranges.ang_vel_z[1]) + yaw_increment, float(limit_ranges.ang_vel_z[1])),
            )
            command_term._gate_yaw_streak = 0
            advanced = True
            print(f"[INFO] Yaw curriculum advanced to ang_vel_z={tuple(ranges.ang_vel_z)}")
        if advanced:
            _save_gate_state(command_term, state_file)

        command_term._gate_last_eval = env.common_step_counter
        command_term._gate_total = 0.0
        command_term._gate_survived = 0.0
        command_term._gate_lin_success = 0.0
        command_term._gate_yaw_success = 0.0
        command_term._gate_err_xy = 0.0
        command_term._gate_err_yaw = 0.0

    window = command_term._gate_total if command_term._gate_total > 0 else 1.0
    return {
        "x_max": float(ranges.lin_vel_x[1]),
        "y_max": float(ranges.lin_vel_y[1]),
        "z_max": float(ranges.ang_vel_z[1]),
        "success_rate": command_term._gate_lin_success / window,
        "yaw_success_rate": command_term._gate_yaw_success / window,
        "time_out_rate": command_term._gate_survived / window,
        "mean_err_xy": command_term._gate_err_xy / window,
        "mean_err_yaw": command_term._gate_err_yaw / window,
        "streak": float(command_term._gate_streak),
        "yaw_streak": float(command_term._gate_yaw_streak),
        "x_frozen": float(getattr(command_term, "_cmd_freeze_windows", 0)),
    }


def lin_vel_cmd_levels(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    reward_term_name: str = "track_lin_vel_xy",
) -> torch.Tensor:
    command_term = env.command_manager.get_term("base_velocity")
    ranges = command_term.cfg.ranges
    limit_ranges = command_term.cfg.limit_ranges

    reward_term = env.reward_manager.get_term_cfg(reward_term_name)
    reward = torch.mean(env.reward_manager._episode_sums[reward_term_name][env_ids]) / env.max_episode_length_s

    if env.common_step_counter % env.max_episode_length == 0:
        if reward > reward_term.weight * 0.8:
            delta_command = torch.tensor([-0.1, 0.1], device=env.device)
            ranges.lin_vel_x = torch.clamp(
                torch.tensor(ranges.lin_vel_x, device=env.device) + delta_command,
                limit_ranges.lin_vel_x[0],
                limit_ranges.lin_vel_x[1],
            ).tolist()
            ranges.lin_vel_y = torch.clamp(
                torch.tensor(ranges.lin_vel_y, device=env.device) + delta_command,
                limit_ranges.lin_vel_y[0],
                limit_ranges.lin_vel_y[1],
            ).tolist()

    return torch.tensor(ranges.lin_vel_x[1], device=env.device)


def ang_vel_cmd_levels(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    reward_term_name: str = "track_ang_vel_z",
) -> torch.Tensor:
    command_term = env.command_manager.get_term("base_velocity")
    ranges = command_term.cfg.ranges
    limit_ranges = command_term.cfg.limit_ranges

    reward_term = env.reward_manager.get_term_cfg(reward_term_name)
    reward = torch.mean(env.reward_manager._episode_sums[reward_term_name][env_ids]) / env.max_episode_length_s

    if env.common_step_counter % env.max_episode_length == 0:
        if reward > reward_term.weight * 0.8:
            delta_command = torch.tensor([-0.1, 0.1], device=env.device)
            ranges.ang_vel_z = torch.clamp(
                torch.tensor(ranges.ang_vel_z, device=env.device) + delta_command,
                limit_ranges.ang_vel_z[0],
                limit_ranges.ang_vel_z[1],
            ).tolist()

    return torch.tensor(ranges.ang_vel_z[1], device=env.device)

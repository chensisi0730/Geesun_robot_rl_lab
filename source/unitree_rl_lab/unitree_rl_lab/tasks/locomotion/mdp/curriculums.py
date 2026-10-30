from __future__ import annotations

import json
import os
import torch
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from isaaclab.managers import SceneEntityCfg

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


def _episode_forward_ok(
    env, env_ids, command_term, ratio: float = 0.5
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    """Per-env ``forward_ok``: progress along commanded x >= ``ratio`` * mean |cmd_x|.

    2026-10-21 P0 (stand-still loophole): ``err_xy < 0.25`` passes while the robot is
    frozen because ``err_xy ≈ |cmd|``. Require real forward progress as well.

    2026-10-22 P0-2 (zero-command vacuous pass): an episode whose mean |cmd_x| is ~0
    (the ``rel_standing_envs`` standing envs, or a resampled near-zero command) can never
    demonstrate progress. Before this fix ``0 >= 0`` made every such env a free pass,
    inflating the lin-gate ``success_rate``, dragging its ``mean_err_xy`` down, and
    satisfying terrain ``move_up``. Such envs now return ``cmd_active=False`` and are
    excluded from the command-gated statistics instead of counting as success.
    Rollback: treat ``cmd_active`` as all-True (pre-2026-10-22 behavior).

    ``ratio``: 0.7 deadlocked the curriculum (SR≈0, x_max frozen at 0.1) - the training
    default is 0.5; ``test_walk_torque`` passes 0.7 for strict acceptance.

    Returns ``(None, None)`` when the command term has no forward accumulators
    (stock IsaacLab); callers must fall back to "no gate".
    """
    if not (hasattr(command_term, "_fwd_sum") and hasattr(command_term, "_fwd_step_count")):
        return None, None
    denom = command_term._fwd_step_count[env_ids].clamp_min(1.0)
    mean_fwd = command_term._fwd_sum[env_ids] / denom
    mean_cmd_abs_x = command_term._cmd_abs_x_sum[env_ids] / denom
    # episode-mean |cmd_x| <= 0.01 m/s counts as "no forward command" (standing env).
    cmd_active = mean_cmd_abs_x > 1e-2
    return cmd_active & (mean_fwd >= ratio * mean_cmd_abs_x), cmd_active


def _terrain_layout_signature(env, terrain) -> dict:
    """Terrain-grid fingerprint: the column -> sub-terrain mapping depends on all of these."""
    cfg = getattr(getattr(terrain, "cfg", None), "terrain_generator", None)
    if cfg is None:
        return {}
    return {
        "num_rows": int(cfg.num_rows),
        "num_cols": int(cfg.num_cols),
        "sub_terrains": {name: float(term.proportion) for name, term in cfg.sub_terrains.items()},
    }


def _terrain_env_groups(env, terrain) -> dict[str, list[int]]:
    """Group the CURRENT envs by sub-terrain name (pyramid_stairs / flat / random_rough / ...).

    ``terrain.terrain_types`` is ``env_id // (num_envs / num_cols)``, so the env -> column mapping
    changes when ``num_envs`` changes; the column -> sub-terrain mapping (driven by ``proportion``)
    does not. Grouping by name is the only restore route that survives a ``--num_envs`` change.
    """
    columns = _terrain_columns_by_name(env)
    if not columns:
        return {}
    column_to_name = {column: name for name, cols in columns.items() for column in cols}
    groups: dict[str, list[int]] = {name: [] for name in columns}
    for env_id, column in enumerate(terrain.terrain_types.tolist()):
        name = column_to_name.get(int(column))
        if name is not None:
            groups[name].append(env_id)
    return {name: ids for name, ids in groups.items() if ids}


def _terrain_level_by_type(env, terrain) -> dict[str, float]:
    """Mean terrain level per sub-terrain name == the TB ``..._<name>_level`` curves."""
    levels = terrain.terrain_levels
    return {name: round(float(torch.mean(levels[ids].float())), 4) for name, ids in _terrain_env_groups(env, terrain).items()}


def _cycled_sample(pool_size: int, want: int) -> list[int]:
    """Index sequence walking the saved level pool as evenly as possible (mean-preserving)."""
    order = torch.randperm(pool_size).tolist()
    if want <= pool_size:
        return order[:want]
    out: list[int] = []
    while len(out) < want:
        out.extend(order)
    return out[:want]


def _load_terrain_state(env, terrain, state_file: str | None) -> None:
    """Restore per-env terrain levels once per process (rsl-rl checkpoints do not store them).

    Two restore routes (2026-10-20), both keeping the terrain level from dropping:

    1. **exact** - saved ``num_envs``/``max_level`` match: restore the per-env levels verbatim.
    2. **by type** - ``num_envs`` changed (e.g. 4096 -> 3096) while the terrain layout
       (``num_rows``/``num_cols``/``proportion``) is unchanged: resample every env from the saved
       level pool of ITS OWN sub-terrain, so ``pyramid_stairs_level`` (金字塔楼梯难度等级) comes back
       at the saved value instead of collapsing to ``max_init_terrain_level``.

    Anything else (layout changed, corrupt file, a pre-2026-10-20 file without ``levels_by_type``
    under a changed ``num_envs``) keeps the random initial levels and prints a WARN - never aborts.
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
        levels_by_type = saved.get("levels_by_type")
        max_level = int(terrain.max_terrain_level)
        max_ok = int(saved.get("max_level", -1)) == max_level
        layout = saved.get("layout") or {}
        cur_layout = _terrain_layout_signature(env, terrain)
        layout_ok = bool(layout) and layout == cur_layout
        device = terrain.terrain_levels.device

        def _apply(levels_tensor, tag):
            terrain.terrain_levels[:] = levels_tensor.clamp(0, max_level - 1)
            terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
            by_type_str = " ".join(f"{n}={v:.2f}" for n, v in sorted(_terrain_level_by_type(env, terrain).items()))
            print(
                f"[INFO] Restored terrain levels ({tag}) from {state_file}:"
                f" mean={float(terrain.terrain_levels.float().mean()):.2f} | {by_type_str}"
                f" (saved at step {saved.get('step')}, num_envs {saved.get('num_envs')})"
            )

        # Route 1: exact per-env restore (num_envs unchanged).
        if levels is not None and int(saved.get("num_envs", -1)) == int(env.num_envs) and max_ok:
            _apply(torch.tensor(levels, dtype=torch.long, device=device), "exact")
            return

        # Route 2: per-sub-terrain restore (num_envs changed, terrain layout identical).
        # No num_envs-divisibility requirement: terrain_types = floor(env_id / (num_envs/num_cols))
        # is deterministic for ANY num_envs, it just makes the per-column env counts uneven.
        num_cols = int(cur_layout.get("num_cols", 0))
        groups = _terrain_env_groups(env, terrain)
        if (
            levels_by_type
            and max_ok
            and layout_ok
            and num_cols > 0
            and groups
            and all(levels_by_type.get(name) for name in groups)
        ):
            restored = torch.zeros(int(env.num_envs), dtype=torch.long, device=device)
            for name, env_ids in groups.items():
                pool = [int(x) for x in levels_by_type[name]]
                for slot, pool_index in enumerate(_cycled_sample(len(pool), len(env_ids))):
                    restored[env_ids[slot]] = pool[pool_index]
            _apply(restored, f"by type, num_envs {saved.get('num_envs')} -> {env.num_envs}")
            return

        print(
            f"[WARN] terrain-levels state {state_file} does not match this run"
            f" (num_envs {saved.get('num_envs')} -> {env.num_envs}, max_level {saved.get('max_level')} ->"
            f" {max_level}, layout {'same' if layout_ok else 'changed'}); keeping the random initial levels."
        )
    except Exception as exc:  # a corrupt sidecar must never abort training
        print(f"[WARN] Could not read terrain-levels state {state_file}: {exc!r}")


def _save_terrain_state(env, terrain, state_file: str | None) -> None:
    """Persist per-env terrain levels so a restart does not send every env back to level 0.

    Besides the per-env ``levels`` array, the file also carries the per-sub-terrain level pool and
    means (``levels_by_type`` / ``by_type`` - ``by_type["pyramid_stairs"]`` IS the TB
    ``Curriculum/terrain_performance_by_type/pyramid_stairs_level`` value) plus the terrain layout
    signature, so a resume with a DIFFERENT ``--num_envs`` restores the stairs level (楼梯难度等级)
    instead of silently resetting it to ``max_init_terrain_level`` (2026-10-20).
    """
    if not state_file:
        return
    try:
        groups = _terrain_env_groups(env, terrain)
        levels_list = [int(x) for x in terrain.terrain_levels.tolist()]
        payload = {
            "levels": levels_list,
            "num_envs": int(env.num_envs),
            "max_level": int(terrain.max_terrain_level),
            "step": int(env.common_step_counter),
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "types": [int(x) for x in terrain.terrain_types.tolist()],
            "by_type": {
                name: round(float(torch.mean(terrain.terrain_levels[ids].float())), 4)
                for name, ids in groups.items()
            },
            "levels_by_type": {name: [levels_list[i] for i in ids] for name, ids in groups.items()},
            "layout": _terrain_layout_signature(env, terrain),
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
    forward_ok_ratio: float = 0.5,
    demote_no_forward: bool = False,
    demote_warmup_windows: float = 0.0,
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
    * ``demote_warmup_windows``: 地形降级冷静期 (demotion warm-up). For the first
      ``demote_warmup_windows`` EPISODE LENGTHS of env steps after the process starts, terrain
      levels may only move UP - ``move_down`` is suppressed. Rationale (measured 2026-10-24):
      a resumed run re-creates all envs in lockstep, so for the first ~1 episode length no
      episode ends by timeout - only the FALLEN envs reach this term. Demoting on that
      all-failures sample snowballs (6.12 -> 1.91 in 16 iterations, reward 24.5 -> -5.7).
      Default 0.0 = OFF (GO2 / dog1 campaigns unchanged).
    """
    terrain = env.scene.terrain
    command_term = env.command_manager.get_term(command_name)
    _load_terrain_state(env, terrain, state_file)
    err_xy = _episode_mean_error(env, env_ids, command_term, "error_vel_xy")
    err_yaw = _episode_mean_error(env, env_ids, command_term, "error_vel_yaw")
    valid = env.episode_length_buf[env_ids] > 0
    time_outs = getattr(env, "reset_time_outs", None)
    survived = torch.ones_like(valid) if time_outs is None else time_outs[env_ids].bool()
    # P0 2026-10-21: stand-still must not promote (forward_ok). None = tracking unavailable.
    forward_ok, cmd_active = _episode_forward_ok(env, env_ids, command_term, forward_ok_ratio)

    x_max = float(command_term.cfg.ranges.lin_vel_x[1])
    gate_open = x_max >= min_x_max_for_move_up
    move_up = valid & survived & (err_xy < move_up_xy) & (err_yaw < move_up_yaw) & gate_open
    if forward_ok is not None:
        move_up = move_up & forward_ok
    # gate freezes BOTH directions: with only move_up gated, occasional move_down events
    # (falls, error tails) would slowly drain every env to level 0 - the intent is a true
    # freeze of the terrain levels while the command range is still climbing.
    move_down = valid & ((~survived) | (err_xy > move_down_xy) | (err_yaw > move_down_yaw)) & gate_open
    if demote_no_forward and forward_ok is not None and cmd_active is not None:
        # OPT-IN (2026-10-22, default OFF): demote envs that WERE commanded to move forward
        # but did not progress, so stairs drop to a difficulty the robot can traverse.
        # Default OFF because with the wheel lock (WheelVelocityAction scale=0) plus the
        # joint_pos penalty the policy can stand still for reward: demoting on no-progress
        # then crushed terrain_levels 5.0 -> 0.005 in one day (measured 2026-10-21/22).
        # Only envs with a real forward command are demoted; standing envs (cmd_x ~ 0,
        # cmd_active=False) must not be punished for not moving.
        move_down = move_down | (valid & cmd_active & ~forward_ok & gate_open)
    if demote_warmup_windows > 0.0:
        # 地形降级冷静期: see the docstring. Cheap check first (no tensor ops unless configured).
        warmup_steps = demote_warmup_windows * float(env.max_episode_length)
        if float(env.common_step_counter) < warmup_steps:
            if bool(move_down.any()):
                move_down = torch.zeros_like(move_down)
            if not getattr(terrain, "_demote_warmup_logged", False):
                terrain._demote_warmup_logged = True
                print(
                    f"[INFO] Terrain demote warm-up (地形降级冷静期): only level-UP for the first"
                    f" {warmup_steps:.0f} env steps ({demote_warmup_windows:g} x episode length,"
                    f" now at step {int(env.common_step_counter)}). Lockstep resets would otherwise"
                    f" demote on an all-failures sample."
                )
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


def terrain_levels_vel_state(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
    state_file: str | None = None,
    state_save_interval: int = 1000,
) -> torch.Tensor:
    """Stock ``terrain_levels_vel`` (distance-walked curriculum) + a terrain-level sidecar.

    G1 / H1 keep IsaacLab's stock distance-based curriculum, so persistence is added as a thin
    wrapper instead of switching those tasks to ``terrain_levels_vel_strict`` (which would change
    their promotion/demotion rules). Load/save is identical to the strict variant: a resume
    restores the per-env levels instead of re-climbing from ``max_init_terrain_level``, and
    ``train.py`` removes the file on a fresh run.

    Returns:
        The mean terrain level (same value the stock term returns).
    """
    from isaaclab_tasks.manager_based.locomotion.velocity.mdp.curriculums import (
        terrain_levels_vel as _stock_terrain_levels_vel,
    )

    terrain = env.scene.terrain
    _load_terrain_state(env, terrain, state_file)
    mean_level = _stock_terrain_levels_vel(env, env_ids, asset_cfg)
    if state_file:
        step = int(env.common_step_counter)
        last_save = getattr(terrain, "_terrain_state_last_save", -(10**9))
        if step - last_save >= state_save_interval:
            terrain._terrain_state_last_save = step
            _save_terrain_state(env, terrain, state_file)
    return mean_level


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
    forward_ok_ratio: float = 0.5,
) -> dict[str, torch.Tensor]:
    """Log terrain level, tracking errors and success rate for every terrain type.

    2026-10-22 P0-2: episodes with a ~zero x command (standing envs, resampled near-zero
    commands) cannot demonstrate forward progress, so they are excluded from BOTH the
    success numerator and the error means. NOTE this shifts the TB values by the standing
    share (~10% lower success, ~equal error) versus pre-2026-10-22 runs - read old and new
    curves with that offset in mind.
    """
    terrain = env.scene.terrain
    command_term = env.command_manager.get_term(command_name)
    err_xy = _episode_mean_error(env, env_ids, command_term, "error_vel_xy")
    err_yaw = _episode_mean_error(env, env_ids, command_term, "error_vel_yaw")
    valid = env.episode_length_buf[env_ids] > 0
    time_outs = getattr(env, "reset_time_outs", None)
    survived = torch.ones_like(valid) if time_outs is None else time_outs[env_ids].bool()
    forward_ok, cmd_active = _episode_forward_ok(  # P0 2026-10-21
        env, env_ids, command_term, forward_ok_ratio
    )
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
            # P0-2 2026-10-22: zero-command episodes cannot show progress; drop them from
            # the statistics instead of letting them pass for free (0 >= 0).
            stat_mask = reset_mask if cmd_active is None else (reset_mask & cmd_active)
            if torch.any(stat_mask):
                success = (
                    survived[stat_mask]
                    & (err_xy[stat_mask] < success_xy)
                    & (err_yaw[stat_mask] < success_yaw)
                )
                if forward_ok is not None:
                    success = success & forward_ok[stat_mask]
                result[f"{name}_error_xy"] = torch.mean(err_xy[stat_mask])
                result[f"{name}_error_yaw"] = torch.mean(err_yaw[stat_mask])
                result[f"{name}_success_rate"] = torch.mean(success.float())
    return result


def stairs_updown_performance(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    command_name: str = "base_velocity",
    success_xy: float = 0.25,
    success_yaw: float = 0.35,
    forward_ok_ratio: float = 0.5,
    dz_threshold: float = 0.06,
    upright_gravity_z: float = -0.6,
) -> dict[str, torch.Tensor]:
    """Split the stairs statistics by CLIMB DIRECTION (up vs down), 2026-10-27 P0-3.

    The curriculum cannot tell "climbed the stairs" from "descended the stairs": descending
    is nearly free (gravity + braked wheels), so a policy that only descends keeps
    satisfying the promotion gate and the terrain level plateaus exactly where ascending
    stops working (measured 2026-10-24: level 5.16 = 0.153 m riser, stairs success 0.53,
    time_out 0.52; the recorded videos show "下楼可以、爬楼失败").

    Every env is classified by the net base-height change over its CURRENT episode
    (``dz > +dz_threshold`` = climbing, ``dz < -dz_threshold`` = descending), and the two
    groups get their own success rate / tracking errors, so the asymmetry becomes visible
    in TensorBoard instead of only on video. Envs that are still on the spawn platform
    (|dz| <= threshold) are excluded - they neither climbed nor descended.

    Note the classification is per episode, so a policy that climbs then falls classifies
    as "up" by its net displacement; pair it with ``Episode_Termination/bad_orientation``.

    2026-10-27 (v2): an UPRIGHT gate is applied - a robot that collapses at spawn drops its
    base by ~0.11 m, which the raw height delta read as "descending" (measured: iteration 55
    of a fresh run reported down_share 0.98 / up_share 0.00 while nothing had walked yet).
    Envs whose base is tilted past ``upright_gravity_z`` are excluded from both groups.
    """
    command_term = env.command_manager.get_term(command_name)
    robot = env.scene["robot"]
    base_z = robot.data.root_pos_w[:, 2]
    # per-episode start height: refresh for envs that just reset, keep it otherwise
    start_z = getattr(env, "_stairs_start_z", None)
    if start_z is None or start_z.shape[0] != base_z.shape[0]:
        start_z = base_z.clone()
        env._stairs_start_z = start_z
    just_reset = env.episode_length_buf <= 1
    start_z[just_reset] = base_z[just_reset]
    dz = (base_z - start_z)[env_ids]

    err_xy = _episode_mean_error(env, env_ids, command_term, "error_vel_xy")
    err_yaw = _episode_mean_error(env, env_ids, command_term, "error_vel_yaw")
    valid = env.episode_length_buf[env_ids] > 0
    # upright gate: projected_gravity_b[:, 2] ~= -1 when the base is level, > -0.6 when tipped
    upright_all = robot.data.projected_gravity_b[:, 2] < upright_gravity_z
    upright = upright_all[env_ids]
    time_outs = getattr(env, "reset_time_outs", None)
    survived = torch.ones_like(valid) if time_outs is None else time_outs[env_ids].bool()
    forward_ok, cmd_active = _episode_forward_ok(env, env_ids, command_term, forward_ok_ratio)

    result: dict[str, torch.Tensor] = {}
    for label, direction_mask in (("up", dz > dz_threshold), ("down", dz < -dz_threshold)):
        mask = direction_mask & valid & upright
        if cmd_active is not None:
            mask = mask & cmd_active
        if torch.any(mask):
            success = survived[mask] & (err_xy[mask] < success_xy) & (err_yaw[mask] < success_yaw)
            if forward_ok is not None:
                success = success & forward_ok[mask]
            result[f"{label}_success_rate"] = torch.mean(success.float())
            result[f"{label}_error_xy"] = torch.mean(err_xy[mask])
            result[f"{label}_error_yaw"] = torch.mean(err_yaw[mask])
            result[f"{label}_mean_dz"] = torch.mean(dz[mask])
        else:  # keep the tag alive at 0 so the TB curve does not vanish mid-run
            result[f"{label}_success_rate"] = torch.zeros((), device=dz.device)
        result[f"{label}_share"] = torch.mean((direction_mask & upright).float())
    result["upright_share"] = torch.mean(upright.float())
    return result


def freeze_terrain_levels(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    max_level: int = 2,
) -> dict[str, torch.Tensor]:
    """Cap the terrain curriculum difficulty (2026-10-28 P0-B).

    The stock ``terrain_levels_vel`` term promotes an env when its horizontal travel
    exceeds half a terrain tile (4 m). On stairs that criterion is broken: measured on run
    ``2026-10-27_23-15-44`` the mean level went 0.51 -> 5.70 within **1142 iterations**
    while ``stairs_updown/up_share`` stayed **0.0000** - the robot was skittering around
    the pit floor / against the first riser, never climbing, and the level distribution
    piled up on level 9 (0.23 m risers) where climbing is impossible for a wheel-locked
    quadruped. The curriculum then froze for the remaining 8000 iterations.

    This term runs AFTER ``terrain_levels`` in the CurriculumCfg dict order and simply
    clamps ``terrain.terrain_levels`` to ``max_level``, so every future reset spawns on an
    easy column (level 2 -> riser 0.05 + 2/9 x 0.18 = 0.09 m). It reports both the level
    the curriculum WANTED (``desired``) and the one actually applied (``applied``), so the
    gap shows how badly the stock gate over-estimates progress.

    Set ``max_level < 0`` to disable (pure stock behaviour).
    """
    del env_ids
    terrain = env.scene.terrain
    desired = torch.mean(terrain.terrain_levels.float())
    if max_level >= 0:
        terrain.terrain_levels.clamp_(max=max_level)
    applied = torch.mean(terrain.terrain_levels.float())
    return {"desired": desired, "applied": applied}


def adaptive_stairs_levels(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    enabled: bool = True,
    start_cap: int = 1,
    max_level: int = 9,
    min_level: int = 0,
    promote_share: float = 0.55,
    demote_share: float = 0.25,
    cooldown_steps: int = 1500,
    ema_beta: float = 0.999,
    dz_threshold: float = 0.06,
    upright_gravity_z: float = -0.6,
) -> dict[str, torch.Tensor]:
    """Terrain curriculum driven by ACTUAL CLIMBING, not horizontal travel (2026-10-30).

    Why the stock gate has to be replaced (measured twice):
      * 2026-10-27: level 0.51 -> 5.70 within 1142 iterations while ``up_share`` was
        0.0000, then frozen for 8000 iterations - ``terrain_levels_vel`` promotes on 4 m of
        HORIZONTAL travel, which on stairs is satisfied by skittering around the pit floor;
      * 2026-10-29: the same gate wanted level 2.0 and had to be hard-clamped.

    This term reads the same signal the diagnostic uses - the share of envs whose base is
    more than ``dz_threshold`` above its episode-start height and that are still upright -
    smooths it with an EMA (the raw per-step share is spiky because a fresh episode starts
    at dz=0), and moves a per-run ``cap`` one row up when the EMA is above
    ``promote_share`` and one row down when it is below ``demote_share``. Rows are the
    terrain difficulty ladder, so the riser grows 0.02 -> 0.23 m in ten rungs and the robot
    only ever sees a step it has demonstrably been able to climb.

    ``cooldown_steps`` (~30 s = 1.5 episodes at 50 Hz) prevents oscillating promotions, and
    the EMA is re-centred after every move so the next move needs fresh evidence.

    Set ``enabled=False`` to make it a pure observer (no clamping).
    """
    terrain = env.scene.terrain
    robot = env.scene["robot"]
    if not enabled:
        return {"cap": torch.zeros((), device=env.device), "up_share_ema": torch.zeros((), device=env.device)}

    state = getattr(env, "_stairs_adaptive", None)
    if state is None:
        # start neutrally: ema at half the promotion threshold and a full cooldown, so the very
        # first calls (policy still collapsing, dz = 0) cannot demote the cap before any evidence
        state = {"cap": float(start_cap), "ema": 0.5 * promote_share, "cool": cooldown_steps}
        env._stairs_adaptive = state

    # --- measure the climbing share exactly like stairs_updown_performance -----------------
    base_z = robot.data.root_pos_w[:, 2]
    start_z = getattr(env, "_stairs_adapt_start_z", None)
    if start_z is None or start_z.shape[0] != base_z.shape[0]:
        start_z = base_z.clone()
        env._stairs_adapt_start_z = start_z
    just_reset = env.episode_length_buf <= 1
    start_z[just_reset] = base_z[just_reset]
    dz = base_z - start_z
    upright = robot.data.projected_gravity_b[:, 2] < upright_gravity_z
    # IMPORTANT (2026-10-30 fix): CurriculumManager.compute() is called from _reset_idx with the
    # ids of the envs being reset, i.e. ~1000 steps into their episode and just before
    # scene.reset() - so base_z here is the END of a FINISHED episode. Averaging over ALL envs
    # instead (the first version of this function) mixed in envs that had just spawned
    # (dz = 0) and diluted the share: measured 0.505 while stairs_updown (which honours
    # env_ids) reported 0.653 at the same step, so the cap never promoted (threshold 0.55).
    # Restricting to env_ids measures exactly "fraction of finished episodes that climbed".
    climbed = ((dz > dz_threshold) & upright)[env_ids]
    share = torch.mean(climbed.float())
    share_f = float(share)

    state["ema"] = (1.0 - ema_beta) * share_f + ema_beta * state["ema"]
    if state["cool"] > 0:
        state["cool"] -= 1
    elif state["ema"] > promote_share and state["cap"] < max_level:
        state["cap"] += 1.0
        state["cool"] = cooldown_steps
        state["ema"] = 0.5 * promote_share  # require fresh evidence for the next rung
    elif state["ema"] < demote_share and state["cap"] > min_level:
        state["cap"] -= 1.0
        state["cool"] = cooldown_steps
        state["ema"] = 0.5 * promote_share

    cap = int(round(state["cap"]))
    desired = torch.mean(terrain.terrain_levels.float())
    terrain.terrain_levels.clamp_(max=cap)
    applied = torch.mean(terrain.terrain_levels.float())
    return {
        "cap": torch.tensor(float(cap), device=env.device),
        "up_share": share,
        "up_share_ema": torch.tensor(state["ema"], device=env.device),
        "desired": desired,
        "applied": applied,
    }


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
        # P0-2 2026-10-22: lin-gate statistics restricted to envs with a real forward
        # command (zero-command / standing envs excluded from numerator AND denominator).
        command_term._gate_cmd_total = 0.0
        command_term._gate_cmd_lin_success = 0.0
        command_term._gate_cmd_err_xy = 0.0


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
    forward_ok_ratio: float = 0.5,
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
    forward_ok, cmd_active = _episode_forward_ok(  # P0 2026-10-21
        env, env_ids, command_term, forward_ok_ratio
    )
    lin_success = survived & (err_xy < success_xy)
    if forward_ok is not None:
        # P0: reject stand-still fake success (err_xy ≈ |cmd| < success_xy while frozen)
        lin_success = lin_success & forward_ok
    yaw_success = survived & (err_yaw < success_yaw)
    # P0-2 2026-10-22: envs whose episode-mean |cmd_x| is ~0 (standing envs, near-zero
    # resampled commands) cannot demonstrate progress; counting them inflated success_rate
    # and dragged mean_err_xy down. The lin GATE therefore evaluates only over commanded
    # envs (``_gate_cmd_*``); the TB ``success_rate`` / ``mean_err_xy`` keys keep the
    # all-env values so existing curves stay comparable.
    active = valid if cmd_active is None else (valid & cmd_active)

    command_term._gate_total += float(valid.sum().item())
    command_term._gate_survived += float((survived & valid).sum().item())
    command_term._gate_lin_success += float((lin_success & valid).sum().item())
    command_term._gate_yaw_success += float((yaw_success & valid).sum().item())
    command_term._gate_err_xy += float(err_xy[valid].sum().item())
    command_term._gate_err_yaw += float(err_yaw[valid].sum().item())
    command_term._gate_cmd_total += float(active.sum().item())
    command_term._gate_cmd_lin_success += float((lin_success & active).sum().item())
    command_term._gate_cmd_err_xy += float(err_xy[active].sum().item())

    elapsed = env.common_step_counter - command_term._gate_last_eval
    if elapsed >= min_env_steps and command_term._gate_total >= float(min_episodes):
        total = command_term._gate_total
        time_out_rate = command_term._gate_survived / total
        yaw_rate = command_term._gate_yaw_success / total
        mean_err_yaw = command_term._gate_err_yaw / total
        # P0-2: gate inputs restricted to envs that actually had a forward command
        # (zero-command / standing envs excluded - see the accumulation block above).
        cmd_total = command_term._gate_cmd_total
        gate_lin_rate = command_term._gate_cmd_lin_success / cmd_total if cmd_total > 0 else 0.0
        gate_err_xy = command_term._gate_cmd_err_xy / cmd_total if cmd_total > 0 else float("inf")

        freeze = int(getattr(command_term, "_cmd_freeze_windows", 0))
        if freeze > 0:
            # terrain level-up freeze (terrain_levels_vel_strict sets _cmd_freeze_windows):
            # the x range holds as-is and the streak restarts after the freeze, so the policy
            # gets clean windows on the new terrain before the range widens again. The yaw
            # gate stays independent and keeps evaluating.
            command_term._cmd_freeze_windows = freeze - 1
            command_term._gate_streak = 0
            print(f"[INFO] x command range frozen ({freeze - 1} eval windows left)")
        elif gate_lin_rate >= min_success_rate and time_out_rate >= min_success_rate and gate_err_xy <= success_xy:
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
        command_term._gate_cmd_total = 0.0
        command_term._gate_cmd_lin_success = 0.0
        command_term._gate_cmd_err_xy = 0.0

    window = command_term._gate_total if command_term._gate_total > 0 else 1.0
    cmd_window = command_term._gate_cmd_total if command_term._gate_cmd_total > 0 else 1.0
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
        # P0-2 2026-10-22: the values the x gate actually decides on (commanded envs only).
        "cmd_success_rate": command_term._gate_cmd_lin_success / cmd_window,
        "cmd_mean_err_xy": command_term._gate_cmd_err_xy / cmd_window,
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

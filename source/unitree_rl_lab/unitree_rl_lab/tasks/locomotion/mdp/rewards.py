from __future__ import annotations

import torch
from typing import TYPE_CHECKING

try:
    from isaaclab.utils.math import quat_apply_inverse
except ImportError:
    from isaaclab.utils.math import quat_rotate_inverse as quat_apply_inverse
from isaaclab.assets import Articulation, RigidObject
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import ContactSensor

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv

"""
Joint penalties.
"""


def energy(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """Penalize the energy used by the robot's joints."""
    asset: Articulation = env.scene[asset_cfg.name]

    qvel = asset.data.joint_vel[:, asset_cfg.joint_ids]
    qfrc = asset.data.applied_torque[:, asset_cfg.joint_ids]
    return torch.sum(torch.abs(qvel) * torch.abs(qfrc), dim=-1)


def stand_still(
    env: ManagerBasedRLEnv, command_name: str = "base_velocity", asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")
) -> torch.Tensor:
    asset: Articulation = env.scene[asset_cfg.name]

    reward = torch.sum(torch.abs(asset.data.joint_pos - asset.data.default_joint_pos), dim=1)
    cmd_norm = torch.norm(env.command_manager.get_command(command_name), dim=1)
    return reward * (cmd_norm < 0.1)


"""
Robot.
"""


def orientation_l2(
    env: ManagerBasedRLEnv, desired_gravity: list[float], asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")
) -> torch.Tensor:
    """Reward the agent for aligning its gravity with the desired gravity vector using L2 squared kernel."""
    # extract the used quantities (to enable type-hinting)
    asset: RigidObject = env.scene[asset_cfg.name]

    desired_gravity = torch.tensor(desired_gravity, device=env.device)
    cos_dist = torch.sum(asset.data.projected_gravity_b * desired_gravity, dim=-1)  # cosine distance
    normalized = 0.5 * cos_dist + 0.5  # map from [-1, 1] to [0, 1]
    return torch.square(normalized)


def upward(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """Penalize z-axis base linear velocity using L2 squared kernel."""
    # extract the used quantities (to enable type-hinting)
    asset: RigidObject = env.scene[asset_cfg.name]
    reward = torch.square(1 - asset.data.projected_gravity_b[:, 2])
    return reward


def joint_position_penalty(
    env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg, stand_still_scale: float, velocity_threshold: float
) -> torch.Tensor:
    """Penalize joint position error from default on the articulation.

    .. note::
        Only the joints configured in :attr:`asset_cfg.joint_ids` contribute to the term.
    """
    # extract the used quantities (to enable type-hinting)
    asset: Articulation = env.scene[asset_cfg.name]
    cmd = torch.linalg.norm(env.command_manager.get_command("base_velocity"), dim=1)
    body_vel = torch.linalg.norm(asset.data.root_lin_vel_b[:, :2], dim=1)
    joint_pos = asset.data.joint_pos[:, asset_cfg.joint_ids]
    default_joint_pos = asset.data.default_joint_pos[:, asset_cfg.joint_ids]
    reward = torch.linalg.norm(joint_pos - default_joint_pos, dim=1)
    return torch.where(torch.logical_or(cmd > 0.0, body_vel > velocity_threshold), reward, stand_still_scale * reward)


"""
Feet rewards.
"""


def feet_stumble(env: ManagerBasedRLEnv, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
    # extract the used quantities (to enable type-hinting)
    contact_sensor: ContactSensor = env.scene.sensors[sensor_cfg.name]
    forces_z = torch.abs(contact_sensor.data.net_forces_w[:, sensor_cfg.body_ids, 2])
    forces_xy = torch.linalg.norm(contact_sensor.data.net_forces_w[:, sensor_cfg.body_ids, :2], dim=2)
    # Penalize feet hitting vertical surfaces
    reward = torch.any(forces_xy > 4 * forces_z, dim=1).float()
    return reward


def feet_height_body(
    env: ManagerBasedRLEnv,
    command_name: str,
    asset_cfg: SceneEntityCfg,
    target_height: float,
    tanh_mult: float,
) -> torch.Tensor:
    """Reward the swinging feet for clearing a specified height off the ground"""
    asset: RigidObject = env.scene[asset_cfg.name]
    cur_footpos_translated = asset.data.body_pos_w[:, asset_cfg.body_ids, :] - asset.data.root_pos_w[:, :].unsqueeze(1)
    footpos_in_body_frame = torch.zeros(env.num_envs, len(asset_cfg.body_ids), 3, device=env.device)
    cur_footvel_translated = asset.data.body_lin_vel_w[:, asset_cfg.body_ids, :] - asset.data.root_lin_vel_w[
        :, :
    ].unsqueeze(1)
    footvel_in_body_frame = torch.zeros(env.num_envs, len(asset_cfg.body_ids), 3, device=env.device)
    for i in range(len(asset_cfg.body_ids)):
        footpos_in_body_frame[:, i, :] = quat_apply_inverse(asset.data.root_quat_w, cur_footpos_translated[:, i, :])
        footvel_in_body_frame[:, i, :] = quat_apply_inverse(asset.data.root_quat_w, cur_footvel_translated[:, i, :])
    foot_z_target_error = torch.square(footpos_in_body_frame[:, :, 2] - target_height).view(env.num_envs, -1)
    foot_velocity_tanh = torch.tanh(tanh_mult * torch.norm(footvel_in_body_frame[:, :, :2], dim=2))
    reward = torch.sum(foot_z_target_error * foot_velocity_tanh, dim=1)
    reward *= torch.linalg.norm(env.command_manager.get_command(command_name), dim=1) > 0.1
    reward *= torch.clamp(-env.scene["robot"].data.projected_gravity_b[:, 2], 0, 0.7) / 0.7
    return reward


def foot_clearance_reward(
    env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg, target_height: float, std: float, tanh_mult: float
) -> torch.Tensor:
    """Reward the swinging feet for clearing a specified height off the ground"""
    asset: RigidObject = env.scene[asset_cfg.name]
    foot_z_target_error = torch.square(asset.data.body_pos_w[:, asset_cfg.body_ids, 2] - target_height)
    foot_velocity_tanh = torch.tanh(tanh_mult * torch.norm(asset.data.body_lin_vel_w[:, asset_cfg.body_ids, :2], dim=2))
    reward = foot_z_target_error * foot_velocity_tanh
    return torch.exp(-torch.sum(reward, dim=1) / std)


def foot_clearance_air(
    env: ManagerBasedRLEnv,
    asset_cfg: SceneEntityCfg,
    sensor_cfg: SceneEntityCfg,
    target_height: float,
    std: float,
    tanh_mult: float,
    command_name: str = "base_velocity",
    min_command_speed: float = 0.0,
) -> torch.Tensor:
    """P1 2026-10-21: like foot_clearance_reward but only while the foot is airborne.

    Stock foot_clearance_reward pays 1.0 when feet are on the ground (tanh=0), so rolling
    at wheel-radius height collects full reward and never lifts. Gating on current_air_time
    makes the term pay only for real wheel lifts (stairs: clear the 0.23 m riser).

    2026-10-23 P0-3: the air gate alone still pays out for lifting the legs **in place**
    (measured +0.594 per episode with the wheels locked, while the robot made no forward
    progress at all). The optional ``min_command_speed`` gate adds a second condition: the
    env must actually be commanded to move (|cmd_xy| >= threshold) for the lift to be paid.
    ``min_command_speed = 0.0`` (default) keeps the old behaviour for every other task.
    Rollback: use mdp.foot_clearance_reward instead and delete this function.
    """
    asset: RigidObject = env.scene[asset_cfg.name]
    contact_sensor: ContactSensor = env.scene.sensors[sensor_cfg.name]
    in_air = contact_sensor.data.current_air_time[:, sensor_cfg.body_ids] > 0
    foot_z_target_error = torch.square(asset.data.body_pos_w[:, asset_cfg.body_ids, 2] - target_height)
    foot_velocity_tanh = torch.tanh(tanh_mult * torch.norm(asset.data.body_lin_vel_w[:, asset_cfg.body_ids, :2], dim=2))
    cost = foot_z_target_error * foot_velocity_tanh
    reward = torch.exp(-torch.sum(cost, dim=1) / std)
    if min_command_speed > 0.0:
        command = env.command_manager.get_command(command_name)
        commanded = torch.linalg.norm(command[:, :2], dim=1) >= min_command_speed
    else:
        commanded = torch.ones_like(in_air[:, 0])
    # all feet planted (rolling / standing): zero, no free lunch
    # not commanded to move: zero as well - lifting in place is not progress
    return torch.where(in_air.any(dim=1) & commanded, reward, torch.zeros_like(reward))


def body_climb_progress(
    env: ManagerBasedRLEnv,
    command_name: str = "base_velocity",
    min_command_speed: float = 0.15,
    climb_speed_ref: float = 0.25,
) -> torch.Tensor:
    """Reward ASCENDING base height while the robot is commanded to move (2026-10-27 P0-1).

    Why this term exists (measured on run ``2026-10-24_15-43-11_airy_A_stairs_only``):
    the stairs curriculum cannot discriminate climbing from descending, and the only task
    reward is ``track_lin_vel_xy`` - i.e. HORIZONTAL velocity. Descending manufactures
    horizontal velocity for free (gravity, and the braked wheels act as brakes), while
    climbing costs 40 kg x 9.81 x riser of potential energy per step and additionally
    raises every penalty term (joint_torques / action_rate / joint_acc). Consequence:
    descending is optimal, the terrain level plateaus exactly where ascending stops
    working (level 5.16 = 0.153 m riser, stairs success 0.53, time_out 0.52) and the
    recorded videos show "downstairs works, upstairs fails".

    The reward is a dimensionless ascent rate: ``clamp(dz/dt, 0, climb_speed_ref) /
    climb_speed_ref`` in [0, 1], gated on a real movement command (standing envs are not
    paid) and capped at ``climb_speed_ref`` so bunny-hopping up cannot farm it without
    bound. With weight 1.0 it is comparable in scale to ``track_lin_vel_xy`` (both are
    ~O(1)/s), so it rebalances the reward instead of dominating it.
    """
    robot: RigidObject = env.scene["robot"]
    base_z = robot.data.root_pos_w[:, 2]
    prev_z = getattr(env, "_climb_prev_z", None)
    if prev_z is None or prev_z.shape[0] != base_z.shape[0]:
        prev_z = base_z.clone()
        env._climb_prev_z = prev_z
    dz = base_z - prev_z
    prev_z[:] = base_z  # keep the running reference in place (no per-call allocation)
    climb_speed = dz.clamp(min=0.0) / float(env.step_dt)
    reward = (climb_speed / climb_speed_ref).clamp(max=1.0)
    if min_command_speed > 0.0:
        command = env.command_manager.get_command(command_name)
        commanded = torch.linalg.norm(command[:, :2], dim=1) >= min_command_speed
        reward = reward * commanded
    return reward


def body_climb_progress_peak(
    env: ManagerBasedRLEnv,
    command_name: str = "base_velocity",
    min_command_speed: float = 0.15,
    climb_speed_ref: float = 0.25,
) -> torch.Tensor:
    """Reward ONLY a new episode-high base height (2026-10-28 P0-A, replaces the dt form).

    Why the per-step ``dz`` form had to go (measured on run ``2026-10-27_23-15-44``):
    it scored 0.295 of the full mark while ``Curriculum/stairs_updown/up_share`` stayed at
    **0.0000 for 9424 iterations** - i.e. the robot bobbed its base up and down in place
    (leg lifting, trotting) and collected the "climb" reward without ever ascending a
    single step. A per-step reward cannot tell vibration from progress.

    This version pays only for the NET new maximum: ``gain = clamp(z - peak_z, 0, ...)``
    with ``peak_z`` = highest base height reached in the CURRENT episode (reset at spawn).
    Bobbing now pays exactly 0 because the base never exceeds its own record; the only way
    to earn it is to actually get higher up the stairs.

    Scale: reward in [0, 1] per step, capped at ``climb_speed_ref`` (0.25 m/s of ascent).
    Because only net gains are paid, the episode total equals ``climb_height /
    (climb_speed_ref * dt)`` = 200 x climb_height, so a 2 m climb with weight 2.0 yields
    ~0.4/s of episode reward - competitive with ``track_lin_vel_xy`` (1.07/s) but not
    dominant. Rollback: swap the RewTerm back to ``mdp.body_climb_progress``.
    """
    robot: RigidObject = env.scene["robot"]
    base_z = robot.data.root_pos_w[:, 2]
    peak_z = getattr(env, "_climb_peak_z", None)
    if peak_z is None or peak_z.shape[0] != base_z.shape[0]:
        peak_z = base_z.clone()
        env._climb_peak_z = peak_z
    # a fresh episode restarts the record at the spawn height (spawn z differs per level)
    just_reset = env.episode_length_buf <= 1
    peak_z[just_reset] = base_z[just_reset]
    gain = (base_z - peak_z).clamp(min=0.0)
    torch.maximum(peak_z, base_z, out=peak_z)  # in place, no per-step allocation
    climb_speed = gain / float(env.step_dt)
    reward = (climb_speed / climb_speed_ref).clamp(max=1.0)
    if min_command_speed > 0.0:
        command = env.command_manager.get_command(command_name)
        commanded = torch.linalg.norm(command[:, :2], dim=1) >= min_command_speed
        reward = reward * commanded
    return reward


def feet_too_near(
    env: ManagerBasedRLEnv, threshold: float = 0.2, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")
) -> torch.Tensor:
    asset: Articulation = env.scene[asset_cfg.name]
    feet_pos = asset.data.body_pos_w[:, asset_cfg.body_ids, :]
    distance = torch.norm(feet_pos[:, 0] - feet_pos[:, 1], dim=-1)
    return (threshold - distance).clamp(min=0)


def feet_contact_without_cmd(
    env: ManagerBasedRLEnv, sensor_cfg: SceneEntityCfg, command_name: str = "base_velocity"
) -> torch.Tensor:
    """
    Reward for feet contact when the command is zero.
    """
    # asset: Articulation = env.scene[asset_cfg.name]
    contact_sensor: ContactSensor = env.scene.sensors[sensor_cfg.name]
    is_contact = contact_sensor.data.current_contact_time[:, sensor_cfg.body_ids] > 0

    command_norm = torch.norm(env.command_manager.get_command(command_name), dim=1)
    reward = torch.sum(is_contact, dim=-1).float()
    return reward * (command_norm < 0.1)


def air_time_variance_penalty(env: ManagerBasedRLEnv, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
    """Penalize variance in the amount of time each foot spends in the air/on the ground relative to each other"""
    # extract the used quantities (to enable type-hinting)
    contact_sensor: ContactSensor = env.scene.sensors[sensor_cfg.name]
    if contact_sensor.cfg.track_air_time is False:
        raise RuntimeError("Activate ContactSensor's track_air_time!")
    # compute the reward
    last_air_time = contact_sensor.data.last_air_time[:, sensor_cfg.body_ids]
    last_contact_time = contact_sensor.data.last_contact_time[:, sensor_cfg.body_ids]
    return torch.var(torch.clip(last_air_time, max=0.5), dim=1) + torch.var(
        torch.clip(last_contact_time, max=0.5), dim=1
    )


"""
Feet Gait rewards.
"""


def feet_gait(
    env: ManagerBasedRLEnv,
    period: float,
    offset: list[float],
    sensor_cfg: SceneEntityCfg,
    threshold: float = 0.5,
    command_name=None,
) -> torch.Tensor:
    contact_sensor: ContactSensor = env.scene.sensors[sensor_cfg.name]
    is_contact = contact_sensor.data.current_contact_time[:, sensor_cfg.body_ids] > 0

    global_phase = ((env.episode_length_buf * env.step_dt) % period / period).unsqueeze(1)
    phases = []
    for offset_ in offset:
        phase = (global_phase + offset_) % 1.0
        phases.append(phase)
    leg_phase = torch.cat(phases, dim=-1)

    reward = torch.zeros(env.num_envs, dtype=torch.float, device=env.device)
    for i in range(len(sensor_cfg.body_ids)):
        is_stance = leg_phase[:, i] < threshold
        reward += ~(is_stance ^ is_contact[:, i])

    if command_name is not None:
        cmd_norm = torch.norm(env.command_manager.get_command(command_name), dim=1)
        reward *= cmd_norm > 0.1
    return reward


"""
Other rewards.
"""


def joint_mirror(env: ManagerBasedRLEnv, asset_cfg: SceneEntityCfg, mirror_joints: list[list[str]]) -> torch.Tensor:
    # extract the used quantities (to enable type-hinting)
    asset: Articulation = env.scene[asset_cfg.name]
    if not hasattr(env, "joint_mirror_joints_cache") or env.joint_mirror_joints_cache is None:
        # Cache joint positions for all pairs
        env.joint_mirror_joints_cache = [
            [asset.find_joints(joint_name) for joint_name in joint_pair] for joint_pair in mirror_joints
        ]
    reward = torch.zeros(env.num_envs, device=env.device)
    # Iterate over all joint pairs
    for joint_pair in env.joint_mirror_joints_cache:
        # Calculate the difference for each pair and add to the total reward
        reward += torch.sum(
            torch.square(asset.data.joint_pos[:, joint_pair[0][0]] - asset.data.joint_pos[:, joint_pair[1][0]]),
            dim=-1,
        )
    reward *= 1 / len(mirror_joints) if len(mirror_joints) > 0 else 0
    return reward

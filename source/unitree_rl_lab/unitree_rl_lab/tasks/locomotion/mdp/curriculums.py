from __future__ import annotations

import torch
from collections.abc import Sequence
from typing import TYPE_CHECKING

from isaaclab.assets import Articulation
from isaaclab.managers import SceneEntityCfg

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def terrain_levels_vel(
    env: ManagerBasedRLEnv,
    env_ids: Sequence[int],
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
    upgrade_factor: float = 0.5,
) -> torch.Tensor:
    """地形等级课程学习（自适应升级阈值）。

    升级阈值根据指令速度自适应：
        threshold = |cmd_vel| * episode_length_s * upgrade_factor

    示例（upgrade_factor=0.3, episode_length_s=20）：
        cmd=0.1 m/s → threshold = 0.1×20×0.3 = 0.6m
        cmd=0.5 m/s → threshold = 0.5×20×0.3 = 3.0m
        cmd=1.0 m/s → threshold = 1.0×20×0.3 = 6.0m

    慢速时容易晋级，快速时需要走更远——与机器人实际能力匹配。

    与原版相比仅改动 move_up 阈值（从固定 4m 改成自适应），
    move_down 降级逻辑保持原样。

    原版升级阈值：threshold = |cmd_vel| * episode_length_s * 0.5 = 4m
    原版函数位置：unitree_rl_lab/tasks/locomotion/mdp/curriculums.py
    """
    asset: Articulation = env.scene[asset_cfg.name]
    terrain = env.scene.terrain
    command = env.command_manager.get_command("base_velocity")

    # 计算机器人从出生点的行走距离
    distance = torch.norm(
        asset.data.root_pos_w[env_ids, :2] - env.scene.env_origins[env_ids, :2], dim=1
    )
    # 自适应升级阈值
    cmd_speed = torch.norm(command[env_ids, :2], dim=1)
    threshold = cmd_speed * env.max_episode_length_s * upgrade_factor
    # 走得足够远 → 升一级
    move_up = distance > threshold
    # 走得不够 → 降一级（原版逻辑，保持不变）
    move_down = distance < cmd_speed * env.max_episode_length_s * 0.5
    move_down *= ~move_up

    # 更新地形原点
    terrain.update_env_origins(env_ids, move_up, move_down)
    return torch.mean(terrain.terrain_levels.float())


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

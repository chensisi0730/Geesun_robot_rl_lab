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
    upgrade_factor: float = 0.4,
    downgrade_factor: float = 0.15,
    min_upgrade_distance: float = 1.0,
    min_downgrade_distance: float = 0.5,
) -> torch.Tensor:
    """地形等级课程学习（自适应升级/降级阈值，无冲突）。

    三个区域设计：
        降级区: distance < max(V × T × downgrade_factor, min_downgrade_distance)
        保持区: 降级阈值 ≤ distance ≤ 升级阈值
        升级区: distance > max(V × T × upgrade_factor, min_upgrade_distance)

    示例（episode_length_s=20, cmd_vel=1.0 m/s）：
        降级阈值 = max(1.0×20×0.15, 0.5) = 3.0m
        升级阈值 = max(1.0×20×0.25, 1.0) = 5.0m
        保持区间 = 3.0m ~ 5.0m

    示例（episode_length_s=20, cmd_vel=0.3 m/s）：
        降级阈值 = max(0.3×20×0.15, 0.5) = 0.9m
        升级阈值 = max(0.3×20×0.25, 1.0) = 1.5m

    这种设计确保：
        1. 升级和降级条件永远不会冲突（upgrade_factor > downgrade_factor）
        2. 有明显的"保持区"避免频繁变动
        3. 机器人需要真正掌握当前地形难度才能晋级
        4. min_upgrade_distance/min_downgrade_distance 防止低速指令时阈值过低
    """
    asset: Articulation = env.scene[asset_cfg.name]
    terrain = env.scene.terrain
    command = env.command_manager.get_command("base_velocity")

    # 计算机器人从出生点的行走距离
    distance = torch.norm(
        asset.data.root_pos_w[env_ids, :2] - env.scene.env_origins[env_ids, :2], dim=1
    )
    # 指令速度
    cmd_speed = torch.norm(command[env_ids, :2], dim=1)

    # 理想行走距离 = 速度 × episode时长
    ideal_distance = cmd_speed * env.max_episode_length_s

    # 升级阈值：取比例阈值和最小绝对距离的较大值，防止低速时异常升级
    move_up = distance > torch.maximum(ideal_distance * upgrade_factor,
                                        torch.tensor(min_upgrade_distance, device=distance.device))
    # 降级阈值：取比例阈值和最小绝对距离的较大值
    move_down = distance < torch.maximum(ideal_distance * downgrade_factor,
                                          torch.tensor(min_downgrade_distance, device=distance.device))

    # 安全保护：确保不会同时触发（虽然参数设计已保证不冲突）
    move_down *= ~move_up

    # 更新地形原点
    terrain.update_env_origins(env_ids, move_up, move_down)

    # 调试日志
    if hasattr(env, "extras") and "log" in env.extras:
        env.extras["log"]["Curriculum/terrain_up_count"] = move_up.sum().item()
        env.extras["log"]["Curriculum/terrain_down_count"] = move_down.sum().item()
        env.extras["log"]["Curriculum/terrain_mean_distance"] = distance.mean().item()

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
        # 平均每步奖励达到最大可能值的 improvement_threshold 比例才升级
        if reward > reward_term.weight * improvement_threshold:
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

from __future__ import annotations

import torch
from typing import TYPE_CHECKING

from isaaclab.managers import SceneEntityCfg

from unitree_rl_lab.tasks.locomotion.sensors.airy_bev import (
    AIRY_BEV_AZ_BINS,
    AIRY_BEV_DIST_BINS,
    AIRY_BEV_MAX_DIST,
    airy_bev_grid,
)

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def gait_phase(env: ManagerBasedRLEnv, period: float) -> torch.Tensor:
    if not hasattr(env, "episode_length_buf"):
        env.episode_length_buf = torch.zeros(env.num_envs, device=env.device, dtype=torch.long)

    global_phase = (env.episode_length_buf * env.step_dt) % period / period

    phase = torch.zeros(env.num_envs, 2, device=env.device)
    phase[:, 0] = torch.sin(global_phase * torch.pi * 2.0)
    phase[:, 1] = torch.cos(global_phase * torch.pi * 2.0)
    return phase


def airy_bev_scan(
    env: ManagerBasedRLEnv,
    sensor_cfg: SceneEntityCfg,
    n_az: int = AIRY_BEV_AZ_BINS,
    n_dist: int = AIRY_BEV_DIST_BINS,
    max_dist: float = AIRY_BEV_MAX_DIST,
    ground_z: float = 0.0,
) -> torch.Tensor:
    """Airy LiDAR point cloud as a polar max-height grid, for use as an ObsTerm.

    Thin ``ObsTerm`` wrapper around :func:`airy_bev_grid`: pulls the ray-cast buffers off the
    sensor and returns a flat ``(num_envs, n_az * n_dist)`` tensor, i.e. 720 dims at the default
    36 x 20 budget.

    ``ground_z`` is the world z of the ground plane. The training terrain is generated with its
    surface at z = 0 (see ``TerrainImporterCfg``), so 0.0 is correct here; if the terrain is ever
    re-based, pass the new value.

    Empty bins (rays that escaped, or a sector with no return) come back as 0.0, i.e. "nothing
    there", which is the same convention ``mdp.height_scan`` uses for its ground cells.
    """
    sensor = env.scene.sensors[sensor_cfg.name]
    data = sensor.data
    grid = airy_bev_grid(
        data.ray_hits_w,
        data.pos_w,
        data.quat_w,
        n_az=n_az,
        n_dist=n_dist,
        max_dist=max_dist,
        ground_z=ground_z,
    )
    return grid.reshape(grid.shape[0], -1)

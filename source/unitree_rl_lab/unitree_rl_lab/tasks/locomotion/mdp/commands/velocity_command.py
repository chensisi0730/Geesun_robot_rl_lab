from __future__ import annotations

from collections.abc import Sequence
from dataclasses import MISSING

import torch
from isaaclab.envs.mdp import UniformVelocityCommand, UniformVelocityCommandCfg
from isaaclab.utils import configclass


class UniformLevelVelocityCommand(UniformVelocityCommand):
    """Uniform velocity command with episode sums for the ``forward_ok`` gate.

    2026-10-21 P0: track progress along the commanded x axis so curriculum / test
    success can reject "stand still and pass err_xy < 0.25". Rollback: set
    ``UniformLevelVelocityCommandCfg.class_type`` back to ``UniformVelocityCommand``
    (and drop the forward_ok AND in curriculums / test_walk_torque).
    """

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self._fwd_sum = torch.zeros(self.num_envs, device=self.device)
        self._cmd_abs_x_sum = torch.zeros(self.num_envs, device=self.device)
        self._fwd_step_count = torch.zeros(self.num_envs, device=self.device)

    def _update_metrics(self):
        super()._update_metrics()
        cmd_x = self.vel_command_b[:, 0]
        # progress along command: +v when cmd>0, -v when cmd<0 (0 cmd contributes 0)
        self._fwd_sum += torch.sign(cmd_x) * self.robot.data.root_lin_vel_b[:, 0]
        self._cmd_abs_x_sum += cmd_x.abs()
        self._fwd_step_count += 1.0

    def reset(self, env_ids: Sequence[int] | None = None) -> dict[str, torch.Tensor]:
        extras = super().reset(env_ids)
        # this IsaacLab has no isaaclab.utils.index_fill_; clear with index assignment
        if env_ids is None:
            self._fwd_sum.zero_()
            self._cmd_abs_x_sum.zero_()
            self._fwd_step_count.zero_()
        else:
            ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long)
            self._fwd_sum[ids] = 0.0
            self._cmd_abs_x_sum[ids] = 0.0
            self._fwd_step_count[ids] = 0.0
        return extras


@configclass
class UniformLevelVelocityCommandCfg(UniformVelocityCommandCfg):
    limit_ranges: UniformVelocityCommandCfg.Ranges = MISSING
    class_type: type = UniformLevelVelocityCommand

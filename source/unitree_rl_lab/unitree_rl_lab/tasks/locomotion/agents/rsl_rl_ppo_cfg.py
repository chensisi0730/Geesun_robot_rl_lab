# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from isaaclab.utils import configclass
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoActorCriticCfg, RslRlPpoAlgorithmCfg


@configclass
class BasePPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 50000
    save_interval = 100
    experiment_name = ""  # same as task name
    empirical_normalization = False
    policy = RslRlPpoActorCriticCfg(
        init_noise_std=1.0,
        actor_hidden_dims=[512, 256, 128],
        critic_hidden_dims=[512, 256, 128],
        activation="elu",
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.01,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class UnitreeGo2PPORunnerCfg(BasePPORunnerCfg):
    """PPO for the Go2 velocity task, tuned between the shared config and a too-conservative one.

    The shared :class:`BasePPORunnerCfg` was too aggressive once the command curriculum
    widened (entropy bonus kept growing the exploration noise, the KL-adaptive LR collapsed to
    its 1e-5 floor, and the value function diverged). An earlier "stability-tuned" variant went
    too far the other way: with ``init_noise_std=0.5`` and ``entropy_coef=0.005`` a *fresh*
    run collapsed its exploration noise within a few hundred iterations and got stuck in a
    yaw-ignoring local optimum (``error_vel_yaw`` ≈ 0.9 vs. the 0.35 gate, velocity range
    frozen at ±0.25 m/s). The values below restore enough exploration/learning pressure to
    escape that optimum while keeping the moderate update size and mini-batch count that
    stabilise late training (see the curve analysis in ``doc/training_monitoring.md``).
    """

    policy = RslRlPpoActorCriticCfg(
        init_noise_std=0.8,
        actor_hidden_dims=[512, 256, 128],
        critic_hidden_dims=[512, 256, 128],
        activation="elu",
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.02,
        num_learning_epochs=4,
        num_mini_batches=8,
        learning_rate=8.0e-4,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=0.8,
    )

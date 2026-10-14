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

    # ABLATION (2026-09-24): height_scanner critic-obs run; revert to "" after launch.
    experiment_name = "unitree_go2_velocity_ht"

    policy = RslRlPpoActorCriticCfg(
        # ABLATION (2026-10-09): 10x network width [512, 256, 128] -> [1536, 1024, 512]
        # (0.48M -> 4.66M params total); revert after the ablation run.
        init_noise_std=0.8,
        actor_hidden_dims=[1536, 1024, 512],
        critic_hidden_dims=[1536, 1024, 512],
        activation="elu",
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.02,
        num_learning_epochs=4,
        num_mini_batches=8,
        learning_rate=1.0e-04,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.025,
        max_grad_norm=0.8,
    )


@configclass
class UnitreeG1PPORunnerCfg(BasePPORunnerCfg):
    """PPO for the G1 29-DoF velocity task.

    The 2026-09-07 run (27k iters, shared adaptive schedule) stalled: the KL-adaptive LR
    collapsed to ~0 within the first ~100 iterations (``Loss/learning_rate`` == 0 from iter
    1001 on) while ``bad_orientation`` stayed at ~0.98 and the command range frozen at ±0.1.
    Minimal change (2026-09-24): keep everything from :class:`BasePPORunnerCfg` but use a
    constant LR so early learning is not frozen; see ``doc/training_monitoring.md`` §4.6.
    """

    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.01,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="constant",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


# --- Geesun dog: one PPO runner class per asset variant ---
# The two campaigns get *separate* classes (not a shared base) so the 6h auto-tuner can edit
# one without touching the other and they can run concurrently. Hyper-parameters are kept
# identical on purpose (the dog1 <-> lingsi_d30w ablation must differ only in the asset); when
# you change one, change the other and note it in the ablation log.


@configclass
class UnitreeGeesunDogDog1PPORunnerCfg(BasePPORunnerCfg):
    """PPO for the GeesunDog **dog1** (footed quadruped) velocity task.

    Hyper-parameters identical to :class:`BasePPORunnerCfg` (re-declared explicitly so the
    auto-tuner's knob edits are scoped to this class and can never touch the shared Base used
    by other robots); only ``experiment_name`` differs so runs land in
    ``logs/rsl_rl/unitree_geesun_dog1/`` and the 6h monitor / auto-tuner can follow this
    campaign independently of the Go2 and lingsi_d30w ones.
    """

    experiment_name = "unitree_geesun_dog1"
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
class UnitreeGeesunDogLingsiD30WPPORunnerCfg(BasePPORunnerCfg):
    """PPO for the GeesunDog **lingsi_d30w** (D30W wheel-legged) velocity task.

    Same hyper-parameters as :class:`UnitreeGeesunDogDog1PPORunnerCfg` on purpose (ablation
    parity); a separate class so runs land in ``logs/rsl_rl/unitree_geesun_lingsi_d30w/`` and
    the auto-tuner scope can never cross into the dog1 campaign.
    """

    experiment_name = "unitree_geesun_lingsi_d30w"
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

"""Gym registrations for the GeesunDog ``lingsi_d30w`` (wheel-legged) locomotion task.

Four tasks share ONE policy (策略) observation - 49 dims of proprioception - and differ only in the
critic (评论家) privileged observation, so the actor stays deployable and the ablation isolates what
external perception buys. See the ablation table in ``velocity_env_cfg.py``.

=================  =====================================================  ==============
task id            critic external perception                              critic dims
=================  =====================================================  ==============
``...-Velocity``   height_scanner 187 (baseline, config A)                   263
``...-AiryReplace`` Airy BEV 720, no height_scanner (config B)               796
``...-AiryStacked`` height_scanner 187 + Airy BEV 720 (config C)              983
``...-ProprioOnly`` none (config D, lower bound)                               76
=================  =====================================================  ==============

Widths are MEASURED (``scripts/diagnose/smoke_env_obs.py``), not derived: policy is 57 and action
is 16 for every variant, because the D30W platform has 16 actuated joints (not 12).

Each variant writes to its OWN ``experiment_name`` so the four runs can be compared side by side in
TensorBoard without clobbering each other. Changing the critic obs changes the value net input
layer, so **every variant must train from scratch** - no checkpoint transfers between them.
"""

import gymnasium as gym

_BASE = "Unitree-GeesunDog-LingsiD30W"
_CFG = f"{__name__}.velocity_env_cfg"
_RSL = "unitree_rl_lab.tasks.locomotion.agents.rsl_rl_ppo_cfg:UnitreeGeesunDogLingsiD30WPPORunnerCfg"


def _register(suffix: str, env_cfg: str, play_cfg: str, doc: str) -> None:
    gym.register(
        id=f"{_BASE}-Velocity{suffix}",
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": f"{_CFG}:{env_cfg}",
            "play_env_cfg_entry_point": f"{_CFG}:{play_cfg}",
            "rsl_rl_cfg_entry_point": _RSL,
        },
    )


_register("", "RobotEnvCfg", "RobotPlayEnvCfg", "config A")
_register("-AiryReplace", "RobotEnvCfgAiryReplace", "RobotPlayEnvCfgAiryReplace", "config B")
_register("-AiryStacked", "RobotEnvCfgAiryStacked", "RobotPlayEnvCfgAiryStacked", "config C")
_register("-ProprioOnly", "RobotEnvCfgProprioOnly", "RobotPlayEnvCfgProprioOnly", "config D")
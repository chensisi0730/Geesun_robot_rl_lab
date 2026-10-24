# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Load a training run's saved env cfg snapshot (训练运行配置快照).

Each training run saves the exact environment configuration (环境配置) it was trained with into
``<run>/params/velocity_env_cfg.py``. Loading that snapshot keeps the observation (观测) layout in
sync with an old checkpoint even after the task cfg in the repo has moved on - e.g. when
``height_scanner`` (高度扫描传感器) was added to the critic (价值网络) observations, an old checkpoint
fails to load with ``size mismatch for critic.0.weight`` unless the snapshot is used.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys


def load_snapshot_env_cfg(path: str, device: str | None = None, num_envs: int | None = None, use_fabric: bool | None = None):
    """Instantiate the env cfg class saved by a training run.

    Args:
        path: Path to the run's ``params/velocity_env_cfg.py`` snapshot.
        device: Optional simulation device override (e.g. ``"cuda:0"``).
        num_envs: Optional number-of-environments override.
        use_fabric: Optional Fabric (Fabric 并行数据接口) override.

    Returns:
        The instantiated ``ManagerBasedRLEnvCfg``; the ``*PlayEnvCfg`` class is preferred when the
        snapshot defines one.
    """
    from isaaclab.envs import ManagerBasedRLEnvCfg

    module_name = "run_snapshot_env_cfg"
    spec = importlib.util.spec_from_file_location(module_name, os.path.abspath(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load env cfg module from: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    candidates = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, ManagerBasedRLEnvCfg) and obj.__module__ == module_name
    ]
    if not candidates:
        raise ValueError(f"No ManagerBasedRLEnvCfg class found in snapshot: {path}")
    play_cfgs = [cls for cls in candidates if cls.__name__.endswith("PlayEnvCfg")]
    chosen = (play_cfgs or candidates)[0]

    cfg = chosen()
    if device is not None:
        cfg.sim.device = device
    if use_fabric is not None:
        cfg.sim.use_fabric = use_fabric
    if num_envs is not None:
        cfg.scene.num_envs = num_envs
    return cfg

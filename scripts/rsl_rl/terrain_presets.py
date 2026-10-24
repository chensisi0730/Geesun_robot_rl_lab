# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Shared evaluation terrain presets (评估地形预设) for the play / test scripts.

Single source of truth (单一事实来源) for the evaluation terrains used by
``scripts/rsl_rl/play.py`` (``--terrain``) and ``scripts/rsl_rl/test_walk_torque.py``
(``--terrain``).

Design rule: the sub-terrain (子地形) limits are read from the **task's own**
``terrain_generator.sub_terrains`` whenever that task defines them, so every robot is
evaluated on the limits it was trained with. As of 2026-10-14 the wheel-legged lingsi_d30w
uses the **same** stair riser range as GO2 - (0.05, 0.23) m - so the stairs test is a strict
ablation (消融对照): same terrain, same hyper-parameters, only the body differs. The D30W
wheel radius is 0.095 m, so the 0.23 m top riser is 1.21x its wheel diameter and the
expected outcome is a clearly lower stairs success rate than GO2. The GO2 reference values
below are only the fallback for tasks that do not define the sub-terrain at all.

Modes (模式):

- ``play``: no override, use the task's play environment (环境) terrain as configured.
- ``flat``: pure flat ground (平地), single difficulty level.
- ``random_rough`` / ``stairs``: isolate one terrain type (单一地形) on all difficulty rows.
- ``complex``: mixed rough terrain (混合复杂地形) - flat + random_rough + pyramid_stairs -
  on all difficulty rows, i.e. the worst-case walking test.
"""

from __future__ import annotations

import isaaclab.terrains as terrain_gen

# GO2 reference limits, used only when the task cfg does not define the sub-terrain.
GO2_NOISE_RANGE = (0.01, 0.06)
GO2_NOISE_STEP = 0.01
GO2_STAIR_HEIGHT_RANGE = (0.05, 0.23)
GO2_STAIR_STEP_WIDTH = 0.3
GO2_STAIR_PLATFORM_WIDTH = 3.0

TERRAIN_MODES = ("play", "flat", "random_rough", "stairs", "complex")

# Common grid geometry, identical to the training terrain grid.
_GRID_KWARGS = dict(
    size=(8.0, 8.0),
    border_width=20.0,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    difficulty_range=(0.0, 1.0),
    use_cache=False,
)


def task_sub_terrains(env_cfg) -> dict:
    """Return the task cfg's own sub-terrain (子地形) definitions, if any."""
    generator = getattr(env_cfg.scene.terrain, "terrain_generator", None)
    if generator is None or not generator.sub_terrains:
        return {}
    return dict(generator.sub_terrains)


def _rough_terrain(task_sub: dict, proportion: float, noise_range: tuple | None):
    """Random uniform height-field (随机粗糙) sub-terrain, limits taken from the task cfg."""
    source = task_sub.get("random_rough")
    if noise_range is None:
        noise_range = tuple(source.noise_range) if source is not None else GO2_NOISE_RANGE
    noise_step = source.noise_step if source is not None else GO2_NOISE_STEP
    return terrain_gen.HfRandomUniformTerrainCfg(
        proportion=proportion, noise_range=noise_range, noise_step=noise_step, border_width=0.25
    )


def _stairs_terrain(task_sub: dict, proportion: float, stair_height: tuple | None):
    """Pyramid stairs (金字塔楼梯) sub-terrain, limits taken from the task cfg."""
    source = task_sub.get("pyramid_stairs")
    if stair_height is None:
        stair_height = tuple(source.step_height_range) if source is not None else GO2_STAIR_HEIGHT_RANGE
    step_width = source.step_width if source is not None else GO2_STAIR_STEP_WIDTH
    platform_width = source.platform_width if source is not None else GO2_STAIR_PLATFORM_WIDTH
    return terrain_gen.MeshPyramidStairsTerrainCfg(
        proportion=proportion,
        step_height_range=stair_height,
        step_width=step_width,
        platform_width=platform_width,
        border_width=1.0,
        holes=False,
    )


def flat_terrain_cfg() -> terrain_gen.TerrainGeneratorCfg:
    """Pure flat terrain (纯平地): one terrain type, one difficulty level."""
    return terrain_gen.TerrainGeneratorCfg(
        size=(8.0, 8.0),
        border_width=20.0,
        num_rows=2,
        num_cols=1,
        horizontal_scale=0.1,
        vertical_scale=0.005,
        slope_threshold=0.75,
        difficulty_range=(0.0, 0.0),
        use_cache=False,
        sub_terrains={"flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0)},
    )


def isolated_terrain_cfg(mode: str, task_sub: dict, stair_height=None, noise_range=None):
    """One single terrain type on all difficulty rows (5 rows x 4 columns)."""
    if mode == "random_rough":
        terrain = _rough_terrain(task_sub, proportion=1.0, noise_range=noise_range)
    elif mode == "stairs":
        terrain = _stairs_terrain(task_sub, proportion=1.0, stair_height=stair_height)
    else:
        raise ValueError(f"Unsupported isolated terrain mode: {mode}")
    return terrain_gen.TerrainGeneratorCfg(
        num_rows=5,
        num_cols=4,
        curriculum=True,
        sub_terrains={mode: terrain},
        **_GRID_KWARGS,
    )


def complex_terrain_cfg(task_sub: dict, stair_height=None, noise_range=None):
    """Mixed rough terrain (混合复杂地形): flat + random_rough + pyramid_stairs, 5 rows x 12 columns.

    Proportions are auto-normalized by IsaacLab -> flat 20% / random_rough 40% / stairs 40%.
    """
    return terrain_gen.TerrainGeneratorCfg(
        num_rows=5,
        num_cols=12,
        curriculum=True,
        sub_terrains={
            "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.1),
            "random_rough": _rough_terrain(task_sub, proportion=0.2, noise_range=noise_range),
            "pyramid_stairs": _stairs_terrain(task_sub, proportion=0.2, stair_height=stair_height),
        },
        **_GRID_KWARGS,
    )



def apply_terrain(env_cfg, mode: str, stair_height=None, noise_range=None) -> str:
    """Override ``env_cfg.scene.terrain`` for the requested evaluation mode.

    Args:
        env_cfg: The parsed environment configuration (mutated in place).
        mode: One of :data:`TERRAIN_MODES`. ``play`` leaves the cfg untouched.
        stair_height: Optional explicit stair riser height range (m), overrides the task cfg.
        noise_range: Optional explicit random-rough noise range (m), overrides the task cfg.

    Returns:
        A human-readable description of the terrain that will be used.
    """
    if mode == "play":
        return "play (task play-config terrain, untouched)"
    if mode not in TERRAIN_MODES:
        raise ValueError(f"Unsupported terrain mode: {mode} (choose from {TERRAIN_MODES})")

    task_sub = task_sub_terrains(env_cfg)
    if mode == "flat":
        generator = flat_terrain_cfg()
    elif mode in {"random_rough", "stairs"}:
        generator = isolated_terrain_cfg(mode, task_sub, stair_height=stair_height, noise_range=noise_range)
    else:
        generator = complex_terrain_cfg(task_sub, stair_height=stair_height, noise_range=noise_range)

    env_cfg.scene.terrain.terrain_generator = generator
    # Spawn on a random difficulty row (easiest -> hardest) so the whole curriculum range is seen.
    env_cfg.scene.terrain.max_init_terrain_level = generator.num_rows - 1

    stairs = generator.sub_terrains.get("pyramid_stairs")
    rough = generator.sub_terrains.get("random_rough")
    detail = ", ".join(f"{name} x {cfg.proportion}" for name, cfg in generator.sub_terrains.items())
    if stairs is not None:
        detail += f", stair_riser={tuple(stairs.step_height_range)} m"
    if rough is not None:
        detail += f", noise={tuple(rough.noise_range)} m"
    return f"{mode} ({generator.num_rows}x{generator.num_cols} grid: {detail})"


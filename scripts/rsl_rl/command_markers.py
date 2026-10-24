# Copyright (c) 2022-2026, GESUN ROBOTICS. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

"""Hide/show the Isaac Lab command debug markers (green/blue velocity arrows).

背景 (2026-10-20): ``UniformVelocityCommand`` 在 ``debug_vis=True`` 时, 会在**每台**机器狗
基座上方 0.5 m 处画两支扁平箭头:
  * 绿色 = 目标速度 (goal velocity)
  * 蓝色 = 当前速度 (current velocity)
跟拍机离狗只有 ~0.6 m, 这两支箭头几乎贴着镜头, 直接把画面糊成绿蓝色花瓣, 狗完全看不见
—— 这就是录像里"一堆东西堆在出生点"的真凶 (之前误判为相机 gizmo)。

这些标记纯粹是可视化, 录像时隐藏即可, 不影响任何训练量。
"""

from __future__ import annotations

from typing import Any

# 命令项里可能存放 VisualizationMarkers 实例的属性名 (Isaac Lab 的命名习惯)
_MARKER_ATTRS = (
    "goal_vel_visualizer",
    "current_vel_visualizer",
    "visualization_markers",
    "goal_pose_visualizer",
)


def set_command_markers_visible(env: Any, visible: bool) -> int:
    """Show/hide every command-term visualization marker group.

    Args:
        env: Gym env (or wrapper). ``env.unwrapped.command_manager`` is used.
        visible: ``True`` shows the markers, ``False`` hides them.

    Returns:
        Number of marker groups that were toggled.
    """
    try:
        from isaaclab.markers import VisualizationMarkers

        cmd_mgr = getattr(getattr(env, "unwrapped", env), "command_manager", None)
        if cmd_mgr is None:
            return 0
        objects = []
        for name in cmd_mgr.active_terms:
            term = cmd_mgr.get_term(name)
            try:
                objects.extend(vars(term).values())
            except TypeError:  # term without __dict__
                pass
            for attr in _MARKER_ATTRS:
                obj = getattr(term, attr, None)
                if obj is not None:
                    objects.append(obj)
        seen: set[int] = set()
        groups = 0
        for obj in objects:
            if not isinstance(obj, VisualizationMarkers) or id(obj) in seen:
                continue
            seen.add(id(obj))
            obj.set_visibility(visible)
            groups += 1
        return groups
    except Exception as exc:  # visualization only, never fatal
        print(f"[WARN] command marker toggle failed: {exc}")
        return 0

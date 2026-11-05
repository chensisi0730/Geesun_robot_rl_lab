"""Local mirror for Omniverse cloud USD assets used by Isaac Lab.

Isaac Lab's :func:`check_usd_path_with_timeout` calls ``omni.client.stat_async()`` for any
``UsdFileCfg`` whose path is a remote URL. In pip-installed Isaac Sim 5.x that HTTP resolver
often cannot reach the AWS S3 asset host even though the URL is publicly reachable (plain
``curl`` returns 200). The check then blocks for up to 300 s and finally raises
``FileNotFoundError``.

Only the command-visualization arrows (``arrow_x.usd``) hit this path in this project; MDL
materials and HDR textures use separate loaders. This module caches that USD locally once and
rewrites the visualizer configs to point at the absolute local path, so ``os.path.isfile()``
short-circuits the remote check entirely. GUI visualization keeps working and training needs no
``debug_vis=False`` workaround.
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

_ASSET_BASE_URL = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac"
_REMOTE_ARROW = f"{_ASSET_BASE_URL}/Props/UIElements/arrow_x.usd"

_CACHE_DIR = Path(
    os.environ.get("UNITREE_ASSET_CACHE", str(Path.home() / ".cache" / "unitree_rl_lab" / "isaac_assets"))
)
_LOCAL_ARROW = _CACHE_DIR / "arrow_x.usd"


def local_arrow_usd(download_timeout: float = 30.0) -> str:
    """Return the absolute path to a locally cached ``arrow_x.usd``, downloading it if needed."""
    if _LOCAL_ARROW.is_file() and _LOCAL_ARROW.stat().st_size > 0:
        return str(_LOCAL_ARROW)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _LOCAL_ARROW.with_suffix(".usd.part")
    try:
        with urllib.request.urlopen(_REMOTE_ARROW, timeout=download_timeout) as response, tmp.open("wb") as out:
            out.write(response.read())
        tmp.replace(_LOCAL_ARROW)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"无法下载 Omniverse 资产 {_REMOTE_ARROW}；"
            f"可手动放置到 {_LOCAL_ARROW} 或设置 UNITREE_ASSET_CACHE。原因: {exc}"
        ) from exc
    return str(_LOCAL_ARROW)


def patch_command_visualizers(env_cfg, command_name: str = "base_velocity") -> int:
    """Replace cloud ``usd_path`` entries in a velocity command's visualizers with local ones.

    Args:
        env_cfg: Parsed environment configuration (mutated in place).
        command_name: Name of the command term, defaults to ``base_velocity``.

    Returns:
        Number of marker paths rewritten.
    """
    term = getattr(getattr(env_cfg, "commands", None), command_name, None)
    if term is None:
        return 0

    rewritten = 0
    for attr in ("goal_vel_visualizer_cfg", "current_vel_visualizer_cfg"):
        markers = getattr(getattr(term, attr, None), "markers", None)
        if not markers:
            continue
        for marker in markers.values():
            usd_path = getattr(marker, "usd_path", "")
            if isinstance(usd_path, str) and usd_path.startswith("http") and "arrow_x.usd" in usd_path:
                marker.usd_path = local_arrow_usd()
                rewritten += 1
    return rewritten

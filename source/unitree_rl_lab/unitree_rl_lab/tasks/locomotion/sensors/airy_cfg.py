"""RoboSense Airy LiDAR (96-beam) simulation spec for the GeesunDog wheel-legged platform.

HardWARE (from the PRO datasheet, confirmed by the user + the product drawing):

============  ==========================================================
``channels``  96 beams
``FOV``       horizontal 360 deg x vertical 90 deg (hemisphere)
``range``     30 m @ 10% reflectivity
``quantity``  2 units - one at the head, one at the tail (drawing labels
              "头部激光雷达" / "尾部激光雷达")
============  ==========================================================

Modelling choice (decided 2026-10-15): ray-casting via ``RayCasterCfg`` +
``LidarPatternCfg`` instead of a rendered sensor. Ray casting does not rasterise images, so
the 96-beam scan stays affordable at the 4096-env training scale this project runs, which a
rendered camera could not (it would force the run down to a few hundred envs). Isaac Lab has
no ``RsdCameraCfg`` in this version, so a physically-modelled depth camera is not an option
anyway.

Only ONE unit feeds the observation, and this is a measured constraint rather than a modelling
choice: the PRO datasheet lists 2 units, but one 360 deg sweep already covers fore and aft, so a
second instance would add no information while doubling VRAM. Measured at 4096 envs (RTX 5090,
32 GB): one unit at 0.8 deg azimuth already occupies 26.2 GB, and a second one would need another
~8-12 GB -> certain OOM. Add :data:`AIRY_TAIL_OFFSET` back only if a future ablation shows the
tail sweep carries information the head sweep cannot.

VERTICAL HEMISPHERE ORIENTATION IS THE ONE UNVERIFIED ASSUMPTION
-----------------------------------------------------------------
The datasheet states "vertical 90 deg (hemisphere)" without saying which half. We assume
**downward** (``AIRY_VERTICAL_FOV_RANGE = (-90.0, 0.0)``) because that is the only choice
that yields full ground coverage for a terrain-following policy. ``scripts/diagnose/
verify_airy_lidar.py`` renders a side view + a top view precisely to confirm or refute this
one assumption; if the side view shows sky instead of ground, flip this constant to
``(0.0, 90.0)`` and re-run - nothing else has to change.
"""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.sensors import MultiMeshRayCasterCfg
from isaaclab.sensors.ray_caster import patterns

# ---------------------------------------------------------------------------
# Datasheet values (single source of truth - the verify script asserts against these).
# ---------------------------------------------------------------------------
AIRY_CHANNELS: int = 96
"""Number of beams. Sets the vertical angular resolution: 90 deg / 96 ~= 0.94 deg per beam."""

AIRY_HORIZONTAL_FOV_RANGE: tuple[float, float] = (-180.0, 180.0)
"""Full 360 deg horizontal sweep, per datasheet."""

AIRY_VERTICAL_FOV_RANGE: tuple[float, float] = (-90.0, 0.0)
"""Vertical 90 deg hemisphere. ASSUMED DOWNWARD - flip to (0.0, 90.0) if verification says so."""

AIRY_MAX_DISTANCE: float = 30.0
"""Datasheet: 30 m @ 10% reflectivity. Also the RayCaster far clip."""

AIRY_MIN_DISTANCE: float = 0.2
"""Near clip. Below ~0.2 m returns are dominated by the mount/leg self-geometry."""

# Horizontal angular resolution. NOT a datasheet number: Airy is a digitally scanned sensor
# (no mechanical rotation), so its azimuthal point density is a design choice of the driver,
# not a published spec.
#
# MEASURED (2026-10-15, RTX 5090, 96 beams, see scripts/diagnose/verify_airy_lidar.py):
#   0.4 deg -> 86,400 rays/env;4096 envs needs a 3.96 GiB ray_hits tensor and then a second
#              3.96 GiB one in _update_ray_infos -> CUDA OOM on a 32 GB card.
#   0.8 deg -> 43,200 rays/env; 4096 envs fits in 26.2 / 32.6 GB and costs 0.44 ms/step.
# Cost is essentially IDENTICAL (0.39 vs 0.44 ms/step), i.e. this knob buys memory, not time:
# the 96 vertical beams dominate compute. Halving the azimuth density also leaves the polar BEV
# grid unchanged in accuracy - at 0.8 deg a 10 deg azimuth bin still samples 12.5 rays, and the
# grid takes the bin MAX, so a step edge (a surface, not a point) is still captured. Hit rate is
# unchanged too: 98.68% at both 0.4 and 0.8 deg.
AIRY_HORIZONTAL_RES: float = 0.8

# ---------------------------------------------------------------------------
# Mounting. Read off the product drawing: the two units sit at the head and tail ends of the
# trunk, on top. Frame is the robot base frame (z up, +x forward) per the URDF rewrite notes
# in assets/robots/unitree.py. These are ESTIMATES from the drawing proportions, not a
# calibration - they are deliberately covered by the randomisation ranges below.
# ---------------------------------------------------------------------------
AIRY_HEAD_OFFSET: tuple[float, float, float] = (0.25, 0.0, 0.10)
"""Head LiDAR, in base_link frame (x forward, y left, z up)."""

AIRY_TAIL_OFFSET: tuple[float, float, float] = (-0.25, 0.0, 0.10)
"""Tail LiDAR, in base_link frame."""


def _pattern() -> patterns.LidarPatternCfg:
    return patterns.LidarPatternCfg(
        channels=AIRY_CHANNELS,
        vertical_fov_range=AIRY_VERTICAL_FOV_RANGE,
        horizontal_fov_range=AIRY_HORIZONTAL_FOV_RANGE,
        horizontal_res=AIRY_HORIZONTAL_RES,
    )


def airy_ray_caster_cfg(
    prim_path: str,
    offset: tuple[float, float, float],
    mesh_prim_paths: list[str] | None = None,
    horizontal_res: float | None = None,
    channels: int | None = None,
) -> MultiMeshRayCasterCfg:
    """Build one Airy ray-caster sensor.

    Args:
        prim_path: USD prim the sensor is attached to, e.g.
            ``"{ENV_REGEX_NS}/Robot/base_link"``.
        offset: Mount position in the attached prim's frame. Use the mounting constants
            (:data:`AIRY_HEAD_OFFSET` / :data:`AIRY_TAIL_OFFSET`) for the nominal case, or a
            randomised offset for domain randomisation.
        mesh_prim_paths: Meshes the rays may hit. Defaults to the ground only. Pass several
            paths (e.g. terrain + the robot itself) to model self-occlusion - see the
            MultiMesh note below for why the plain ``RayCaster`` cannot do this.
        horizontal_res: Override the azimuthal step (domain randomisation).
        channels: Override the beam count (domain randomisation).

    Returns:
        A configured :class:`MultiMeshRayCasterCfg`.

    WHY MultiMeshRayCaster INSTEAD OF RayCaster
    -------------------------------------------
    ``RayCaster`` accepts ``len(mesh_prim_paths) == 1`` **and then reads only the first
    matching ``UsdGeomMesh`` under that path** (isaaclab/sensors/ray_caster/ray_caster.py,
    ``get_first_matching_child_prim``). Everything else below that path is silently dropped -
    measured directly: with the ground spawned first, 94% of all hits landed on the ground
    plane and nothing above z=0.10 m was detected, even though the props were rendered.
    That is fine for the existing ``height_scanner`` (the training terrain is one merged mesh)
    but useless for a LiDAR, which must also see obstacles and its own legs.
    ``MultiMeshRayCasterCfg`` subclasses ``RayCasterCfg`` - so it keeps ``pattern_cfg`` and
    therefore still accepts :class:`LidarPatternCfg` - while casting against every listed mesh.
    Its ``MultiMeshRayCasterData`` subclasses ``RayCasterData``, so ``data.ray_hits_w`` keeps
    the same ``(N, B, 3)`` layout; ``data.ray_mesh_ids`` additionally reports which mesh each
    hit came from.

    Note:
        ``offset`` defaults to (0, 0, 0) rather than the ``height_scanner`` convention of
        ``(0, 0, 20)``: a LiDAR emits from its housing, whereas a height scanner drops rays
        from a virtual plane above the robot.
    """
    pattern = _pattern()
    if horizontal_res is not None:
        pattern.horizontal_res = float(horizontal_res)
    if channels is not None:
        pattern.channels = int(channels)

    return MultiMeshRayCasterCfg(
        prim_path=prim_path,
        offset=MultiMeshRayCasterCfg.OffsetCfg(pos=offset),
        mesh_prim_paths=mesh_prim_paths if mesh_prim_paths is not None else ["/World/ground"],
        pattern_cfg=pattern,
        max_distance=AIRY_MAX_DISTANCE,
        # A LiDAR bolted to the trunk rigidly inherits the body pose, including roll/pitch on
        # stairs - that coupling is exactly what a wheeled robot needs to perceive, so keep
        # "base" (full pose) rather than "yaw".
        ray_alignment="base",
        debug_vis=False,
    )


# ---------------------------------------------------------------------------
# Domain randomisation ranges. The nominal values above are the datasheet centre; these widen
# the model around it so a single training run is robust to the calibration error and to the
# driver-level differences between the two physical units.
# ---------------------------------------------------------------------------
AIRY_RANDOMISATION: dict[str, tuple[float, float]] = {
    # extrinsic error (mounting tolerance / assembly variance)
    "offset_xy_m": (-0.03, 0.03),
    "offset_z_m": (-0.02, 0.02),
    "offset_roll_deg": (-2.0, 2.0),
    "offset_pitch_deg": (-2.0, 2.0),
    "offset_yaw_deg": (-2.0, 2.0),
    # intrinsic error
    "horizontal_res_deg": (0.6, 1.0),  # centred on AIRY_HORIZONTAL_RES = 0.8 (memory-bound knob)
    "channels": (88.0, 96.0),  # rounded to int at sampling time
    "range_scale": (0.85, 1.0),  # shorten the effective range; models reflectivity loss
    # point-level noise
    "dropout_rate": (0.0, 0.15),
    "range_noise_coeff": (0.0, 0.02),  # sigma = coeff * distance^2 (LiDAR-inherent)
    # temporal
    "latency_ms": (0.0, 50.0),
}


__all__ = [
    "AIRY_CHANNELS",
    "AIRY_HORIZONTAL_FOV_RANGE",
    "AIRY_VERTICAL_FOV_RANGE",
    "AIRY_MAX_DISTANCE",
    "AIRY_MIN_DISTANCE",
    "AIRY_HORIZONTAL_RES",
    "AIRY_HEAD_OFFSET",
    "AIRY_TAIL_OFFSET",
    "AIRY_RANDOMISATION",
    "airy_ray_caster_cfg",
]
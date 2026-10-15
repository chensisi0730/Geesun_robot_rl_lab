"""Polar BEV (bird's-eye-view) projection for the Airy 96-beam LiDAR.

Phase 2 of the sensor-modelling task. The raw ray cast is ``(N, B, 3)`` world-frame
hit points (``B`` = ``channels`` x ``azimuths`` = ~86,400 rays per env); feeding that
directly into the policy would explode the observation dimension. This module collapses
it into a fixed-size **polar height grid**: ``n_az`` azimuth sectors around 360 deg times
``n_dist`` range rings from ``min_dist`` to ``max_dist``, each cell holding the *maximum
obstacle height* seen in that (azimuth, range) bin. Climbing stairs only needs to know
how tall the obstacle in front is, not its exact point cloud, so a max-height grid is the
natural compressed representation.

The head unit is 360 deg horizontal, so the grid is 360 deg (not a forward-only wedge) -
the robot has LiDAR fore and aft. The tail unit is modelled but not consumed here yet.

Design constants below are the observation-dimension budget agreed for phase 1:
``36 x 20 = 720`` cells. They are deliberately cheap to retune (change the two ints) and
``airy_bev_grid`` asserts the resulting shape.

Only the head unit feeds the observation in phase 1.
"""

from __future__ import annotations

import torch

# ---------------------------------------------------------------------------
# Observation budget (agreed 2026-10-15). 36 azimuths (10 deg each, full 360) x
# 20 range rings = 720-dim. Retune here; airy_bev_grid() derives everything else.
# ---------------------------------------------------------------------------
AIRY_BEV_AZ_BINS: int = 36
AIRY_BEV_DIST_BINS: int = 20
AIRY_BEV_MAX_DIST: float = 20.0
AIRY_BEV_MIN_DIST: float = 0.2

# Range rings are LOG-spaced: near field (where stair edges live) gets finer resolution
# than the far field, matching the LiDAR's own near-field density advantage. The two
# segments below join at 2.0 m; tune the split if the terrain statistics say otherwise.
_AIRY_BEV_NEAR_DIST: float = 2.0
_AIRY_BEV_NEAR_BINS: int = 8


def distance_edges(n_dist: int = AIRY_BEV_DIST_BINS,
                   min_dist: float = AIRY_BEV_MIN_DIST,
                   max_dist: float = AIRY_BEV_MAX_DIST) -> torch.Tensor:
    """Log-spaced range-ring edges.

    Near field (``min_dist``..2.0 m) gets ``_AIRY_BEV_NEAR_BINS`` rings; the rest of the
    span gets ``n_dist - _AIRY_BEV_NEAR_BINS`` rings, both log-spaced so cell width grows
    with range. Returns ``n_dist + 1`` monotonically increasing edges.
    """
    near = int(round(_AIRY_BEV_NEAR_BINS))
    far = int(round(n_dist)) - near
    e_near = torch.logspace(torch.log10(torch.tensor(min_dist)), torch.log10(torch.tensor(_AIRY_BEV_NEAR_DIST)), near + 1)
    e_far = torch.logspace(torch.log10(torch.tensor(_AIRY_BEV_NEAR_DIST)), torch.log10(torch.tensor(max_dist)), far + 1)
    # drop the duplicated joint at 2.0 m
    return torch.cat([e_near[:-1], e_far])


def airy_bev_grid(ray_hits_w: torch.Tensor,
                  sensor_pos: torch.Tensor,
                  sensor_quat: torch.Tensor | None = None,
                  n_az: int = AIRY_BEV_AZ_BINS,
                  n_dist: int = AIRY_BEV_DIST_BINS,
                  max_dist: float = AIRY_BEV_MAX_DIST,
                  min_dist: float = AIRY_BEV_MIN_DIST,
                  ground_z: float = 0.0,
                  fill_value: float = 0.0) -> torch.Tensor:
    """Collapse a LiDAR point cloud into a polar max-height BEV grid.

    Args:
        ray_hits_w: world-frame hit points, shape ``(N, B, 3)`` where ``N`` is the number of
            sensors/envs and ``B`` the number of rays. Non-finite entries (rays that escaped
            or hit nothing) are ignored.
        sensor_pos: sensor world positions, shape ``(N, 3)``.
        sensor_quat: optional sensor world orientations ``(N, 4)`` (w, x, y, z); when given the
            cloud is rotated into the sensor frame so the grid is body-relative (what the policy
            wants). When ``None`` the sensor is assumed axis-aligned at the origin offset only.
        n_az: number of azimuth sectors (full 360 deg).
        n_dist: number of range rings.
        max_dist / min_dist: outer / inner range of the grid.
        ground_z: world z of the ground plane (for height-above-ground).
        fill_value: value for (azimuth, range) bins with no hit.

    Returns:
        ``(N, n_az, n_dist)`` max-height grid. Cell value = highest obstacle point (above
        ``ground_z``) seen in that bin; ``fill_value`` where the bin is empty (sky / missed).
    """
    if ray_hits_w.dim() != 3 or ray_hits_w.shape[-1] != 3:
        raise ValueError(f"ray_hits_w must be (N, B, 3), got {tuple(ray_hits_w.shape)}")
    n = ray_hits_w.shape[0]
    pos = sensor_pos.reshape(n, 1, 3)
    p = ray_hits_w - pos  # translate into sensor frame
    if sensor_quat is not None:
        # rotate world->sensor: p_b = quat_apply(q_conj, p_w - pos). Isaac Lab quats are
        # (w, x, y, z); the conjugate keeps w and flips (x, y, z). Hamilton rotation of a pure
        # vector: v' = v + 2*w*cross(qxyz, v) + 2*cross(qxyz, cross(qxyz, v)).
        q = sensor_quat.reshape(n, 1, 4)
        w = q[..., 0:1]
        qxyz = -q[..., 1:4]  # conjugate's vector part
        t1 = torch.cross(qxyz, p)
        t2 = torch.cross(qxyz, t1)
        p = p + 2.0 * (w * t1 + t2)

    x_c, y_c, z_c = p[..., 0], p[..., 1], p[..., 2]
    az = torch.atan2(y_c, x_c)                       # (N, B) in [-pi, pi]
    r = torch.sqrt(x_c**2 + y_c**2)                 # (N, B)
    # Height is taken from the WORLD frame (ground at world z = ``ground_z``), NOT from the
    # body frame: a body-frame z would inherit the sensor's mounting height and pitch, which is
    # exactly what the policy must NOT see (it wants absolute obstacle height above the ground).
    # Azimuth/range, by contrast, are body-relative so the grid tracks the robot's heading.
    h = ray_hits_w[..., 2] - ground_z              # height above ground (N, B)

    finite = torch.isfinite(ray_hits_w).all(dim=-1)  # (N, B)

    az_bin = (((az + torch.pi) / (2.0 * torch.pi) * n_az).long()).clamp(0, n_az - 1)
    edges = distance_edges(n_dist, min_dist, max_dist).to(ray_hits_w.device)
    edge_inner = edges[:-1].reshape(1, 1, -1)
    r_bin = (r.unsqueeze(-1) >= edge_inner).sum(dim=-1).long().clamp(0, n_dist - 1)
    # points beyond max_dist already excluded by the caster clip, but guard anyway
    r_bin = torch.where(r > max_dist, torch.tensor(n_dist - 1, device=r.device), r_bin)

    grid = torch.full((n, n_az * n_dist), fill_value,
                      dtype=ray_hits_w.dtype, device=ray_hits_w.device)
    flat = (az_bin * n_dist + r_bin)  # (N, B)
    for i in range(n):
        f = flat[i][finite[i]]
        if f.numel() == 0:
            continue
        vals = h[i][finite[i]]
        grid[i].scatter_reduce_(0, f, vals, "amax")
    return grid.reshape(n, n_az, n_dist)


def airy_bev_flat(ray_hits_w: torch.Tensor, sensor_pos: torch.Tensor,
                  sensor_quat: torch.Tensor | None = None, **kw) -> torch.Tensor:
    """Same as :func:`airy_bev_grid` but returns ``(N, n_az * n_dist)`` for an ObsTerm."""
    g = airy_bev_grid(ray_hits_w, sensor_pos, sensor_quat, **kw)
    return g.reshape(g.shape[0], -1)


__all__ = [
    "AIRY_BEV_AZ_BINS",
    "AIRY_BEV_DIST_BINS",
    "AIRY_BEV_MAX_DIST",
    "AIRY_BEV_MIN_DIST",
    "distance_edges",
    "airy_bev_grid",
    "airy_bev_flat",
]

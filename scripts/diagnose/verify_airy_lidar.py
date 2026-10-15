"""Verify the simulated RoboSense Airy 96-beam LiDAR against its datasheet.

Phase 1 of the sensor-modelling task. Deliberately does NOT touch any task cfg, does NOT
wire an observation, and does NOT need the robot: it only proves that the ray-cast sensor
built by :mod:`unitree_rl_lab.tasks.locomotion.sensors.airy_cfg` behaves like the datasheet
says. Everything downstream depends on this passing.

WHY THIS SCRIPT EXISTS
----------------------
The datasheet states "vertical 90 deg (hemisphere)" but never says which half. That single
ambiguity decides whether the BEV (bird's-eye-view) observation can see the ground at all,
so the script decides it empirically instead of by assumption.

DECISION RULE (derived from the hemisphere direction):
- rays land on the ground **out to the far clip** -> 90 deg hemisphere points DOWN (nominal)
- **zero hits** (all rays escape) -> hemisphere points UP; flip ``AIRY_VERTICAL_FOV_RANGE``
- hits collapse to a **small ring** near the sensor -> hemisphere is split (e.g. -45..+45)

Usage::

    conda run -n env_isaaclab_sim51 python scripts/diagnose/verify_airy_lidar.py
    # optional overrides
    conda run -n env_isaaclab_sim51 python scripts/diagnose/verify_airy_lidar.py \
        --vertical_fov -45 45 --horizontal_res 0.4 --envs 64
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "rsl_rl"))

parser = argparse.ArgumentParser(description="Verify the simulated Airy 96-beam LiDAR")
parser.add_argument("--sensor_height", type=float, default=0.50, help="LiDAR mount height above the ground (m)")
parser.add_argument("--horizontal_res", type=float, default=None, help="Override azimuthal step (deg)")
parser.add_argument("--vertical_fov", type=float, nargs=2, default=None, metavar=("MIN", "MAX"),
                    help="Override the vertical FOV range to test a different hemisphere assumption")
parser.add_argument("--out", type=str, default=str(REPO / "outputs" / "verify_airy"))
parser.add_argument("--envs", type=int, default=1,
                    help="Number of simulated sensors (envs). >1 turns on the throughput probe.")

# NOTE: do not call parse_args() here - AppLauncher contributes its own flags (--headless,
# --device, ...) further down and a first parse would reject them.
from isaaclab.app import AppLauncher  # noqa: E402

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch  # noqa: E402

import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.sensors.ray_caster import MultiMeshRayCaster  # noqa: E402

from unitree_rl_lab.tasks.locomotion.sensors import airy_cfg as airy  # noqa: E402

OUT = Path(args_cli.out)
OUT.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# Ground truth geometry. Each box has a known size so the numeric check can compare the
# measured hit distances/heights against the exact expected values.
# --------------------------------------------------------------------------------------
SENSOR_HEIGHT = args_cli.sensor_height
STEP_HEIGHT, STEP_WIDTH = 0.15, 2.0     # a step the robot is known to be able to climb
LOW_BOX_H, HIGH_BOX_H, BOX_W = 0.30, 0.90, 1.0
# LOW_BOX_H is BELOW the sensor and HIGH_BOX_H is ABOVE it: with a downward hemisphere the
# former's top face must be visible and the latter's must NOT be. That pair is a much sharper
# test of the vertical FOV than a single box, and it is the direct empirical proof that the
# hemisphere really points down (a split FOV would see both, an upward one would see neither).
WALL_DIST = 6.0                         # wall range: checks the far end of the range spec


def _spawn(cfg, prim_path: str, translation: tuple[float, float, float] | None = None):
    """Isaac Lab 2.x spawner API: call ``SpawnerCfg.func(prim_path, cfg, translation)``.

    There is no ``SimulationContext.spawn`` / ``SpawnerCfg.spawn`` helper in this version,
    and ``GroundPlaneCfg`` has no ``.spawn()`` method, so every asset goes through ``func``.
    """
    return cfg.func(prim_path, cfg, translation)


def build_scene(sim, n_envs: int = 1):
    """Spawn the ground and the three known-geometry props, then the sensor mount prims.

    NOTE - geometry must be *mesh* based. ``CuboidCfg`` creates a ``UsdGeomCube`` primitive,
    but RayCaster ray-casts against Warp meshes which are triangulated from ``UsdGeomMesh``
    only. A ``CuboidCfg`` prop therefore renders yet is completely invisible to the sensor
    (measured: 94% of hits landed on the ground plane and nothing above z=0.10 m).
    ``MeshCuboidCfg`` creates a real ``UsdGeomMesh`` and is picked up correctly. Production is
    unaffected because the training terrain comes from ``TerrainImporter``, which emits meshes.
    """
    _spawn(
        sim_utils.GroundPlaneCfg(size=(120.0, 120.0),
                                 physics_material=sim_utils.RigidBodyMaterialCfg(
                                     static_friction=1.0, dynamic_friction=1.0, restitution=0.0)),
        "/World/Ground",
    )
    # a raised step 3 m ahead (+x), its top face is exactly STEP_HEIGHT above the ground
    _spawn(sim_utils.MeshCuboidCfg(size=(2.0, STEP_WIDTH, STEP_HEIGHT),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/Step", (3.0, 0.0, STEP_HEIGHT / 2.0))
    # a box 5 m ahead whose top face (LOW_BOX_H) sits BELOW the sensor -> must be seen
    _spawn(sim_utils.MeshCuboidCfg(size=(BOX_W, BOX_W, LOW_BOX_H),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/BoxLow", (5.0, 0.0, LOW_BOX_H / 2.0))
    # a taller box 5 m to the side, top face (HIGH_BOX_H) ABOVE the sensor -> must NOT be seen
    _spawn(sim_utils.MeshCuboidCfg(size=(BOX_W, BOX_W, HIGH_BOX_H),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/BoxHigh", (0.0, 5.0, HIGH_BOX_H / 2.0))
    # a wall 6 m ahead so there is always a hit for near-horizontal rays
    _spawn(sim_utils.MeshCuboidCfg(size=(0.2, 20.0, 2.0),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/Wall", (WALL_DIST, 0.0, 1.0))
    # invisible stand-in for the robot base_link: the sensor only needs a transformed prim.
    # One per "environment" so the throughput probe can measure the real per-env ray cost.
    # The env index MUST sit in a middle path segment: RayCaster rejects a regex in the leaf
    # name (isaaclab/sensors/ray_caster/ray_caster.py __init__), hence /World/Env/env_i/Mount
    # rather than /World/Mount_i.
    for i in range(n_envs):
        _spawn(sim_utils.MeshCuboidCfg(size=(0.05, 0.05, 0.05), visible=False),
               f"/World/Env/env_{i}/Mount", (0.0, 0.0, SENSOR_HEIGHT))


def write_ply(path: Path, hits: torch.Tensor, finite: torch.Tensor):
    """ASCII PLY so the cloud can be opened in any external viewer."""
    pts = hits[finite].detach().cpu().numpy()
    if pts.size == 0:
        path.write_text("ply\nformat ascii 1.0\nelement vertex 0\n"
                        "property float x\nproperty float y\nproperty float z\nend_header\n")
        return
    body = "".join(f"{x:.4f} {y:.4f} {z:.4f}\n" for x, y, z in pts)
    path.write_text(
        "ply\nformat ascii 1.0\n"
        f"element vertex {pts.shape[0]}\n"
        "property float x\nproperty float y\nproperty float z\nend_header\n" + body
    )


def main():
    from isaaclab.sim import SimulationContext

    sim_cfg = sim_utils.SimulationCfg(dt=0.005)
    sim = SimulationContext(sim_cfg)
    sim.set_camera_view(eye=[14.0, 0.0, 9.0], target=[1.0, 0.0, 0.2])
    build_scene(sim, n_envs=args_cli.envs)

    # ---- build the sensor exactly the way a task cfg would -------------------------
    if args_cli.vertical_fov is not None:
        airy.AIRY_VERTICAL_FOV_RANGE = (float(args_cli.vertical_fov[0]), float(args_cli.vertical_fov[1]))
    cfg = airy.airy_ray_caster_cfg(
        # regex in a MIDDLE segment (the leaf must stay literal) -> one sensor instance fans
        # out over all env mounts, exactly like InteractiveScene does for the height_scanner
        prim_path="/World/Env/env_.*/Mount",
        offset=(0.0, 0.0, 0.0),
        # every prop listed explicitly: plain RayCaster would only ever read the first matching
        # mesh under the path, which is the ground, and silently drop the rest
        mesh_prim_paths=["/World/Ground", "/World/Step", "/World/BoxLow", "/World/BoxHigh", "/World/Wall"],
        horizontal_res=args_cli.horizontal_res,
    )
    azimuths = int(
        (cfg.pattern_cfg.horizontal_fov_range[1] - cfg.pattern_cfg.horizontal_fov_range[0])
        / cfg.pattern_cfg.horizontal_res
    )
    num_rays = cfg.pattern_cfg.channels * azimuths
    print(f"[INFO] Airy cfg: channels={cfg.pattern_cfg.channels} "
          f"vertical_fov={cfg.pattern_cfg.vertical_fov_range} "
          f"horizontal_fov={cfg.pattern_cfg.horizontal_fov_range} "
          f"horizontal_res={cfg.pattern_cfg.horizontal_res} deg")
    print(f"[INFO] derived rays per environment: {num_rays} ({cfg.pattern_cfg.channels} beams x {azimuths} azimuths)")

    ray_caster = MultiMeshRayCaster(cfg)
    # Isaac Lab initialises a manually constructed sensor through the USD stage callback that
    # `SimulationContext.reset()` fires - calling `ray_caster.reset()` beforehand raises
    # because `_timestamp` does not exist yet (same order as test/sensors/check_ray_caster.py).
    sim.reset()
    print(ray_caster)
    for _ in range(3):
        sim.step()

    # ---- throughput probe: is the full scan affordable at the training env count? -------
    n_inst = ray_caster.num_instances
    print(f"[PERF] sensor instances (envs): {n_inst}, rays per env: {num_rays}, "
          f"total rays: {n_inst * num_rays}")
    for _ in range(5):                      # warm up: JIT / mesh upload / allocator
        sim.step()
    t_start = time.perf_counter()
    n_bench = 20
    for _ in range(n_bench):
        sim.step()
    dt_per_step = (time.perf_counter() - t_start) / n_bench
    rays_per_s = n_inst * num_rays / dt_per_step
    print(f"[PERF] {dt_per_step * 1000:.2f} ms / sim step at {n_inst} envs "
          f"-> {rays_per_s / 1e6:.2f} M rays/s")
    print(f"[PERF] control budget at 50 Hz is 20.00 ms/step; the sensor alone uses "
          f"{100.0 * dt_per_step / 0.020:.1f}% of it at {n_inst} envs")
    perf = {
        "envs": int(n_inst),
        "rays_per_env": int(num_rays),
        "ms_per_sim_step": round(dt_per_step * 1000, 3),
        "mrays_per_s": round(rays_per_s / 1e6, 2),
        "control_budget_ms": 20.0,
        "sensor_fraction_of_budget": round(100.0 * dt_per_step / 0.020, 1),
    }

    hits = ray_caster.data.ray_hits_w[0].clone()          # (num_rays, 3) world-frame hits
    finite = torch.isfinite(hits).all(dim=-1)
    n_hit = int(finite.sum())
    stats = {
        "num_rays": int(hits.shape[0]),
        "sensor_height_m": SENSOR_HEIGHT,
        "vertical_fov_deg": list(cfg.pattern_cfg.vertical_fov_range),
        "hits": n_hit,
        "hit_rate": round(float(finite.float().mean()), 4),
    }
    print(f"[INFO] rays={hits.shape[0]}  hits={n_hit}  miss={int((~finite).sum())}")

    if n_hit == 0:
        stats.update({"verdict": "UP",
                      "detail": "every ray escaped -> the hemisphere does NOT cover the ground; "
                                "flip AIRY_VERTICAL_FOV_RANGE to (0.0, 90.0)"})
        print(f"[VERDICT] {stats['verdict']}: {stats['detail']}")
    else:
        p = hits[finite]
        radius = torch.linalg.norm(p[:, :2], dim=-1)
        hit_z = p[:, 2]
        radius_max = float(radius.max())
        stats.update({
            "radius_min_m": round(float(radius.min()), 3),
            "radius_max_m": round(radius_max, 3),
            "radius_median_m": round(float(radius.median()), 3),
            "z_min_m": round(float(hit_z.min()), 3),
            "z_max_m": round(float(hit_z.max()), 3),
        })
        # geometric truth checks against the exact box dimensions
        stats["geometry_checks"] = {
            "sees_step_top(0.15m)": bool((hit_z > STEP_HEIGHT - 0.02).any()),
            f"sees_low_box_top({LOW_BOX_H}m, below sensor)": bool((hit_z > LOW_BOX_H - 0.02).any()),
            f"blind_to_high_box_top({HIGH_BOX_H}m, above sensor)": not bool(
                (hit_z > HIGH_BOX_H - 0.02).any()),
            "far_clip_respected(<=30m)": bool(radius_max <= airy.AIRY_MAX_DISTANCE + 0.05),
        }
        stats["geometry_checks_passed"] = all(stats["geometry_checks"].values())
        if radius_max > 0.5 * airy.AIRY_MAX_DISTANCE:
            stats["verdict"] = "DOWN"
            stats["detail"] = (f"ground covered out to {radius_max} m -> the 90 deg hemisphere "
                               "points DOWN (nominal assumption holds)")
        else:
            stats["verdict"] = "SPLIT"
            stats["detail"] = (f"ground only covered to {radius_max} m -> the hemisphere is split "
                               "(e.g. -45..+45), not a single 90 deg half")
        print(f"[VERDICT] {stats['verdict']}: {stats['detail']}")
        print(f"[CHECKS] {json.dumps(stats['geometry_checks'], ensure_ascii=False)}")
        # where did the hits actually land? Distinguishes "only the ground was visible" from
        # "the props were visible but too tall / too far to register in z".
        zs = hit_z
        edges = [0.0, 0.02, 0.10, 0.14, 0.16, 0.30, 0.49, 0.51, 10.0]
        counts = [int(((zs >= edges[i]) & (zs < edges[i + 1])).sum()) for i in range(len(edges) - 1)]
        stats["z_histogram_edges"] = edges
        stats["z_histogram_counts"] = counts
        print("[DIAG] z histogram: " + ", ".join(
            f"[{edges[i]:.2f},{edges[i + 1]:.2f})={counts[i]}" for i in range(len(counts))))
        r_counts = [int(((radius >= airy.AIRY_MAX_DISTANCE * i / 10) &
                         (radius < airy.AIRY_MAX_DISTANCE * (i + 1) / 10)).sum()) for i in range(10)]
        stats["radius_histogram_counts_0_to_30m"] = r_counts
        print("[DIAG] radius histogram (0..30 m, 10 bins): " + str(r_counts))
        on_ground = int(((zs < 0.02) & (zs > -0.02)).sum())
        stats["hits_on_ground_plane"] = on_ground
        print(f"[DIAG] hits lying on the z=0 plane: {on_ground}/{n_hit} "
              f"({100.0 * on_ground / max(1, n_hit):.1f}%)")

    stats["throughput"] = perf

    write_ply(OUT / "points_head.ply", hits, finite)
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"[INFO] wrote {OUT / 'stats.json'} and {OUT / 'points_head.ply'}")


if __name__ == "__main__":
    main()
    simulation_app.close()
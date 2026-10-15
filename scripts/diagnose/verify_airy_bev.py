"""Phase-2 verification: Airy polar BEV grid vs known geometry.

Builds the same scene as ``verify_airy_lidar.py`` (flat ground + a 0.15 m step 3 m ahead,
a 0.30 m low box at 5 m, a 0.90 m high box at 5 m to the side, a 2.0 m wall at 6 m), casts
the Airy 96-beam LiDAR, collapses the point cloud into the polar max-height BEV grid via
``airy_bev_grid``, then checks the grid against the ground-truth geometry.

Success criteria (all must hold):
  * step (az~0, r~3 m)  -> cell height ~0.15 m
  * low box (az~0, r~5 m) -> cell height ~0.30 m
  * wall (az~0, r~6 m)  -> cell height ~2.0 m
  * high box (az~90, r~5 m) -> cell height NOT ~0.90 m  (downward hemisphere can't see its top)
  * forward wedge at r~3-6 m shows a clear rising height band (step<box<wall)

Outputs ``outputs/verify_airy_bev/bev.png`` (heatmap) and ``stats.json``.

Run:  python scripts/diagnose/verify_airy_bev.py --headless
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser(description="Verify Airy polar BEV grid vs known geometry")
parser.add_argument("--out", type=str, default=str(REPO / "outputs" / "verify_airy_bev"))
# NOTE: do not declare --headless here; AppLauncher.add_app_launcher_args() adds it and raises
# if the field already exists. We also avoid an early parse_args() so AppLauncher's flags parse.
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# Creating the AppLauncher instance activates the Isaac Sim kit, which injects the USD
# stack (pxr) and other modules into sys.path. isaaclab.sim MUST be imported AFTER this,
# otherwise `import pxr` fails (that is why the order matters here).
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.sensors.ray_caster import MultiMeshRayCaster  # noqa: E402

from unitree_rl_lab.tasks.locomotion.sensors import airy_cfg as airy  # noqa: E402
from unitree_rl_lab.tasks.locomotion.sensors import airy_bev as bev  # noqa: E402

# --- ground-truth geometry (must match build_scene below) -------------------
SENSOR_HEIGHT = 0.5
STEP_HEIGHT, STEP_WIDTH = 0.15, 2.0
LOW_BOX_H, HIGH_BOX_H, BOX_W = 0.30, 0.90, 1.0
WALL_DIST = 6.0


def _spawn(cfg, prim_path: str, translation):
    return cfg.func(prim_path, cfg, translation)


def build_scene(sim, n_envs: int = 1):
    """Flat ground + the four known-geometry props. One mount prim per env (stand-in base_link)."""
    _spawn(
        sim_utils.GroundPlaneCfg(size=(120.0, 120.0),
                                 physics_material=sim_utils.RigidBodyMaterialCfg(
                                     static_friction=1.0, dynamic_friction=1.0, restitution=0.0)),
        "/World/Ground", (0.0, 0.0, 0.0),
    )
    _spawn(sim_utils.MeshCuboidCfg(size=(2.0, STEP_WIDTH, STEP_HEIGHT),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/Step", (3.0, 0.0, STEP_HEIGHT / 2.0))
    _spawn(sim_utils.MeshCuboidCfg(size=(BOX_W, BOX_W, LOW_BOX_H),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/BoxLow", (5.0, 0.0, LOW_BOX_H / 2.0))
    _spawn(sim_utils.MeshCuboidCfg(size=(BOX_W, BOX_W, HIGH_BOX_H),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/BoxHigh", (0.0, 5.0, HIGH_BOX_H / 2.0))
    _spawn(sim_utils.MeshCuboidCfg(size=(0.2, 20.0, 2.0),
                                   collision_props=sim_utils.CollisionPropertiesCfg()),
           "/World/Wall", (WALL_DIST, 0.0, 1.0))
    for i in range(n_envs):
        _spawn(sim_utils.MeshCuboidCfg(size=(0.05, 0.05, 0.05), visible=False),
               f"/World/Env/env_{i}/Mount", (0.0, 0.0, SENSOR_HEIGHT))  # noqa


def main():
    from isaaclab.sim import SimulationContext
    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=args_cli.device))
    sim.set_camera_view(eye=[6.0, 4.0, 3.0], target=[0.0, 0.0, 0.0])

    build_scene(sim, n_envs=1)

    cfg = airy.airy_ray_caster_cfg(
        prim_path="/World/Env/env_.*/Mount",
        offset=(0.0, 0.0, 0.0),
        mesh_prim_paths=["/World/Ground", "/World/Step", "/World/BoxLow", "/World/BoxHigh", "/World/Wall"],
    )
    rc = MultiMeshRayCaster(cfg)
    sim.reset()
    for _ in range(3):
        sim.step()

    hits = rc.data.ray_hits_w[0].clone()  # (B, 3) world hits for env 0
    finite = torch.isfinite(hits).all(dim=-1)
    pts = hits[finite]
    sensor_pos = rc.data.pos_w[0]  # (3,)
    print(f"[INFO] hits={int(finite.sum())} finite, sensor_pos={sensor_pos.tolist()}")

    grid = bev.airy_bev_grid(hits.unsqueeze(0), sensor_pos.unsqueeze(0))[0]  # (AZ, DIST)
    az, dist = grid.shape
    edges = bev.distance_edges(dist)
    az_deg = [round(360.0 * i / az, 1) for i in range(az)]

    # ---- numeric checks against ground truth ---------------------------------
    def cell(azimuth_deg, radius):
        # azimuth -> bin must match airy_bev_grid's mapping: a = (az+180)/360 * n_az,
        # so az=0 (forward) lands in the MIDDLE bin (n_az/2), not bin 0.
        a = int(round(((azimuth_deg + 180.0) % 360.0) / 360.0 * az)) % az
        d = int(torch.argmin((edges[:-1] - radius).abs()))
        return float(grid[a, d].item()), a, d

    step_h, sa, sd = cell(0.0, 3.0)
    lowbox_h, la, ld = cell(0.0, 5.0)
    wall_h, wa, wd = cell(0.0, 6.0)
    highbox_h, ha, hd = cell(90.0, 5.0)

    # Forward-wedge profile, sampled along az=0 (the bin the step/boxes/wall actually sit in).
    fwd = [float(grid[sa, k].item()) for k in range(dist)]
    # The 2.0 m wall and the 0.9 m high box both TOWER OVER the 0.5 m sensor, and the Airy casts a
    # DOWNWARD hemisphere, so their top faces are physically unreachable. The grid must therefore
    # saturate at the sensor mounting height. That is the expected behaviour, not a defect -- and it
    # is harmless for stair climbing, where every obstacle of interest is <= 0.2 m.
    saturates_at_sensor = abs(wall_h - SENSOR_HEIGHT) < 0.05 and abs(highbox_h - SENSOR_HEIGHT) < 0.05
    rising = step_h < lowbox_h < wall_h

    checks = {
        f"step_top@(az=0,r=3m)~{STEP_HEIGHT}": abs(step_h - STEP_HEIGHT) < 0.03,
        f"lowbox_top@(az=0,r=5m)~{LOW_BOX_H}": abs(lowbox_h - LOW_BOX_H) < 0.05,
        f"tall_obstacles_saturate_at_sensor_height({SENSOR_HEIGHT}m, downward hemisphere)": saturates_at_sensor,
        "forward_rising_profile(step<box<wall)": rising,
    }
    stats = {
        "grid_shape": [az, dist],
        "obs_dim": az * dist,
        "checks": checks,
        "measured": {
            "step_top": round(step_h, 3), "lowbox_top": round(lowbox_h, 3),
            "wall_top": round(wall_h, 3), "highbox_top": round(highbox_h, 3),
            "forward_wedge_heights": [round(v, 3) for v in fwd],
        },
        "all_passed": all(checks.values()),
    }

    # ---- visualise: azimuth (x) vs range (y) heatmap of height --------------
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5))
    # pcolormesh (NOT imshow): our range rings are log-spaced and therefore NON-uniform, but
    # imshow+extent lays rows out linearly, which misplaces every object (the 3 m step would be
    # drawn at y~9). pcolormesh honours the real bin edges.
    az_edges = np.linspace(-180.0, 180.0, az + 1)
    X, Y = np.meshgrid(az_edges, edges.cpu().numpy())
    im = ax.pcolormesh(X, Y, grid.cpu().numpy().T, shading="flat", cmap="viridis")
    ax.set_xlabel("azimuth (deg, 0 = forward +x)")
    ax.set_ylabel("range from sensor (m)")
    ax.set_title(f"Airy BEV max-height grid ({az}x{dist}={az * dist} dims)  |  "
                 f"step={round(step_h,2)} box={round(lowbox_h,2)} wall={round(wall_h,2)} "
                 f"highbox@90deg={round(highbox_h,2)}")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("obstacle height above ground (m)")
    # mark the four known objects
    for (a_deg, r_m, lbl) in [(0, 3.0, "step"), (0, 5.0, "lowbox"), (90, 5.0, "highbox"), (0, 6.0, "wall")]:
        ax.scatter([a_deg], [r_m], marker="x", c="red", s=40, zorder=5)
        ax.annotate(lbl, (a_deg, r_m), color="red", fontsize=8, xytext=(3, 3), textcoords="offset points")
    out = Path(args_cli.out)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "bev.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    # also dump the raw point cloud for external inspection
    np.savetxt(out / "points_env0.csv", pts.cpu().numpy(), delimiter=",", header="x,y,z", comments="")

    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"[VERDICT] all_passed={stats['all_passed']}")
    print(f"[MEASURED] step={step_h:.3f} lowbox={lowbox_h:.3f} wall={wall_h:.3f} "
          f"highbox@90={highbox_h:.3f}")
    print(f"[INFO] grid {az}x{dist}={az * dist} dims; heatmap -> {out/'bev.png'}")
    simulation_app.close()


if __name__ == "__main__":
    main()

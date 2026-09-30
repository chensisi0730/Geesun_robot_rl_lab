"""This script imports the Geesun dog (dog1) URDF into Isaac Sim and animates all 12 joints.

The robot is spawned from ``geesun_dog_urdf/geesun-dog/dog1`` (updated ``dog921.urdf`` with
real meshes and joint limits; legacy ``dog1.urdf`` as fallback) with a standing pose, then
each joint follows its own sinusoid so the dog walks in place
in a trot-like gait (diagonal legs in phase).

.. code-block:: bash

    # Usage (inside conda env with Isaac Lab installed)
    python scripts/geesun_dog/move_geesun_dog.py --num_steps 1500
"""

"""Launch Isaac Sim Simulator first."""

import argparse
import math
import os

import torch

from isaaclab.app import AppLauncher

# add argparse arguments
parser = argparse.ArgumentParser(description="Move all joints of the Geesun dog (dog1).")
parser.add_argument(
    "--variant",
    type=str,
    default="dog1",
    help="Geesun asset variant directory under geesun_dog_urdf/geesun-dog/ (dog1, lingsi_d30w, ...)",
)
parser.add_argument("--num_steps", type=int, default=2000, help="Number of physics steps to run (0 = forever)")
parser.add_argument(
    "--gait_freq", type=float, default=1.5, help="Gait frequency in Hz for the sinusoidal joint motion"
)
parser.add_argument("--amp_deg", type=float, default=25.0, help="Joint oscillation amplitude in degrees")
parser.add_argument("--root_z", type=float, default=1.0, help="Initial root height (m); 0.17 puts the feet on the ground (measured stance height 0.166 m); the default 1.0 is for the pinned air-trot demo")
parser.add_argument("--no_pin_root", action="store_true", help="Do not re-write the root state every step (let gravity/dynamics act)")
parser.add_argument("--rear_thigh", type=float, default=1.0, help="Standing-pose base angle for rear thigh joints (rad); 1.0 = mirrored stance matching GEESUN_DOG_CFG, -1.0 = legacy sitting stance (ablation)")
parser.add_argument("--calf_base", type=float, default=-1.4, help="Standing-pose base angle for all calf joints (rad); more negative flattens the foot plate under the knee")
parser.add_argument("--settle_steps", type=int, default=100, help="In --no_pin_root mode: hold the root at --root_z for this many steps (lets the PD settle into the stance) before releasing it")
parser.add_argument("--no_self_collision", action="store_true", help="Disable articulation self-collisions (the degenerate dog921 meshes can pinch the legs)")
parser.add_argument("--stiffness", type=float, default=0.0, help="Override the actuator PD stiffness (0 = keep the cfg value)")
parser.add_argument("--damping", type=float, default=0.0, help="Override the actuator PD damping (0 = keep the cfg value)")
parser.add_argument("--wheel_speed", type=float, default=10.0, help="Rotation speed (rad/s) for wheel joints (names containing 'wheel', e.g. the lingsi_d30w wheel-legged variant); 0 holds them fixed")
parser.add_argument("--print_contact", action="store_true", help="Print per-body net contact force z every 100 steps")


# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli = parser.parse_args()

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.sim import SimulationContext
from isaaclab.utils import configclass

# select the asset variant before importing the robot module (it reads GEESUN_DOG_VARIANT
# at import time to pick the source URDF dir and the temp URDF/USD paths)
os.environ["GEESUN_DOG_VARIANT"] = args_cli.variant
print(f"Geesun variant: {args_cli.variant}", flush=True)

from unitree_rl_lab.assets.robots.unitree import GEESUN_DOG_CFG as ROBOT_CFG
from unitree_rl_lab.assets.robots.unitree import ensure_geesun_dog_usd


@configclass
class GeesunDogSceneCfg(InteractiveSceneCfg):
    """Configuration for a scene with the Geesun dog."""

    # NOTE: GroundPlaneCfg references an NVIDIA cloud asset which is unreachable on this
    # machine (blocks/fails when the viewport loads it), so use a local cuboid ground instead.
    ground = AssetBaseCfg(
        prim_path="/World/defaultGroundPlane",
        spawn=sim_utils.CuboidCfg(
            size=(30.0, 30.0, 0.1),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            physics_material=sim_utils.RigidBodyMaterialCfg(
                static_friction=1.0, dynamic_friction=1.0, restitution=0.0
            ),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.35, 0.35, 0.35)),
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(0.0, 0.0, -0.05)),  # top surface at z = 0
    )

    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        # NOTE: do not use an ISAAC_NUCLEUS_DIR HDR texture here - it requires access to the
        # Omniverse asset server and blocks forever when unreachable.
        spawn=sim_utils.DomeLightCfg(intensity=750.0),
    )

    # articulation
    robot: ArticulationCfg = ROBOT_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")


def main():
    # convert the URDF to USD first if needed (converting during scene creation deadlocks)
    usd_path = ensure_geesun_dog_usd()
    print("Using converted USD:", usd_path, flush=True)

    sim_cfg = sim_utils.SimulationCfg(device=args_cli.device)
    sim_cfg.dt = 0.02
    sim = SimulationContext(sim_cfg)

    scene_cfg = GeesunDogSceneCfg(num_envs=1, env_spacing=5.0)
    if args_cli.no_self_collision:
        # dog921 meshes are degenerate (each link is a single repeated vertex); the thin
        # self-colliding slivers pinch the legs, so disable self-collisions for this ablation.
        scene_cfg.robot = ROBOT_CFG.replace(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=ROBOT_CFG.spawn.replace(
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=False,
                    solver_position_iteration_count=8,
                    solver_velocity_iteration_count=4,
                )
            ),
        )
        print("Self-collisions: disabled", flush=True)
    scene = InteractiveScene(scene_cfg)
    robot: Articulation = scene["robot"]
    sim.reset()

    # print joint names for sanity check (requires reset first to populate PhysX views)
    print("Loaded robot joints:", robot.joint_names, flush=True)

    if args_cli.stiffness > 0 or args_cli.damping > 0:
        act = robot.actuators["GeEsunDog"]
        if args_cli.stiffness > 0:
            act.stiffness = (
                torch.full_like(act.stiffness, args_cli.stiffness)
                if torch.is_tensor(act.stiffness)
                else args_cli.stiffness
            )
        if args_cli.damping > 0:
            act.damping = (
                torch.full_like(act.damping, args_cli.damping) if torch.is_tensor(act.damping) else args_cli.damping
            )
        print(
            f"PD override: k={args_cli.stiffness if args_cli.stiffness > 0 else 'cfg'}, "
            f"b={args_cli.damping if args_cli.damping > 0 else 'cfg'}",
            flush=True,
        )

    # --- define per-joint sinusoid parameters (standing base + amplitude, phase in rad) ---
    amp = math.radians(args_cli.amp_deg)
    freq = args_cli.gait_freq  # Hz
    w = 2.0 * math.pi * freq

    # standing pose base angles (rad), matching GEESUN_DOG_CFG init_state
    # trot gait: front-left & rear-right in phase, front-right & rear-left in opposite phase
    base = {
        "joint_fr_hip": 0.0,
        "joint_fl_hip": 0.0,
        "joint_hr_hip": 0.0,
        "joint_hl_hip": 0.0,
        "joint_fr_thigh": 1.0,
        "joint_fl_thigh": 1.0,
        "joint_hr_thigh": args_cli.rear_thigh,
        "joint_hl_thigh": args_cli.rear_thigh,
        "joint_fr_calf": args_cli.calf_base,
        "joint_fl_calf": args_cli.calf_base,
        "joint_hr_calf": args_cli.calf_base,
        "joint_hl_calf": args_cli.calf_base,
    }
    # hip swing amplitude (smaller than thigh/calf)
    amp_map = {name: amp * 0.5 if name.endswith("_hip") else amp for name in base}
    # phases: diagonal legs (fr & hl), (fl & hr) move together; the other pair opposite
    phase_map = {
        "joint_fr_hip": 0.0,
        "joint_fl_hip": math.pi,
        "joint_hr_hip": math.pi,
        "joint_hl_hip": 0.0,
        "joint_fr_thigh": 0.0,
        "joint_fl_thigh": math.pi,
        "joint_hr_thigh": math.pi,
        "joint_hl_thigh": 0.0,
        "joint_fr_calf": 0.0,
        "joint_fl_calf": math.pi,
        "joint_hr_calf": math.pi,
        "joint_hl_calf": 0.0,
    }

    dt = sim.get_physics_dt()
    num_joints = robot.num_joints
    joint_names = robot.joint_names
    # order base/amp/phase to match robot.joint_names
    # order base/amp/phase to match robot.joint_names; unknown joints (e.g. wheel joints on
    # wheel-legged variants such as lingsi_d30w) default to base=0/amp=0 and are not KeyError'd
    base_vec = torch.tensor([base.get(n, 0.0) for n in joint_names], dtype=torch.float32, device=sim.device)
    amp_vec = torch.tensor([amp_map.get(n, 0.0) for n in joint_names], dtype=torch.float32, device=sim.device)
    phase_vec = torch.tensor([phase_map.get(n, 0.0) for n in joint_names], dtype=torch.float32, device=sim.device)
    # wheel joints (name contains 'wheel') spin at a constant --wheel_speed instead of the gait sinusoid
    wheel_mask = torch.tensor(["wheel" in n for n in joint_names], dtype=torch.bool, device=sim.device)

    actions = robot.data.default_joint_pos.clone()  # (num_envs, num_joints), standing pose
    default_root = robot.data.default_root_state.clone()
    # raise the base well above the ground (leg reach is ~0.7 m) so the swinging legs
    # do not hit the ground and jam the joints
    default_root[0, 2] = args_cli.root_z

    # Write the exact target stance as the initial joint state, so the PD does not swing
    # the joints across large angles (e.g. an ablation --rear_thigh) through the ground.
    # Also place the root at --root_z so the height is exact even in --no_pin_root mode.
    robot.write_root_state_to_sim(default_root)
    robot.write_joint_state_to_sim(base_vec.unsqueeze(0), torch.zeros(1, num_joints, device=sim.device))

    sim_dt = dt
    total_steps = args_cli.num_steps
    step_idx = 0

    while simulation_app.is_running():
        t = step_idx * sim_dt
        actions[0] = base_vec + amp_vec * torch.sin(w * t + phase_vec)
        if wheel_mask.any():
            actions[0, wheel_mask] = args_cli.wheel_speed * t
        if not args_cli.no_pin_root or step_idx < args_cli.settle_steps:
            robot.write_root_state_to_sim(default_root)
        robot.set_joint_position_target(actions)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)

        # track the robot with the camera
        root_pos = robot.data.root_state_w[0, :3].cpu().numpy()
        sim.set_camera_view(root_pos + [2.5, 1.5, 0.8], root_pos)

        if step_idx % 100 == 0:
            pos = robot.data.joint_pos[0].cpu().tolist()
            root = robot.data.root_state_w[0, :3].cpu().tolist()
            print(f"[step {step_idx}] root=({root[0]:.3f},{root[1]:.3f},{root[2]:.3f}) joint_pos (rad):", ["%.3f" % p for p in pos], flush=True)
            if args_cli.print_contact:
                tq = robot.data.applied_torque[0].cpu().tolist()
                print(f"[step {step_idx}] applied_torque (N*m):", ["%.2f" % t for t in tq], flush=True)

        step_idx += 1
        if total_steps > 0 and step_idx >= total_steps:
            break


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()

"""This script imports the Geesun dog (dog1) URDF into Isaac Sim and animates all 12 joints.

The robot is spawned from ``unitree_model/geesun_dog/geesun-dog/dog1/urdf/dog1.urdf``
with a standing pose, then each joint follows its own sinusoid so the dog walks in place
in a trot-like gait (diagonal legs in phase).

.. code-block:: bash

    # Usage (inside conda env with Isaac Lab installed)
    python scripts/geesun_dog/move_geesun_dog.py --num_steps 1500
"""

"""Launch Isaac Sim Simulator first."""

import argparse
import math

import torch

from isaaclab.app import AppLauncher

# add argparse arguments
parser = argparse.ArgumentParser(description="Move all joints of the Geesun dog (dog1).")
parser.add_argument("--num_steps", type=int, default=2000, help="Number of physics steps to run (0 = forever)")
parser.add_argument(
    "--gait_freq", type=float, default=1.5, help="Gait frequency in Hz for the sinusoidal joint motion"
)
parser.add_argument("--amp_deg", type=float, default=25.0, help="Joint oscillation amplitude in degrees")

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
    scene = InteractiveScene(scene_cfg)
    robot: Articulation = scene["robot"]
    sim.reset()

    # print joint names for sanity check (requires reset first to populate PhysX views)
    print("Loaded robot joints:", robot.joint_names, flush=True)

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
        "joint_hr_thigh": -1.0,
        "joint_hl_thigh": -1.0,
        "joint_fr_calf": -1.4,
        "joint_fl_calf": -1.4,
        "joint_hr_calf": 1.4,
        "joint_hl_calf": 1.4,
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
    base_vec = torch.tensor([base[n] for n in joint_names], dtype=torch.float32, device=sim.device)
    amp_vec = torch.tensor([amp_map[n] for n in joint_names], dtype=torch.float32, device=sim.device)
    phase_vec = torch.tensor([phase_map[n] for n in joint_names], dtype=torch.float32, device=sim.device)

    actions = robot.data.default_joint_pos.clone()  # (num_envs, num_joints), standing pose
    default_root = robot.data.default_root_state.clone()
    # raise the base well above the ground (leg reach is ~0.7 m) so the swinging legs
    # do not hit the ground and jam the joints
    default_root[0, 2] = 1.0

    sim_dt = dt
    total_steps = args_cli.num_steps
    step_idx = 0

    while simulation_app.is_running():
        t = step_idx * sim_dt
        actions[0] = base_vec + amp_vec * torch.sin(w * t + phase_vec)
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
            print(f"[step {step_idx}] joint_pos (rad):", ["%.3f" % p for p in pos], flush=True)

        step_idx += 1
        if total_steps > 0 and step_idx >= total_steps:
            break


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()

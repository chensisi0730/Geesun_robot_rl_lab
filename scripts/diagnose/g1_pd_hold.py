"""G1 29-DoF PD-hold diagnostic (no policy, zero actions).

Spawns the ``Unitree-G1-29dof-Velocity`` environment, resets to the default
standing pose and steps the physics with **zero actions**, i.e. only the PD
actuators hold the default joint positions. If the default pose / asset is
healthy the base height should stay near the standing height; if it sags or
falls within a couple of control steps the collapse is a pose/asset problem,
not a learning problem.

Usage (headless, ~1-2 min):

    conda activate env_isaaclab_sim51
    ISAACLAB_PATH=/home/css/work/unitree/rl/unitree_Robert/isaaclab/IsaacLab \
        python scripts/diagnose/g1_pd_hold.py --headless --num_envs 64 --steps 300
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from list_envs import import_packages  # noqa: F401,E402

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser(description="PD-hold diagnostic (zero actions).")
parser.add_argument("--task", type=str, default="Unitree-G1-29dof-Velocity")
parser.add_argument("--num_envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=300, help="Control steps to run (dt=0.02 s).")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.enable_cameras = False
app_launcher = AppLauncher(args_cli)
sim_app = app_launcher.app

"""Rest follows."""

import gymnasium as gym  # noqa: E402

import torch  # noqa: E402

import unitree_rl_lab.tasks  # noqa: E402,F401
from unitree_rl_lab.utils.parser_cfg import parse_env_cfg  # noqa: E402

env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs)
env = gym.make(args_cli.task, cfg=env_cfg)

robot = env.unwrapped.scene.robot if hasattr(env.unwrapped.scene, "robot") else env.unwrapped.scene["robot"]
device = env.unwrapped.device
wenv = env.unwrapped
actions = torch.zeros(wenv.num_envs, env.action_space.shape[-1], device=device)
obs, _ = env.reset()

z0 = robot.data.root_state_w[:, 2].mean().item()
print(f"[PD-hold] task={args_cli.task} num_envs={wenv.num_envs} initial base z_mean={z0:.3f} m")
print("[PD-hold] t[s]  z_mean  z_min   |dq|max  q_off_max  (zero actions -> PD holds default pose)")

for i in range(args_cli.steps):
    obs, rew, terminated, truncated, _ = env.step(actions)
    if i % 25 == 0 or i == args_cli.steps - 1:
        z = robot.data.root_state_w[:, 2]
        q_off = (robot.data.joint_pos - robot.data.default_joint_pos).abs()
        print(
            f"  {i * 0.02:6.2f}  {z.mean().item():7.3f}  {z.min().item():7.3f}  "
            f"{robot.data.joint_vel.abs().max().item():8.3f}  {q_off.max().item():9.4f}"
        )

# final per-joint detail: which joints deviate the most from the default pose
q_off = (robot.data.joint_pos - robot.data.default_joint_pos).abs()
names = robot.joint_names
order = q_off.max(dim=0).values.argsort(descending=True)
print("[PD-hold] top joint deviations from default pose (max over envs):")
for idx in order[:10]:
    print(f"  {names[idx]:32s} max|dq|={q_off[:, idx].max().item():.4f} rad  mean|dq|={q_off[:, idx].mean().item():.4f} rad")
print(f"[PD-hold] final base: pos_mean={robot.data.root_state_w[:, :3].mean(dim=0).tolist()} "
      f"z_min={robot.data.root_state_w[:, 2].min().item():.3f} m")

sim_app.close()

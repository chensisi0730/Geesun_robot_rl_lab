# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to play a checkpoint if an RL agent from RSL-RL."""

"""Launch Isaac Sim Simulator first."""

import argparse
from importlib.metadata import version

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

# add argparse arguments
parser = argparse.ArgumentParser(description="Train an RL agent with RSL-RL.")
parser.add_argument("--video", action="store_true", default=False, help="Record videos during training.")
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument(
    "--use_pretrained_checkpoint",
    action="store_true",
    help="Use the pre-trained checkpoint from Nucleus.",
)
parser.add_argument("--real-time", action="store_true", default=False, help="Run in real-time, if possible.")
parser.add_argument(
    "--camera_view",
    type=str,
    default="side",
    choices=["rear", "side", "diag", "free"],
    help=(
        "Camera style for videos: 'side' (default, 侧向跟拍 lateral tracking shot), "
        "'rear' (身后追拍 chase camera behind the robot), "
        "'diag' (斜后方高俯拍 high oblique from behind-left - the rig that keeps the other robots "
        "out of frame; see --camera_distance/--camera_height defaults) or "
        "'free' (自由视角: the camera is positioned once at startup and then left alone, so you "
        "can orbit/zoom freely in the Kit viewport; use --camera_eye/--camera_target to set it)."
    ),
)
parser.add_argument(
    "--camera_distance",
    type=float,
    default=None,
    help=(
        "Follow-camera horizontal offset from the robot (m). Defaults per view: side/rear 2.2 m, "
        "diag 0.57 m. With the 2.5 m env_spacing grid a 2.2 m lateral rig ends up 0.3 m from a "
        "neighbour, so all dogs appear in one frame at spawn; 'diag' avoids that."
    ),
)
parser.add_argument(
    "--camera_height",
    type=float,
    default=None,
    help="Follow-camera height above the robot root (m). Defaults per view: side/rear 1.1 m, diag 1.2 m.",
)
parser.add_argument(
    "--camera_focal",
    type=float,
    default=None,
    help=(
        "Focal length (mm) applied to the viewport camera while recording, then restored on exit. "
        "Defaults per view: side/rear 0 (keep viewport default), diag 21 mm (~20 deg half-FOV), "
        "which excludes the grid neighbours (>= 35 deg off-axis)."
    ),
)
parser.add_argument(
    "--camera_eye",
    type=float,
    nargs=3,
    default=None,
    metavar=("X", "Y", "Z"),
    help="Only with --camera_view free: initial camera eye position (m, world frame). Default: 3.5 m away, 1.6 m up.",
)
parser.add_argument(
    "--camera_target",
    type=float,
    nargs=3,
    default=None,
    metavar=("X", "Y", "Z"),
    help="Only with --camera_view free: initial camera look-at point (m, world frame). Default: robot spawn origin, 0.15 m up.",
)
parser.add_argument(
    "--terrain",
    type=str,
    default="play",
    choices=["play", "flat", "random_rough", "stairs", "complex"],
    help=(
        "Terrain for playback/videos: 'play' (default) = the task's play-config terrain, "
        "'flat' = forced pure flat ground, 'random_rough'/'stairs' = isolate one terrain type on all "
        "difficulty rows, 'complex' = mixed rough terrain (flat + random_rough + pyramid_stairs)."
    ),
)
parser.add_argument(
    "--stair_height",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the stair riser height range (m) used by the 'stairs'/'complex' terrain presets.",
)
parser.add_argument(
    "--cmd_x",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the linear-x velocity command range (m/s). Default: the play config's full range.",
)
parser.add_argument(
    "--cmd_y",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the linear-y velocity command range (m/s). Default: the play config's full range.",
)
parser.add_argument(
    "--cmd_z",
    type=float,
    nargs=2,
    default=None,
    metavar=("MIN", "MAX"),
    help="Override the yaw velocity command range (rad/s). Default: the play config's full range.",
)
parser.add_argument(
    "--video_tag",
    type=str,
    default="play",
    help="Sub-folder of <run>/videos/ the recording is written to, so different terrain runs do not overwrite each other.",
)
parser.add_argument(
    "--env_cfg_file",
    type=str,
    default=None,
    help=(
        "Replay with the env cfg saved by a training run (the run's params/velocity_env_cfg.py snapshot) "
        "instead of the currently registered task cfg. Use this when the task cfg has changed since the "
        "checkpoint was trained (e.g. height_scanner added to the critic obs), which otherwise breaks "
        "the checkpoint's observation dimensions."
    ),
)
parser.add_argument(
    "--no_standing",
    action="store_true",
    default=False,
    help="Disable standing envs so every robot keeps walking (recommended for videos).",
)
parser.add_argument(
    "--no_curriculum",
    action="store_true",
    default=False,
    help="Disable curriculum terms so terrain levels stay fixed during playback (recommended for videos).",
)
parser.add_argument(
    "--episode_length_s",
    type=float,
    default=None,
    help=(
        "Override env_cfg.episode_length_s (episode 长度, 默认 20 s = 1000 步). Set it above "
        "--video_length * step_dt (e.g. 35 for a 1500-step / 30 s clip) so the recording contains NO "
        "mid-clip lockstep reset (锁步复位). Default None = keep the cfg value = unchanged behaviour."
    ),
)
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
# always enable cameras to record video
if args_cli.video:
    args_cli.enable_cameras = True

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import gymnasium as gym
import os
import time
import torch

from rsl_rl.runners import OnPolicyRunner

import isaaclab_tasks  # noqa: F401
from isaaclab.envs import DirectMARLEnv, multi_agent_to_single_agent
from isaaclab.utils.assets import retrieve_file_path
from isaaclab.utils.dict import print_dict
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlVecEnvWrapper, export_policy_as_jit, export_policy_as_onnx
from isaaclab_tasks.utils import get_checkpoint_path

import unitree_rl_lab.tasks  # noqa: F401
from unitree_rl_lab.utils.parser_cfg import parse_env_cfg


def main():
    """Play with RSL-RL agent."""
    # terrain presets (地形预设) and the run-snapshot loader live next to this script; imported here
    # (after the AppLauncher has booted) because isaaclab.terrains needs the running kit app.
    from snapshot_cfg import load_snapshot_env_cfg
    from terrain_presets import apply_terrain

    # parse configuration
    if args_cli.env_cfg_file:
        env_cfg = load_snapshot_env_cfg(
            args_cli.env_cfg_file,
            device=args_cli.device,
            num_envs=args_cli.num_envs,
            use_fabric=not args_cli.disable_fabric,
        )
        print(f"[INFO] Using snapshot env cfg from: {os.path.abspath(args_cli.env_cfg_file)}")
    else:
        env_cfg = parse_env_cfg(
            args_cli.task,
            device=args_cli.device,
            num_envs=args_cli.num_envs,
            use_fabric=not args_cli.disable_fabric,
            entry_point_key="play_env_cfg_entry_point",
        )
    # evaluation terrain (--terrain): 'play' (default) keeps the play-config terrain untouched
    print(f"[INFO] Terrain mode: {apply_terrain(env_cfg, args_cli.terrain, stair_height=args_cli.stair_height)}")
    if args_cli.no_curriculum:
        env_cfg.curriculum = None
    if args_cli.no_standing:
        env_cfg.commands.base_velocity.rel_standing_envs = 0.0
    if args_cli.cmd_x is not None:
        env_cfg.commands.base_velocity.ranges.lin_vel_x = tuple(args_cli.cmd_x)
    if args_cli.cmd_y is not None:
        env_cfg.commands.base_velocity.ranges.lin_vel_y = tuple(args_cli.cmd_y)
    if args_cli.cmd_z is not None:
        env_cfg.commands.base_velocity.ranges.ang_vel_z = tuple(args_cli.cmd_z)
    if args_cli.episode_length_s is not None:
        # 35 s = 1750 步 > 1500 帧 (30 s @ 50 fps) -> 整段录像内不出现 time_out (超时) 锁步复位
        env_cfg.episode_length_s = args_cli.episode_length_s
        print(f"[INFO] Episode length override (episode 长度覆盖): {args_cli.episode_length_s} s")
    agent_cfg: RslRlOnPolicyRunnerCfg = cli_args.parse_rsl_rl_cfg(args_cli.task, args_cli)

    # specify directory for logging experiments
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Loading experiment from directory: {log_root_path}")
    if args_cli.use_pretrained_checkpoint:
        # NOTE: in newer Isaac Lab versions (isaaclab_rl >= 0.4.7), this utility was moved from
        # isaaclab.utils.pretrained_checkpoint to isaaclab_rl.utils.pretrained_checkpoint.
        try:
            from isaaclab.utils.pretrained_checkpoint import get_published_pretrained_checkpoint
        except ModuleNotFoundError:
            try:
                from isaaclab_rl.utils.pretrained_checkpoint import get_published_pretrained_checkpoint
            except ModuleNotFoundError:
                print("[WARN] pretrained_checkpoint utility not available in this Isaac Lab version.")
                print("[INFO] Unfortunately a pre-trained checkpoint is currently unavailable for this task.")
                return
        resume_path = get_published_pretrained_checkpoint("rsl_rl", args_cli.task)
        if not resume_path:
            print("[INFO] Unfortunately a pre-trained checkpoint is currently unavailable for this task.")
            return
    elif args_cli.checkpoint:
        resume_path = retrieve_file_path(args_cli.checkpoint)
    else:
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)

    log_dir = os.path.dirname(resume_path)

    # create isaac environment
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # convert to single-agent instance if required by the RL algorithm
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # wrap for video recording
    if args_cli.video:
        video_kwargs = {
            "video_folder": os.path.join(log_dir, "videos", args_cli.video_tag),
            "step_trigger": lambda step: step == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during training.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    # wrap around environment for rsl-rl
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    print(f"[INFO]: Loading model checkpoint from: {resume_path}")
    # load previously trained model
    if not hasattr(agent_cfg, "class_name") or agent_cfg.class_name == "OnPolicyRunner":
        runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    elif agent_cfg.class_name == "DistillationRunner":
        from rsl_rl.runners import DistillationRunner

        runner = DistillationRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    else:
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")
    runner.load(resume_path)

    # obtain the trained policy for inference
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    # extract the neural network module
    # we do this in a try-except to maintain backwards compatibility.
    try:
        # version 2.3 onwards
        policy_nn = runner.alg.policy
    except AttributeError:
        # version 2.2 and below
        policy_nn = runner.alg.actor_critic

    # extract the normalizer
    if hasattr(policy_nn, "actor_obs_normalizer"):
        normalizer = policy_nn.actor_obs_normalizer
    elif hasattr(policy_nn, "student_obs_normalizer"):
        normalizer = policy_nn.student_obs_normalizer
    else:
        normalizer = None

    # export policy to onnx/jit
    export_model_dir = os.path.join(os.path.dirname(resume_path), "exported")
    export_policy_as_jit(policy_nn, normalizer=normalizer, path=export_model_dir, filename="policy.pt")
    export_policy_as_onnx(policy_nn, normalizer=normalizer, path=export_model_dir, filename="policy.onnx")

    dt = env.unwrapped.step_dt

    # reset environment
    obs = env.get_observations()
    if version("rsl-rl-lib").startswith("2.3."):
        obs, _ = env.get_observations()
    # Per-view default rig geometry (m) and focal length (mm). The 'diag' numbers come from a
    # sweep over all yaw (偏航角) values against the 2.5 m env_spacing grid: a 2.2 m lateral rig
    # puts the camera 0.3 m from a neighbour (worst neighbour 10 deg off-axis vs a 16 deg half-FOV
    # -> every dog in frame, indistinguishable), while 0.57 m offset + 1.2 m height + 21 mm keeps
    # the neighbours >= 35 deg off-axis and the target dog at ~1.2 m filling ~31 deg of the frame.
    CAM_DEFAULTS = {"side": (2.2, 1.1, 0.0), "rear": (2.2, 1.1, 0.0), "diag": (0.57, 1.2, 21.0)}

    def _set_focal(focal: float, cam_prim_path: str = "/OmniverseKit_Persp"):
        """Narrow the viewport camera's field of view for the recording (restored on exit)."""
        if not focal:
            return None
        import omni.usd

        attr = omni.usd.get_context().get_stage().GetPrimAtPath(cam_prim_path).GetAttribute("focalLength")
        if not attr.IsValid():
            return None
        original = float(attr.Get())
        attr.Set(float(focal))
        print(f"[INFO] Recording camera: focal length {original:.2f} -> {float(focal):.2f} mm (收窄视场角 narrow FOV)")
        return original

    def _follow_camera():
        """Follow camera for videos; style selected by --camera_view.

        - "side" (default): lateral tracking shot - the camera rides next to the robot at a
          fixed world-side offset and keeps looking at it (does not spin with its yaw).
        - "rear": classic chase camera behind the robot, aligned with its yaw.
        - "diag": 斜后方高俯拍 - high oblique rig from behind-left, yaw-locked; the only geometry
          in the sweep that keeps the grid neighbours out of frame, so ONE robot is identifiable.
        - "free": 自由视角 - position the viewport camera (视口相机) ONCE at the first frame
          (--camera_eye / --camera_target, else a sensible default) and never move it again,
          so the user can orbit / zoom freely in the Kit viewport while the robot walks.
        """
        from isaacsim.core.utils import viewports as vp_utils

        view = args_cli.camera_view
        d0, h0, f0 = CAM_DEFAULTS.get(view, CAM_DEFAULTS["side"])
        distance = d0 if args_cli.camera_distance is None else args_cli.camera_distance
        height = h0 if args_cli.camera_height is None else args_cli.camera_height
        focal = f0 if args_cli.camera_focal is None else args_cli.camera_focal
        if focal and not getattr(_follow_camera, "_focal_done", False):
            _follow_camera._focal_done = True
            _follow_camera._focal_original = _set_focal(focal)

        robot = env.unwrapped.scene["robot"]
        pos = robot.data.root_pos_w[0].cpu()
        if args_cli.camera_view == "free":
            if getattr(_follow_camera, "_free_done", False):
                return  # 自由视角：机位只设一次，之后完全交给用户
            _follow_camera._free_done = True
            origin = env.unwrapped.scene.env_origins[0].cpu()
            eye = args_cli.camera_eye or [float(origin[0]) + 3.5, float(origin[1]) + 3.5, float(origin[2]) + 1.6]
            target = args_cli.camera_target or [float(origin[0]), float(origin[1]), float(origin[2]) + 0.15]
            vp_utils.set_camera_view(eye=list(eye), target=list(target), camera_prim_path="/OmniverseKit_Persp")
            print(f"[INFO] Free camera (自由视角): eye={list(eye)}, target={list(target)}")
            return
        if args_cli.camera_view in ("rear", "diag"):
            quat = robot.data.root_quat_w[0].cpu()  # (w, x, y, z)
            yaw = torch.atan2(2.0 * (quat[0] * quat[3] + quat[1] * quat[2]), 1.0 - 2.0 * (quat[2] ** 2 + quat[3] ** 2))
            fx, fy = torch.cos(yaw), torch.sin(yaw)
        if args_cli.camera_view == "rear":
            eye = [float(pos[0] - distance * fx), float(pos[1] - distance * fy), float(pos[2] + height)]
            target = [float(pos[0] + 0.5 * fx), float(pos[1] + 0.5 * fy), float(pos[2] + 0.1)]
        elif args_cli.camera_view == "diag":
            half = 0.5 * distance
            eye = [
                float(pos[0] - half * (fx + fy)),
                float(pos[1] - half * (fy - fx)),
                float(pos[2] + height),
            ]
            target = [float(pos[0] + 0.15 * fx), float(pos[1] + 0.15 * fy), float(pos[2] + 0.15)]
        else:  # side
            eye = [float(pos[0]), float(pos[1] + distance), float(pos[2] + height)]
            target = [float(pos[0]), float(pos[1]), float(pos[2] + 0.15)]
        vp_utils.set_camera_view(eye=eye, target=target, camera_prim_path="/OmniverseKit_Persp")

    timestep = 0
    # simulate environment
    while simulation_app.is_running():
        start_time = time.time()
        # run everything in inference mode
        with torch.inference_mode():
            # agent stepping
            actions = policy(obs)
            # env stepping
            obs, _, _, _ = env.step(actions)
        # camera follows the robot so recordings stay framed on it
        _follow_camera()
        if args_cli.video:
            timestep += 1
            # Exit the play loop after recording one video
            if timestep == args_cli.video_length:
                break

        # time delay for real-time evaluation
        sleep_time = dt - (time.time() - start_time)
        if args_cli.real_time and sleep_time > 0:
            time.sleep(sleep_time)

    # restore the viewport camera focal length so the GUI is back to its normal field of view
    _orig_focal = getattr(_follow_camera, "_focal_original", None)
    if _orig_focal:
        import omni.usd

        omni.usd.get_context().get_stage().GetPrimAtPath("/OmniverseKit_Persp").GetAttribute("focalLength").Set(
            float(_orig_focal)
        )
        print(f"[INFO] Restored viewport camera focal length to {float(_orig_focal):.2f} mm")

    # close the simulator
    env.close()


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()

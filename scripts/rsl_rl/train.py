# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to train RL agent with RSL-RL."""

"""Launch Isaac Sim Simulator first."""


import gymnasium as gym
import pathlib
import sys

sys.path.insert(0, f"{pathlib.Path(__file__).parent.parent}")
from list_envs import import_packages  # noqa: F401

sys.path.pop(0)

tasks = []
for task_spec in gym.registry.values():
    if "Unitree" in task_spec.id and "Isaac" not in task_spec.id:
        tasks.append(task_spec.id)

import argparse

import argcomplete

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

# add argparse arguments
parser = argparse.ArgumentParser(description="Train an RL agent with RSL-RL.")
parser.add_argument("--video", action="store_true", default=False, help="Record videos during training.")
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
parser.add_argument(
    "--video_interval",
    type=int,
    default=2000,
    help="Interval between video recordings (in env.step() CALLS, i.e. iterations x num_steps_per_env).",
)
parser.add_argument(
    "--camera_view",
    type=str,
    default="diag",
    choices=["diag", "rear", "side", "free"],
    help=(
        "Camera style for in-training videos: 'diag' (default, 斜后方跟拍 - behind-left elevated "
        "chase rig; keeps the 2.5 m env_spacing neighbours outside the frame), "
        "'rear' (身后追拍 chase camera behind the robot), "
        "'side' (侧向跟拍 lateral shot - NOTE: with env_spacing 2.5 m the camera sits 0.3 m from "
        "the neighbouring robot and that neighbour fills the frame), "
        "'free' (自由视角: camera is positioned once and left alone). Requires --video."
    ),
)
parser.add_argument(
    "--camera_distance",
    type=float,
    default=0.57,
    help=(
        "Follow-camera HORIZONTAL offset from the robot (m), split 50/50 behind/left for 'diag'. "
        "Keep it small (<= 0.6 m) and pair it with a large --camera_height: the sweep over all yaw "
        "(偏航角) values shows the 2.5 m grid neighbours stay >= 35 deg off-axis only in this regime "
        "(a 2.2 m lateral rig puts the camera 0.3 m from a neighbour)."
    ),
)
parser.add_argument(
    "--camera_height",
    type=float,
    default=1.2,
    help="Follow-camera height above the robot root (m). 1.2 m with distance 0.57 m = 25 deg from vertical.",
)
parser.add_argument(
    "--camera_focal",
    type=float,
    default=21.0,
    help=(
        "Focal length (mm) applied to the recording camera WHILE a clip is captured, then restored. "
        "21 mm gives a ~33 deg half-FOV (min of horizontal/vertical), which excludes the grid "
        "neighbours (>= 35 deg off-axis) while the dog fills ~half the frame width. 0 = keep the "
        "viewport default focal length."
    ),
)
parser.add_argument(
    "--video_start_delay",
    type=int,
    default=None,
    help="First clip is skipped below this env.step() count. Default = --video_interval (so the "
    "first video is recorded mid-walk, not at the spawn where all robots stand in a dense grid).",
)
parser.add_argument(
    "--video_start_frac",
    type=float,
    default=None,
    help=(
        "How far AFTER the loaded checkpoint the first clip starts, as a fraction (0-1) of ONE "
        "CHECKPOINT INTERVAL (agent save_interval, = 100 iterations). 0.5 = exactly midway between "
        "the two checkpoints (检查点), i.e. 50 iterations in; 0.0 = immediately; 1.0 = at the next "
        "checkpoint. Every later clip keeps the same phase, so all clips land midway between "
        "consecutive checkpoints. Requires --video. Overrides --video_start_delay."
    ),
)
parser.add_argument(
    "--video_start_run_frac",
    type=float,
    default=None,
    help=(
        "Alternative to --video_start_frac: fraction (0-1) of THIS RUN'S REMAINING training "
        "(loaded checkpoint iteration -> max_iterations) to skip before the first clip. "
        "0.5 = halfway to max_iterations. Overrides --video_start_frac. Requires --video."
    ),
)
parser.add_argument(
    "--video_start_episode_frac",
    type=float,
    default=None,
    help=(
        "Episode-phase locking (episode 相位锁定): pin every clip to this phase (0-1) INSIDE the 20 s "
        "episode instead of inside the checkpoint interval. All envs reset in lockstep (time_out "
        "dominates), so the spawn crowd recurs every episode_length_s; a plain checkpoint fraction "
        "drifts across that boundary and lands some clips exactly on a reset. 0.35 = start 7 s into "
        "the episode, so a 500-step (10 s) clip covers 7-17 s and never straddles the reset. "
        "Also snaps --video_interval to a whole number of episodes so the phase stays locked. "
        "Overrides --video_start_frac and --video_start_run_frac. Requires --video."
    ),
)
parser.add_argument(
    "--camera_eye",
    type=float,
    nargs=3,
    default=None,
    metavar=("X", "Y", "Z"),
    help="Only with --camera_view free: initial camera eye position (m, world frame).",
)
parser.add_argument(
    "--camera_target",
    type=float,
    nargs=3,
    default=None,
    metavar=("X", "Y", "Z"),
    help="Only with --camera_view free: initial camera look-at point (m, world frame).",
)
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default=None, choices=tasks, help="Name of the task.")
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
parser.add_argument("--max_iterations", type=int, default=None, help="RL Policy training iterations.")
parser.add_argument(
    "--distributed", action="store_true", default=False, help="Run training with multiple GPUs or nodes."
)
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
argcomplete.autocomplete(parser)
args_cli, hydra_args = parser.parse_known_args()

# always enable cameras to record video
if args_cli.video:
    args_cli.enable_cameras = True

# clear out sys.argv for Hydra
sys.argv = [sys.argv[0]] + hydra_args

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Check for minimum supported RSL-RL version."""

import importlib.metadata as metadata
import platform

from packaging import version

# for distributed training, check minimum supported rsl-rl version
RSL_RL_VERSION = "2.3.1"
installed_version = metadata.version("rsl-rl-lib")
if args_cli.distributed and version.parse(installed_version) < version.parse(RSL_RL_VERSION):
    if platform.system() == "Windows":
        cmd = [r".\isaaclab.bat", "-p", "-m", "pip", "install", f"rsl-rl-lib=={RSL_RL_VERSION}"]
    else:
        cmd = ["./isaaclab.sh", "-p", "-m", "pip", "install", f"rsl-rl-lib=={RSL_RL_VERSION}"]
    print(
        f"Please install the correct version of RSL-RL.\nExisting version is: '{installed_version}'"
        f" and required version is: '{RSL_RL_VERSION}'.\nTo install the correct version, run:"
        f"\n\n\t{' '.join(cmd)}\n"
    )
    exit(1)

"""Rest everything follows."""

import gymnasium as gym
import inspect
import os
import shutil
import torch
from datetime import datetime

from rsl_rl.runners import OnPolicyRunner  # TODO: Consider printing the experiment name in the terminal.

import isaaclab_tasks  # noqa: F401
from isaaclab.envs import (
    DirectMARLEnv,
    DirectMARLEnvCfg,
    DirectRLEnvCfg,
    ManagerBasedRLEnvCfg,
    multi_agent_to_single_agent,
)
from isaaclab.utils.dict import print_dict
from isaaclab.utils.io import dump_yaml
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlVecEnvWrapper
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

import unitree_rl_lab.tasks  # noqa: F401
from unitree_rl_lab.utils.export_deploy_cfg import export_deploy_cfg

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.deterministic = False
torch.backends.cudnn.benchmark = False


class FollowCameraWrapper(gym.Wrapper):
    """Keep the recording camera framed on ONE robot during in-training videos (训练内录像跟拍相机).

    ``gym.wrappers.RecordVideo`` renders from ``env.cfg.viewer.cam_prim_path`` (default
    ``/OmniverseKit_Persp``, the Kit viewport camera), which is a FIXED rig: with thousands of
    parallel envs the robot drives out of the frame within seconds. This wrapper moves that prim
    every env step while a clip is being recorded.

    Why ``diag`` (斜后方跟拍) is the default - the neighbour problem (2026-10-14):
    the scene uses ``env_spacing = 2.5 m``, so robots stand on a 2.5 m grid. The old ``side`` rig
    sat 2.2 m laterally from the target, i.e. only **0.3 m from its +Y neighbour**, which then
    filled the whole frame and the target robot was indistinguishable from the crowd. ``diag``
    puts the camera behind-left and elevated (``-d/2 * forward + d/2 * left + height``), pushing
    the 4 nearest grid neighbours to >= 38 deg off-axis; combined with the narrowed focal length
    (half-FOV 18 deg) they fall outside the frustum, so the clip shows exactly one dog.

    Styles (``--camera_view``): ``diag`` (斜后方, default), ``rear`` (身后追拍, aligned with yaw),
    ``side`` (侧向跟拍, legacy - see the neighbour warning above), ``free`` (自由视角, placed once).

    Cost: one tiny GPU->CPU sync (3 floats) per env step, and only while a clip is being recorded.
    """

    def __init__(
        self,
        env,
        view: str = "diag",
        eye=None,
        target=None,
        distance: float = 0.57,
        height: float = 1.2,
        focal: float = 21.0,
        check_every: int = 100,
    ):
        super().__init__(env)
        self.view = view
        self.eye0 = eye
        self.target0 = target
        self.distance = distance
        self.height = height
        self.focal = focal
        self.check_every = check_every
        self._free_placed = False
        self._cam_prim_path = None
        self._focal_backup = None
        self._applied_focal = None
        self._frame = 0

    def _set_focal(self, focal):
        """Apply (focal given) or restore (focal None) the focal length on the camera prim."""
        try:
            import omni.usd

            attr = omni.usd.get_context().get_stage().GetPrimAtPath(self._cam_prim_path).GetAttribute("focalLength")
            if not attr.IsValid():
                return None
            if focal is None:
                if self._focal_backup is not None:
                    attr.Set(self._focal_backup)
                    self._focal_backup = None
            else:
                if self._focal_backup is None:
                    self._focal_backup = float(attr.Get())
                attr.Set(focal)
            return float(attr.Get())
        except Exception as exc:  # rendering-only fallback, never fatal
            print(f"[WARN] Could not set camera focal length: {exc}")
            return None

    def _half_fov_deg(self, focal):
        """Smaller half-FOV (deg) of the camera prim at the given focal length (mm).

        Uses min(horizontal, vertical) so the framing check is conservative for a 16:9 image.
        Plain ``math`` here: these are scalars, and torch.atan rejects Python floats.
        """
        import math

        try:
            import omni.usd

            prim = omni.usd.get_context().get_stage().GetPrimAtPath(self._cam_prim_path)
            h_attr = prim.GetAttribute("horizontalAperture")
            v_attr = prim.GetAttribute("verticalAperture")
            h_ap = float(h_attr.Get()) if h_attr.IsValid() else 24.0
            v_ap = float(v_attr.Get()) if v_attr.IsValid() else 13.5
        except Exception:
            h_ap, v_ap = 24.0, 13.5
        focal = max(float(focal), 1e-3)
        return min(
            math.degrees(math.atan(h_ap / 2.0 / focal)),
            math.degrees(math.atan(v_ap / 2.0 / focal)),
        )

    def _update_camera(self):
        from isaacsim.core.utils import viewports as vp_utils

        if self._cam_prim_path is None:
            self._cam_prim_path = self.env.unwrapped.cfg.viewer.cam_prim_path
        if self.view == "free":
            if self._free_placed:
                return
            self._free_placed = True
            origin = self.env.unwrapped.scene.env_origins[0].cpu()
            eye = self.eye0 or [float(origin[0]) + 3.5, float(origin[1]) + 3.5, float(origin[2]) + 1.6]
            target = self.target0 or [float(origin[0]), float(origin[1]), float(origin[2]) + 0.15]
            vp_utils.set_camera_view(eye=list(eye), target=list(target), camera_prim_path=self._cam_prim_path)
            print(f"[INFO] Free camera (自由视角): eye={list(eye)}, target={list(target)}")
            return
        robot = self.env.unwrapped.scene["robot"]
        pos = robot.data.root_pos_w[0].cpu()
        quat = robot.data.root_quat_w[0].cpu()  # (w, x, y, z)
        yaw = torch.atan2(2.0 * (quat[0] * quat[3] + quat[1] * quat[2]), 1.0 - 2.0 * (quat[2] ** 2 + quat[3] ** 2))
        fx, fy = torch.cos(yaw), torch.sin(yaw)  # unit forward vector (机首方向)
        if self.view == "side":
            eye = [float(pos[0]), float(pos[1] + self.distance), float(pos[2] + self.height)]
            target = [float(pos[0]), float(pos[1]), float(pos[2] + 0.15)]
        elif self.view == "rear":
            eye = [float(pos[0] - self.distance * fx), float(pos[1] - self.distance * fy), float(pos[2] + self.height)]
            target = [float(pos[0] + 0.5 * fx), float(pos[1] + 0.5 * fy), float(pos[2] + 0.1)]
        else:  # diag: high oblique from behind-left (斜后方高俯拍) - neighbours stay >= 35 deg off-axis
            half = 0.5 * self.distance
            eye = [
                float(pos[0] - half * (fx + fy)),
                float(pos[1] - half * (fy - fx)),
                float(pos[2] + self.height),
            ]
            target = [float(pos[0] + 0.15 * fx), float(pos[1] + 0.15 * fy), float(pos[2] + 0.15)]
        vp_utils.set_camera_view(eye=eye, target=target, camera_prim_path=self._cam_prim_path)
        self._check_framing(eye, target)

    def _check_framing(self, eye, target):
        """Numerically prove no neighbouring robot is inside the frame (邻居离轴角诊断).

        A clip is clean when ``nearest neighbour off-axis angle > half-FOV``.
        Pure diagnostics: wrapped in try/except so a bug here can NEVER kill a training run.
        """
        self._frame += 1
        if self._frame % self.check_every:
            return
        try:
            robot = self.env.unwrapped.scene["robot"]
            eye_t = torch.tensor(eye, dtype=torch.float32, device=robot.data.root_pos_w.device)
            view = torch.tensor(target, dtype=torch.float32, device=eye_t.device) - eye_t
            view = view / view.norm()
            rel = robot.data.root_pos_w[:512] - eye_t
            dist = rel.norm(dim=1)
            cos = (rel @ view).clamp(-1.0, 1.0) / dist.clamp_min(1e-6)
            ang = torch.rad2deg(torch.acos(cos))
            ang[0] = float("inf")  # the tracked robot itself
            nearest = float(ang.min())
            target_dist = float(dist[0])
            half_fov = self._half_fov_deg(self.focal if self.focal else 24.0)
            dog_span = float(torch.rad2deg(torch.atan(torch.tensor(0.35 / max(target_dist, 1e-3)))) * 2.0)
            status = "OK (single dog in frame)" if nearest > half_fov else "NEIGHBOUR IN FRAME"
            print(
                f"[VIDEO-CAM] frame {self._frame}: target {target_dist:.2f} m (dog spans {dog_span:.1f} deg), "
                f"nearest neighbour {nearest:.1f} deg off-axis, half-FOV {half_fov:.1f} deg -> {status}"
            )
        except Exception as exc:  # diagnostics must never be fatal
            print(f"[WARN] framing check skipped: {exc}")

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._free_placed = False
        self._update_camera()  # place the rig on the robot before the first captured frame
        return obs, info

    def step(self, action):
        out = self.env.step(action)
        # only pay for the camera while the inner RecordVideo is actually capturing frames
        recording = bool(getattr(self.env, "recording", False))
        if recording:
            if self._focal_backup is None and self.focal:
                applied = self._set_focal(self.focal)
                self._applied_focal = applied
                note = ""
                if applied is not None and abs(applied - self.focal) > 0.5:
                    note = (
                        f" [WARN] prim kept {applied:.2f} mm (the Kit viewport camera owns its focal "
                        "length, so the requested narrowing was NOT applied - the framing check below "
                        "uses the prim's real focal length)"
                    )
                print(f"[INFO] Recording camera: focal length {applied} mm (收窄视场角 narrow FOV){note}")
            self._update_camera()
        elif self._focal_backup is not None:
            self._set_focal(None)  # restore the viewport FOV for the rest of the run
        return out


@hydra_task_config(args_cli.task, "rsl_rl_cfg_entry_point")
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlOnPolicyRunnerCfg):
    """Train with RSL-RL agent."""
    # override configurations with non-hydra CLI arguments
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs
    agent_cfg.max_iterations = (
        args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    )

    # set the environment seed
    # note: certain randomizations occur in the environment initialization so we set the seed here
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    # multi-gpu training configuration
    if args_cli.distributed:
        env_cfg.sim.device = f"cuda:{app_launcher.local_rank}"
        agent_cfg.device = f"cuda:{app_launcher.local_rank}"

        # set seed to have diversity in different threads
        seed = agent_cfg.seed + app_launcher.local_rank
        env_cfg.seed = seed
        agent_cfg.seed = seed

    # specify directory for logging experiments
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Logging experiment in directory: {log_root_path}")
    # velocity-curriculum sidecar (see mdp.curriculums.lin_vel_cmd_levels): fresh runs must not
    # inherit command ranges from a previous run; resume runs keep the file so the range/gate
    # survive restarts (the rsl-rl checkpoint does not store command ranges).
    _curric_state_file = os.path.join(log_root_path, "curriculum_state.json")
    if not (agent_cfg.resume or agent_cfg.algorithm.class_name == "Distillation") and os.path.exists(
        _curric_state_file
    ):
        os.remove(_curric_state_file)
        print(f"[INFO] Removed stale velocity-curriculum state: {_curric_state_file}")
    # terrain-levels sidecar (see mdp.curriculums._save_terrain_state): same rule - fresh runs
    # start from the cfg's max_init_terrain_level draw, resume runs keep the saved levels.
    _terrain_state_file = os.path.join(log_root_path, "terrain_levels_state.json")
    if not (agent_cfg.resume or agent_cfg.algorithm.class_name == "Distillation") and os.path.exists(
        _terrain_state_file
    ):
        os.remove(_terrain_state_file)
        print(f"[INFO] Removed stale terrain-levels state: {_terrain_state_file}")
    # specify directory for logging runs: {time-stamp}_{run_name}
    log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # This way, the Ray Tune workflow can extract experiment name.
    print(f"Exact experiment name requested from command line: {log_dir}")
    if agent_cfg.run_name:
        log_dir += f"_{agent_cfg.run_name}"
    log_dir = os.path.join(log_root_path, log_dir)

    # create isaac environment
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # convert to single-agent instance if required by the RL algorithm
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # save resume path before creating a new log_dir
    resume_path = None
    if agent_cfg.resume or agent_cfg.algorithm.class_name == "Distillation":
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)

    # wrap for video recording
    if args_cli.video:
        # When does the first clip start? Never at the spawn (出生点): with thousands of parallel envs
        # all robots stand packed on the env_spacing grid, so a clip at step 0 shows a crowd, not a
        # dog. --video_start_frac states the delay as a fraction of ONE CHECKPOINT INTERVAL
        # (agent save_interval = 100 iterations): 0.5 = exactly midway between the two checkpoints.
        # The trigger is PHASE-ALIGNED, so every clip lands at that same offset from the checkpoints.
        steps_per_iter = int(getattr(agent_cfg, "num_steps_per_env", 24))
        save_interval = int(getattr(agent_cfg, "save_interval", 100))
        # iteration of the checkpoint we resumed from (model_<iter>.pt); 0 for a fresh run
        start_iter = 0
        if resume_path is not None:
            try:
                start_iter = int(pathlib.Path(resume_path).stem.rsplit("_", 1)[-1])
            except ValueError:
                print(f"[WARN] Could not parse the checkpoint iteration from {resume_path}; assuming 0.")
        remaining_iters = max(int(agent_cfg.max_iterations) - start_iter, 0)
        start_delay = args_cli.video_start_delay
        delay_iters = None
        basis = None
        video_interval = int(args_cli.video_interval)
        # Episode length in env.step() calls. All envs reset in lockstep (time_out dominates the
        # termination mix), so the dense spawn grid (出生密集网格) recurs every episode_length_s:
        # a clip that straddles that boundary shows a crowd plus a mid-clip teleport.
        episode_steps = 0
        step_dt = 0.0
        try:
            step_dt = float(env_cfg.sim.dt) * int(env_cfg.decimation)
            episode_steps = int(round(float(env_cfg.episode_length_s) / step_dt))
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            print("[WARN] Could not derive the episode length from the task cfg; phase locking off.")
        if args_cli.video_start_episode_frac is not None and episode_steps > 0:
            frac = min(max(args_cli.video_start_episode_frac, 0.0), 1.0)
            phase = int(round(frac * episode_steps))
            # earliest clip that honours --video_start_frac's checkpoint offset and lands on the phase
            ckpt_frac = min(max(args_cli.video_start_frac or 0.0, 0.0), 1.0)
            min_delay = int(round(save_interval * ckpt_frac)) * steps_per_iter
            start_delay = min_delay + (phase - min_delay) % episode_steps
            # keep the phase locked for every later clip: interval must be a whole number of episodes
            snapped = max(episode_steps, int(round(video_interval / episode_steps)) * episode_steps)
            if snapped != video_interval:
                print(
                    f"[INFO] video_interval snapped {video_interval} -> {snapped} env.step() calls "
                    f"({snapped // episode_steps} whole episodes) to keep the clip phase locked."
                )
                video_interval = snapped
            delay_iters = start_delay // steps_per_iter
            basis = (
                f"episode-phase {frac} of the {episode_steps}-step ({episode_steps * step_dt:.0f} s) "
                f"episode -> clip starts {phase} steps ({phase * step_dt:.1f} s) into an episode"
            )
        elif args_cli.video_start_run_frac is not None:
            frac = min(max(args_cli.video_start_run_frac, 0.0), 1.0)
            delay_iters = int(remaining_iters * frac)
            basis = f"run fraction {frac} of the remaining {remaining_iters} iterations"
        elif args_cli.video_start_frac is not None:
            frac = min(max(args_cli.video_start_frac, 0.0), 1.0)
            delay_iters = int(round(save_interval * frac))
            basis = f"checkpoint-interval fraction {frac} x save_interval ({save_interval} iterations)"
        if delay_iters is not None:
            if args_cli.video_start_episode_frac is None:
                start_delay = delay_iters * steps_per_iter
            print(
                f"[INFO] Video start = {basis} -> first clip at env.step() #{start_delay} = iteration "
                f"{start_iter + start_delay // steps_per_iter} ({start_delay // steps_per_iter} iterations "
                f"after checkpoint {start_iter})."
            )
        elif start_delay is None:
            start_delay = video_interval
        video_kwargs = {
            "video_folder": os.path.join(log_dir, "videos", "train"),
            # phase-aligned: clips at start_delay, +interval, +2*interval, ... (a plain
            # ``step % interval == 0`` trigger cannot express a half-checkpoint offset)
            "step_trigger": lambda step: step >= start_delay and (step - start_delay) % video_interval == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during training.")
        print_dict(video_kwargs, nesting=4)
        print(
            f"[INFO] First clip at env.step() #{start_delay} = iteration "
            f"{start_iter + start_delay // steps_per_iter} (避开出生密集网格, not at spawn); "
            f"then every {video_interval // steps_per_iter} iterations."
        )
        env = gym.wrappers.RecordVideo(env, **video_kwargs)
        # keep the fixed viewport rig framed on the robot (the prim RecordVideo renders from)
        env = FollowCameraWrapper(
            env,
            view=args_cli.camera_view,
            eye=args_cli.camera_eye,
            target=args_cli.camera_target,
            distance=args_cli.camera_distance,
            height=args_cli.camera_height,
            focal=args_cli.camera_focal,
        )
        print(
            f"[INFO] Follow camera (跟拍相机) enabled for training videos: view={args_cli.camera_view}, "
            f"distance={args_cli.camera_distance} m, height={args_cli.camera_height} m, "
            f"focal={args_cli.camera_focal} mm"
        )

    # wrap around environment for rsl-rl
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # create runner from rsl-rl
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=log_dir, device=agent_cfg.device)
    # write git state to logs
    runner.add_git_repo_to_log(__file__)
    # load the checkpoint
    if agent_cfg.resume or agent_cfg.algorithm.class_name == "Distillation":
        print(f"[INFO]: Loading model checkpoint from: {resume_path}")
        # load previously trained model
        runner.load(resume_path)

    # dump the configuration into log-directory
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), agent_cfg)
    export_deploy_cfg(env.unwrapped, log_dir)
    # copy the environment configuration file to the log directory
    shutil.copy(
        inspect.getfile(env_cfg.__class__),
        os.path.join(log_dir, "params", os.path.basename(inspect.getfile(env_cfg.__class__))),
    )

    # run training
    runner.learn(num_learning_iterations=agent_cfg.max_iterations, init_at_random_ep_len=True)

    # close the simulator
    env.close()


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()

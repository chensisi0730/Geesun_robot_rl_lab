"""Velocity-tracking locomotion task for the Geesun dog **lingsi_d30w** variant (D30W wheel-legged).

STANDALONE TASK DEFINITION: this file is self-contained for lingsi_d30w and deliberately shares
no task-config code with the ``dog1`` task, so the two campaigns can be tuned independently
(and auto-tuned concurrently) without cross-contaminating each other's reward / curriculum knobs.
For a dog1 <-> lingsi_d30w ablation, diff the two files: the asset / foot / action differences
below are the only intended deltas.

Adapted from the Go2 task. Main differences:
- robot is spawned from ``GEESUN_DOG_CFG`` (URDF converted to USD on demand)
- base body is named ``base_link`` (Go2 uses ``base``)
- the URDF has no dedicated foot links; the wheel links are the feet and the calves must stay
  clear of the ground
- 4 wheel joints are velocity-servo driven on top of the 12 position-controlled leg joints
"""

import math
import os

import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.assets import ArticulationCfg, AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import ContactSensorCfg, RayCasterCfg, patterns
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR, ISAACLAB_NUCLEUS_DIR
from isaaclab.utils.noise import AdditiveUniformNoiseCfg as Unoise

# Pin the asset variant before importing the shared asset module (that module freezes the
# variant into module-level constants on first import). This task is lingsi_d30w regardless of
# the ambient GEESUN_DOG_VARIANT, so an unset/mis-set env var can never train the wrong robot.
os.environ["GEESUN_DOG_VARIANT"] = "lingsi_d30w"

from unitree_rl_lab.assets.robots.unitree import GEESUN_DOG_CFG as ROBOT_CFG  # noqa: E402
from unitree_rl_lab.assets.robots.unitree import ensure_geesun_dog_usd  # noqa: E402
from unitree_rl_lab.tasks.locomotion import mdp  # noqa: E402
from unitree_rl_lab.tasks.locomotion.sensors import airy_cfg as airy  # noqa: E402

# -- lingsi_d30w traits, hard-coded on purpose (cf. GEESUN_DOG_VARIANT_SPECS["lingsi_d30w"]) --
# Links that touch the ground: lingsi_d30w rolls on its wheels, so the wheel links are the feet
# and the calves (which sit right above the wheels) must stay clear of the ground.
FOOT_BODY_NAMES = ".*_wheel"
# Position-controlled leg joints. The wheel joints are velocity-servo driven and deliberately
# excluded from the joint-space penalties (velocity / acceleration / torque / position
# deviation), which would otherwise directly fight free rolling.
LEG_JOINT_NAMES = ["joint_(fr|fl|hr|hl)_(hip|thigh|calf)"]
WHEEL_JOINT_NAMES = ["joint_(fr|fl|hr|hl)_wheel"]

# 2026-10-22 A/B switch for the wheel-lock experiment (see ActionsCfg.WheelVelocityAction and
# RewardsCfg.joint_pos): GEESUN_D30W_WHEEL_LOCK=1 (default) locks the wheels (scale=0) so the
# 12 leg joints must climb the stairs; =0 restores free rolling (scale=20) as the control arm.
# Record the value in the run name - it is NOT stored in the checkpoint.
WHEEL_LOCKED = os.environ.get("GEESUN_D30W_WHEEL_LOCK", "1") == "1"

# 2026-10-22 P0-2: the joint_pos stand-still penalty is now an INDEPENDENT switch. Coupling it
# to WHEEL_LOCKED confounded the ablation - the locked arm carried -0.7 while the control arm
# carried 0.0, so the comparison measured "lock + penalty" vs "free + no penalty" instead of the
# lock alone (measured 2026-10-21/22: locked wheels + this penalty let the policy stand still
# for reward - success_rate 0.87 -> 0.01, terrain_levels 6.0 -> 0.005). The default reproduces
# the previous coupled behaviour (reproducibility of existing runs); override to isolate:
#   GEESUN_D30W_JOINT_POS=0    drop the penalty entirely (both arms)
#   GEESUN_D30W_JOINT_POS=0.7  give the free-wheel control arm the same penalty as the locked arm
JOINT_POS_WEIGHT = float(os.environ.get("GEESUN_D30W_JOINT_POS", "-0.7" if WHEEL_LOCKED else "0.0"))

COBBLESTONE_ROAD_CFG = terrain_gen.TerrainGeneratorCfg(
    size=(8.0, 8.0),
    border_width=20.0,
    num_rows=10,
    num_cols=20,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    difficulty_range=(0.0, 1.0),
    use_cache=False,
    sub_terrains={
        # 2026-10-23 stairs-only (全楼梯地形): flat/random_rough removed so 100% of columns are
        # pyramid_stairs (金字塔楼梯). Proportions are auto-normalized by IsaacLab.
        # step_height_range is the GO2 value (0.05, 0.23) VERBATIM - strict ablation (消融对照).
        # D30W wheel radius 0.095 m -> top riser 0.23 m is 1.21x the 0.19 m wheel diameter and
        # must be cleared by the 12 leg joints alone.
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=1.0,
            step_height_range=(0.05, 0.23),
            step_width=0.3,
            platform_width=3.0,
            border_width=1.0,
            holes=False,
        ),
    },
)


@configclass
class RobotSceneCfg(InteractiveSceneCfg):
    """Configuration for the terrain scene with a legged robot."""

    # ground terrain
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",  # "plane", "generator"
        terrain_generator=COBBLESTONE_ROAD_CFG,  # None, ROUGH_TERRAINS_CFG
        max_init_terrain_level=1,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True,
            texture_scale=(0.25, 0.25),
        ),
        debug_vis=False,
    )
    # robots
    robot: ArticulationCfg = ROBOT_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

    # sensors
    height_scanner = RayCasterCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base_link",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        ray_alignment="yaw",
        pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=[1.6, 1.0]),
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
    )
    contact_forces = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/Robot/.*", history_length=3, track_air_time=True)
    # lights
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(
            intensity=750.0,
            texture_file=f"{ISAAC_NUCLEUS_DIR}/Materials/Textures/Skies/PolyHaven/kloofendal_43d_clear_puresky_4k.hdr",
        ),
    )


@configclass
class RobotSceneCfgAiry(RobotSceneCfg):
    """Scene variant that adds the RoboSense Airy 96-beam LiDAR (head unit).

    Kept as a SUBCLASS so the baseline ``RobotSceneCfg`` stays byte-for-byte unchanged: the existing
    task and every checkpoint trained from it must keep working, and the baseline must not pay 26 GB
    of VRAM for a sensor whose observation it never reads.

    实机 PRO 版规格: 96 线 / 水平 360° x 垂直 90° 半球(朝下) / 30 m@10% 反射率, 装在机身头部上方。
    Modelled as critic-only privileged obs - same convention as ``height_scanner`` - so the policy
    inputs stay untouched and deployable.

    WHY ONLY ONE (measured, not stylistic): the real robot carries 2 units (head + tail), but one
    360 deg sweep already covers fore and aft, so a 2nd instance adds no information while costing
    another ~8-12 GB VRAM. At 4096 envs one unit already sits at 26.2 / 32.6 GB.
    """

    # WHY MultiMeshRayCasterCfg: plain RayCaster reads only the FIRST UsdGeomMesh under
    # mesh_prim_paths, so it would see the ground and nothing else; MultiMesh casts against all
    # listed meshes, which is what a LiDAR needs. See airy_cfg.py for the measurement.
    airy_front = airy.airy_ray_caster_cfg(
        prim_path="{ENV_REGEX_NS}/Robot/base_link",
        offset=airy.AIRY_HEAD_OFFSET,
        # TERRAIN ONLY - the robot's own meshes are deliberately NOT listed (2026-10-16, measured).
        # Adding "{ENV_REGEX_NS}/Robot" for near-field self-occlusion makes `MultiMeshRayCasterCfg`
        # dedup one USD mesh per env at ~1 s/env: 4096 envs took ~68 min of pure init and then the
        # process died silently (no Traceback, log frozen at "Starting the simulation", died at env
        # ~2796/4096) - twice. It also pushes VRAM past the 26.2 GB figure measured WITHOUT the robot
        # (that is the number the airy_cfg guard was calibrated on). Net effect: no training at all.
        # Dropping it costs only the near-field self-shadow of the legs/trunk, which is exactly the
        # trade this comment originally sanctioned ("drop the robot path if training OOMs and you
        # only lose near-field self-shadowing") - the terrain/stair signal the BEV exists for is
        # unaffected, because the sub-terrain obstacles live under /World/ground.
        mesh_prim_paths=["/World/ground"],
    )


@configclass
class EventCfg:
    """Configuration for events."""

    # startup
    physics_material = EventTerm(
        func=mdp.randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "static_friction_range": (0.3, 1.2),
            "dynamic_friction_range": (0.3, 1.2),
            "restitution_range": (0.0, 0.15),
            "num_buckets": 64,
        },
    )

    add_base_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_link"),
            "mass_distribution_params": (-1.0, 3.0),
            "operation": "add",
        },
    )

    # reset
    base_external_force_torque = EventTerm(
        func=mdp.apply_external_force_torque,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_link"),
            "force_range": (0.0, 0.0),
            "torque_range": (-0.0, 0.0),
        },
    )

    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)},
            "velocity_range": {
                "x": (0.0, 0.0),
                "y": (0.0, 0.0),
                "z": (0.0, 0.0),
                "roll": (0.0, 0.0),
                "pitch": (0.0, 0.0),
                "yaw": (0.0, 0.0),
            },
        },
    )

    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_scale,
        mode="reset",
        params={
            "position_range": (1.0, 1.0),
            "velocity_range": (-1.0, 1.0),
        },
    )

    # interval
    push_robot = EventTerm(
        func=mdp.push_by_setting_velocity,
        mode="interval",
        interval_range_s=(5.0, 10.0),
        params={"velocity_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5)}},
    )


@configclass
class CommandsCfg:
    """Command specifications for the MDP."""

    base_velocity = mdp.UniformLevelVelocityCommandCfg(
        asset_name="robot",
        resampling_time_range=(10.0, 10.0),
        rel_standing_envs=0.1,
        debug_vis=True,
        ranges=mdp.UniformLevelVelocityCommandCfg.Ranges(
            # 2026-10-23 P0-3: was (-0.1, 0.1) - with such a small command, standing still
            # already collected 1.433/1.5 of the tracking reward (std 0.5), so the policy
            # never had to move. The command range is now wide enough that "moving" and
            # "standing" are clearly different in reward space.
            lin_vel_x=(-0.3, 0.3), lin_vel_y=(-0.2, 0.2), ang_vel_z=(-1, 1)
        ),
        limit_ranges=mdp.UniformLevelVelocityCommandCfg.Ranges(
            lin_vel_x=(-1.0, 1.0), lin_vel_y=(-0.4, 0.4), ang_vel_z=(-1.0, 1.0)
        ),
    )


@configclass
class ActionsCfg:
    """Action specifications for the MDP.

    lingsi_d30w is wheel-legged: 12 leg joints position-controlled + 4 wheel joints
    velocity-servo driven.
    """

    JointPositionAction = mdp.JointPositionActionCfg(
        asset_name="robot",
        joint_names=LEG_JOINT_NAMES,
        scale=0.25,
        use_default_offset=True,
        clip={".*": (-100.0, 100.0)},
    )
    WheelVelocityAction = mdp.JointVelocityActionCfg(
        asset_name="robot",
        joint_names=WHEEL_JOINT_NAMES,
        # 2026-10-21 A-cut + wheel lock: scale=0 pins wheel velocity at the default (0),
        # so the wheels act as feet and stairs must be climbed with the 12 leg joints.
        # Action dim stays 4 so old checkpoints still load. Rollback: scale=20.0.
        # 2026-10-22: switchable via GEESUN_D30W_WHEEL_LOCK=0 for the A/B control arm
        # (measured 2026-10-21/22: locked wheels + the joint_pos penalty below let the policy
        # stand still for reward - success_rate 0.87 -> 0.01, terrain_levels 6.0 -> 0.005).
        scale=0.0 if WHEEL_LOCKED else 20.0,
        use_default_offset=True,
        clip={".*": (-25.0, 25.0)},
    )


@configclass
class ObservationsCfg:
    """Observation specifications for the MDP."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for policy group."""

        # observation terms (order preserved)
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, scale=0.2, clip=(-100, 100), noise=Unoise(n_min=-0.2, n_max=0.2))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, clip=(-100, 100), noise=Unoise(n_min=-0.05, n_max=0.05))
        velocity_commands = ObsTerm(
            func=mdp.generated_commands, clip=(-100, 100), params={"command_name": "base_velocity"}
        )
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel, clip=(-100, 100), noise=Unoise(n_min=-0.01, n_max=0.01))
        joint_vel_rel = ObsTerm(
            func=mdp.joint_vel_rel, scale=0.05, clip=(-100, 100), noise=Unoise(n_min=-1.5, n_max=1.5)
        )
        last_action = ObsTerm(func=mdp.last_action, clip=(-100, 100))

        def __post_init__(self):
            # self.history_length = 5
            self.enable_corruption = True
            self.concatenate_terms = True

    # observation groups
    policy: PolicyCfg = PolicyCfg()

    @configclass
    class CriticCfg(ObsGroup):
        """Observations for critic group."""

        base_lin_vel = ObsTerm(func=mdp.base_lin_vel, clip=(-100, 100))
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, scale=0.2, clip=(-100, 100))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, clip=(-100, 100))
        velocity_commands = ObsTerm(
            func=mdp.generated_commands, clip=(-100, 100), params={"command_name": "base_velocity"}
        )
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel, clip=(-100, 100))
        joint_vel_rel = ObsTerm(func=mdp.joint_vel_rel, scale=0.05, clip=(-100, 100))
        joint_effort = ObsTerm(func=mdp.joint_effort, scale=0.01, clip=(-100, 100))
        last_action = ObsTerm(func=mdp.last_action, clip=(-100, 100))
        # DEMO (2026-10-14): height_scanner (高度扫描传感器) enabled as critic-only privileged
        # obs (仅特权 critic 观测) - the same ablation convention as the GO2
        # unitree_go2_velocity_ht run (robots/go2/velocity_env_cfg.py). The policy (策略) obs is
        # deliberately left untouched, so the actor stays deployable on the real Realsense D435i /
        # MID360 without changing the actor inputs. Critic obs grows by 187 dims (17x11 grid at
        # 0.1 m over 1.6 x 1.0 m), which changes the value net input layer -> old checkpoints
        # cannot be resumed, this run must start fresh.
        #
        # OFFSET REVERT (2026-10-16, MEASURED - scripts/diagnose/check_height_scanner_values.py):
        # ``mdp.height_scan`` returns ``sensor.data.pos_w.z - ray_hits_w.z - offset``, and the 20 m
        # ``OffsetCfg(pos=(0,0,20))`` only raises the ray START - it does NOT enter ``pos_w``.
        # Measured on this task: pos_w z = [0.610, 0.610, 0.640] (base_link / trunk height) and
        # ray_hits_w z spans 0.000 .. 0.524. So with the default offset=0.5 the raw value is
        #     0.61 - hit_z - 0.5  in  [-0.41, +0.11]
        # which clip=(-1.0, 1.0) passes through untouched: a live, terrain-varying term.
        #
        # The 2026-10-15 "fix" that set offset=20.5 assumed pos_w were base_z + 20 = 20.61. It is
        # wrong: it drove the raw value to ~ -19.9, so ALL 187 cells pinned to the clip floor -1.0
        # (measured 187/187 at -1.0 even after 20 steps) - i.e. it turned a live privileged term
        # into a constant, which silently degraded every run trained since. Reverted to 0.5.
        # Obs DIMS stay 187, so the value-net input layer is unchanged and checkpoints remain
        # shape-compatible; only the CONTENT of those 187 inputs changed (constant -> terrain).
        # NOTE: this makes checkpoints trained with offset=20.5 (dead term) NOT comparable to the
        # A-baseline; the A arm of the ablation must be re-trained from scratch.
        height_scanner = ObsTerm(
            func=mdp.height_scan,
            params={"sensor_cfg": SceneEntityCfg("height_scanner"), "offset": 0.5},
            clip=(-1.0, 1.0),
        )

        # def __post_init__(self):
        #     self.history_length = 5

    # privileged observations
    critic: CriticCfg = CriticCfg()


@configclass
class RewardsCfg:
    """Reward terms for the MDP."""

    # -- task
    track_lin_vel_xy = RewTerm(
        # 2026-10-23 P0-3: std was sqrt(0.25)=0.5 - far too flat for the command range:
        # a 0.18 m/s tracking error still scored 0.95 of the maximum. std=0.2 makes
        # exp(-e^2/0.04) decay properly, so standing still with a 0.3 m/s command now
        # scores ~0.1 instead of ~0.7.
        func=mdp.track_lin_vel_xy_exp, weight=1.5, params={"command_name": "base_velocity", "std": 0.2}
    )
    track_ang_vel_z = RewTerm(
        func=mdp.track_ang_vel_z_exp, weight=0.75, params={"command_name": "base_velocity", "std": math.sqrt(0.25)}
    )

    # -- base
    base_linear_velocity = RewTerm(func=mdp.lin_vel_z_l2, weight=-2.0)
    base_angular_velocity = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)
    # joint-space penalties are restricted to the position-controlled leg joints: on the wheel-legged
    # variant the wheels must be free to spin fast, so penalising their speed / acceleration /
    # torque / position offset would make rolling impossible
    joint_vel = RewTerm(
        func=mdp.joint_vel_l2, weight=-0.001, params={"asset_cfg": SceneEntityCfg("robot", joint_names=LEG_JOINT_NAMES)}
    )
    joint_acc = RewTerm(
        func=mdp.joint_acc_l2,
        weight=-2.5e-7,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=LEG_JOINT_NAMES)},
    )
    joint_torques = RewTerm(
        func=mdp.joint_torques_l2,
        weight=-2e-4,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=LEG_JOINT_NAMES)},
    )
    action_rate = RewTerm(func=mdp.action_rate_l2, weight=-0.1)
    dof_pos_limits = RewTerm(
        func=mdp.joint_pos_limits,
        weight=-10.0,
        # wheel joints are continuous (no limits) and are excluded from the soft-limit penalty
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=LEG_JOINT_NAMES)},
    )
    energy = RewTerm(func=mdp.energy, weight=-2e-5)

    # -- robot
    flat_orientation_l2 = RewTerm(func=mdp.flat_orientation_l2, weight=-2.5)

    joint_pos = RewTerm(
        func=mdp.joint_position_penalty,
        # 2026-10-22 P0-1: with the wheels locked (scale=0 above) this penalty fights the only
        # remaining forward drive - lifting the leg joints to step - so standing still became
        # reward-optimal (success_rate 0.87 -> 0.01, terrain_levels 6.0 -> 0.005). The weight is
        # now an INDEPENDENT switch (GEESUN_D30W_JOINT_POS, default = the old coupled value) so
        # the ablation can run "lock + penalty" vs "lock only" instead of confounding both.
        weight=JOINT_POS_WEIGHT,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=LEG_JOINT_NAMES),
            "stand_still_scale": 5.0,
            "velocity_threshold": 0.3,
        },
    )

    # -- feet (the dog URDF has no foot links: dog1 uses the calf tips, lingsi_d30w the wheels)
    feet_air_time = RewTerm(
        func=mdp.feet_air_time,
        # 2026-10-15 reward-hack fix (stair slide -> leg lift): threshold 0.5 was punishing
        # every normal lift (wheel air time 0.1-0.3 s < 0.5 s -> negative term on landing,
        # confirmed by Episode_Reward/feet_air_time = -0.006). 2026-10-15 later: 0.1 -> 0.05,
        # because the term was still negative after the fix (most wheel lifts land < 0.1 s);
        # 0.05 only filters contact-jitter while every real lift pays off. Then 0.05 -> 0.02:
        # the residual -0.0015 came from 0.02-0.05 s lifts being charged on landing; 0.02
        # flips them positive (raising weight alone would also amplify the negative term).
        weight=0.5,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODY_NAMES),
            "command_name": "base_velocity",
            "threshold": 0.02,
        },
    )
    air_time_variance = RewTerm(
        func=mdp.air_time_variance_penalty,
        weight=-1.0,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODY_NAMES)},
    )
    feet_slide = RewTerm(
        func=mdp.feet_slide,
        weight=-0.1,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=FOOT_BODY_NAMES),
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODY_NAMES),
        },
    )
    # P1 2026-10-21: swing-wheel clearance (stairs 0.23 m riser, wheel r=0.095 m).
    # Air-gated foot_clearance so flat rolling does not collect free reward.
    # target_height is wheel-center world z while swinging (ground roll ≈ 0.095).
    # Rollback: delete this term (or switch func to mdp.foot_clearance_reward).
    feet_clearance = RewTerm(
        func=mdp.foot_clearance_air,
        weight=1.0,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=FOOT_BODY_NAMES),
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODY_NAMES),
            "std": 0.05,
            "tanh_mult": 2.0,
            "target_height": 0.30,
            # 2026-10-23 P0-3: command gate - the air gate alone still paid +0.594 per
            # episode for lifting the legs IN PLACE while making no forward progress.
            # Only envs that are actually commanded to move (|cmd_xy| >= 0.2 m/s) collect
            # the lift reward now, so the term pays for stepping, not for twitching.
            # 2026-10-23 P0-3 fix: was 0.2. With x_max stuck at 0.30 (P0-1 deadlock) and
            # resampling ~10% standing envs, most episodes had |cmd| < 0.2 so the reward
            # collapsed from +0.123 (mixed terrain) to +0.006 (stairs-only). Lowering to
            # 0.1 lets the lift reward fire at a 0.3 m/s x command (the current x_max)
            # while still filtering pure stand-still envs. Pairs with P0-1 (x_max unlock).
            "command_name": "base_velocity",
            "min_command_speed": 0.1,
        },
    )
    # feet_contact_forces = RewTerm(
    #     func=mdp.contact_forces,
    #     weight=-0.02,
    #     params={
    #         "threshold": 100.0,
    #         "sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODY_NAMES),
    #     },
    # )

    # -- other
    # the calf links sit right above the wheels and must not scrape the ground, so they join
    # the hips and thighs as undesired-contact bodies
    undesired_contacts = RewTerm(
        func=mdp.undesired_contacts,
        weight=-1,
        params={
            "threshold": 1,
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=[".*_hip", ".*_thigh", ".*_calf"]),
        },
    )


@configclass
class TerminationsCfg:
    """Termination terms for the MDP."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    base_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base_link"), "threshold": 1.0},
    )
    # 2026-10-23 P0-2: was 0.8 (~46 deg). On stairs-only the bad_orientation termination
    # hit 17% (vs 4.8% on mixed terrain) - the 12 leg joints under wheel lock cannot hold
    # the trunk level on stair edges, so episodes die before the policy learns to climb.
    # 1.0 (~57 deg) lets the policy explore tilted postures during stair ascent without
    # terminating, matching the GO2 stairs default. Rollback: 0.8.
    bad_orientation = DoneTerm(func=mdp.bad_orientation, params={"limit_angle": 1.0})


@configclass
class CurriculumCfg:
    """Curriculum terms for the MDP.

    Go2 dual-curriculum strategy (adopted 2026-10-13): terrain levels and velocity-command
    ranges advance *in sync* - terrain_levels_vel_strict gates terrain difficulty on survival
    + tracking with hysteresis, gated_lin_vel_cmd_levels widens the x/y and yaw command ranges
    independently on success rate + tracking error. This replaces the earlier one-sided pair
    (terrain_levels_vel + non-gated lin_vel_cmd_levels) that let the command range run ahead
    of terrain competence during the 2026-10-12 collapse.
    """

    terrain_levels = CurrTerm(
        func=mdp.terrain_levels_vel_strict,
        params={
            # terrain<->command coupling (2026-10-14): envs may only climb once the gated
            # velocity range has reached the threshold below (locks terrain progress to
            # command-range progress), and every +1.0 mean-level gain freezes the x range for
            # 2 eval windows so the policy settles on the new terrain before widening again.
            # 2026-10-15 00:57: relaxed 0.3 -> 0.2. Measured on run 2026-10-14_23-26-00: the
            # gate metrics were 3x under thresholds (err_xy 0.074 vs 0.25) while terrain sat
            # frozen at mean level 0.505 for 1400+ iterations - the 0.3 floor only delayed
            # stairs training by ~1 h (x_max climbs one 0.05 step per ~29 min). 0.2 keeps a
            # soft floor (== the demonstrated +-0.2 m/s competence) and restores the verified
            # GO2/dog1 dual-curriculum behavior (those campaigns run this param at 0.0).
            # 2026-10-23 P0-3: 0.2 -> 0.1. The terrain could only level up once the command
            # range reached 0.2 m/s, but the command range itself needed success >= 0.90, so
            # the two deadlocked each other (terrain_levels frozen at 0.5054 for 20k iterations,
            # x_max frozen at 0.10). 0.1 matches the new initial command range.
            "min_x_max_for_move_up": 0.1,
            "cmd_freeze_windows": 2,
            # 2026-10-22 P0-2: forward_ok threshold (episode progress along cmd x must reach
            # this fraction of mean |cmd_x|). 0.7 deadlocked the curriculum; training 0.5.
            "forward_ok_ratio": 0.5,
            # 2026-10-22 P0-1: demote-on-no-progress stays OFF - with the wheel lock below
            # plus the joint_pos penalty the policy can stand still for reward, and demoting
            # crushed terrain_levels 5.0 -> 0.005 in one day (measured 2026-10-21/22).
            "demote_no_forward": False,
            # 2026-10-24 P1 (resume 续训): 地形降级冷静期 (demotion warm-up). A resumed run
            # re-creates every env in lockstep, so for the first ~1 episode length (1000 steps
            # = 42 iterations) no episode ends by timeout - only the FALLEN envs reach the
            # curriculum term. Demoting on that all-failures sample snowballed (measured while
            # resuming model_3700 on 2026-10-24 00:40): terrain_levels 6.12 -> 1.91 and reward
            # 24.5 -> -5.7 within 16 iterations. 2.0 = suppress move_down for the first two
            # episode lengths (~4 min of training). Ablation-safe: the parameter defaults to
            # 0.0 so GO2 / dog1 are untouched; rollback = delete this line.
            "demote_warmup_windows": 2.0,
            # terrain-levels sidecar (2026-10-14, scheme A): resume restores the per-env levels
            # instead of re-climbing from max_init_terrain_level; train.py removes it on fresh.
            "state_file": "logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/terrain_levels_state.json",
        },
    )
    terrain_performance_by_type = CurrTerm(func=mdp.terrain_performance_by_type)
    lin_vel_cmd_levels = CurrTerm(
        func=mdp.gated_lin_vel_cmd_levels,
        params={
            # lingsi_d30w stairs+height_scanner demo campaign state, under its own experiment_name
            # dir: the flat/random_rough baseline has already widened lin_vel_x to +-0.9 m/s, and
            # loading that state onto stairs would outrun the policy immediately (the exact
            # 2026-10-12 collapse mode). Demo run therefore starts from the cfg's +-0.1 m/s.
            "state_file": "logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/curriculum_state.json",
            "lin_increment": 0.05,
            "yaw_increment": 0.1,
            "success_xy": 0.25,
            "success_yaw": 0.35,
            # 2026-10-23 P0-3: was 0.90. With the old +-0.1 m/s command the policy could
            # "succeed" by standing still (tracking error ~0), so the gate opened on
            # stand-still envs while forward_ok stayed false -> the command range never
            # widened (x_max stuck at 0.10 for 20k iterations). 0.75 pairs with the tighter
            # tracking reward (std 0.2) and the wider command range.
            # 2026-10-23 P0-1: was 0.75 / hold 2. On stairs the success_rate hovered at
            # 0.765 - just above 0.75 - but streak could never reach 2 consecutive windows,
            # so x_max froze at 0.30 for 3456 iterations (curriculum deadlock). Lowering to
            # 0.65 + hold 1 lets x_max climb one 0.05 step per eval window once success is
            # merely above-average, breaking the deadlock while still gating on real success.
            "min_success_rate": 0.65,
            "min_env_steps": 6000,
            "min_episodes": 4000,
            "hold": 1,
            # 2026-10-22 P0-2: forward_ok threshold for the x gate (see curriculums.py).
            "forward_ok_ratio": 0.5,
        },
    )
    command_ranges = CurrTerm(func=mdp.velocity_command_ranges)


# 2026-10-20: the four Airy ablation arms share ONE experiment dir (rsl_rl_ppo_cfg.py:
# experiment_name = unitree_geesun_lingsi_d30w_ht_stairs_10x) and therefore shared ONE pair of
# curriculum sidecars (课程旁路状态文件). Consequence, measured: resuming the 4096-env B arm with
# 3096 envs reset pyramid_stairs_level (金字塔楼梯难度等级) 5.05 -> 0.49 and x_max 0.3 -> 0.1, and
# the 20096-env A arm then overwrote the same file. Each arm now gets its own files; the A
# baseline keeps the original names, so its runs and checkpoints are untouched (ablation-safe).
_SIDECAR_DIR = "logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x"


def _isolate_curriculum_sidecars(cfg, arm: str) -> None:
    """Point one ablation arm's curriculum sidecars at arm-specific files (A keeps the defaults)."""
    cfg.curriculum.terrain_levels.params["state_file"] = f"{_SIDECAR_DIR}/terrain_levels_state_{arm}.json"
    cfg.curriculum.lin_vel_cmd_levels.params["state_file"] = f"{_SIDECAR_DIR}/curriculum_state_{arm}.json"



@configclass
class RobotEnvCfg(ManagerBasedRLEnvCfg):
    """Configuration for the locomotion velocity-tracking environment."""

    # Scene settings
    scene: RobotSceneCfg = RobotSceneCfg(num_envs=4096, env_spacing=2.5)
    # Basic settings
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    # MDP settings
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()

    def __post_init__(self):
        """Post initialization."""
        # make sure the converted USD asset exists before the scene spawns the robot
        ensure_geesun_dog_usd()
        print(f"Geesun task: lingsi_d30w (wheel-legged, feet='{FOOT_BODY_NAMES}')", flush=True)

        # general settings
        self.decimation = 4
        self.episode_length_s = 20.0
        # simulation settings
        self.sim.dt = 0.005
        self.sim.render_interval = self.decimation
        self.sim.physics_material = self.scene.terrain.physics_material
        self.sim.physx.gpu_max_rigid_patch_count = 10 * 2**15

        # update sensor update periods
        # we tick all the sensors based on the smallest update period (physics update period)
        self.scene.contact_forces.update_period = self.sim.dt
        self.scene.height_scanner.update_period = self.decimation * self.sim.dt
        # Airy is an active 50 Hz sensor (not a 30 fps camera), so it ticks with the control step.
        # Only the Airy scene variants define it; the baseline scene must stay untouched.
        if hasattr(self.scene, "airy_front"):
            self.scene.airy_front.update_period = self.decimation * self.sim.dt

            # Memory guard: the Airy ray-cast buffers are what actually caps the env count, not
            # compute. CALIBRATED from two measured points on RTX 5090 (32.6 GB) at 4096 envs:
            #   0.8 deg / 43,200 rays/env -> 26.2 GB total (fits, 6.4 GB spare)
            #   0.4 deg / 86,400 rays/env -> OOM (needed >31.7 GB)
            # A naive "rays x 3 x 4 bytes x 2 buffers" estimate gives only 4.0 GB for the case that
            # actually needs 26.2 GB - it misses the per-env mesh BVH and the ray-info buffers, and a
            # guard that under-counts by 6x is worse than none. Two-point fit instead:
            #   total ~= 2.0 GB fixed (Isaac Sim + mesh BVH) + 1.4e-7 GB per ray per env.
            # This deliberately OVER-estimates at high ray counts, so it errs towards warning.
            _AIRY_VRAM_FIXED_GB = 2.0
            _AIRY_VRAM_PER_RAY_GB = 1.4e-7
            _airy_rays = self.scene.airy_front.pattern_cfg.channels * int(
                (self.scene.airy_front.pattern_cfg.horizontal_fov_range[1]
                 - self.scene.airy_front.pattern_cfg.horizontal_fov_range[0])
                / self.scene.airy_front.pattern_cfg.horizontal_res
            )
            _airy_gb = _AIRY_VRAM_FIXED_GB + self.scene.num_envs * _airy_rays * _AIRY_VRAM_PER_RAY_GB
            assert _airy_gb < 28.0, (
                f"Airy VRAM budget ~{_airy_gb:.1f} GB at {self.scene.num_envs} envs "
                f"({_airy_rays} rays/env) risks OOM on a 32 GB card. Lower scene.num_envs or "
                f"AIRY_HORIZONTAL_RES."
            )
            print(f"[airy] {self.scene.num_envs} envs x {_airy_rays} rays/env ~ {_airy_gb:.1f} GB VRAM", flush=True)

        # check if terrain levels curriculum is enabled - if so, enable curriculum for terrain generator
        # this generates terrains with increasing difficulty and is useful for training
        if getattr(self.curriculum, "terrain_levels", None) is not None:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = True
        else:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = False


@configclass
class RobotPlayEnvCfg(RobotEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 32
        self.scene.terrain.terrain_generator.num_rows = 2
        self.scene.terrain.terrain_generator.num_cols = 1
        self.commands.base_velocity.ranges = self.commands.base_velocity.limit_ranges


# =============================================================================
# Sensor ablation variants (added 2026-10-15).
#
# Four configurations, all sharing the SAME policy (策略) observation (49 dims of proprioception)
# so the actor network - and therefore every checkpoint trained under config A - stays loadable.
# Only the critic (评论家) privileged observation changes:
#
#   A  baseline     height_scanner 187              (== plain RobotEnvCfg, the existing task)
#   B  replace      airy_bev 720 (no height_scanner) <- deployable end-state: no privileged info
#   C  stacked      height_scanner 187 + airy_bev 720
#   D  proprio only none                              (worst case: no external perception at all)
#
# B is the configuration that answers the real question: how much performance was the privileged
# height_scanner lending, and can the real sensor replace it? D bounds the loss when nothing is
# observable at all.
#
# CRITIC DIMENSIONS (measured by scripts/diagnose/smoke_env_obs.py):
#   A 263 / B 796 / C 983 / D 76, with policy 57 in all four.
# Changing critic obs invalidates the value net, so each variant trains from scratch - only the
# ACTOR of an existing checkpoint can be reused, and only for A.
# =============================================================================


@configclass
class ObservationsCfgAiryReplace(ObservationsCfg):
    """Config B: Airy BEV replaces height_scanner - no privileged terrain height."""

    @configclass
    class CriticCfg(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel, clip=(-100, 100))
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, scale=0.2, clip=(-100, 100))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, clip=(-100, 100))
        velocity_commands = ObsTerm(
            func=mdp.generated_commands, clip=(-100, 100), params={"command_name": "base_velocity"}
        )
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel, clip=(-100, 100))
        joint_vel_rel = ObsTerm(func=mdp.joint_vel_rel, scale=0.05, clip=(-100, 100))
        joint_effort = ObsTerm(func=mdp.joint_effort, scale=0.01, clip=(-100, 100))
        last_action = ObsTerm(func=mdp.last_action, clip=(-100, 100))
        airy_bev = ObsTerm(
            func=mdp.airy_bev_scan,
            params={"sensor_cfg": SceneEntityCfg("airy_front")},
            clip=(0.0, 2.0),
        )

    critic: CriticCfg = CriticCfg()


@configclass
class ObservationsCfgAiryStacked(ObservationsCfg):
    """Config C: Airy BEV stacked on top of height_scanner (isolates the LiDAR's marginal value)."""

    @configclass
    class CriticCfg(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel, clip=(-100, 100))
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, scale=0.2, clip=(-100, 100))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, clip=(-100, 100))
        velocity_commands = ObsTerm(
            func=mdp.generated_commands, clip=(-100, 100), params={"command_name": "base_velocity"}
        )
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel, clip=(-100, 100))
        joint_vel_rel = ObsTerm(func=mdp.joint_vel_rel, scale=0.05, clip=(-100, 100))
        joint_effort = ObsTerm(func=mdp.joint_effort, scale=0.01, clip=(-100, 100))
        last_action = ObsTerm(func=mdp.last_action, clip=(-100, 100))
        # Same OFFSET REVERT as ObservationsCfg.CriticCfg (see the long comment there): the 20 m
        # OffsetCfg does NOT enter pos_w (measured pos_w z = 0.61), so the correct offset is the
        # default 0.5 -> base_z - hit_z - 0.5 in [-0.41, +0.11]. Config C must use the SAME
        # convention as A or the "marginal value of the LiDAR" comparison would be between two
        # different height terms.
        height_scanner = ObsTerm(
            func=mdp.height_scan,
            params={"sensor_cfg": SceneEntityCfg("height_scanner"), "offset": 0.5},
            clip=(-1.0, 1.0),
        )
        airy_bev = ObsTerm(
            func=mdp.airy_bev_scan,
            params={"sensor_cfg": SceneEntityCfg("airy_front")},
            clip=(0.0, 2.0),
        )

    critic: CriticCfg = CriticCfg()


@configclass
class ObservationsCfgProprioOnly(ObservationsCfg):
    """Config D: no external perception at all - the lower bound the LiDAR has to beat."""

    @configclass
    class CriticCfg(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel, clip=(-100, 100))
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, scale=0.2, clip=(-100, 100))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, clip=(-100, 100))
        velocity_commands = ObsTerm(
            func=mdp.generated_commands, clip=(-100, 100), params={"command_name": "base_velocity"}
        )
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel, clip=(-100, 100))
        joint_vel_rel = ObsTerm(func=mdp.joint_vel_rel, scale=0.05, clip=(-100, 100))
        joint_effort = ObsTerm(func=mdp.joint_effort, scale=0.01, clip=(-100, 100))
        last_action = ObsTerm(func=mdp.last_action, clip=(-100, 100))

    critic: CriticCfg = CriticCfg()


@configclass
class RobotEnvCfgAiryReplace(RobotEnvCfg):
    """Config B env: LiDAR BEV replaces the privileged height scanner."""

    scene: RobotSceneCfgAiry = RobotSceneCfgAiry(num_envs=4096, env_spacing=2.5)
    observations: ObservationsCfgAiryReplace = ObservationsCfgAiryReplace()

    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_geesun_lingsi_d30w_ht_stairs_10x_airy_replace"
        _isolate_curriculum_sidecars(self, "airy_B")


@configclass
class RobotEnvCfgAiryStacked(RobotEnvCfg):
    """Config C env: LiDAR BEV stacked on top of height_scanner."""

    scene: RobotSceneCfgAiry = RobotSceneCfgAiry(num_envs=4096, env_spacing=2.5)
    observations: ObservationsCfgAiryStacked = ObservationsCfgAiryStacked()

    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_geesun_lingsi_d30w_ht_stairs_10x_airy_stacked"
        _isolate_curriculum_sidecars(self, "airy_C")


@configclass
class RobotEnvCfgProprioOnly(RobotEnvCfg):
    """Config D env."""

    observations: ObservationsCfgProprioOnly = ObservationsCfgProprioOnly()

    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_geesun_lingsi_d30w_ht_stairs_10x_proprio_only"
        _isolate_curriculum_sidecars(self, "airy_D")


@configclass
class RobotPlayEnvCfgAiryReplace(RobotEnvCfgAiryReplace):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 32
        self.scene.terrain.terrain_generator.num_rows = 2
        self.scene.terrain.terrain_generator.num_cols = 1
        self.commands.base_velocity.ranges = self.commands.base_velocity.limit_ranges


@configclass
class RobotPlayEnvCfgAiryStacked(RobotEnvCfgAiryStacked):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 32
        self.scene.terrain.terrain_generator.num_rows = 2
        self.scene.terrain.terrain_generator.num_cols = 1
        self.commands.base_velocity.ranges = self.commands.base_velocity.limit_ranges


@configclass
class RobotPlayEnvCfgProprioOnly(RobotEnvCfgProprioOnly):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 32
        self.scene.terrain.terrain_generator.num_rows = 2
        self.scene.terrain.terrain_generator.num_cols = 1
        self.commands.base_velocity.ranges = self.commands.base_velocity.limit_ranges

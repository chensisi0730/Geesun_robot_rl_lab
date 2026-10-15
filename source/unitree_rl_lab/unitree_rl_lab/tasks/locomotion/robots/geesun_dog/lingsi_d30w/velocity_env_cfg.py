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

# -- lingsi_d30w traits, hard-coded on purpose (cf. GEESUN_DOG_VARIANT_SPECS["lingsi_d30w"]) --
# Links that touch the ground: lingsi_d30w rolls on its wheels, so the wheel links are the feet
# and the calves (which sit right above the wheels) must stay clear of the ground.
FOOT_BODY_NAMES = ".*_wheel"
# Position-controlled leg joints. The wheel joints are velocity-servo driven and deliberately
# excluded from the joint-space penalties (velocity / acceleration / torque / position
# deviation), which would otherwise directly fight free rolling.
LEG_JOINT_NAMES = ["joint_(fr|fl|hr|hl)_(hip|thigh|calf)"]
WHEEL_JOINT_NAMES = ["joint_(fr|fl|hr|hl)_wheel"]

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
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.1),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=0.2, noise_range=(0.01, 0.03), noise_step=0.01, border_width=0.25
        ),
        # DEMO STAGE (2026-10-14): pyramid_stairs (金字塔楼梯) re-enabled together with the
        # height_scanner (高度扫描传感器) for the stairs demo. step_height_range is now the
        # GO2 value (0.05, 0.23) VERBATIM - strict ablation (消融对照): same terrain, same PPO
        # hyper-parameters, only the body differs (wheel-legged D30W vs legged GO2).
        # NOTE the expected ablation outcome: the D30W wheel radius is 0.095 m
        # (assets/robots/unitree.py, GEESUN_DOG_VARIANT_SPECS["lingsi_d30w"]), so the 0.23 m
        # top riser is 1.21x the 0.19 m wheel diameter and must be cleared by the 12 leg joints
        # alone -> pyramid_stairs_success_rate is expected to stay well below GO2's, with
        # terrain_levels pinned at low rows and bad_orientation (摔倒终止) higher.
        # With max_init_terrain_level=1 the first real riser is ~0.07 m. Proportions are
        # auto-normalized by IsaacLab -> flat 20% / random_rough 40% / pyramid_stairs 40%.
        # Fresh (non-resume) training: critic obs dim changes as well.
        "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=0.2,
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
            lin_vel_x=(-0.1, 0.1), lin_vel_y=(-0.1, 0.1), ang_vel_z=(-1, 1)
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
        # 0.25 rad/s per unit action would crawl; 20 rad/s per unit covers the 25 rad/s URDF limit
        scale=20.0,
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
        height_scanner = ObsTerm(
            func=mdp.height_scan,
            params={"sensor_cfg": SceneEntityCfg("height_scanner")},
            clip=(-1.0, 5.0),
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
        func=mdp.track_lin_vel_xy_exp, weight=1.5, params={"command_name": "base_velocity", "std": math.sqrt(0.25)}
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
        weight=-0.7,
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
        # confirmed by Episode_Reward/feet_air_time = -0.006). 0.1 s only filters jitter and
        # the bigger weight makes lifting pay before the stairs reward does.
        weight=0.5,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODY_NAMES),
            "command_name": "base_velocity",
            "threshold": 0.1,
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
    bad_orientation = DoneTerm(func=mdp.bad_orientation, params={"limit_angle": 0.8})


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
            "min_x_max_for_move_up": 0.2,
            "cmd_freeze_windows": 2,
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
            "min_success_rate": 0.90,
            "min_env_steps": 6000,
            "min_episodes": 4000,
            "hold": 2,
        },
    )
    command_ranges = CurrTerm(func=mdp.velocity_command_ranges)


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

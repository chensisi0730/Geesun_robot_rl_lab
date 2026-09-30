# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Configuration for Unitree robots.

Reference: https://github.com/unitreerobotics/unitree_ros
"""

import os

import isaaclab.sim as sim_utils
from isaaclab.actuators import IdealPDActuatorCfg, ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg
from isaaclab.utils import configclass

from unitree_rl_lab.assets.robots import unitree_actuators

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
UNITREE_MODEL_DIR = os.environ.get("UNITREE_MODEL_DIR", os.path.join(_REPO_ROOT, "unitree_model"))
UNITREE_ROS_DIR = os.environ.get("UNITREE_ROS_DIR", "/home/css/work/robot/unitree/unitree_ros")


@configclass
class UnitreeArticulationCfg(ArticulationCfg):
    """Configuration for Unitree articulations."""

    joint_sdk_names: list[str] = None

    soft_joint_pos_limit_factor = 0.9


@configclass
class UnitreeUsdFileCfg(sim_utils.UsdFileCfg):
    activate_contact_sensors: bool = True
    rigid_props = sim_utils.RigidBodyPropertiesCfg(
        disable_gravity=False,
        retain_accelerations=False,
        linear_damping=0.0,
        angular_damping=0.0,
        max_linear_velocity=1000.0,
        max_angular_velocity=1000.0,
        max_depenetration_velocity=1.0,
    )
    articulation_props = sim_utils.ArticulationRootPropertiesCfg(
        enabled_self_collisions=True, solver_position_iteration_count=8, solver_velocity_iteration_count=4
    )


@configclass
class UnitreeUrdfFileCfg(sim_utils.UrdfFileCfg):
    fix_base: bool = False
    activate_contact_sensors: bool = True
    replace_cylinders_with_capsules = True
    joint_drive = sim_utils.UrdfConverterCfg.JointDriveCfg(
        gains=sim_utils.UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0, damping=0)
    )
    articulation_props = sim_utils.ArticulationRootPropertiesCfg(
        enabled_self_collisions=True,
        solver_position_iteration_count=8,
        solver_velocity_iteration_count=4,
    )
    rigid_props = sim_utils.RigidBodyPropertiesCfg(
        disable_gravity=False,
        retain_accelerations=False,
        linear_damping=0.0,
        angular_damping=0.0,
        max_linear_velocity=1000.0,
        max_angular_velocity=1000.0,
        max_depenetration_velocity=1.0,
    )

    def replace_asset(self, meshes_dir, urdf_path):
        """Replace the asset with a temporary copy to avoid modifying the original asset.

        When need to change the collisions, place the modified URDF file separately in this repository,
        and let `meshes_dir` be provided by `unitree_ros`.
        This function will auto construct a complete `robot_description` file structure in the `/tmp` directory.
        Note: The mesh references inside the URDF should be in the same directory level as the URDF itself.
        """
        tmp_meshes_dir = "/tmp/IsaacLab/unitree_rl_lab/meshes"
        if os.path.exists(tmp_meshes_dir):
            os.remove(tmp_meshes_dir)
        os.makedirs("/tmp/IsaacLab/unitree_rl_lab", exist_ok=True)
        os.symlink(meshes_dir, tmp_meshes_dir)

        self.asset_path = "/tmp/IsaacLab/unitree_rl_lab/robot.urdf"
        if os.path.exists(self.asset_path):
            os.remove(self.asset_path)
        os.symlink(urdf_path, self.asset_path)


""" Configuration for the Unitree robots."""

UNITREE_GO2_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/go2_description/urdf/go2_description.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/Go2/usd/go2.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.4),
        joint_pos={
            ".*R_hip_joint": -0.1,
            ".*L_hip_joint": 0.1,
            "F[L,R]_thigh_joint": 0.8,
            "R[L,R]_thigh_joint": 1.0,
            ".*_calf_joint": -1.5,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "GO2HV": unitree_actuators.UnitreeActuatorCfg_Go2HV(
            joint_names_expr=[".*"],
            stiffness=25.0,
            damping=0.5,
            friction=0.01,
        ),
    },
    # fmt: off
    joint_sdk_names=[
        "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
        "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
        "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
        "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint"
    ],
    # fmt: on
)

UNITREE_GO2W_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/go2w_description/urdf/go2w_description.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/Go2W/usd/go2w.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.45),
        joint_pos={
            "F.*_thigh_joint": 0.8,
            "R.*_thigh_joint": 0.8,
            ".*_calf_joint": -1.5,
            ".*_foot_joint": 0.0,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "GO2HV": IdealPDActuatorCfg(
            joint_names_expr=[".*"],
            effort_limit=23.5,
            velocity_limit=30.0,
            stiffness={
                ".*_hip_.*": 25.0,
                ".*_thigh_.*": 25.0,
                ".*_calf_.*": 25.0,
                ".*_foot_.*": 0,
            },
            damping=0.5,
            friction=0.01,
        ),
    },
    # fmt: off
    joint_sdk_names=[
        "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
        "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
        "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
        "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
        "FR_foot_joint", "FL_foot_joint", "RR_foot_joint", "RL_foot_joint"
    ],
    # fmt: on
)

UNITREE_B2_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/b2_description/urdf/b2_description.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/B2/usd/b2.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.58),
        joint_pos={
            ".*R_hip_joint": -0.1,
            ".*L_hip_joint": 0.1,
            "F[L,R]_thigh_joint": 0.8,
            "R[L,R]_thigh_joint": 1.0,
            ".*_calf_joint": -1.5,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "M107-24-2": IdealPDActuatorCfg(
            joint_names_expr=[".*_hip_.*", ".*_thigh_.*"],
            effort_limit=200,
            velocity_limit=23,
            stiffness=160.0,
            damping=5.0,
            friction=0.01,
        ),
        "2": IdealPDActuatorCfg(
            joint_names_expr=[".*_calf_.*"],
            effort_limit=320,
            velocity_limit=14,
            stiffness=160.0,
            damping=5.0,
            friction=0.01,
        ),
    },
    joint_sdk_names=UNITREE_GO2_CFG.joint_sdk_names.copy(),
)

UNITREE_H1_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/h1_description/urdf/h1.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/H1/h1/usd/h1.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 1.1),
        joint_pos={
            ".*_hip_pitch_joint": -0.1,
            ".*_knee_joint": 0.3,
            ".*_ankle_joint": -0.2,
            ".*_shoulder_pitch_joint": 0.20,
            ".*_elbow_joint": 0.32,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "GO2HV-1": IdealPDActuatorCfg(
            joint_names_expr=[".*ankle.*", ".*_shoulder_pitch_.*", ".*_shoulder_roll_.*"],
            effort_limit=40,
            velocity_limit=9,
            stiffness={
                ".*ankle.*": 40.0,
                ".*_shoulder_.*": 100.0,
            },
            damping=2.0,
            armature=0.01,
        ),
        "GO2HV-2": IdealPDActuatorCfg(
            joint_names_expr=[".*_shoulder_yaw_.*", ".*_elbow_.*"],
            effort_limit=18,
            velocity_limit=20,
            stiffness=50,
            damping=2.0,
            armature=0.01,
        ),
        "M107-24-1": IdealPDActuatorCfg(
            joint_names_expr=[".*_knee_.*"],
            effort_limit=300.0,
            velocity_limit=14.0,
            stiffness=200.0,
            damping=4.0,
            armature=0.01,
        ),
        "M107-24-2": IdealPDActuatorCfg(
            joint_names_expr=[".*_hip_.*", "torso_joint"],
            effort_limit=200,
            velocity_limit=23.0,
            stiffness={
                ".*_hip_.*": 150.0,
                "torso_joint": 300.0,
            },
            damping={
                ".*_hip_.*": 2.0,
                "torso_joint": 6.0,
            },
            armature=0.01,
        ),
    },
    joint_sdk_names=[
        "right_hip_roll_joint",
        "right_hip_pitch_joint",
        "right_knee_joint",
        "left_hip_roll_joint",
        "left_hip_pitch_joint",
        "left_knee_joint",
        "torso_joint",
        "left_hip_yaw_joint",
        "right_hip_yaw_joint",
        "",
        "left_ankle_joint",
        "right_ankle_joint",
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
    ],
)

UNITREE_G1_23DOF_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/g1_description/g1_23dof_rev_1_0.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/G1/23dof/usd/g1_23dof_rev_1_0/g1_23dof_rev_1_0.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.8),
        joint_pos={
            ".*_hip_pitch_joint": -0.1,
            ".*_knee_joint": 0.3,
            ".*_ankle_pitch_joint": -0.2,
            ".*_shoulder_pitch_joint": 0.3,
            "left_shoulder_roll_joint": 0.25,
            "right_shoulder_roll_joint": -0.25,
            ".*_elbow_joint": 0.97,
            "left_wrist_roll_joint": 0.15,
            "right_wrist_roll_joint": -0.15,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "N7520-14.3": ImplicitActuatorCfg(
            joint_names_expr=[".*_hip_pitch_.*", ".*_hip_yaw_.*", "waist_yaw_joint"],  # 5
            effort_limit_sim=88,
            velocity_limit_sim=32.0,
            stiffness={
                ".*_hip_.*": 100.0,
                "waist_yaw_joint": 200.0,
            },
            damping={
                ".*_hip_.*": 2.0,
                "waist_yaw_joint": 5.0,
            },
            armature=0.01,
        ),
        "N7520-22.5": ImplicitActuatorCfg(
            joint_names_expr=[".*_hip_roll_.*", ".*_knee_.*"],  # 4
            effort_limit_sim=139,
            velocity_limit_sim=20.0,
            stiffness={
                ".*_hip_roll_.*": 100.0,
                ".*_knee_.*": 150.0,
            },
            damping={
                ".*_hip_roll_.*": 2.0,
                ".*_knee_.*": 4.0,
            },
            armature=0.01,
        ),
        "N5020-16": ImplicitActuatorCfg(
            joint_names_expr=[".*_shoulder_.*", ".*_elbow_.*", ".*_wrist_roll_.*"],  # 10
            effort_limit_sim=25,
            velocity_limit_sim=37,
            stiffness=40.0,
            damping=1.0,
            armature=0.01,
        ),
        "N5020-16-parallel": ImplicitActuatorCfg(
            joint_names_expr=[".*ankle.*"],  # 4
            effort_limit_sim=35,
            velocity_limit_sim=30,
            stiffness=40.0,
            damping=2.0,
            armature=0.01,
        ),
    },
    joint_sdk_names=[
        "left_hip_pitch_joint",
        "left_hip_roll_joint",
        "left_hip_yaw_joint",
        "left_knee_joint",
        "left_ankle_pitch_joint",
        "left_ankle_roll_joint",
        "right_hip_pitch_joint",
        "right_hip_roll_joint",
        "right_hip_yaw_joint",
        "right_knee_joint",
        "right_ankle_pitch_joint",
        "right_ankle_roll_joint",
        "waist_yaw_joint",
        "",
        "",
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
        "left_wrist_roll_joint",
        "",
        "",
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "right_wrist_roll_joint",
    ],
)

UNITREE_G1_29DOF_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/g1_description/g1_29dof_rev_1_0.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/G1/29dof/usd/g1_29dof_rev_1_0/g1_29dof_rev_1_0.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.8),
        joint_pos={
            "left_hip_pitch_joint": -0.1,
            "right_hip_pitch_joint": -0.1,
            ".*_knee_joint": 0.3,
            ".*_ankle_pitch_joint": -0.2,
            ".*_shoulder_pitch_joint": 0.3,
            "left_shoulder_roll_joint": 0.25,
            "right_shoulder_roll_joint": -0.25,
            ".*_elbow_joint": 0.97,
            "left_wrist_roll_joint": 0.15,
            "right_wrist_roll_joint": -0.15,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "N7520-14.3": ImplicitActuatorCfg(
            joint_names_expr=[".*_hip_pitch_.*", ".*_hip_yaw_.*", "waist_yaw_joint"],
            effort_limit_sim=88,
            velocity_limit_sim=32.0,
            stiffness={
                ".*_hip_.*": 100.0,
                "waist_yaw_joint": 200.0,
            },
            damping={
                ".*_hip_.*": 2.0,
                "waist_yaw_joint": 5.0,
            },
            armature=0.01,
        ),
        "N7520-22.5": ImplicitActuatorCfg(
            joint_names_expr=[".*_hip_roll_.*", ".*_knee_.*"],
            effort_limit_sim=139,
            velocity_limit_sim=20.0,
            stiffness={
                ".*_hip_roll_.*": 100.0,
                ".*_knee_.*": 150.0,
            },
            damping={
                ".*_hip_roll_.*": 2.0,
                ".*_knee_.*": 4.0,
            },
            armature=0.01,
        ),
        "N5020-16": ImplicitActuatorCfg(
            joint_names_expr=[
                ".*_shoulder_.*",
                ".*_elbow_.*",
                ".*_wrist_roll.*",
                ".*_ankle_.*",
                "waist_roll_joint",
                "waist_pitch_joint",
            ],
            effort_limit_sim=25,
            velocity_limit_sim=37,
            stiffness=40.0,
            damping={
                ".*_shoulder_.*": 1.0,
                ".*_elbow_.*": 1.0,
                ".*_wrist_roll.*": 1.0,
                ".*_ankle_.*": 2.0,
                "waist_.*_joint": 5.0,
            },
            armature=0.01,
        ),
        "W4010-25": ImplicitActuatorCfg(
            joint_names_expr=[".*_wrist_pitch.*", ".*_wrist_yaw.*"],
            effort_limit_sim=5,
            velocity_limit_sim=22,
            stiffness=40.0,
            damping=1.0,
            armature=0.01,
        ),
    },
    joint_sdk_names=[
        "left_hip_pitch_joint",
        "left_hip_roll_joint",
        "left_hip_yaw_joint",
        "left_knee_joint",
        "left_ankle_pitch_joint",
        "left_ankle_roll_joint",
        "right_hip_pitch_joint",
        "right_hip_roll_joint",
        "right_hip_yaw_joint",
        "right_knee_joint",
        "right_ankle_pitch_joint",
        "right_ankle_roll_joint",
        "waist_yaw_joint",
        "waist_roll_joint",
        "waist_pitch_joint",
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
        "left_wrist_roll_joint",
        "left_wrist_pitch_joint",
        "left_wrist_yaw_joint",
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "right_wrist_roll_joint",
        "right_wrist_pitch_joint",
        "right_wrist_yaw_joint",
    ],
)


ARMATURE_5020 = 0.003609725
ARMATURE_7520_14 = 0.010177520
ARMATURE_7520_22 = 0.025101925
ARMATURE_4010 = 0.00425

NATURAL_FREQ = 10 * 2.0 * 3.1415926535  # 10Hz
DAMPING_RATIO = 2.0

STIFFNESS_5020 = ARMATURE_5020 * NATURAL_FREQ**2  # 14.25062309787429
STIFFNESS_7520_14 = ARMATURE_7520_14 * NATURAL_FREQ**2  # 40.17923847137318
STIFFNESS_7520_22 = ARMATURE_7520_22 * NATURAL_FREQ**2  # 99.09842777666113
STIFFNESS_4010 = ARMATURE_4010 * NATURAL_FREQ**2  # 16.77832748089279

DAMPING_5020 = 2.0 * DAMPING_RATIO * ARMATURE_5020 * NATURAL_FREQ  # 0.907222843292423
DAMPING_7520_14 = 2.0 * DAMPING_RATIO * ARMATURE_7520_14 * NATURAL_FREQ  # 2.5578897650279457
DAMPING_7520_22 = 2.0 * DAMPING_RATIO * ARMATURE_7520_22 * NATURAL_FREQ  # 6.3088018534966395
DAMPING_4010 = 2.0 * DAMPING_RATIO * ARMATURE_4010 * NATURAL_FREQ  # 1.06814150219

UNITREE_G1_29DOF_MIMIC_CFG = UnitreeArticulationCfg(
    # spawn=UnitreeUrdfFileCfg(
    #     asset_path=f"{UNITREE_ROS_DIR}/robots/g1_description/g1_29dof_rev_1_0.urdf",
    # ),
    spawn=UnitreeUsdFileCfg(
        usd_path=f"{UNITREE_MODEL_DIR}/G1/29dof/usd/g1_29dof_rev_1_0/g1_29dof_rev_1_0.usd",
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.76),
        joint_pos={
            ".*_hip_pitch_joint": -0.312,
            ".*_knee_joint": 0.669,
            ".*_ankle_pitch_joint": -0.363,
            ".*_elbow_joint": 0.6,
            "left_shoulder_roll_joint": 0.2,
            "left_shoulder_pitch_joint": 0.2,
            "right_shoulder_roll_joint": -0.2,
            "right_shoulder_pitch_joint": 0.2,
        },
        joint_vel={".*": 0.0},
    ),
    soft_joint_pos_limit_factor=0.9,
    actuators={
        "legs": ImplicitActuatorCfg(
            joint_names_expr=[
                ".*_hip_yaw_joint",
                ".*_hip_roll_joint",
                ".*_hip_pitch_joint",
                ".*_knee_joint",
            ],
            effort_limit_sim={
                ".*_hip_yaw_joint": 88.0,
                ".*_hip_roll_joint": 139.0,
                ".*_hip_pitch_joint": 88.0,
                ".*_knee_joint": 139.0,
            },
            velocity_limit_sim={
                ".*_hip_yaw_joint": 32.0,
                ".*_hip_roll_joint": 20.0,
                ".*_hip_pitch_joint": 32.0,
                ".*_knee_joint": 20.0,
            },
            stiffness={
                ".*_hip_pitch_joint": STIFFNESS_7520_14,
                ".*_hip_roll_joint": STIFFNESS_7520_22,
                ".*_hip_yaw_joint": STIFFNESS_7520_14,
                ".*_knee_joint": STIFFNESS_7520_22,
            },
            damping={
                ".*_hip_pitch_joint": DAMPING_7520_14,
                ".*_hip_roll_joint": DAMPING_7520_22,
                ".*_hip_yaw_joint": DAMPING_7520_14,
                ".*_knee_joint": DAMPING_7520_22,
            },
            armature={
                ".*_hip_pitch_joint": ARMATURE_7520_14,
                ".*_hip_roll_joint": ARMATURE_7520_22,
                ".*_hip_yaw_joint": ARMATURE_7520_14,
                ".*_knee_joint": ARMATURE_7520_22,
            },
        ),
        "feet": ImplicitActuatorCfg(
            effort_limit_sim=50.0,
            velocity_limit_sim=37.0,
            joint_names_expr=[".*_ankle_pitch_joint", ".*_ankle_roll_joint"],
            stiffness=2.0 * STIFFNESS_5020,
            damping=2.0 * DAMPING_5020,
            armature=2.0 * ARMATURE_5020,
        ),
        "waist": ImplicitActuatorCfg(
            effort_limit_sim=50,
            velocity_limit_sim=37.0,
            joint_names_expr=["waist_roll_joint", "waist_pitch_joint"],
            stiffness=2.0 * STIFFNESS_5020,
            damping=2.0 * DAMPING_5020,
            armature=2.0 * ARMATURE_5020,
        ),
        "waist_yaw": ImplicitActuatorCfg(
            effort_limit_sim=88,
            velocity_limit_sim=32.0,
            joint_names_expr=["waist_yaw_joint"],
            stiffness=STIFFNESS_7520_14,
            damping=DAMPING_7520_14,
            armature=ARMATURE_7520_14,
        ),
        "arms": ImplicitActuatorCfg(
            joint_names_expr=[
                ".*_shoulder_pitch_joint",
                ".*_shoulder_roll_joint",
                ".*_shoulder_yaw_joint",
                ".*_elbow_joint",
                ".*_wrist_roll_joint",
                ".*_wrist_pitch_joint",
                ".*_wrist_yaw_joint",
            ],
            effort_limit_sim={
                ".*_shoulder_pitch_joint": 25.0,
                ".*_shoulder_roll_joint": 25.0,
                ".*_shoulder_yaw_joint": 25.0,
                ".*_elbow_joint": 25.0,
                ".*_wrist_roll_joint": 25.0,
                ".*_wrist_pitch_joint": 5.0,
                ".*_wrist_yaw_joint": 5.0,
            },
            velocity_limit_sim={
                ".*_shoulder_pitch_joint": 37.0,
                ".*_shoulder_roll_joint": 37.0,
                ".*_shoulder_yaw_joint": 37.0,
                ".*_elbow_joint": 37.0,
                ".*_wrist_roll_joint": 37.0,
                ".*_wrist_pitch_joint": 22.0,
                ".*_wrist_yaw_joint": 22.0,
            },
            stiffness={
                ".*_shoulder_pitch_joint": STIFFNESS_5020,
                ".*_shoulder_roll_joint": STIFFNESS_5020,
                ".*_shoulder_yaw_joint": STIFFNESS_5020,
                ".*_elbow_joint": STIFFNESS_5020,
                ".*_wrist_roll_joint": STIFFNESS_5020,
                ".*_wrist_pitch_joint": STIFFNESS_4010,
                ".*_wrist_yaw_joint": STIFFNESS_4010,
            },
            damping={
                ".*_shoulder_pitch_joint": DAMPING_5020,
                ".*_shoulder_roll_joint": DAMPING_5020,
                ".*_shoulder_yaw_joint": DAMPING_5020,
                ".*_elbow_joint": DAMPING_5020,
                ".*_wrist_roll_joint": DAMPING_5020,
                ".*_wrist_pitch_joint": DAMPING_4010,
                ".*_wrist_yaw_joint": DAMPING_4010,
            },
            armature={
                ".*_shoulder_pitch_joint": ARMATURE_5020,
                ".*_shoulder_roll_joint": ARMATURE_5020,
                ".*_shoulder_yaw_joint": ARMATURE_5020,
                ".*_elbow_joint": ARMATURE_5020,
                ".*_wrist_roll_joint": ARMATURE_5020,
                ".*_wrist_pitch_joint": ARMATURE_4010,
                ".*_wrist_yaw_joint": ARMATURE_4010,
            },
        ),
    },
    joint_sdk_names=[
        "left_hip_pitch_joint",
        "left_hip_roll_joint",
        "left_hip_yaw_joint",
        "left_knee_joint",
        "left_ankle_pitch_joint",
        "left_ankle_roll_joint",
        "right_hip_pitch_joint",
        "right_hip_roll_joint",
        "right_hip_yaw_joint",
        "right_knee_joint",
        "right_ankle_pitch_joint",
        "right_ankle_roll_joint",
        "waist_yaw_joint",
        "waist_roll_joint",
        "waist_pitch_joint",
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
        "left_wrist_roll_joint",
        "left_wrist_pitch_joint",
        "left_wrist_yaw_joint",
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "right_wrist_roll_joint",
        "right_wrist_pitch_joint",
        "right_wrist_yaw_joint",
    ],
)

UNITREE_G1_29DOF_MIMIC_ACTION_SCALE = {}
for a in UNITREE_G1_29DOF_MIMIC_CFG.actuators.values():
    e = a.effort_limit_sim
    s = a.stiffness
    names = a.joint_names_expr
    if not isinstance(e, dict):
        e = {n: e for n in names}
    if not isinstance(s, dict):
        s = {n: s for n in names}
    for n in names:
        if n in e and n in s and s[n]:
            UNITREE_G1_29DOF_MIMIC_ACTION_SCALE[n] = 0.25 * e[n] / s[n]


""" Configuration for the Geesun dog (dog1) quadruped robot."""

# GEESUN_DOG_DIR = f"{UNITREE_MODEL_DIR}/geesun_dog/geesun-dog/dog1"  # not available in UNITREE_MODEL_DIR
_GEESUN_REPO_ROOT = (
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
)
# The updated dog asset (9/21 "dog921" export with real meshes and joint limits) lives in
# <repo>/geesun_dog_urdf; the legacy <repo>/unitree_model/geesun_dog location is kept as a
# fallback so ablation runs against the old dog1 URDF keep working.
_GEESEN_DOG_CANDIDATES = [
    os.path.join(_GEESUN_REPO_ROOT, "geesun_dog_urdf"),
    os.path.join(_GEESUN_REPO_ROOT, "unitree_model", "geesun_dog"),
]
GEESUN_DOG_DIR = next((d for d in _GEESEN_DOG_CANDIDATES if os.path.isdir(d)), _GEESEN_DOG_CANDIDATES[0])

# Robot asset variant = sub-directory under <GEESUN_DOG_DIR>/geesun-dog/. "dog1" (default)
# keeps the legacy temp paths and behaviour byte-identical for ablation runs; other variants
# (e.g. "lingsi_d30w") get their own per-variant temp area so their URDF/USD never collide
# with dog1's. Select via the GEESUN_DOG_VARIANT environment variable before import
# (scripts/geesun_dog/move_geesun_dog.py --variant does this).
GEESUN_DOG_VARIANT = os.environ.get("GEESUN_DOG_VARIANT", "dog1")


def _geesun_dog_temp_paths() -> tuple:
    """Return (temp_pkg_dir, temp_urdf_path, usd_path) for the active variant."""
    if GEESUN_DOG_VARIANT == "dog1":
        return "/tmp/IsaacLab/geesun_dog", "/tmp/IsaacLab/geesun_dog/dog1.urdf", "/tmp/IsaacLab/geesun_dog/dog1.usd"
    base = f"/tmp/IsaacLab/geesun_dog/{GEESUN_DOG_VARIANT}"
    return base, f"{base}/{GEESUN_DOG_VARIANT}.urdf", f"{base}/{GEESUN_DOG_VARIANT}.usd"


def _write_placeholder_cylinder_stl(path: str, radius: float, length: float, segments: int = 24) -> None:
    """Write a binary STL cylinder along the X axis (used to replace broken/empty meshes).

    The original ``Link_*_hip.STL`` files exported from SolidWorks are empty (80-byte header
    with zero triangles), which crashes Isaac Sim's URDF importer. We generate a simple
    cylinder (approximating the hip motor housing) as a placeholder so the model imports.
    """
    import math
    import struct

    tris = []
    half = length * 0.5

    def tri(p0, p1, p2, n):
        tris.append((n, p0, p1, p2))

    # side wall
    for i in range(segments):
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments
        x0, x1 = -half, half
        p00 = (x0, radius * math.cos(a0), radius * math.sin(a0))
        p01 = (x0, radius * math.cos(a1), radius * math.sin(a1))
        p10 = (x1, radius * math.cos(a0), radius * math.sin(a0))
        p11 = (x1, radius * math.cos(a1), radius * math.sin(a1))
        n0 = (0.0, math.cos(a0), math.sin(a0))
        n1 = (0.0, math.cos(a1), math.sin(a1))
        nm = (0.0, math.cos(0.5 * (a0 + a1)), math.sin(0.5 * (a0 + a1)))
        tri(p00, p11, p01, n1)
        tri(p00, p10, p11, nm)
        # caps
        cap0 = (-1.0, 0.0, 0.0)
        cap1 = (1.0, 0.0, 0.0)
        tri((x0, 0.0, 0.0), p01, p00, cap0)
        tri((x1, 0.0, 0.0), p10, p11, cap1)

    with open(path, "wb") as f:
        f.write(b"placeholder hip cylinder" + b" " * (80 - len(b"placeholder hip cylinder")))
        f.write(struct.pack("<I", len(tris)))
        for n, p0, p1, p2 in tris:
            f.write(struct.pack("<3f", *n))
            f.write(struct.pack("<3f", *p0))
            f.write(struct.pack("<3f", *p1))
            f.write(struct.pack("<3f", *p2))
            f.write(struct.pack("<H", 0))


def _prepare_geesun_dog_urdf() -> None:
    """Create a temporary URDF copy with fixed mesh paths, joint limits and placeholder meshes.

    The dog URDF references meshes via ``package://dog1/meshes/...`` which Isaac Sim's URDF importer
    cannot resolve, and the four ``Link_*_hip.STL`` files are empty (80-byte header, zero triangles)
    which makes the URDF importer crash. We create a fixed copy of the URDF in a temp directory:
    all mesh references use absolute paths, and the empty hip meshes are replaced by generated
    placeholder cylinders.

    Layout::

        /tmp/IsaacLab/geesun_dog/dog1.urdf                  (copy with rewritten references)
        /tmp/IsaacLab/geesun_dog/meshes/Link_*_hip.STL      (generated placeholder cylinders)

    The original asset is never modified.
    """
    import re
    import shutil
    import glob

    tmp_pkg_dir, dst_urdf, _ = _geesun_dog_temp_paths()
    if GEESUN_DOG_VARIANT == "dog1":
        tmp_mesh_dir = f"{tmp_pkg_dir}/meshes"
        dog_pkg_dir = f"{GEESUN_DOG_DIR}/geesun-dog/dog1"
        # Prefer the updated dog921 export (real meshes and joint limits); fall back to the
        # legacy dog1 URDF so ablation runs against the old asset keep working.
        src_urdf = f"{dog_pkg_dir}/urdf/dog921.urdf"
        if not os.path.isfile(src_urdf):
            src_urdf = f"{dog_pkg_dir}/urdf/dog1.urdf"
        if not os.path.isfile(src_urdf):
            return
        os.makedirs(tmp_mesh_dir, exist_ok=True)
        has_real_limits = os.path.basename(src_urdf) == "dog921.urdf"
    else:
        # Other variants (e.g. lingsi_d30w, generated from the STEP export) carry absolute
        # mesh paths and their own joint limits; stage whichever URDF the variant dir holds.
        dog_pkg_dir = f"{GEESUN_DOG_DIR}/geesun-dog/{GEESUN_DOG_VARIANT}"
        candidates = sorted(glob.glob(f"{dog_pkg_dir}/urdf/*.urdf")) + sorted(
            glob.glob(f"{dog_pkg_dir}/*.urdf")
        )
        src_urdf = candidates[0] if candidates else ""
        if not src_urdf:
            return
        tmp_mesh_dir = f"{tmp_pkg_dir}/meshes"  # shared fixup loop below stays safe
        has_real_limits = True

    # Handle both the legacy (Link_*) and updated (link_*) hip mesh name variants: the
    # legacy export ships empty meshes (80-byte header, zero triangles) which are replaced
    # by generated placeholder cylinders; the dog921 meshes are real and get copied.
    empty_hip_meshes = [f"{prefix}_{side}_hip.STL" for side in ("fr", "fl", "hl", "hr") for prefix in ("Link", "link")]
    for name in empty_hip_meshes:
        src_mesh = f"{dog_pkg_dir}/meshes/{name}"
        dst_mesh = f"{tmp_mesh_dir}/{name}"
        if not os.path.exists(src_mesh):
            continue
        if os.path.getsize(src_mesh) <= 84:
            _write_placeholder_cylinder_stl(dst_mesh, radius=0.035, length=0.08)
        else:
            shutil.copyfile(src_mesh, dst_mesh)

    with open(src_urdf, "r") as f:
        content = f.read()

    # Replace package://dog{1,921}/meshes/FILE with an absolute path to the real meshes dir,
    # except for the empty hip meshes which point to the generated placeholders.
    meshes_abs = os.path.abspath(f"{dog_pkg_dir}/meshes")
    content = re.sub(r"package://(?:dog1|dog921)/meshes/", f"{meshes_abs}/", content)
    for name in empty_hip_meshes:
        content = content.replace(f"{meshes_abs}/{name}", f"{tmp_mesh_dir}/{name}")

    # The legacy dog1 export has zeroed / too-tight joint limits (SolidWorks export default),
    # so they are replaced with reasonable ranges that let the robot actually move.
    # The updated dog921 export carries real joint limits, which we keep as-is.
    if not has_real_limits:
        content = re.sub(
            r'(<joint\s+name="joint_fr_thigh".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-2.0"{m.group(2)}"2.5"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_fl_thigh".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-2.0"{m.group(2)}"2.5"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_hl_thigh".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-2.5"{m.group(2)}"2.0"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_hr_thigh".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-2.5"{m.group(2)}"2.0"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_fr_calf".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-2.5"{m.group(2)}"0.5"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_fl_calf".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-2.5"{m.group(2)}"0.5"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_hl_calf".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-0.5"{m.group(2)}"2.5"',
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'(<joint\s+name="joint_hr_calf".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
            lambda m: f'{m.group(1)}"-0.5"{m.group(2)}"2.5"',
            content,
            flags=re.DOTALL,
        )
        # Hip joints (all 4): symmetric range
        for hip in ["joint_fr_hip", "joint_fl_hip", "joint_hr_hip", "joint_hl_hip"]:
            content = re.sub(
                rf'(<joint\s+name="{hip}".*?lower=)"[^"]*"(\s+upper=)"[^"]*"',
                lambda m: f'{m.group(1)}"-0.8"{m.group(2)}"0.8"',
                content,
                flags=re.DOTALL,
            )

    # Also set non-zero effort/velocity limits so the URDF is well-formed
    content = re.sub(r'effort="0"\s+velocity="0"', 'effort="100" velocity="25"', content)

    # Skip writing if the temp URDF is already up-to-date (keeps the URDF stable between
    # imports; the USD conversion itself is forced on every launch via ensure_geesun_dog_usd).
    if os.path.exists(dst_urdf):
        with open(dst_urdf, "r") as f:
            if f.read() == content:
                return
    os.makedirs(os.path.dirname(dst_urdf), exist_ok=True)
    with open(dst_urdf, "w") as f:
        f.write(content)



_prepare_geesun_dog_urdf()

# Converted USD asset (rebuilt by any caller via `ensure_geesun_dog_usd()`, which always
# re-converts from the fixed URDF). Converting the URDF during scene creation
# (UrdfFileCfg spawn) deadlocks inside the URDF importer on this setup, so the scene spawns
# from the freshly converted USD instead. Paths follow the active GEESUN_DOG_VARIANT.
GEESUN_DOG_TMP_DIR, GEESUN_DOG_TMP_URDF, GEESUN_DOG_USD = _geesun_dog_temp_paths()


def ensure_geesun_dog_usd() -> str:
    """Convert the Geesun dog URDF to USD, always rebuilding from the current source files.

    The fixed URDF (regenerated from ``geesun_dog_urdf/geesun-dog/<GEESUN_DOG_VARIANT>`` at
    import time; "dog1" by default) is converted on every call with
    ``force_usd_conversion=True``: no mtime/asset-hash cache, so any update under the variant
    source dir (URDF text or meshes) is picked up without deleting the temp area. (The
    converter's built-in lazy hash only covers the URDF text and would miss mesh-only
    updates.) Costs ~5-10 s per launch.

    Returns:
        The path to the converted USD file.
    """
    urdf_path = GEESUN_DOG_TMP_URDF
    if not os.path.isfile(urdf_path):
        raise FileNotFoundError(
            f"Geesun dog URDF is unavailable for variant '{GEESUN_DOG_VARIANT}': expected source "
            f"under {os.path.join(GEESUN_DOG_DIR, 'geesun-dog', GEESUN_DOG_VARIANT)}"
        )

    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg

    converter = UrdfConverter(
        UrdfConverterCfg(
            asset_path=urdf_path,
            usd_dir=os.path.dirname(GEESUN_DOG_USD),
            usd_file_name=os.path.splitext(os.path.basename(GEESUN_DOG_USD))[0],
            force_usd_conversion=True,  # no cache: rebuild the USD from the current source files every time
            make_instanceable=True,
            fix_base=False,
            joint_drive=sim_utils.UrdfConverterCfg.JointDriveCfg(
                gains=sim_utils.UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0, damping=0)
            ),
        )
    )
    return converter.usd_path


GEESUN_DOG_CFG = UnitreeArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=GEESUN_DOG_USD,
        activate_contact_sensors=True,
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=True,
            solver_position_iteration_count=8,
            solver_velocity_iteration_count=4,
        ),
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=1000.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        # Measured standing height: in the standing pose the foot-plate bottom is 0.166 m
        # below the base origin (see README, Geesun 站立姿态验证); 0.17 leaves ~4 mm clearance.
        pos=(0.0, 0.0, 0.17),
        joint_pos={
            # front legs (fr/fl): thigh forward (+), calf backward (-)
            "joint_fr_thigh": 1.0,
            "joint_fl_thigh": 1.0,
            "joint_fr_calf": -1.4,
            "joint_fl_calf": -1.4,
            # rear legs (hl/hr): thigh +1.0 (same sign as the front legs). Measured against
            # the dog921 foot-plate mesh, +1.0 puts all four feet at the same height
            # (0.166 m below the base) - the natural standing stance. The legacy -1.0
            # stance lifts the rear feet ~2.5 cm and leaves the rear foot plate vertical
            # (the dog "sits" on its front paws and tips backwards).
            # Calf -1.4 stays inside the real dog921 limit range [-1.885, 0]
            # (the legacy +1.4 pose exceeded upper=0).
            "joint_hl_thigh": 1.0,
            "joint_hr_thigh": 1.0,
            "joint_hl_calf": -1.4,
            "joint_hr_calf": -1.4,
        },
        joint_vel={"joint_.*": 0.0},
    ),
    actuators={
        "GeEsunDog": unitree_actuators.UnitreeActuatorCfg_GeesunDog(
            joint_names_expr=["joint_.*"],
            stiffness=30.0,
            damping=1.0,
            friction=0.02,
        ),
    },
    # fmt: off
    joint_sdk_names=[
        "joint_fr_hip", "joint_fr_thigh", "joint_fr_calf",
        "joint_fl_hip", "joint_fl_thigh", "joint_fl_calf",
        "joint_hr_hip", "joint_hr_thigh", "joint_hr_calf",
        "joint_hl_hip", "joint_hl_thigh", "joint_hl_calf",
    ],
    # fmt: on
)

from __future__ import annotations

import torch
from dataclasses import MISSING

from isaaclab.actuators import DelayedPDActuator, DelayedPDActuatorCfg
from isaaclab.utils import configclass
from isaaclab.utils.types import ArticulationActions


class UnitreeActuator(DelayedPDActuator):
    """Unitree actuator class that implements a torque-speed curve for the actuators.

    The torque-speed curve is defined as follows:

            Torque Limit, N·m
                ^
    Y2──────────|
                |──────────────Y1
                |              │\
                |              │ \
                |              │  \
                |              |   \
    ------------+--------------|------> velocity: rad/s
                              X1   X2

    - Y1: Peak Torque Test (Torque and Speed in the Same Direction)
    - Y2: Peak Torque Test (Torque and Speed in the Opposite Direction)
    - X1: Maximum Speed at Full Torque (T-N Curve Knee Point)
    - X2: No-Load Speed Test

    - Fs: Static friction coefficient
    - Fd: Dynamic friction coefficient
    - Va: Velocity at which the friction is fully activated
    """

    cfg: UnitreeActuatorCfg

    armature: torch.Tensor
    """The armature of the actuator joints. Shape is (num_envs, num_joints).
        armature = J2 + J1 * i2 ^ 2 + Jr * (i1 * i2) ^ 2
    """

    def __init__(self, cfg: UnitreeActuatorCfg, *args, **kwargs):
        super().__init__(cfg, *args, **kwargs)

        self._joint_vel = torch.zeros_like(self.computed_effort)
        self._effort_y1 = self._parse_joint_parameter(cfg.Y1, 1e9)
        self._effort_y2 = self._parse_joint_parameter(cfg.Y2, cfg.Y1)
        self._velocity_x1 = self._parse_joint_parameter(cfg.X1, 1e9)
        self._velocity_x2 = self._parse_joint_parameter(cfg.X2, 1e9)
        self._friction_static = self._parse_joint_parameter(cfg.Fs, 0.0)
        self._friction_dynamic = self._parse_joint_parameter(cfg.Fd, 0.0)
        self._activation_vel = self._parse_joint_parameter(cfg.Va, 0.01)

    def compute(
        self, control_action: ArticulationActions, joint_pos: torch.Tensor, joint_vel: torch.Tensor
    ) -> ArticulationActions:
        # save current joint vel
        self._joint_vel[:] = joint_vel
        # calculate the desired joint torques
        control_action = super().compute(control_action, joint_pos, joint_vel)

        # apply friction model on the torque
        self.applied_effort -= (
            self._friction_static * torch.tanh(joint_vel / self._activation_vel) + self._friction_dynamic * joint_vel
        )

        control_action.joint_positions = None
        control_action.joint_velocities = None
        control_action.joint_efforts = self.applied_effort

        return control_action

    def _clip_effort(self, effort: torch.Tensor) -> torch.Tensor:
        # check if the effort is the same direction as the joint velocity
        same_direction = (self._joint_vel * effort) > 0
        max_effort = torch.where(same_direction, self._effort_y1, self._effort_y2)
        # check if the joint velocity is less than the max speed at full torque
        max_effort = torch.where(
            self._joint_vel.abs() < self._velocity_x1, max_effort, self._compute_effort_limit(max_effort)
        )
        return torch.clip(effort, -max_effort, max_effort)

    def _compute_effort_limit(self, max_effort):
        k = -max_effort / (self._velocity_x2 - self._velocity_x1)
        limit = k * (self._joint_vel.abs() - self._velocity_x1) + max_effort
        return limit.clip(min=0.0)


@configclass
class UnitreeActuatorCfg(DelayedPDActuatorCfg):
    """
    Configuration for Unitree actuators.
    """

    class_type: type = UnitreeActuator

    X1: float = 1e9
    """Maximum Speed at Full Torque(T-N Curve Knee Point) Unit: rad/s"""

    X2: float = 1e9
    """No-Load Speed Test Unit: rad/s"""

    Y1: float = MISSING
    """Peak Torque Test(Torque and Speed in the Same Direction) Unit: N*m"""

    Y2: float | None = None
    """Peak Torque Test(Torque and Speed in the Opposite Direction) Unit: N*m"""

    Fs: float = 0.0
    """ Static friction coefficient """

    Fd: float = 0.0
    """ Dynamic friction coefficient """

    Va: float = 0.01
    """ Velocity at which the friction is fully activated """


@configclass
class UnitreeActuatorCfg_M107_15(UnitreeActuatorCfg):
    X1 = 14.0
    X2 = 25.6
    Y1 = 150.0
    Y2 = 182.8

    armature = 0.063259741


@configclass
class UnitreeActuatorCfg_M107_24(UnitreeActuatorCfg):
    X1 = 8.8
    X2 = 16
    Y1 = 240
    Y2 = 292.5

    armature = 0.160478022


@configclass
class UnitreeActuatorCfg_Go2HV(UnitreeActuatorCfg):
    X1 = 13.5
    X2 = 30
    Y1 = 20.2
    Y2 = 23.4


@configclass
class UnitreeActuatorCfg_N7520_14p3(UnitreeActuatorCfg):
    # Decimal point cannot be used as variable name, use `p` instead
    X1 = 22.63
    X2 = 35.52
    Y1 = 71
    Y2 = 83.3

    Fs = 1.6
    Fd = 0.16

    """
    | rotor  | 0.489e-4 kg·m²
    | gear_1 | 0.098e-4 kg·m² | ratio | 4.5
    | gear_2 | 0.533e-4 kg·m² | ratio | 48/22+1
    """
    armature = 0.01017752


@configclass
class UnitreeActuatorCfg_N7520_22p5(UnitreeActuatorCfg):
    # Decimal point cannot be used as variable name, use `p` instead
    X1 = 14.5
    X2 = 22.7
    Y1 = 111.0
    Y2 = 131.0

    Fs = 2.4
    Fd = 0.24

    """
    | rotor  | 0.489e-4 kg·m²
    | gear_1 | 0.109e-4 kg·m² | ratio | 4.5
    | gear_2 | 0.738e-4 kg·m² | ratio | 5.0
    """
    armature = 0.025101925


@configclass
class UnitreeActuatorCfg_N5010_16(UnitreeActuatorCfg):
    X1 = 27.0
    X2 = 41.5
    Y1 = 9.5
    Y2 = 17.0

    """
    | rotor  | 0.084e-4 kg·m²
    | gear_1 | 0.015e-4 kg·m² | ratio | 4
    | gear_2 | 0.068e-4 kg·m² | ratio | 4
    """
    armature = 0.0021812


@configclass
class UnitreeActuatorCfg_N5020_16(UnitreeActuatorCfg):
    X1 = 30.86
    X2 = 40.13
    Y1 = 24.8
    Y2 = 31.9

    Fs = 0.6
    Fd = 0.06

    """
    | rotor  | 0.139e-4 kg·m²
    | gear_1 | 0.017e-4 kg·m² | ratio | 46/18+1
    | gear_2 | 0.169e-4 kg·m² | ratio | 56/16+1
    """
    armature = 0.003609725


@configclass
class UnitreeActuatorCfg_W4010_25(UnitreeActuatorCfg):
    X1 = 15.3
    X2 = 24.76
    Y1 = 4.8
    Y2 = 8.6

    Fs = 0.6
    Fd = 0.06

    """
    | rotor  | 0.068e-4 kg·m²
    | gear_1 |                | ratio | 5
    | gear_2 |                | ratio | 5
    """
    armature = 0.00425


@configclass
class UnitreeActuatorCfg_D30W(UnitreeActuatorCfg):
    """Self-contained actuator + PD parameter set for the lingsi_d30w wheel-legged variant.

    Values from the vendor sheet `geesun_dog_urdf/geesun-dog/lingsi_d30w/urdf/D30W关节电气参数.xlsx`
    (output-side parameters "输出端参数"): LS100_WLA/WLH (hip/thigh) 120 N*m / 40 rad/s,
    LS100_WLK (calf) 200 N*m / 20 rad/s, LS75_WL (wheel) 14 N*m / 65 rad/s, KP max 500 /
    KD max 5 (PD-gain upper bounds, output-side; the actual gains below are chosen inside
    this envelope for numerical stability - see the fields). The sheet gives max ratings but
    no torque-speed knee point, so X1 is placed at half the max speed (full torque below X1,
    linear derating to X2) - conservative. Defaults below = LS100_WLH (thigh/hip); the calf
    and wheel groups override X/Y at instance level in unitree.py. Isolated from GO2/dog1
    parameter sets.
    """

    # torque-speed curve (N*m, rad/s) - LS100_WLA/WLH default
    X1 = 20.0
    X2 = 40.0
    Y1 = 120.0
    Y2 = 120.0
    # friction model (not specified by the vendor sheet)
    Fs = 0.0
    Fd = 0.0
    Va = 0.01
    # rotor inertia (not in the sheet)
    armature = 0.0
    # PD gains: the sheet gives KP max 500 / KD max 5 (upper bounds, output-side). Gains are
    # picked INSIDE that envelope for numerical stability of the explicit-PD actuator at the
    # 5 ms physics step: the vendor maxima are deep in the negative-damping zone for these
    # small joint inertias (b*dt/J >~ 2 -> exponential blow-up measured from a still start;
    # KD=5 reproduced it, KD=2 did not). 100/2 keeps the leg joints in a measured-stable band
    # (air PD tracking holds the stance to 0.001 rad; ground stand test holds 2 s with <1 cm
    # sag). See README "lingsi_d30w PD 参数" for the tuning record.
    stiffness = 100.0
    damping = 2.0
    friction = 0.0


@configclass
class UnitreeActuatorCfg_GeesunDog(UnitreeActuatorCfg):
    """Self-contained actuator + PD parameter set for the Geesun dog (dog1).

    Isolation contract (2026-10-12): every field is declared explicitly here, so editing
    GeesunDog parameters can never affect GO2/H1/G1 (and vice versa: editing Go2HV or the
    shared UnitreeActuatorCfg base cannot change GeesunDog). The PD gains
    (stiffness/damping/friction) live here too - unitree.py just passes joint names.

    Values were originally derived by linear mass scaling from GO2 (whose parameters are the
    verified ones): r = m_dog1 / m_go2 = 41.4172 kg (dog921.urdf link masses) / 15.0 kg
    (GO2 spec) = 2.7611 -> Y1/Y2 = 20.2/23.4 x r, k/b/friction = 25/0.5/0.01 x r. Speed
    limits X1/X2 are motor properties and stay at GO2's 13.5/30 rad/s. Replace with real
    specs when available.
    """

    # torque-speed curve (N*m, rad/s)
    X1 = 13.5
    X2 = 30.0
    Y1 = 55.8
    Y2 = 64.6
    # friction model
    Fs = 0.0
    Fd = 0.0
    Va = 0.01
    # rotor inertia (no real spec yet)
    armature = 0.0
    # PD gains (position servo)
    stiffness = 69.0
    damping = 1.38
    friction = 0.028

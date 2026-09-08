# RL 的输出是什么？如何给到 PD 控制？

结合本仓库（G1 29dof / GO2 velocity 任务）的实际代码，结论如下：

## 一、RL（actor 网络）的输出

__输出是"目标关节位置角"的增量（无量纲动作），不是力矩。__

以 G1 为例（`source/.../tasks/locomotion/robots/g1/29dof/velocity_env_cfg.py` 约 L183-187）：

```python
class ActionsCfg:
    JointPositionAction = mdp.JointPositionActionCfg(
        asset_name="robot", joint_names=[".*"], scale=0.25, use_default_offset=True
    )
```

actor 网络输出 __29 个动作值__（每个关节一个，原始值大致在 [-1, 1]），含义是"相对默认站姿的关节角偏移量"。网络本身不直接输出力矩、速度或位置绝对值——它只学"该往哪偏、偏多少"。

## 二、从网络输出到 PD 目标位置的映射

仿真侧（IsaacLab）和部署侧（`deploy/` C++）用的是同一套 `scale + offset` 变换：

```javascript
target_pos[i] = raw_action[i] * scale[i] + offset[i]     （可选 clip）
```

- __offset__ = 默认关节位置（`use_default_offset=True`，即站立构型，如髋 pitch -0.1、膝 0.3、踝 -0.25 …），对应 `deploy.yaml` 里的 `actions.JointPositionAction.offset / default_joint_pos`；
- __scale = 0.25__：限制单步动作最多让关节偏离默认站姿 ±0.25 rad，保证安全；
- C++ 部署侧由 `deploy/include/isaaclab/envs/mdp/actions/joint_actions.h` 中的 `JointAction::process_actions()` 实现（scale → offset → clip），与 `deploy.yaml` 中 `actions` 段一致。

## 三、如何接入 PD 控制

__关键：RL 输出不进入力矩，而是作为 Unitree 底层关节电机的位置模式目标角 q。__ 真正的 PD 由 Unitree SDK2 电机固件完成（或部署程序显式下发 kp/kd）：

```javascript
tau = kp * (q_target - q) + kd * (0 - q̇)
```

流程（见 `deploy/robots/g1_29dof/src/State_RLBase.cpp` L55-60，GO2 的 `State_RLBase.cpp` 相同）：

```cpp
void State_RLBase::run() {
    auto action = env->action_manager->processed_actions();   // ONNX 推理 → scale+offset
    for (int i(0); i < env->robot->data.joint_ids_map.size(); i++) {
        lowcmd->msg_.motor_cmd()[env->robot->data.joint_ids_map[i]].q() = action[i];
    }
}
```

- `kp / kd` 来自 `deploy.yaml`（如 G1：髋/膝 kp=100~200、kd=2~5；踝 kp=40、kd=10），在 mimic 版 `State_Mimic.cpp` L164-167 中显式写入 `motor_cmd().kp()/kd()`，velocity 部署则依赖电机预设的 PD 参数（应与训练时 `unitree.py` 中的 stiffness/damping 一致）；
- `joint_ids_map` 负责把"策略关节顺序"映射到 Unitree LowCmd 的 motor 槽位。

## 四、完整闭环链路

```javascript
IMU/编码器(500Hz) → 观测构造(base_ang_vel×0.2, projected_gravity, vel_cmd,
                          joint_pos_rel, joint_vel_rel×0.05, last_action; history=5)
→ ONNX actor (policy.onnx, step_dt=0.02s 即 50Hz)
→ raw action[29] → ×scale(0.25) + offset(默认站姿) → target q[29]
→ LowCmd.motor_cmd[i].q = target_q   （kp/kd 由 PD 参数提供）
→ Unitree 电机固件位置模式: tau = kp(q*-q) - kd·q̇ → 关节执行
```

__要点总结：__ RL 学的是"目标姿态/动作增量"，PD 是固定的低层跟踪器（kp/kd 写死在部署配置里）；RL 只需以 ~50 Hz 更新 `q*`，电机内部 PD 以高频闭环跟踪。这也是为什么训练时的 action_scale、默认站姿 offset、kp/kd 必须与真机部署完全一致——三者任何一项不匹配都会造成 sim2real 行为偏差（如动作被静默截断、步态僵硬或抖动）。




# 把 action_scale / offset / kp/kd 设成一致，困难吗？

**结论先说：单纯"参数写一样"是容易的（本仓库已经基本做到了）；真正的困难在于——就算数值完全相同，仿真里执行的 PD 和真机电机固件里的 PD 也不是同一个东西。** 下面分三层讲。

## 一、"抄对数"这一层 —— 不难，但有几个坑

以 G1-29dof 为例，三处参数分别写在不同地方：

| 参数 | 训练侧 | 部署侧 |
|---|---|---|
| action_scale=0.25、offset（默认站姿） | `velocity_env_cfg.py` 的 `ActionsCfg` + `unitree.py` 的 `init_state.joint_pos` | `deploy.yaml` 的 `actions.JointPositionAction.scale/offset` |
| kp/kd | `unitree.py` actuator 配置（如 GO2: stiffness=25, damping=0.5） | `deploy.yaml` 的 `stiffness/damping`，或电机预设值 |

数值抄对不难，但实践中容易出偏差的点：

1. **两处独立维护、无单一事实来源**。训练侧是 Python configclass，部署侧是手写 YAML，改一边忘另一边是最常见的出错方式。本仓库里 `deploy.yaml` 的 offset/scale 和 `unitree.py` 默认站姿目前是一致的（髋 -0.1/+0.1、膝 0.3/0.8、踝 -1.5/-0.25），但没有任何自动化检查保证它们同步。
2. **关节顺序映射**。`joint_ids_map` / `joint_sdk_names` 决定第 i 个动作对应哪个电机槽位，scale/offset/kp 数组是按这个顺序排的——顺序错一位，机器人姿态直接崩，且这种错误不易从日志发现（往往只是"走得怪"）。
3. **offset 的语义对齐**：训练侧 `use_default_offset=True` 用的是 USD init_state；部署侧 offset 是手写在 YAML 里的。如果改了默认站姿只改一处，网络输出的目标角就整体平移了，表现为机器人"半蹲或弓背走路"。
4. **scale 必须严格一致**：scale 是唯一一个"训练时策略已经把它学进权重里"的参数——scale 变了等于换了动作空间，checkpoint 直接作废，这是三者中唯一改了就不可复用的。

## 二、真困难所在 —— "数值相同 ≠ 动力学等价"

即使 scale/offset/kp/kd 逐项对齐，仿真和实机的执行器模型仍有本质差异：

1. **PD 的执行时机与延迟**
   - 训练侧（`UnitreeActuator(DelayedPDActuator)`）是理想 PD：每个物理步（5ms）直接算 `τ = kp(q*-q) + kd(0-q̇)`，无采样-保持、无量化。
   - 真机：策略 50Hz 下发 `q*`，电机固件内部以 1kHz+ 做 PD；且 LowCmd/LowState 各有通信延迟和丢包（网络抖动、重发）。仿真里这条"动作→力矩"链路是零延迟的。
2. **仿真侧额外加了真机没有的东西**：`UnitreeActuatorCfg` 里的 `armature`（一阶惯性项）、`Fs/Fd` 摩擦模型、T-N 曲线力矩限幅（X1/X2/Y1/Y2）——这些是刻意模仿电机特性，但只是近似；而真机还有减速器非线性、齿轮间隙、温升导致的性能漂移。
3. **kp/kd 的"名义一致"陷阱**：仿真里 kp=25/damping=0.5 是一个连续时间理想环节；真机电机的位置模式内部可能叠加了速度环、力矩限幅、软限位，同样的 kp 数值在两侧产生的实际响应带宽并不相同。尤其 G1 踝部（kp=40, kd=10）这种"高增益+低刚度"组合，仿真里稳定不代表实机不抖。
4. **默认站姿 offset 的物理可达性**：USD 的 init_state 是纯几何设定；真机上机器人能否精确停在完全相同的关节角（重力补偿能力、软限位范围），需要上电后实测确认。

## 三、工程建议（改动尽量小的前提下）

1. **以 `deploy.yaml` 为单一事实来源**：训练配置里凡与部署重复的量（scale、offset、kp/kd），在注释中注明来源是 `config/policy/*/params/deploy.yaml`；改参数时先改 YAML 再同步 Python，或写个小脚本从 YAML 生成/校验。
2. **加一致性检查**：CI 或训练启动时比对 `ActionsCfg`（scale、default offset）与对应 `deploy.yaml` 的 `actions` 段，不一致就报错——几十行代码就能把最高频的人为错误挡住。
3. **不要追求 kp/kd"数值相同"就结束**，而是做行为验证：用真机录一段静止站立的 LowState（q、q̇），和仿真里同样的 `q*` 目标跑出的轨迹对比收敛速度/超调；或直接用 Unitree 官方提供的电机特性参数填训练侧的 X1/X2/Y1/Y2/armature，而不是拍脑袋。
4. **scale 一旦定死就不要动**：它被烙进策略权重里，重训成本高；offset/kp/kd 不一致顶多让机器人"姿态不对、动作发软"，而 scale 不一致会直接让动作空间错位。
5. **首次上真机前**：先用 `deploy.yaml` 的 offset 值做静态站立测试（不给速度指令），确认默认站姿可达且不抖；再逐步放开速度指令范围（本仓库 G1 velocity 训练时 ranges 是 ±0.1，limit_ranges 才是 ±0.5~1.0，真机调试正好可以利用这个 curriculum 分级）。

一句话总结：**"抄对数"只是十分钟的活，真正的 sim2real gap 在 PD 执行链路的延迟、非理想性和电机特性上——这部分靠"参数一致"消不掉，只能靠行为级对比（同指令下的 q/q̇ 轨迹对照）来确认。**

# PD 参数运行在哪里？

**核心答案：PD（位置模式）真正执行的位置是 Unitree 每个关节电机内部的固件里，不在训练代码、也不在部署 C++ 程序里。** kp/kd 数值只是"配置"，分布在四个地方，最终生效点只有一个。

## 一、四个存放/使用位置

### 1. 仿真侧：Isaac Sim 的 Python actuator（训练中）
- 文件：`source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py`（如 GO2: `stiffness=25.0, damping=0.5`）、`unitree_actuators.py`
- **运行位置**：Isaac Sim 物理引擎的每个物理步（G1 任务 sim.dt=5ms）里，由 `UnitreeActuator.compute()`（继承 `DelayedPDActuator`）执行：

```python
τ = kp*(q* − q) + kd*(0 − q̇)      # 理想 PD，零延迟、无量化
→ 再叠加 armature/摩擦/T-N 限幅 → 关节力矩
```

这是"仿真的 PD"，只在训练时存在于 GPU 仿真器内。

### 2. 部署侧：`deploy.yaml`（只是数据）
- `config/policy/*/params/deploy.yaml` 里的 `stiffness/damping` 数组——它**本身不执行任何计算**，只是被 C++ 程序加载后写进 LowCmd 的候选值。

### 3. 部署侧：C++ 进程（只是"搬运工"）
- `deploy/robots/*/src/State_RLBase.cpp` / `State_Mimic.cpp`：以策略频率（G1 step_dt=0.02s，即 50Hz；GO2 类似）把 `motor_cmd[i].q()` 填好发出。
- **只有 mimic 分支显式写 kp/kd**（`State_Mimic.cpp:164-167`）：

```cpp
lowcmd->msg_.motor_cmd()[i].kp() = env->robot->data.joint_stiffness[i];
lowcmd->msg_.motor_cmd()[i].kd() = env->robot->data.joint_damping[i];
```

- velocity 分支（`State_RLBase.cpp:26-31`）只写 `q()`，**kp/kd 不在这份代码里下发**——依赖电机当前已生效的参数。

### 4. 真正执行 PD 的地方：电机固件 ✅
- Unitree M107/GO2HV/N5020 等关节电机的 MCU 收到 LowCmd（Unitree 总线，~500Hz）后，在**电机内部以 1kHz+ 的高频控制环**执行位置模式：

```
τ = kp*(q_cmd − q_meas) + kd*(0 − q̇_meas)   ← 运行在电机 MCU 里
```

然后按 T-N 曲线限幅、输出电流。这是唯一"真正闭环跟踪目标角"的地方。

## 二、完整信号链（谁在哪里跑）

```
[PC, C++进程, 50Hz]        [网线/CAN]        [电机MCU, ≥1kHz]
ONNX推理 → scale+offset     LowCmd            ┌─────────────┐
→ motor_cmd[i].q = q*  ───► (motor_cmd:      │ PD位置环执行 │
   (mimic分支还带kp/kd)    q,kp,kd,tau) ───► │ τ=kp(q*-q)   │
                                             │ +kd(0-q̇),限幅│
LowState ◄──────────────────── 回传q,q̇,τ     └─────────────┘
```

## 三、由此产生的两个实用要点

1. **velocity 部署不写 kp/kd，意味着真机 PD 参数取决于电机当前状态**：上电默认值、或之前某次 `motor_cmd.kp()/kd()` 下发的残留。所以首次真机调试前应该像 mimic 分支那样显式下发一次与训练一致的 kp/kd（改动很小：在 velocity 的 `State_RLBase::run()` 里加两行，或直接复用 `data.joint_stiffness/damping`）。
2. **仿真侧的 PD 是"替身"**：训练时它替代的是电机固件那个环。两者数值相同但执行环境不同（5ms 理想离散 vs 1kHz+ 硬件），这就是上一轮说的 sim2real gap 的物理根源——所以验证方式不是比对代码，而是同指令下对比 q/q̇ 轨迹收敛行为。

# 这两行代表什么？——"仿真电机模型"的完整数学定义

这段是我对 `UnitreeActuator.compute()`（`source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree_actuators.py:56-88`）的简写。它代表**在 Isaac Sim 里，每个物理步（G1 是 5ms），仿真器如何把"RL 给的目标关节角 q*"换算成真正施加到刚体上的力矩 τ**。逐符号解释：

## 第一行：PD 位置环

```
τ = kp*(q* − q) + kd*(0 − q̇)
```

| 符号 | 含义 |
|---|---|
| `q` | **当前**关节角（仿真器积分出来的状态量） |
| `q̇` | **当前**关节角速度 |
| `q*` | RL 动作经 scale+offset 后的**目标**关节角（上一轮说的 `processed_actions()`） |
| `0` | 目标角速度——注意是 0！位置模式只跟踪角度，不要求速度 |
| `kp` | 位置增益：偏差越大，回正力矩越强（决定响应快慢/刚度感） |
| `kd` | 速度阻尼项：抑制振荡、吸收冲击（没有它系统会来回抖） |

物理意义：**弹簧 + 阻尼器**。`kp*(q*−q)` 像一根把关节拉向目标角的"弹簧"，`kd*(0−q̇)` 像一个粘在关节上的"油缸"。两者合成力矩 τ 后，由刚体动力学 `J·q̈ = τ + 重力项 + 接触力...` 决定下一时刻的 q、q̇——即 PD 不直接控制角度，而是通过**出力矩**间接让角度收敛到 q*。

"零延迟、无量化"的意思：仿真里这条链路在物理步内瞬时算完（不像真机有 50Hz 指令更新 + 通信延迟），数值是 float32/64 连续量（不像电机固件有电流环离散化和 ADC 量化）。

## 第二行：叠加非理想项 → 最终力矩

```
τ_final = clip_TN( τ_PD − friction )      ← "再叠加 armature/摩擦/T-N 限幅"的展开
```

对应代码里的三个环节，各自模仿真机电机的哪个特性：

1. **摩擦**（`unitree_actuators.py:65-67`）：
   ```python
   τ_final -= Fs·tanh(q̇/Va) + Fd·q̇
   ```
   模仿齿轮/轴承的静摩擦（低速时 tanh≈饱和，需要克服"起步阻力"）和动摩擦（与速度成正比）。没有它仿真机器人会"太顺滑"。

2. **T-N 曲线限幅**（`_clip_effort`, L75-83）：
   ```python
   τ_final = clip(τ, −max_effort, +max_effort)
   max_effort = Y1/Y2 (|q̇|<X1 时) → 线性下降到 X2 处为 0
   ```
   就是电机手册里的"扭矩-转速特性曲线"：低速段能出峰值扭矩（Y1=同向、Y2=反向），转速超过 X1 后力矩能力随速度线性衰减，到 X2（空载最高速）时出力矩为零。防止仿真机器人做出真机电机做不到的"高速+大力"动作。

3. **armature（一阶惯性）**：`DelayedPDActuator` 里 `kp/q̇` 项会乘以 `1/(1+kd/armature)` 类的等效形式，模仿电机转子+减速器惯量造成的 PD 响应延迟——真机的 kp/kd 不是"瞬时生效"的。

## 一句话总结

这两行代表**仿真里"假想电机固件"的执行模型**：

```
q*(RL目标) ──[理想PD: 弹簧+阻尼]──► τ_ideal
τ_ideal ──[减摩擦项][按T-N曲线限幅][armature惯性修正]──► τ_final → 施加到关节刚体
```

它的存在目的只有一个：**让训练时的"动作→实际运动"链条尽可能像真机电机**，这样 RL 学到的策略（什么时候给多大的 q*）在真机上才有效。这也是为什么 `unitree_actuators.py` 里每个电机型号（M107-24、N5020-16…）都填了厂商手册的 X1/X2/Y1/Y2/armature——这些数就是"仿真替身"和真机之间的相似度来源。
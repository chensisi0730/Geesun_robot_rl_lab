# Unitree RL Lab

[![IsaacSim](https://img.shields.io/badge/IsaacSim-5.1.0-silver.svg)](https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html)
[![Isaac Lab](https://img.shields.io/badge/IsaacLab-2.3.0-silver)](https://isaac-sim.github.io/IsaacLab)
[![License](https://img.shields.io/badge/license-Apache2.0-yellow.svg)](https://opensource.org/license/apache-2-0)
[![Discord](https://img.shields.io/badge/-Discord-5865F2?style=flat&logo=Discord&logoColor=white)](https://discord.gg/ZwcVwxv5rq)


## Overview

This project provides a set of reinforcement learning environments for Unitree robots, built on top of [IsaacLab](https://github.com/isaac-sim/IsaacLab).

Currently supports Unitree **Go2**, **H1** and **G1-29dof** robots.

<div align="center">

| <div align="center"> Isaac Lab </div> | <div align="center">  Mujoco </div> |  <div align="center"> Physical </div> |
|--- | --- | --- |
| [<img src="https://oss-global-cdn.unitree.com/static/d879adac250648c587d3681e90658b49_480x397.gif" width="240px">](g1_sim.gif) | [<img src="https://oss-global-cdn.unitree.com/static/3c88e045ab124c3ab9c761a99cb5e71f_480x397.gif" width="240px">](g1_mujoco.gif) | [<img src="https://oss-global-cdn.unitree.com/static/6c17c6cf52ec4e26bbfab1fbf591adb2_480x270.gif" width="240px">](g1_real.gif) |

</div>

## Installation

- Install Isaac Lab by following the [installation guide](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html).
- Install the Unitree RL IsaacLab standalone environments.

  - Clone or copy this repository separately from the Isaac Lab installation (i.e. outside the `IsaacLab` directory):

    ```bash
    git clone https://github.com/unitreerobotics/unitree_rl_lab.git
    ```
  - Use a python interpreter that has Isaac Lab installed, install the library in editable mode using:

    ```bash
    conda activate env_isaaclab_sim5
    ./unitree_rl_lab.sh -i
    # restart your shell to activate the environment changes.
    ```
- Download unitree robot description files

  *Method 1: Using USD Files*
  - Download unitree usd files from [unitree_model](https://huggingface.co/datasets/unitreerobotics/unitree_model/tree/main), keeping folder structure
    ```bash
    git clone https://huggingface.co/datasets/unitreerobotics/unitree_model
    ```
  - Config `UNITREE_MODEL_DIR` in `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py`.

    ```bash
    UNITREE_MODEL_DIR = "</home/user/projects/unitree_usd>"
    ```

  *Method 2: Using URDF Files [Recommended]* Only for Isaacsim >= 5.0
  -  Download unitree robot urdf files from [unitree_ros](https://github.com/unitreerobotics/unitree_ros)
      ```
      git clone https://github.com/unitreerobotics/unitree_ros.git
      ```
  - Config `UNITREE_ROS_DIR` in `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py`.
    ```bash
    UNITREE_ROS_DIR = "</home/user/projects/unitree_ros/unitree_ros>"
    ```
  - [Optional]: change *robot_cfg.spawn* if you want to use urdf files



- Verify that the environments are correctly installed by:

  - Listing the available tasks:

    ```bash
    ./unitree_rl_lab.sh -l # This is a faster version than isaaclab
    ```
  - Running a task:
    g1: 平地  2026-07-08_14-09-16
    GO2：平地 unitree_go2_velocity/2026-07-08_21-46-54

    ```bash
    ./unitree_rl_lab.sh -t --task Unitree-G1-29dof-Velocity # support for autocomplete task-name
    # same as
    conda run -n env_isaaclab_sim5  python scripts/rsl_rl/train.py --headless --task Unitree-G1-29dof-Velocity --num_envs 12000 --resume  --load_run 2026-07-21_13-42-56

    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/train.py --headless --task Unitree-Go2-Velocity --num_envs 12000 --resume
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/train.py --headless --task Unitree-GeesunDog-Velocity --num_envs 12000
    
    tensorboard --logdir logs/rsl_rl/

    ```
  - Inference with a trained agent:

    ```bash
    ./unitree_rl_lab.sh -p --task Unitree-G1-29dof-Velocity # support for autocomplete task-name
    # same as
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py --task Unitree-G1-29dof-Velocity
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py --task Unitree-Go2-Velocity   --load_run 2026-08-31_23-22-03
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py --task Unitree-GeesunDog-Velocity
    ```

### Torque Statistics (Motor Selection)

`scripts/rsl_rl/record_torque_stats.py` runs a **trained checkpoint** in the play environment and records the per-joint actuator applied torque at every control step. It outputs three statistics per joint, which serve as a reference for motor selection:

| Statistic | Meaning |
|---|---|
| `Peak \|tau\|` | Max absolute torque over all samples — use with a 1.5-2.0x safety margin to select peak (peak/short-time) torque. |
| `P99 \|tau\|` | 99th percentile of absolute torque — robust against rare spikes, closer to sustained worst-case load. |
| `RMS` | Root-mean-square torque — compare against motor continuous/thermal rating. |

**Usage:**

```bash
# Explicit checkpoint:
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/record_torque_stats.py \
    --task Unitree-Go2-Velocity \
    --checkpoint logs/rsl_rl/unitree_go2_velocity/<run>/model_7300.pt --steps 500

# Automatically load the latest run / latest checkpoint:
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/record_torque_stats.py --task Unitree-Go2-Velocity
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `--task` | `Unitree-Go2-Velocity` | Task name (e.g. `Unitree-G1-29dof-Velocity`, `Unitree-Go2-Velocity`). |
| `--num_envs` | 64 | Number of parallel play environments to simulate. |
| `--steps` | 500 | Number of policy steps to record. |
| `--warmup` | 50 | Initial discarded steps used to skip the settling transient after spawning. |
| `--output` | `<checkpoint_dir>/torque_stats.csv` | Output CSV path (auto-named if omitted). |
| `--save_raw` | off | Additionally save raw torque samples to a `.npz` file for further analysis. |
| `--disable_fabric` | off | Disable fabric and use USD I/O operations. |
| RSL-RL args | — | Standard arguments like `--experiment_name`, `--load_run`, `--checkpoint`. For example, to specify a particular run: add `--load_run 2026-08-31_23-22-03`. |

**Output:**

- A formatted table is printed to the console (per-joint peak/P99/RMS + pooled values).
- A CSV file (`torque_stats.csv`) with columns `joint, peak_abs_torque_Nm, p99_abs_torque_Nm, rms_torque_Nm` is saved next to the checkpoint.
- If `--save_raw` is set, raw samples are also saved to `<output_stem>_raw.npz` (keys: `torques`, `joint_names`, `checkpoint`).

> **Note:** This script only supports manager-based RL environments and requires a previously trained checkpoint under `logs/rsl_rl/<experiment_name>/`. It uses the *play* environment configuration (`play_env_cfg_entry_point`) with no terrain curriculum.

> **故障排查：控制台只显示部分关节的力矩表格**
>
> 现象：终端/日志里力矩表格只打印出前面若干行（如 8 个关节）就没了，看不到 `ALL (pooled)` 汇总行和 `[INFO] Statistics saved` 提示。
>
> 原因：Isaac Sim（kit）退出时是硬退出，不会刷新 Python 的 stdout 缓冲区。当 stdout 是管道时（`conda run`、`| tee`、`> log` 等均为块缓冲），缓冲区末尾未 flush 的内容会被静默丢弃——表格后半部分因此丢失。
>
> 说明：这只影响**控制台显示**，CSV 文件的数据始终是完整的（包含全部关节），可以放心使用 CSV 做电机选型分析。
>
> 解决（二选一）：
> 1. 脚本已在结果打印结束后显式 `sys.stdout.flush()`，直接重新运行即可；
> 2. 或运行时加 `-u` 关闭缓冲：`python -u scripts/rsl_rl/record_torque_stats.py ...`。

### 验证训练结果

训练完成后，需要验证策略在不同地形上的性能。以下是验证步骤：

#### 1. 平地行走测试

使用 `test_flat_walk.py` 脚本在纯平地形上测试策略：

```bash
# 测试 Go2 在平地上的行走性能
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --checkpoint logs/rsl_rl/unitree_go2_velocity/<run>/model_7300.pt --steps 500

# 或自动加载最新训练结果
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity
```

**输出指标：**
- 平均前进速度（m/s）
- 平均高度（m）
- 高度方差（m²）- 衡量行走稳定性
- 各关节力矩统计（峰值、P99、RMS）

> 若控制台的力矩表格只显示部分关节（如 8 个），属于 Isaac Sim 硬退出导致 stdout 缓冲未刷新的显示问题，CSV 数据是完整的；脚本已加 `sys.stdout.flush()` 修复，详见上文故障排查说明。

#### 2. 复杂地形测试

使用 `play.py` 在复杂地形上测试策略：

```bash
# 在复杂地形上测试
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py --task Unitree-Go2-Velocity --load_run <run_id>
```

**观察要点：**
- 机器人能否稳定行走
- 是否能适应不同地形
- 步态是否自然

#### 3. 力矩统计分析

使用 `record_torque_stats.py` 分析关节力矩，为电机选型提供参考：

```bash
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/record_torque_stats.py \
    --task Unitree-Go2-Velocity --steps 1000
```

#### 4. TensorBoard 监控

训练过程中使用 TensorBoard 监控关键指标：

```bash
tensorboard --logdir logs/rsl_rl/
```

**关键指标：**
- `rewards/track_lin_vel_xy`: 速度跟踪奖励
- `rewards/track_ang_vel_z`: 角速度跟踪奖励
- `losses/policy_loss`: 策略损失
- `losses/value_loss`: 价值损失

#### 5. 验证清单

- [ ] 平地行走稳定，无明显晃动
- [ ] 速度跟踪准确，能达到目标速度
- [ ] 关节力矩在电机额定范围内
- [ ] 复杂地形适应性良好
- [ ] 步态自然，无异常动作

### Geesun Dog 导入与全关节运动演示（dog1）

`scripts/geesun_dog/move_geesun_dog.py` 将自研 Geesun 四足机器人（`unitree_model/geesun_dog/geesun-dog/dog1/urdf/dog1.urdf`，4 条腿 x hip/thigh/calf 共 12 个关节）导入 Isaac Sim，并以对角步态（trot）正弦曲线驱动全部关节运动，便于直观检查整条运动链。

**自动修复的资产问题**（不修改原始资产，修复副本写入 `/tmp/IsaacLab/geesun_dog/`）：

| SolidWorks 导出 URDF 中的问题 | 自动修复方式 |
|---|---|
| 网格以 `package://dog1/meshes/...` 引用（无 ROS 无法解析） | 重写为绝对路径 |
| `Link_fr/fl/hl/hr_hip.STL` 为空文件（仅 80 字节头、0 个三角形），导入器会丢弃/崩溃 | 自动生成占位圆柱网格（半径 0.035 m、长 0.08 m、沿髋关节轴） |
| 所有关节 `limit lower/upper/effort/velocity` 均为 0，机器人无法运动 | 替换为合理范围（hip ±0.8，thigh -2.0~2.5 / 镜像，calf -2.5~0.5 / 镜像），effort=100，velocity=25 |
| 在 `InteractiveScene` 创建过程中做 URDF 转换会使导入器死锁（Isaac Sim 5.1） | 先单独把 URDF 转成 USD（`ensure_geesun_dog_usd()`，按 mtime 缓存），场景再从 USD 生成 |

**用法：**

```bash
conda activate env_isaaclab_sim5
python scripts/geesun_dog/move_geesun_dog.py                    # 图形界面，2000 步
python scripts/geesun_dog/move_geesun_dog.py --num_steps 0      # 一直运行，直到关闭窗口
python scripts/geesun_dog/move_geesun_dog.py --headless --num_steps 300     # 无界面快速检查
python scripts/geesun_dog/move_geesun_dog.py --gait_freq 2.0 --amp_deg 35   # 更快/摆幅更大
```

**参数：**

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--num_steps` | 2000 | 物理步数（`0` = 一直运行直到关闭窗口） |
| `--gait_freq` | 1.5 Hz | 关节正弦运动频率（对角步态，对角腿同相位） |
| `--amp_deg` | 25 | 关节摆动幅度（度），髋关节减半 |
| `--headless` | 关 | 无图形界面运行 |
| `--device` | `cuda:0` | 也可用 `cpu`，但建议使用 GPU |

**验证要点：**

1. `./unitree_rl_lab.sh -l` 能查到已注册任务 `Unitree-GeesunDog-Velocity`（位于 `tasks/locomotion/robots/geesun_dog/`，复用 Go2 的速度跟踪任务结构）。
2. 控制台打印 `Using converted USD: /tmp/IsaacLab/geesun_dog/dog1.usd` 和 `Loaded robot joints: [12 个关节名]`。
3. 控制台每 100 步打印 `[step N] joint_pos (rad):`，且 12 个关节值**持续振荡**（相邻打印之间没有数值冻结不变）。
4. 图形界面中机器人悬浮在离地约 1 m 处（基座被固定以便四条腿自由摆动），四条腿原地小跑。
5. 首次启动需要几分钟：URDF→USD 转换（约 1 分钟）+ 着色器编译（约 3~5 分钟）。如需强制重新转换：`rm -rf /tmp/IsaacLab/geesun_dog`。

**任务训练（可选）：**

```bash
./unitree_rl_lab.sh -t --task Unitree-GeesunDog-Velocity --num_envs 4096
tensorboard --logdir logs/rsl_rl/
```

> **注意：** 若关节位置冻结在固定姿态，说明腿与地面或彼此卡死——可在脚本中调高基座高度（`default_root[0, 2]`）或减小 `--amp_deg`。

## Deploy

After the model training is completed, we need to perform sim2sim on the trained strategy in Mujoco to test the performance of the model.
Then deploy sim2real.

### Setup

```bash
# Install dependencies
sudo apt install -y libyaml-cpp-dev libboost-all-dev libeigen3-dev libspdlog-dev libfmt-dev
# Install unitree_sdk2
git clone git@github.com:unitreerobotics/unitree_sdk2.git
cd unitree_sdk2
mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=OFF # Install on the /usr/local directory
sudo make install
# Compile the robot_controller
cd unitree_rl_lab/deploy/robots/g1_29dof # or other robots
mkdir build && cd build
cmake .. && make
```

### Sim2Sim

Installing the [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco?tab=readme-ov-file#installation).

- Set the `robot` at `/simulate/config.yaml` to g1
- Set `domain_id` to 0
- Set `enable_elastic_hand` to 1
- Set `use_joystck` to 1.

```bash
# start simulation
cd unitree_mujoco/simulate/build
./unitree_mujoco
# ./unitree_mujoco -i 0 -n eth0 -r g1 -s scene_29dof.xml # alternative
```

```bash
cd unitree_rl_lab/deploy/robots/g1_29dof/build
./g1_ctrl
# 1. press [L2 + Up] to set the robot to stand up
# 2. Click the mujoco window, and then press 8 to make the robot feet touch the ground.
# 3. Press [R1 + X] to run the policy.
# 4. Click the mujoco window, and then press 9 to disable the elastic band.
```

### Sim2Real

You can use this program to control the robot directly, but make sure the on-borad control program has been closed.

```bash
./g1_ctrl --network eth0 # eth0 is the network interface name.
```

## Acknowledgements

This repository is built upon the support and contributions of the following open-source projects. Special thanks to:

- [IsaacLab](https://github.com/isaac-sim/IsaacLab): The foundation for training and running codes.
- [mujoco](https://github.com/google-deepmind/mujoco.git): Providing powerful simulation functionalities.
- [robot_lab](https://github.com/fan-ziqi/robot_lab): Referenced for project structure and parts of the implementation.
- [whole_body_tracking](https://github.com/HybridRobotics/whole_body_tracking): Versatile humanoid control framework for motion tracking.

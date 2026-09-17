# Unitree RL Lab

[![IsaacSim](https://img.shields.io/badge/IsaacSim-5.1.0-silver.svg)](https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html)
[![Isaac Lab](https://img.shields.io/badge/IsaacLab-2.3.0-silver)](https://isaac-sim.github.io/IsaacLab)
[![License](https://img.shields.io/badge/license-Apache2.0-yellow.svg)](https://opensource.org/license/apache-2-0)
[![Discord](https://img.shields.io/badge/-Discord-5865F2?style=flat&logo=Discord&logoColor=white)](https://discord.gg/ZwcVwxv5rq)


## 项目概述

本项目基于 [IsaacLab](https://github.com/isaac-sim/IsaacLab) 提供一套 Unitree 机器人的强化学习环境。

当前支持 Unitree **Go2**、**H1** 和 **G1-29dof** 机器人。

<div align="center">

| <div align="center"> Isaac Lab 仿真 </div> | <div align="center">  Mujoco 仿真 </div> |  <div align="center"> 实机 </div> |
|--- | --- | --- |
| [<img src="https://oss-global-cdn.unitree.com/static/d879adac250648c587d3681e90658b49_480x397.gif" width="240px">](g1_sim.gif) | [<img src="https://oss-global-cdn.unitree.com/static/3c88e045ab124c3ab9c761a99cb5e71f_480x397.gif" width="240px">](g1_mujoco.gif) | [<img src="https://oss-global-cdn.unitree.com/static/6c17c6cf52ec4e26bbfab1fbf591adb2_480x270.gif" width="240px">](g1_real.gif) |

</div>

## 目录

- [项目概述](#项目概述)
- [安装](#安装)
- [策略测试与力矩统计](#策略测试与力矩统计)
- [验证训练结果](#验证训练结果)
- [Geesun Dog 导入与全关节运动演示（dog1）](#geesun-dog-导入与全关节运动演示dog1)
- [部署](#部署)
- [致谢](#致谢)

## 安装

- 按照[安装指南](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html)安装 Isaac Lab。
- 安装 Unitree RL 的 IsaacLab 独立环境。

  - 将本仓库克隆或复制到 Isaac Lab 安装目录之外（即不要放在 `IsaacLab` 目录内部）：

    ```bash
    git clone https://github.com/unitreerobotics/unitree_rl_lab.git
    ```
  - 使用已安装 Isaac Lab 的 Python 解释器，以可编辑（editable）模式安装本库：

    ```bash
    conda activate env_isaaclab_sim5
    ./unitree_rl_lab.sh -i
    # 重启 shell 以使环境变更生效。
    ```

    若仓库路径发生变化，请在当前仓库目录重新执行 `./unitree_rl_lab.sh -i`，
    并用 `pip show unitree_rl_lab` 确认 `Location` 指向本仓库的 `source/unitree_rl_lab`。
- 下载 Unitree 机器人描述文件

  *方法一：使用 USD 文件*
  - 从 [unitree_model](https://huggingface.co/datasets/unitreerobotics/unitree_model/tree/main) 下载 unitree USD 文件，保持原有目录结构
    ```bash
    git clone https://huggingface.co/datasets/unitreerobotics/unitree_model
    ```
  - 在 `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py` 中配置 `UNITREE_MODEL_DIR`。

    ```bash
    UNITREE_MODEL_DIR = "</home/user/projects/unitree_usd>"
    ```

  *方法二：使用 URDF 文件（推荐）* 仅适用于 Isaac Sim >= 5.0
  -  从 [unitree_ros](https://github.com/unitreerobotics/unitree_ros) 下载 unitree 机器人 URDF 文件
      ```
      git clone https://github.com/unitreerobotics/unitree_ros.git
      ```
  - 在 `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py` 中配置 `UNITREE_ROS_DIR`。
    ```bash
    UNITREE_ROS_DIR = "</home/user/projects/unitree_ros/unitree_ros>"
    ```
  - [可选]：如需使用 URDF 文件，请修改 *robot_cfg.spawn*



- 通过以下方式验证环境已正确安装：

  - 列出可用任务：

    ```bash
    ./unitree_rl_lab.sh -l # 比 isaaclab 启动更快
    ```
  - 训练 GO2 复杂地形行走策略：

    ```bash
    set -o pipefail

    # GO2 复杂地形训练，新建训练运行
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/train.py --headless \
        --task Unitree-Go2-Velocity --num_envs 12000 2>&1 | tee /tmp/train_go2.log

    # 从已有运行继续训练时，再添加 --resume 和 --load_run
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/train.py --headless \
        --task Unitree-Go2-Velocity --num_envs 12000 \
        --resume --load_run RUN_ID 2>&1 | tee /tmp/train_go2_resume.log
    ```

    训练日志和 checkpoint 默认保存在 `logs/rsl_rl/unitree_go2_velocity/`。
    新建训练时不要添加 `--resume`；只有从已有运行继续训练时才使用
    `--resume --load_run RUN_ID`，其中 `RUN_ID` 替换为实际运行目录名。
    如需实时查看日志，请在另一个终端执行
    `tail -f /tmp/train_go2.log` 或 `tail -f /tmp/train_go2_resume.log`。
    当前 GO2 的 `height_scanner` 仍保留用于后续消融，但没有接入 policy/critic 观测；
    如需完全关闭传感器，还需移除场景传感器及其 `update_period` 配置。

  - 回放训练好的 GO2 策略：

    ```bash
    ./unitree_rl_lab.sh -p --task Unitree-Go2-Velocity --load_run RUN_ID


    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py \
        --task Unitree-Go2-Velocity
    ```

## 策略测试与力矩统计

`scripts/rsl_rl/test_flat_walk.py` 使用训练好的 checkpoint 进行定量测试，并记录行走指标和每个关节的执行器力矩。通过 `--terrain` 选择测试地形：

| `--terrain` | 地形 | 用途 |
|---|---|---|
| `flat`（默认） | 强制使用纯平地 | 平地基线和名义工况力矩 |
| `play` | 使用任务的 play 配置 | 检查回放配置中的地形 |
| `complex` | 强制使用混合复杂地形，并覆盖全部难度层级 | 复杂地形行走和力矩压力测试 |

| 指标 | 含义 |
|---|---|
| `Peak \|tau\|` | 所有样本中的最大绝对力矩，用于峰值力矩评估；选型时建议保留 1.5-2.0 倍安全余量。 |
| `P99 \|tau\|` | 绝对力矩的 99% 分位值，比峰值更不容易受偶发尖峰影响。 |
| `RMS` | 均方根力矩，用于和电机持续/热力矩能力比较。 |

**用法：**

```bash
# 平地名义工况，自动加载最新 checkpoint
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --steps 500

# 指定 checkpoint 时，将 RUN_ID 和 checkpoint 文件名替换为实际值
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --checkpoint logs/rsl_rl/unitree_go2_velocity/RUN_ID/model_7300.pt \
    --steps 500

# 复杂地形压力测试，推荐用于电机选型参考
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain complex \
    --steps 1000

# 使用任务的 play 配置地形，省略 checkpoint 时自动选择最新结果
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity --terrain play
```

**参数：**

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--task` | `Unitree-Go2-Velocity` | 任务名称。 |
| `--terrain` | `flat` | `flat`、`play` 或 `complex`。 |
| `--num_envs` | 64 | 并行环境数量。 |
| `--steps` | 500 | 采样的策略步数；复杂地形建议使用 1000 或更多。 |
| `--warmup` | 50 | 丢弃的初始步数，用于跳过出生后的稳定过程。 |
| `--output` | 依地形模式自动命名 | 输出 CSV 路径。 |
| `--save_raw` | 关闭 | 额外保存原始样本 `.npz` 文件。 |
| `--disable_fabric` | 关闭 | 禁用 Fabric，改用 USD I/O。 |
| RSL-RL 参数 | - | 可使用 `--load_run`、`--checkpoint` 等参数指定模型。 |

**输出：**

- 控制台打印每个关节及汇总的 Peak/P99/RMS，以及平均前进速度、平均高度和高度方差。
- CSV 文件保存到 checkpoint 所在目录，包含关节力矩统计和 `terrain_mode`、平均速度、高度等行走指标。
- 添加 `--save_raw` 时，额外保存 `<output_stem>_raw.npz`，包含 `torques`、`positions`、`velocities`、`joint_names` 和 `checkpoint`。

> **说明：** 脚本只支持 manager-based RL 环境，需要已有训练 checkpoint。默认使用任务的 `play_env_cfg_entry_point`；`complex` 模式会覆盖为混合复杂地形，并让机器人覆盖全部难度层级。

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
> 2. 或运行时加 `-u` 关闭缓冲：`python -u scripts/rsl_rl/test_flat_walk.py ...`。

## 验证训练结果

训练完成后，建议先目视回放，再进行平地和复杂地形定量测试。

### 1. 复杂地形回放

使用 `play.py` 检查策略在任务 play 配置中的实际表现：

```bash
# 自动选择最新 checkpoint
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py \
    --task Unitree-Go2-Velocity

# 或指定训练运行目录
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/play.py \
    --task Unitree-Go2-Velocity --load_run RUN_ID
```

观察要点：
- 机器人能否稳定行走
- 是否能适应不同地形
- 步态是否自然
- 是否出现侧翻、摔倒或明显打滑

### 2. 定量行走与力矩测试

```bash
# 平地基线
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --steps 500

# 复杂地形压力测试
conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain complex \
    --steps 1000

# 分地形定位短板
for terrain in random_rough boxes stairs; do
    conda run -n env_isaaclab_sim5 python scripts/rsl_rl/test_flat_walk.py \
        --task Unitree-Go2-Velocity --terrain "$terrain" --steps 1000
done
```

检查 body-frame 速度误差、无提前终止成功率、高度方差和各关节 Peak/P99/RMS 力矩。

上述命令默认自动加载最新 checkpoint。指定模型时，增加：
`--checkpoint logs/rsl_rl/unitree_go2_velocity/RUN_ID/model_7300.pt`。

### 3. TensorBoard

```bash
tensorboard --logdir logs/rsl_rl/unitree_go2_velocity
```

重点观察以下实际标签：

- `Train/mean_reward`、`Train/mean_episode_length`
- `Episode_Reward/track_lin_vel_xy`、`Episode_Reward/track_ang_vel_z`
- `Metrics/base_velocity/error_vel_xy`、`Metrics/base_velocity/error_vel_yaw`
- `Curriculum/terrain_levels`、`Curriculum/lin_vel_cmd_levels`
- `Curriculum/command_ranges/{x_min,x_max,y_min,y_max}`
- `Curriculum/terrain_performance_by_type/*_{level,error_xy,error_yaw,success_rate}`
- `Episode_Termination/time_out`、`Episode_Termination/bad_orientation`
- `Loss/value_function`、`Loss/surrogate`、`Policy/mean_noise_std`

判断时使用训练后期的滑动平均，不要只看单个尖峰。通常应同时满足：episode 长度接近上限、`time_out` 占比稳定且较高、
`bad_orientation` 较低，速度误差总体下降，课程等级在达到当前能力上限后保持稳定，损失没有持续发散。
GO2 当前使用两阶段训练：阶段 1 将线速度固定为 `±0.25 m/s`，地形仅在正常超时且
`error_vel_xy < 0.22 m/s`、`error_vel_yaw < 0.30 rad/s` 时升级；提前终止，或误差超过
`0.40 m/s`、`0.45 rad/s` 时降级。分地形成功率稳定后，阶段 2 再启用速度课程。
`terrain_levels` 是平均难度，不是性能分数，必须和分地形误差、成功率一起判断。
修改 curriculum 后，旧 TensorBoard 运行只能用于对照；应重新训练或从头启动一个新运行，确认新的速度课程不会过早解锁。
如果训练因 Isaac Sim 异常退出，最后一个 checkpoint 只能作为候选模型，不能直接作为最终验收模型。

### 4. 训练日志检查（PhysX Overflow）

`Patch buffer overflow` 没有 TensorBoard 标签，训练日志是唯一观察渠道。该错误表示 PhysX GPU
碰撞管线（narrowphase）patch 池耗尽——与显存剩余量无关，空闲显存也可能触发；超出的碰撞对
会被静默跳过，个别 env 可能出现穿地/丢接触，污染训练数据。

```bash
# 训练日志 overflow 计数应为 0（v3 历史值为 98145，可作为异常量级参考）
grep -c 'Patch buffer overflow' /tmp/train_go2.log
```

- 计数为 0：物理管线健康；
- 计数 > 0 且逐物理步重复打印：该 run 的数据不可用于验收，需降低 `num_envs` 或
  简化地形碰撞网格后重新训练（见 `doc/training_monitoring.md` §3.1/§3.5）；
- 监控脚本（`scripts/monitor_tb_check.py`，每 4h 一轮）发现**新增** overflow 行会立即终止
  训练进程组（SIGTERM→SIGKILL）并抑制自动 resume，直到人工重启新 run 后标记自动清除
  （机制见 `doc/training_monitoring.md`）。

### 5. 验收清单

- [ ] 平地行走稳定，无明显晃动
- [ ] 复杂地形上能持续前进
- [ ] `flat/random_rough/boxes/stairs` 分项成功率均达到 90%
- [ ] `error_vel_xy <= 0.25 m/s`、`error_vel_yaw <= 0.35 rad/s`
- [ ] `time_out >= 99%`、`bad_orientation <= 1%`
- [ ] 复杂地形下力矩没有异常峰值
- [ ] 步态自然，无异常动作
- [ ] 训练日志无 PhysX Patch buffer overflow（计数为 0）

## Geesun Dog 导入与全关节运动演示（dog1）

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

## 部署

模型训练完成后，需要在 Mujoco 中对训练好的策略进行 sim2sim 仿真测试，以检验模型性能。
然后再进行 sim2real 实机部署。

### 环境准备

```bash
# 安装依赖
sudo apt install -y libyaml-cpp-dev libboost-all-dev libeigen3-dev libspdlog-dev libfmt-dev
# 安装 unitree_sdk2
git clone git@github.com:unitreerobotics/unitree_sdk2.git
cd unitree_sdk2
mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=OFF # 安装到 /usr/local 目录
sudo make install
# 编译机器人控制器
cd unitree_rl_lab/deploy/robots/g1_29dof # 或其他机器人
mkdir build && cd build
cmake .. && make
```

### Sim2Sim 仿真

安装 [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco?tab=readme-ov-file#installation)。

- 将 `/simulate/config.yaml` 中的 `robot` 设置为 g1
- 将 `domain_id` 设置为 0
- 将 `enable_elastic_hand` 设置为 1
- 将 `use_joystck` 设置为 1。

```bash
# 启动仿真
cd unitree_mujoco/simulate/build
./unitree_mujoco
# ./unitree_mujoco -i 0 -n eth0 -r g1 -s scene_29dof.xml # 备选启动方式
```

```bash
cd unitree_rl_lab/deploy/robots/g1_29dof/build
./g1_ctrl
# 1. 按 [L2 + 上] 使机器人站起
# 2. 点击 mujoco 窗口，然后按 8 使机器人脚接触地面。
# 3. 按 [R1 + X] 运行策略。
# 4. 点击 mujoco 窗口，然后按 9 关闭弹簧拉力（橡皮筋）。
```

### Sim2Real 实机部署

可以直接用该程序控制机器人，但务必先关闭机器人板载控制程序。

```bash
./g1_ctrl --network eth0 # eth0 为网卡名称。
```

## 致谢

本仓库基于以下开源项目的支持与贡献，特别感谢：

- [IsaacLab](https://github.com/isaac-sim/IsaacLab)：训练与运行代码的基础框架。
- [mujoco](https://github.com/google-deepmind/mujoco.git)：提供强大的仿真功能。
- [robot_lab](https://github.com/fan-ziqi/robot_lab)：项目结构与部分实现的参考。
- [whole_body_tracking](https://github.com/HybridRobotics/whole_body_tracking)：用于运动跟踪的多功能人形机器人控制框架。

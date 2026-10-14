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
    conda activate env_isaaclab_sim51
    ./unitree_rl_lab.sh -i
    # 重启 shell 以使环境变更生效。
    ```

    若仓库路径发生变化，请在当前仓库目录重新执行 `./unitree_rl_lab.sh -i`，
    并确认 editable 安装指向本仓库（editable 安装下 `pip show` 的 `Location` 显示的是
    site-packages，不能直接反映真实路径，请用 import 检查）：

    ```bash
    python -c "import unitree_rl_lab; print(unitree_rl_lab.__file__)"
    # 应输出 <本仓库>/source/unitree_rl_lab/unitree_rl_lab/__init__.py
    ```
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

    GeesunDog（Geesun 四足）在列表中有两个任务，指向同一套任务定义、只差资产变体
    GeesunDog（Geesun 四足）在列表中有两个**完全独立**的任务——各自独立的 `velocity_env_cfg.py`
    （任务定义：地形/奖励/课程/动作）、独立的 PPO 类（强化学习算法配置）、独立的日志目录，
    因此两个战役可以**同时训练、同时开自动调参**，互不干扰：

    | 任务名 | 资产变体 | 任务定义 | PPO 类 | 日志目录 |
    |---|---|---|---|---|
    | `Unitree-GeesunDog-Dog1-Velocity` | `dog1`（有足四足） | `robots/geesun_dog/dog1/velocity_env_cfg.py` | `UnitreeGeesunDogDog1PPORunnerCfg` | `logs/rsl_rl/unitree_geesun_dog1/` |
    | `Unitree-GeesunDog-LingsiD30W-Velocity` | `lingsi_d30w`（D30W 轮足） | `robots/geesun_dog/lingsi_d30w/velocity_env_cfg.py` | `UnitreeGeesunDogLingsiD30WPPORunnerCfg` | `logs/rsl_rl/unitree_geesun_lingsi_d30w/` |

    > 两个变体各自在自己的任务定义里锁定资产变体，**不再依赖 `GEESUN_DOG_VARIANT` 环境变量
    > （environment variable）**，因此不会因忘记设环境变量而跑错机器人。
    > 旧入口 `Unitree-GeesunDog-Velocity`（靠 `GEESUN_DOG_VARIANT` 切换）已于 2026-10-14 移除，
    > 改用上表两个任务名。
    >
    > **变体只有资产层共享**（`unitree_rl_lab/assets/robots/unitree.py` 里的 URDF→USD
    > 转换、执行器（actuator）模型、`ArticulationCfg`），任务级配置完全分开。
    > 做 dog1 ↔ lingsi_d30w 消融对照时 `diff` 两个 `velocity_env_cfg.py` 即可看到全部差异。
## 训练 GO2 复杂地形行走策略：

    ```bash
    set -o pipefail

    # GO2 复杂地形训练，新建训练运行
    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
        --task Unitree-Go2-Velocity --num_envs 12000 2>&1 | tee /tmp/train_go2.log

    # 从已有运行继续训练时，再添加 --resume 和 --load_run
    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
        --task Unitree-Go2-Velocity --num_envs 12000 \
        --resume --load_run RUN_ID 2>&1 | tee /tmp/train_go2_resume.log

    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
        --task Unitree-GeesunDog-Dog1-Velocity --num_envs 22000 \
        --resume --load_run 2026-10-12_20-24-42 2>&1 | tee /tmp/train_GeesunDog_resume.log 

    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
        --task Unitree-GeesunDog-LingsiD30W-Velocity    --num_envs 22000 \
        --resume --load_run 2026-10-14_08-47-04 2>&1 | tee /tmp/train_GeesunDog_resume.log 
            
    ```

    训练日志和 checkpoint 默认保存在 `logs/rsl_rl/unitree_go2_velocity/`。
    新建训练时不要添加 `--resume`；只有从已有运行继续训练时才使用
    `--resume --load_run RUN_ID`，其中 `RUN_ID` 替换为实际运行目录名。
    如需实时查看日志，请在另一个终端执行
    `tail -f /tmp/train_go2.log` 或 `tail -f /tmp/train_go2_resume.log`。
    当前 GO2 的 `height_scanner` 仍保留用于后续消融，但没有接入 policy/critic 观测；
    如需完全关闭传感器，还需移除场景传感器及其 `update_period` 配置。
    地形布局与 `terrain_levels` / `lin_vel_cmd_levels` 课程的设计逻辑、
    升降级条件与耦合关系，见 `doc/training_monitoring.md` 第 4 节。

  - 回放训练好的 GO2 策略：

    ```bash
    ./unitree_rl_lab.sh -p --task Unitree-Go2-Velocity --load_run RUN_ID


    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
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
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --steps 500

# 指定 checkpoint 时，将 RUN_ID 和 checkpoint 文件名替换为实际值
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --checkpoint logs/rsl_rl/unitree_go2_velocity/RUN_ID/model_7300.pt \
    --steps 500

# 复杂地形压力测试，推荐用于电机选型参考
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain complex \
    --steps 1000

# 使用任务的 play 配置地形，省略 checkpoint 时自动选择最新结果
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity --terrain play

# GeesunDog（Geesun 狗，dog1）关节力矩统计（硬件选型参考），换 --task 即可
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-GeesunDog-Dog1-Velocity --terrain flat --steps 1000
```

> **GeesunDog 硬件选型力矩测试（2026-10-12 起）：** `scripts/torque_test_when_done.sh <train_pid>`
> 会在训练结束后自动跑 `flat`（平地名义工况）+ `complex`（复杂地形压力）两组力矩统计
> （需独占 GPU（图形处理器），故等待训练结束；期间会写 stop_marker 阻止 6h 监控自动续训）。
> CSV 保存在 `logs/rsl_rl/unitree_geesun_dog/<run>/`。GeesunDog 的 PD/执行器参数自包含在
> `UnitreeActuatorCfg_GeesunDog`（`unitree_actuators.py`），与 GO2 等其他机器人完全隔离。
>
> **命令范围课程现状（2026-10-13 起 = GO2 双课程策略）：** GeesunDog 的 `CurriculumCfg` 已引入
> GO2 同款双课程：`terrain_levels_vel_strict`（地形难度，存活+跟踪滞回门控）与
> `gated_lin_vel_cmd_levels`（速度命令范围，x/y 与 yaw 独立门控、成功门槛、`state_file`
> 持久化到 `logs/rsl_rl/unitree_geesun_dog/curriculum_state.json`），另有
> `terrain_performance_by_type`（分地形表现）与 `command_ranges`（命令范围全量观测）。
> monitor/autotune 的 `x_max`/`success_*` 口径与课程旋钮（`success_xy`/`lin_increment` 等）
> 均随之生效。背景：2026-10-12 非门控版在复杂地形续训中命令范围跑赢地形能力导致崩溃
> （14700 轮白训，run `2026-10-12_23-40-21`），故升级为同步门控。

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

> **回放相机跟随（2026-10-12 起）：** `scripts/rsl_rl/play.py` 录像/回放时视角自动跟随机器人
> （走远不再出画；实现见 play.py 的 `_follow_camera()`，每步更新视口相机位姿），风格由
> `--camera_view` 参数选择：`side`（侧面）为默认——相机在机器人侧方 2.2 m、上方 1.1 m，
> 保持看向机首，不随偏航角（yaw）旋转（侧向跟拍）；`rear`（后面）——相机在机器人身后
> 2.2 m、上方 1.1 m，随偏航角转动（身后追拍）。
> 用法：`python scripts/rsl_rl/play.py ... --camera_view side`（可省略）/ `--camera_view rear`。

> **电机选型（motor sizing）：** 关节力矩数据与选型结论汇总见 [doc/motor_sizing.md](doc/motor_sizing.md)。

## 验证训练结果

训练完成后，建议先目视回放，再进行平地和复杂地形定量测试

### 1. 复杂地形回放

使用 `play.py` 检查策略在任务 play 配置中的实际表现：

```bash
# 自动选择最新 checkpoint
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-Go2-Velocity

# 或指定训练运行目录
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-Go2-Velocity --load_run RUN_ID

conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-GeesunDog-Dog1-Velocity --load_run 2026-10-13_10-07-28

conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-GeesunDog-LingsiD30W-Velocity --load_run 2026-10-14_08-47-04  --num_envs 10

```

观察要点：
- 机器人能否稳定行走
- 是否能适应不同地形
- 步态是否自然
- 是否出现侧翻、摔倒或明显打滑

### 2. 定量行走与力矩测试

```bash
# 平地基线
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --steps 500

# 复杂地形压力测试
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-Go2-Velocity \
    --terrain complex \
    --steps 1000

conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
    --task Unitree-GeesunDog-Dog1-Velocity \
    --terrain complex \
    --steps 1000    

# 分地形定位短板
for terrain in random_rough stairs; do
    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_flat_walk.py \
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
- 监控脚本（`scripts/monitor_tb_check.py`，每 6h 一轮）发现**新增** overflow 行会立即终止
  训练进程组（SIGTERM→SIGKILL）并抑制自动 resume，直到人工重启新 run 后标记自动清除
  （机制见 `doc/training_monitoring.md`）。

### 5. 验收清单

- [ ] 平地行走稳定，无明显晃动
- [ ] 复杂地形上能持续前进
- [ ] `flat/random_rough/stairs` 分项成功率均达到 90%
- [ ] `error_vel_xy <= 0.25 m/s`、`error_vel_yaw <= 0.35 rad/s`
- [ ] `time_out >= 99%`、`bad_orientation <= 1%`
- [ ] 复杂地形下力矩没有异常峰值
- [ ] 步态自然，无异常动作
- [ ] 训练日志无 PhysX Patch buffer overflow（计数为 0）

## Geesun Dog 导入与全关节运动演示（dog1）

`scripts/geesun_dog/move_geesun_dog.py` 将自研 Geesun 四足机器人（4 条腿 x hip/thigh/calf 共 12 个关节）导入 Isaac Sim，并以对角步态（trot）正弦曲线驱动全部关节运动，便于直观检查整条运动链。资产位于 `geesun_dog_urdf/geesun-dog/dog1/`：优先使用 9/21 更新的 `urdf/dog921.urdf`（真实网格与关节限位），缺失时自动回退旧版 `urdf/dog1.urdf`，方便消融对照。

**自动修复的资产问题**（不修改原始资产，修复副本写入 `/tmp/IsaacLab/geesun_dog/`）：

| SolidWorks 导出 URDF 中的问题 | 自动修复方式 |
|---|---|
| 网格以 `package://dog1/meshes/...`（旧版）或 `package://dog921/meshes/...`（新版）引用（无 ROS 无法解析） | 重写为绝对路径 |
| 旧版 dog1 导出：`Link_*_hip.STL` 为空文件（仅 80 字节头、0 个三角形），导入器会丢弃/崩溃 | 自动生成占位圆柱网格（半径 0.035 m、长 0.08 m、沿髋关节轴）；dog921 的 `link_*_hip.STL` 为真实网格（每个约 17 MB），直接复制 |
| 旧版 dog1 导出：所有关节 `limit lower/upper/effort/velocity` 均为 0 或过窄，机器人无法运动 | 替换为合理范围（hip ±0.8，thigh -2.0~2.5 / 镜像，calf -2.5~0.5 / 镜像），effort=100，velocity=25；dog921 保留导出真实限位（hip ±0.873，thigh -3.49~1.57，calf -1.885~0） |
| 在 `InteractiveScene` 创建过程中做 URDF 转换会使导入器死锁（Isaac Sim 5.1） | 先单独把 URDF 转成 USD（`ensure_geesun_dog_usd()`，`force_usd_conversion=True`：**每次启动都从 `geesun_dog_urdf/geesun-dog/dog1` 当前文件重新转换**（约 5~10 s，不依赖 mtime/资产哈希缓存，URDF 或网格任一更新都会被拾取）），场景再从 USD 生成 |

> **注意（9/22 更新）：** 后小腿站立姿态由 `+1.4` 调整为 `-1.4`（`unitree.py` 的 `GEESUN_DOG_CFG` 与脚本 `base` 字典）——dog921 真实 calf 限位为 `[-1.885, 0]`，旧 `+1.4` 姿态会超出上限被 PhysX 限位钳住。
>
> **注意（9/23 站立姿态验证更新）：** 对 dog921 足板网格做正运动学测量后，站立姿态做了两处修正（见下文"站立姿态验证"）：
>
> 1. **后大腿 `joint_hl/hr_thigh` 由 `-1.0` 改为 `+1.0`**（与前腿同号的镜像站姿）。实测 `+1.0` 时四条足板最低点同高（基座原点下方 0.166 m）；旧 `-1.0` 姿态后足抬高约 2.5 cm 且后足板呈竖直"鳍"状，狗会以前爪"坐"着并后仰。
> 2. **生成高度 `init_state.pos.z` 由 `0.2` 改为 `0.17`**。实测站立高度（足板底面到基座原点）为 **0.166 m**，而不是运动学链长度暗示的 ~0.37 m——dog921 的足板是倾斜的平板，只有下前缘接触地面。旧 0.2 m 会让足板陷入地面 3.4 cm，产生去穿透冲量。

**参数：**

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--num_steps` | 2000 | 物理步数（`0` = 一直运行直到关闭窗口） |
| `--gait_freq` | 1.5 Hz | 关节正弦运动频率（对角步态，对角腿同相位） |
| `--amp_deg` | 25 | 关节摆动幅度（度），髋关节减半 |
| `--headless` | 关 | 无图形界面运行 |
| `--device` | `cuda:0` | 也可用 `cpu`，但建议使用 GPU |
| `--root_z` | 1.0 | 初始根高度（m）；`0.17` 让足着地（实测站立高度 0.166 m），默认 1.0 用于空中步态演示 |
| `--no_pin_root` | 关 | 不每步重写根状态（让重力/接触动力学生效）；配合 `--root_z 0.17` 做站立测试 |
| `--rear_thigh` | 1.0 | 站立姿态的后大腿基准角（rad）；`1.0` = 与 `GEESUN_DOG_CFG` 一致的镜像站姿，`-1.0` = 旧"坐"姿态（消融对照） |
| `--calf_base` | -1.4 | 站立姿态的全部 calf 基准角（rad） |
| `--calf_amp_deg` | 0（= `--amp_deg`） | calf 专用摆动幅度（度）；calf 真实限位 `[-1.885, 0]`，base -1.4 时最大对称幅度仅 ~27.8°，放大 calf 摆动需配合 `--calf_base -1.1`（如 `--calf_base -1.1 --calf_amp_deg 40`，峰-峰 80°，范围 `[-1.798, -0.402]` 不触限位） |
| `--settle_steps` | 100 | `--no_pin_root` 模式下先在 `--root_z` 钉住根多少步（让 PD 收敛到站姿）再释放 |
| `--no_self_collision` | 关 | 关闭自碰撞（退化网格细条可能卡腿，消融用） |
| `--stiffness` / `--damping` | 0（=CFG 值） | 运行时覆盖 PD 增益（CFG 默认 k=69.0, b=1.38，2026-10-12 起按质量比 2.7611 从 GO2 的 k=25/b=0.5 线性缩放；旧默认 k=30, b=1） |
| `--print_contact` | 关 | 每 100 步打印各关节施加力矩（N·m） |

**用法：**

```bash
conda activate env_isaaclab_sim51
python scripts/geesun_dog/move_geesun_dog.py                    # 图形界面，2000 步
python scripts/geesun_dog/move_geesun_dog.py --num_steps 0      # 一直运行，直到关闭窗口
python scripts/geesun_dog/move_geesun_dog.py --headless --num_steps 300     # 无界面快速检查
python scripts/geesun_dog/move_geesun_dog.py --gait_freq 2.0 --amp_deg 35   # 更快/摆幅更大
# 站立测试（自由根 + 实测高度 + 镜像后肢姿态）：
python scripts/geesun_dog/move_geesun_dog.py --headless --num_steps 600 \
    --root_z 0.17 --no_pin_root --amp_deg 0 --settle_steps 100 --rear_thigh 1.0
```

**验证要点：**

1. `./unitree_rl_lab.sh -l` 能查到已注册任务 `Unitree-GeesunDog-Dog1-Velocity` 与 `Unitree-GeesunDog-LingsiD30W-Velocity`（位于 `tasks/locomotion/robots/geesun_dog/dog1|lingsi_d30w/`，复用 Go2 的速度跟踪任务结构；旧入口 `Unitree-GeesunDog-Velocity` 已移除）。
2. 控制台打印 `Using converted USD: /tmp/IsaacLab/geesun_dog/dog1.usd` 和 `Loaded robot joints: [12 个关节名]`。
3. 控制台每 100 步打印 `[step N] joint_pos (rad):`，12 个关节值偏离站姿基准角（PD 跟踪滞后）且对角腿成对一致（fr≈hl、fl≈hr）。注意：默认 1.5 Hz 下每 100 步（2.0 s）恰为整数倍周期，稳态后相邻打印落在同一相位、数值相同属正常现象（不是卡死）；想从日志直接看到振荡，可改用非整周期频率（如 `--gait_freq 1.7`）或观察图形界面。
4. 图形界面中机器人悬浮在离地约 1 m 处（基座被固定以便四条腿自由摆动），四条腿原地小跑。
5. 每次启动都会重新执行 URDF→USD 转换（`force_usd_conversion=True`，约 5~10 s，确保使用 `geesun_dog_urdf/geesun-dog/dog1` 的最新文件；Kit 日志中可见 `Saving Stage /tmp/IsaacLab/geesun_dog/dog1.usd`）。首次启动另需着色器编译（约 3~5 分钟）。如转换结果异常可 `rm -rf /tmp/IsaacLab/geesun_dog` 清除全部中间文件。

**站立姿态验证（9/23，自由根测试结论）：**

对 `--no_pin_root --root_z 0.17`（自由根、实测站立高度）做站立测试，结论如下：

| 测试 | 后大腿 | 释放方式 | 结果 |
|---|---|---|---|
| B3 | -1.0（旧姿态） | 钉住 2 s 后释放 | 后足竖直鳍状、抬高 2.5 cm，狗"坐"在前爪上，缓慢后仰趴伏（root z → 0.071） |
| C6/C10 | +1.0（镜像站姿） | 钉住 2 s 后释放 / 直接释放 | 前倾趴伏，root z → 0.030（基座底面恰好触地），calf 卡在下限 -1.885 |
| C5 | +1.0 | 关闭自碰撞 | 与 C6 逐点相同（自碰撞不是主因） |
| C7 | +1.0 | k=200, b=10 | 无法静立，向后"爬行"漂移（足缘接触 + 硬 PD 形成能量泵） |
| C8 | +1.0, calf -1.7 | 足板放平（calf 总角 -0.7） | 与 C6 相同（仍塌缩到同一姿态） |
| C9 | +1.0 | `--print_contact` | 钉住期间 12 关节施加力矩 ≈ 0 N·m —— 腿未被加载，身体由 pin 托着 |

**结论：** 资产链与 12-DOF 控制正常（空中 trot 演示通过）；但默认 PD（k=30, b=1）下**尚不能长时间静立**。塌缩机制：dog921 足板是倾斜平板，接触面只有下前缘（前足缘在膝前方 0.28 m，形成踮脚力臂），软 PD 在落地瞬态后缓慢屈曲（2 s 内 calf 到达下限 -1.885），后大腿网格下端在后足后方戳地，身体前倾直至基座底面（z=-0.030）触地。后续改进方向（按优先级）：① 为足部增加平底 collider（如 0.1×0.08 m 盒体）替代倾斜足板的边缘接触；② 调高 PD 增益并配合临界阻尼；③ 直接上 RL 策略训练（`Unitree-GeesunDog-Velocity`），不依赖纯 PD 静立。

**基础运动能力演示（9/24，A/B/C 日志演示，零代码改动）：**

站姿修正后复测基础运动能力，headless 日志演示（日志在 `outputs/geesun_demo/`；当时 Go2 训练占用同一 GPU，步时偏慢，不影响结果正确性）：

```bash
# A：空中踏步（根固定 1 m，12-DOF 关节控制 + trot 对称性回归）
python scripts/geesun_dog/move_geesun_dog.py --num_steps 400 --root_z 1.0 --headless
# B：地面站立（自由根、实测高度 0.17、镜像站姿）
python scripts/geesun_dog/move_geesun_dog.py --no_pin_root --root_z 0.17 --num_steps 400 --settle_steps 100 --print_contact --headless
# C：地面原地踏步（自由根，1.5 Hz trot，25° 幅值）
python scripts/geesun_dog/move_geesun_dog.py --no_pin_root --root_z 0.17 --num_steps 600 --settle_steps 100 --gait_freq 1.5 --amp_deg 25 --print_contact --headless
```

| 项 | 能力 | 结果 | 关键数据 |
|---|---|---|---|
| A | 12-DOF 关节控制 + 空中原地踏步 | **通过** | root 全程钉住稳定在 z=0.996；关节角偏离站姿基准（step 0 为精确站姿，step 100 起 12 关节全部偏离基准角），对角腿反相结构正确（如 fl_thigh=1.151 vs fr_thigh=0.915，分居 base=1.0 两侧；同相腿取值相近）；同相腿间微小不对称 ≤0.04 rad（自碰撞/初始接触扰动，不影响 trot 结构） |
| B | 地面接触 + 静立 | **部分**（与 9/23 结论一致） | z：0.166 → 0.161（t=2 s，约可维持 2 s）→ 0.037（t=4 s 塌缩）→ 趴伏稳定；塌缩后 calf 施加力矩 10–12.7 N·m（腿在撑地但不足以支撑身体） |
| C | 地面原地踏步 | **部分**（与 B 相同） | z 轨迹与 B 逐点一致（0.166→0.161→0.037→0.037）：1.5 Hz 原地踏步没有延缓塌缩；塌缩后腿部摆动被地面顶住，姿态保持趴伏 |

> **采样说明：** 脚本每 100 步打印一次（dt=0.02 → 间隔 2.0 s），而 1.5 Hz 步态恰好每 2.0 s 完成 3 个整周期，因此日志中的关节角每次打印都处于同一步态相位（混叠），看起来"冻结"——打印点之间关节实际在连续振荡；C 与 B 的打印值逐点相同也部分源于此（另因塌缩后腿部被地面顶住，摆动幅度本身很小）。

**结论：** 资产链、12-DOF 控制、地面接触与步态振荡均正常；地面运动的瓶颈仍是纯 PD 的支撑能力（k=30, b=1），与 9/23 站立姿态验证一致——改进优先级首选 RL 策略训练（`Unitree-GeesunDog-Velocity`），不依赖纯 PD 静立。

**GUI 渲染演示（10/8，calf 幅度放大）：**

去掉 `--headless` 即可在图形界面观察（Isaac Sim 窗口，相机自动跟随机器人；Go2 训练占用同一 GPU 时是慢动作效果）：

```bash
# A：空中踏步（calf 幅度放大：--calf_base -1.1 --calf_amp_deg 40）
python scripts/geesun_dog/move_geesun_dog.py --num_steps 400 --root_z 1.0 --calf_base -1.1 --calf_amp_deg 40
# C：地面原地踏步 + 塌缩（同一 calf 参数）
python scripts/geesun_dog/move_geesun_dog.py --no_pin_root --root_z 0.17 --num_steps 400 --settle_steps 100 \
    --gait_freq 1.5 --amp_deg 25 --calf_base -1.1 --calf_amp_deg 40
```

> **calf 幅度放大的原因（10/8）：** dog921 真实 calf 限位为 `[-1.885, 0]`，旧 base `-1.4` 时最大对称幅度只有 **27.8°**（下限侧余量 0.485 rad），25° 摆动已接近限位；且 calf 力臂短（只带动足板），视觉上摆动明显小于大腿。为此新增 `--calf_amp_deg`（默认 0 = 跟随 `--amp_deg`，原行为不变，方便消融对照），并把 `--calf_base` 移到 `-1.1`（限位中心方向）+ 40° 幅度：calf 峰-峰 80°（原 50°），范围 `[-1.798, -0.402]` 不触限位。空中演示（A）根钉在 1 m，站姿变化无影响；地面演示（C）站姿改变（膝更伸），塌缩轨迹可能与原 C 不同。
>
> 渲染日志：`outputs/geesun_demo/render_a_air_trot_gui_bigcalf.log`、`outputs/geesun_demo/render_c_ground_trot_gui_bigcalf.log`（9/24 首次渲染日志 `render_a_air_trot_gui.log` / `render_c_ground_trot_gui.log` 使用原参数 25°/base -1.4）。

**任务训练（可选）：**

```bash
# dog1（有足四足）训练：独立任务，变体由任务名锁定，无需设 GEESUN_DOG_VARIANT
./unitree_rl_lab.sh -t --task Unitree-GeesunDog-Dog1-Velocity --num_envs 24096
# lingsi_d30w（D30W 轮足）训练：独立任务，可与上面的 dog1 同时跑，run 目录互不覆盖
./unitree_rl_lab.sh -t --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 24096
# run 目录由 experiment_name 决定，两个变体各自独立：
#   dog1        -> logs/rsl_rl/unitree_geesun_dog1/<时间戳>/
#   lingsi_d30w -> logs/rsl_rl/unitree_geesun_lingsi_d30w/<时间戳>/
tensorboard --logdir logs/rsl_rl   # 同时看两个变体的曲线
# 课程状态（速度命令范围进度）也各自独立：
#   logs/rsl_rl/unitree_geesun_dog1/curriculum_state.json
#   logs/rsl_rl/unitree_geesun_lingsi_d30w/curriculum_state.json
```

> **6h 监控/自动调参实例（2026-10-12 起）：** GeesunDog 战役有独立的监控闭环，与 Go2 的
> 互不干扰（独立 state 目录 `outputs/monitor_dog/`、`outputs/autotune_dog/`）：
> ```bash
> nohup bash scripts/monitor_tb_check_dog.sh >> outputs/monitor_dog/monitor.log 2>&1 &
> # lingsi_d30w 战役用独立闭环（state 目录 outputs/monitor_d30w/、outputs/autotune_d30w/）：
> nohup bash scripts/monitor_tb_check_d30w.sh >> outputs/monitor_d30w/monitor.log 2>&1 &
> ```
> 每 6h 检查曲线 → 恶化时自动停止训练、修改超参并重启。每个战役只改自己的文件：
> dog1 编辑 `geesun_dog/dog1/velocity_env_cfg.py` + PPO 类 `UnitreeGeesunDogDog1PPORunnerCfg`；
> d30w 编辑 `geesun_dog/lingsi_d30w/velocity_env_cfg.py` + PPO 类 `UnitreeGeesunDogLingsiD30WPPORunnerCfg`。
> 报告：`outputs/monitor_dog/report.md`（d30w：`outputs/monitor_d30w/report.md`）；关掉自动调参：
> `touch outputs/autotune_dog/DISABLED`（d30w：`touch outputs/autotune_d30w/DISABLED`）。
> **（2026-10-14 起）两个变体的 PPO 类与 env cfg 文件已完全独立，可以同时开自动调参**
> （此前共用一份、必须错开跑的限制已解除）。

> **注意：** 若关节位置冻结在固定姿态，说明腿与地面或彼此卡死——可在脚本中调高基座高度（`default_root[0, 2]`）或减小 `--amp_deg`。

**lingsi_d30w（D30W 轮足，厂家 URDF，2026-10-13 起）：** 变体目录含厂家 SolidWorks（CAD 软件）直接导出的
`urdf/lingsi_d30w.urdf`（robot（机器人）名 A01mW，17 link（连杆）：trunk（躯干）+ 4×hip/thigh/calf/wheel；
16 joint（关节），其中 4 个轮关节为 `revolute`（旋转关节）limit ±999999，等效 `continuous`（连续旋转））
+ 17 个厂家 STL 网格（`meshes/`，来自厂家包 `meshes-ok.zip`）。加载时 `_prepare_geesun_dog_urdf()`
自动把厂家命名（`FR_hip_joint`/`trunk`/`FR_wheel_motor`）改写为代码约定命名
（`joint_fr_hip`/`base_link`/`joint_fr_wheel`），mesh（网格）引用改写为绝对路径，并按
`urdf/D30W关节电气参数.xlsx` 覆盖 effort/velocity（力矩/角速度）上限，可直接加载：

```bash
python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --headless --num_steps 400
# 轮关节按 --wheel_speed 匀速自转（默认 10 rad/s，0 = 锁死只动腿）
# GUI 渲染（一直运行直到关窗；D30W calf（小腿）限位 [0.536, 2.775] rad，calf 幅度取小避免触限位）：
python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --num_steps 0 --root_z 1.0 \
    --calf_base 0.8 --calf_amp_deg 15 --wheel_speed 10
```

**PD 参数（参考 `urdf/D30W关节电气参数.xlsx`，输出端）：** 执行器配置 `UnitreeActuatorCfg_D30W`
（`unitree_actuators.py`，与 GO2/dog1 隔离），effort/velocity（力矩/角速度）上限由 URDF 重写
直接取 Excel 值，PD 增益取 Excel 上限内的实测稳定值：

| 关节组 | 型号 | 力矩上限 (N·m) | 角速度上限 (rad/s) | KP（上限 500） | KD（上限 5） |
| --- | --- | --- | --- | --- | --- |
| hip/thigh（髋/大腿） | LS100_WLA/WLH | 120 | 40 | 100 | 2 |
| calf（小腿） | LS100_WLK | 200 | 20 | 100 | 2 |
| wheel（轮） | LS75_WL | 14 | 65 | 0（速度伺服） | b=1（速度环增益）+ armature（转子惯量）0.01 |

**⚠ 厂家 URDF 自带 limit 与 Excel 的口径差异（2026-10-13 记录）：** 厂家 URDF（`A01mw (3).urdf`，
已同步为 `lingsi_d30w.urdf`）的 `<limit>` 与 `D30W关节电气参数.xlsx` **并不一致**，代码按用户确认
（2026-10-13）以 **Excel 为准**统一覆盖：

| 关节组 | URDF 厂家 limit | Excel（采用） | 差异说明 |
| --- | --- | --- | --- |
| hip/thigh（髋/大腿） | 72 N·m / 27 rad/s | 120 N·m / 40 rad/s | Excel 激进 ~1.7×（疑为连续额定 vs 峰值口径） |
| calf（小腿） | 136 N·m / 14 rad/s | 200 N·m / 20 rad/s | Excel 激进 ~1.5×（同上） |
| wheel（轮） | 20 N·m / 65 rad/s | 14 N·m / 65 rad/s | Excel 保守（厂家轮子口径可能是峰值） |

生效代码共两处，改口径时**必须两处同步**：
1. `unitree.py::_prepare_geesun_dog_urdf()` 内三条 `re.sub` 把 URDF `<limit>` 重写为 Excel 值
   （同时兼容两版 URDF 原值 72/27、136/14、20/65 与 100/20、160/15、14/65）；
2. `unitree_actuators.py::UnitreeActuatorCfg_D30W` 的力矩-速度曲线（X1/X2 拐点、Y1/Y2 饱和力矩
   = 120）+ `unitree.py` 各关节组实例覆盖（calf Y=200、wheel Y=14）。

**sim2real（仿真到实机）注意：** 若实机驱动保护按 URDF 口径（72/136 N·m）执行，训练策略可能用到
实机放不出来的力矩；保守做法是删除上面第 1 条的三条 regex 并把第 2 条的 Y 值同步调小
（腿 72/136、轮保持 14），随后重新训练。

> **为什么不用 Excel 的 KP=500/KD=5 最大值（2026-10-13 实测调参记录）：** Excel 给的是**上限**
> 而非推荐值。显式 PD（explicit PD，力矩 = KP·误差 + KD·误差速度）在 dt=5 ms（毫秒）下对本机的
> 小关节惯量会踩进**离散负阻尼区**（b·dt/J ≥ 2）：从精确保时的静止开始，0.1 N·m 级重力微扰在
> 5 步内被指数放大到力矩饱和（±120 N·m）bang-bang（来回打满），腿 0.5 s 内被甩开 ±0.6 rad。
> 实测矩阵（空中 PD 追踪，`--print_contact`）：KP=500/KD=5 发散、KP=60/KD=5 发散、轮速度伺服
> b=5 轮速 0.5 s 内 ±20 rad/s（b·dt/J≈5）；**KP=100/KD=2 + 轮 b=1/armature 0.01 稳定**
> （地面静立 2 s 下沉 <1 cm、水平漂移 <15 cm 后收敛，是训练关心的工况；空中无接触工况仍有
> 慢漂移，留给 RL 策略闭环纠正；KP=69/KD=1.38（dog1 同款）则空中精确静止但地面半蹲至 z≈0.36，
> 二选一取地面表现）。trunk 碰撞体也已缩小（厂家 mesh 凸包
> 罩住髋/大腿体积，去穿插力 ~80 N·m 会把腿炸开）。
> 调参脚本：`python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --headless \
> --num_steps 300 --root_z 1.5 --amp_deg 0 --wheel_speed 0 --stiffness <KP> --damping <KD>`；
> 诊断开关 `D30W_NO_COLLISION=1` 可临时移除全部碰撞体隔离接触力。

注意：关节 origin（关节原点）来自厂家 CAD，**尚待实测标定**；关节限位（hip ±0.698、thigh [-3.054, 1.0]、
calf [0.536, 2.775] rad）为厂家导出值。STEP → URDF（统一机器人描述格式）自动转换脚本
`scripts/lingsi_d30w/step_to_urdf_d30w.py` 已于 2026-10-13 删除（厂家 URDF 到位后不再需要，
git 历史可找回）；原始 `D30W轮足外发.STEP`（204 MB）已从本地删除（.gitignore 条目保留，
需要时向厂家重新索取）。从 STEP 重新转换的完整历史流程见 [doc/step_to_urdf.md](doc/step_to_urdf.md)。

> **注意（10/8 上下颠倒问题，2026-10-13 已解决）：** 旧 STEP 转换版 URDF 是 **z 朝下坐标系**导出，
> Isaac Sim 为 z-up，直接加载时整机上下颠倒（轮子在机身上方）。现已改用厂家 **z-up** URDF
> （`GEESUN_DOG_VARIANT_SPECS["lingsi_d30w"]`：`z_down=False`，无需 180°（度）root（根节点）翻转，
> `root_z=0.61`，站姿 thigh（大腿）-0.397 / calf 0.8），训练 / `play.py` / `move_geesun_dog.py`
> 各入口一致，左右镜像副作用也随之消失。

**验证训练结果（lingsi_d30w 专用步骤）：** 通用流程见上文[验证训练结果](#验证训练结果)（回放 →
定量测试 → TensorBoard → 日志检查 → 验收清单），只需把入口换成
`--task Unitree-GeesunDog-LingsiD30W-Velocity`：

```bash
# 1. 训练前基线：PD 静立应 2 s 下沉 <1 cm（不达标先按上文 PD 调参，不要带病训练）
python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --headless \
    --num_steps 400 --no_pin_root --root_z 0.61 --settle_steps 100 --amp_deg 0 --wheel_speed 0
# 2. 回放训练策略（自动选最新 checkpoint，加 --headless 录屏）
./unitree_rl_lab.sh -p --task Unitree-GeesunDog-LingsiD30W-Velocity
# 3. 曲线：重点关注 Episode_Termination/base_contact（应接近 0）、
#    Curriculum/terrain_levels_*、Curriculum/lin_vel_cmd_levels/*_max（应稳步上升）
tensorboard --logdir logs/rsl_rl/unitree_geesun_lingsi_d30w
# 4. 与 dog1 的消融对照只改一个变量：--task 任务名
#    （Unitree-GeesunDog-Dog1-Velocity ↔ Unitree-GeesunDog-LingsiD30W-Velocity），
#    其余全不动；用 diff 核对两个 velocity_env_cfg.py 的差异是否只有资产/足部/动作项
```

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

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
        --task Unitree-GeesunDog-LingsiD30W-Velocity    --num_envs 20096 \
        --resume --load_run 2026-10-14_08-47-04 2>&1 | tee /tmp/train_GeesunDog_resume.log 

    # 训练同时录制视频：每 100 迭代一段 10 s（500 步 @ 50 fps），相机侧向跟拍机器狗。
    # video_interval 的单位是 env.step() 调用次数 = 迭代数 × num_steps_per_env(24)，见「验证训练结果 §0」
    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
        --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 20096 --resume --load_run 2026-10-15_01-16-28 \
        --video --video_length 500 --video_interval 10000 --camera_view side 2>&1 | tee /tmp/train_video.log

    # ⚠ 下面是 2026-10-14 当时的历史命令：run 2026-10-14_23-26-00 已停在 model_7900.pt，
    # 当前战役最新 run 是 2026-10-15_01-16-28（model_15300.pt）。今天续训请用下面「当前推荐」版。
    # 从旧 run 续训前必须先备份/移走 terrain_levels_state.json 与 curriculum_state.json
    # （sidecar，旁路状态文件；见「验证训练结果 § 前置检查」），否则旧策略会被灌入最新战役的地形等级。

    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
    --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 20096 \
    --resume --load_run 2026-10-15_01-16-28 \
    --video --video_length 250 --video_interval 10000 --video_start_frac 0.5 \
    --video_start_episode_frac 0.35 --camera_view diag --camera_distance 0.57 --camera_height 1.2 --camera_focal 21            
            

    # 当前推荐（2026-10-15 起）：续训最新 run，录像参数与守护进程逐字一致（camera 三项等于默认值，可省略）
    # ⚠ 必须带 conda run -s（--no-capture-output，不捕获输出），否则日志全程 0 字节 —— 见下方「conda run 吞日志」
    conda run -s -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
        --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 20096 \
        --resume --load_run 2026-10-15_01-16-28 --checkpoint model_15300.pt \
        --video --video_length 250 --video_interval 10000 \
        --video_start_frac 0.5 --video_start_episode_frac 0.35 --camera_view diag \
        --camera_distance 0.57 --camera_height 1.2 --camera_focal 21 2>&1 | tee /tmp/train_d30w_ht10x_manual.log

    # 等价写法（绕开 conda run，用环境解释器绝对路径；守护进程脚本用的就是这个）
    /home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/rsl_rl/train.py --headless \
        --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 20096 \
        --resume --load_run 2026-10-15_01-16-28 --checkpoint model_15300.pt \
        --video --video_length 250 --video_interval 10000 \
        --video_start_frac 0.5 --video_start_episode_frac 0.35 --camera_view diag \
        --camera_distance 0.57 --camera_height 1.2 --camera_focal 21 2>&1 | tee /tmp/train_d30w_ht10x_manual.log

    ```

> **⚠ `conda run` 吞日志（2026-10-15 实测；"训练没有生效"的唯一真相）：** `conda run` 默认
> **capture output（捕获输出）**——它接管子进程的 stdout（标准输出）/ stderr（标准错误），
> **直到子进程退出才一次性打印**。于是 `conda run ... | tee /tmp/xxx.log` 里的 `tee` 全程收到 0 字节，
> 日志文件创建后一直是空的，看起来"命令没有生效"，**而训练进程其实活着**（实测：日志 0 字节，
> 但 `train.py` 已跑 4 分钟、CPU 193%、GPU 已占 6 GB）。
>
> 修法（二选一，上面两条命令已改好）：
> 1. 加 `-s`（= `--no-capture-output` / `--live-stream`，不捕获输出、实时透传）；
> 2. 绕开 `conda run`，直接用该环境的解释器绝对路径（`scripts/monitor_tb_check_d30w_ht10x.sh` 用的就是这个）。
>
> **判定"训练到底有没有在跑"的三步法（不要看日志文件大小）：**
>
> ```bash
> pgrep -af 'train[.]py'                                                              # 有 PID = 进程活着
> nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader           # 训练期 ~20-25 GiB
> ls -lat logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/ | head -3           # 出现新时间戳目录 = 已建 run
> ```
>
> 补充两点容易误判的现象：
> - **`--resume`（续训）也会新建一个带新时间戳的 run 目录**（权重从 `--load_run` 读，日志/checkpoint 写新目录），
>   所以启动早期"没有新目录"是正常的：Isaac Sim（仿真器）启动 + URDF→USD 转换 + 20096 环境地形生成需数分钟，
>   期间 GPU（图形处理器）占用低、CPU（中央处理器）满载。
> - `outputs/<日期>/<时刻>/.hydra/config.yaml` 已写出而 `logs/rsl_rl/` 无新目录 = 卡在 Isaac Sim 启动阶段，
>   不是参数错误（参数错误会在 `hydra.log` 里留下 argparse（命令行解析）报错）。

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

`scripts/rsl_rl/test_walk_torque.py` 使用训练好的 checkpoint 进行定量测试，并记录行走指标和每个关节的执行器力矩。通过 `--terrain` 选择测试地形：

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
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --steps 500

# 指定 checkpoint 时，将 RUN_ID 和 checkpoint 文件名替换为实际值
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --checkpoint logs/rsl_rl/unitree_go2_velocity/RUN_ID/model_7300.pt \
    --steps 500

# 复杂地形压力测试，推荐用于电机选型参考
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-Go2-Velocity \
    --terrain complex \
    --steps 1000

# 使用任务的 play 配置地形，省略 checkpoint 时自动选择最新结果
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py --task Unitree-Go2-Velocity --terrain play

# GeesunDog（Geesun 狗，dog1）关节力矩统计（硬件选型参考），换 --task 即可
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
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
> 2. 或运行时加 `-u` 关闭缓冲：`python -u scripts/rsl_rl/test_walk_torque.py ...`。

> **回放相机跟随（2026-10-12 起，2026-10-14 增加自由视角）：** `scripts/rsl_rl/play.py` 录像/回放时视角默认自动跟随机器人
> （走远不再出画；实现见 play.py 的 `_follow_camera()`，每步更新视口相机位姿），风格由
> `--camera_view` 参数选择：`side`（侧面）为默认——相机在机器人侧方 2.2 m、上方 1.1 m，
> 保持看向机首，不随偏航角（yaw）旋转（侧向跟拍）；`rear`（后面）——相机在机器人身后
> 2.2 m、上方 1.1 m，随偏航角转动（身后追拍）；`free`（自由视角，2026-10-14 新增）——机位只在
> 首帧设置一次，之后**完全不动**，可在 Kit 视口（viewport，图形窗口）里自由拖动/旋转/缩放，
> 适合录楼梯这种需要看全局构图的场景。初始机位用 `--camera_eye X Y Z` / `--camera_target X Y Z`
> 指定（世界坐标，米），不指定则默认取出生点斜上方 3.5 m / 1.6 m。
> 用法：`python scripts/rsl_rl/play.py ... --camera_view side`（默认，可省略）/ `rear` / `free`。

> **电机选型（motor sizing）：** 关节力矩数据与选型结论汇总见 [doc/motor_sizing.md](doc/motor_sizing.md)。

## 验证训练结果

训练完成后，建议先目视回放，再进行平地和复杂地形定量测试

### 前置检查（pre-flight check，启动前检查）与 sidecar（旁路状态文件）规则

**任何手工启动训练 / 录像之前，先确认 GPU（图形处理器）空闲并停掉 6h 守护进程（daemon，后台监控循环）**
——同一 GPU 只能跑一个 IsaacSim（仿真器）实例：

```bash
ps -eo pid,etime,args | grep -E 'monitor_tb_check|train[.]py|play[.]py' | grep -v grep
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader   # 空闲时期望 ~2.7 GiB / 32.6 GiB
MON_PID=$(pgrep -f 'monitor_tb_check_d30w_ht10x[.]sh')
[ -n "$MON_PID" ] && { pkill -P "$MON_PID" sleep; kill "$MON_PID"; }
```

> **为什么必须先停守护进程：** 它每 6 h 一轮，检测到训练进程 DEAD 时会自动
> `--resume --load_run <最新 run> --checkpoint <最新 model_*.pt>` 重启训练
> （`scripts/monitor_tb_check.py:234`），与手工 run 抢同一块 GPU；判定曲线恶化时还会
> SIGTERM→SIGKILL 杀掉手工 run，并按它自己的 `MON_EXTRA_TRAIN_ARGS` 重启（录像参数与手工命令不一致）。
> 停止 / 重启方法见下文「10× 网络规模消融」小节第 **2b** 步。

**sidecar（旁路状态文件）规则**（`scripts/rsl_rl/train.py:447-459`）：`--resume`（续训）时
`terrain_levels_state.json`（地形等级）与 `curriculum_state.json`（速度命令范围）**被保留并加载**，
只有 fresh（重训）才删除它们。二者按 `experiment_name` 目录共享，**不属于某个 run**：

| 情形 | 后果 |
|---|---|
| 从**旧 run** 续训（例：`--load_run 2026-10-14_23-26-00`，其最新 checkpoint 只到 `model_7900.pt`） | 旧策略被直接灌入最新战役的 sidecar（实测 `terrain_levels` 均值 6.006、`x_max` ±0.5、`step` 178000）→ 大面积摔倒 → 等级雪崩，并把雪崩结果**写回同一个 json**，反向污染最新战役状态（2026-10-12 崩溃模式的复现路径） |
| 改 `--num_envs`（并行环境数）后续训 | `curriculums.py:48-49` 校验 `num_envs` / `max_level` 不匹配 → `[WARN] ... keeping the random initial levels`，等级从 `max_init_terrain_level` 重爬 |

跨 run / 回退消融前，必须先备份并移走两个 sidecar：

```bash
cd logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
mv curriculum_state.json     curriculum_state.json.bak_<ITER>
mv terrain_levels_state.json terrain_levels_state.json.bak_<ITER>
# 实验结束后按原名逐字移回（课程项按仓库相对路径读取，文件名不可改）
```



### 0. 训练时录制视频（in-training video recording）——**已重新启用（re-enabled，2026-10-14 23:45，5 s 短片）**

> **当前状态：** `scripts/monitor_tb_check_d30w_ht10x.sh` 第 50 行**已启用**录像：
> `export MON_EXTRA_TRAIN_ARGS="--video --video_length 250 --video_interval 2400 --video_start_frac 0.5 --video_start_episode_frac 0.35 --camera_view diag --camera_distance 0.57 --camera_height 1.2 --camera_focal 21"`
> —— `--video_length 250` = **5.0 s**（`render_fps = 1/step_dt = 1/0.02 = 50`）；`--video_interval 2400`
> 会被 episode 相位锁定吸附为 **2000 步 = 2 个 episode = 83 迭代**一段。
> **历史状态（2026-10-14 曾停用，保留作消融记录）：** `MON_EXTRA_TRAIN_ARGS=""` = 与启用录像前逐字一致
> （消融安全）；停用原因是常驻 +4 GB 显存（RTX 渲染全程开启）+ 约 12% 占空比。做无录像对照就改回空串。
> **重新启用**：把下面这一行粘贴到该脚本的 `export MON_EXTRA_TRAIN_ARGS=`（参数均已实测）：
>
> ```bash
> export MON_EXTRA_TRAIN_ARGS="--video --video_length 500 --video_interval 2400 --video_start_frac 0.5 --video_start_episode_frac 0.35 --camera_view diag --camera_distance 0.57 --camera_height 1.2 --camera_focal 21"
> ```
>
> 启用后**必须重启守护进程**（守护进程持有的是启动时的环境变量，改文件不会生效），且**必须在 GPU
> 空闲时启动训练**：2026-10-14 实测，在另一个 IsaacSim 实例占用 GPU 时启动录像训练，RTX 渲染器
> 初始化失败，产出一段 250 帧全同空白画面（299 KB）。

`scripts/rsl_rl/train.py` 自带训练内录像参数，训练过程中自动产出视频，无需额外脚本：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--video` | 关闭 | 开启训练内录像，并**自动强制** `--enable_cameras`（相机渲染） |
| `--video_length` | 500 | 每段视频的步数；`render_fps = 1/step_dt = 50`，故 **500 = 10 s**、200 = 4 s |
| `--video_interval` | 2000 | 两段录像之间的间隔，**单位是 `env.step()` 调用次数**（见下方单位坑） |
| `--video_start_frac` | 无 | **首段延迟 = 该比例 × 一个检查点（checkpoint，检查点）间隔**（`save_interval` = 100 迭代）；`0.5` = 正好在两个 checkpoint 中间开录，绝不在出生点开录 |
| `--video_start_episode_frac` | 无 | **episode 相位锁定（phase lock，相位锁定）**：把每段录像钉在 episode 的该相位（`0.35` = 20 s episode 的第 7 s 起）；会自动把 `video_interval` 吸附为整数个 episode，使相位永久锁定 |
| `--video_start_run_frac` | 无 | 首段延迟 = 该比例 × 本次剩余迭代数（`max_iterations` − 续训起点） |
| `--camera_view` | `diag` | **跟拍相机（follow camera，跟拍相机）**：`diag`（斜后方高俯拍）/ `rear`（身后追拍）/ `side`（侧向跟拍，旧默认，见下方邻居问题）/ `free`（自由视角，机位只设一次） |
| `--camera_distance` / `--camera_height` / `--camera_focal` | 0.57 / 1.2 / 21 | `diag` 的水平偏移（米，后/左各半）/ 高于机身的垂直偏移（米）/ 录像期间临时收窄的焦距（毫米，录完恢复） |
| `--camera_eye` / `--camera_target` | 出生点斜上方 3.5 / 1.6 m | 仅 `--camera_view free` 用：初始机位（世界坐标，米） |

输出：`<run>/videos/train/rl-video-step-<N>.mp4`（1280×720, 50 fps），**相机每步跟随 `env_0` 的机器狗**
（`FollowCameraWrapper`，见下）。

```bash
# 训练 + 每 100 迭代录一段 10 s 视频，斜后方高俯拍跟随机器狗，避开出生密集网格
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/train.py --headless \
    --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 20096 \
    --video --video_length 500 --video_interval 2400 \
    --video_start_frac 0.5 --video_start_episode_frac 0.35 \
    --camera_view diag --camera_distance 0.57 --camera_height 1.2 --camera_focal 21
```

> **⚠ 单位坑（2026-10-14 实测）：** `video_interval` 由 gymnasium `RecordVideo.step_id` 计数，它只在
> 每次 `env.step()` 调用时 +1；rsl_rl 每个迭代调用 `num_steps_per_env = 24` 次，所以它的单位是
> **策略步（policy step，策略步）调用次数，不是 env steps（环境步）**：
>
> ```
> video_interval = 期望迭代数 × num_steps_per_env(24)
> 每 100 迭代一段 → --video_interval 2400
> ```
>
> 按 env steps 算出的 `48230400`（= 20096 envs × 24 × 100）相当于 200 万迭代 → **永不触发**。
> 首段在 `step_id == 0`（训练一开始）就录制，可立刻用 `ffprobe` 验收。

**代价（2026-10-14 实测：lingsi_d30w 10× 网络 + 20096 envs）：**

| 项 | 无录像 | 带录像 + 跟拍 |
|---|---|---|
| 显存（VRAM） | 21.0 GB | **24.7 GB**（RTX 渲染全程开启，常驻 +4 GB） |
| 迭代耗时 | 3.5 s | 录像写入期间 ~5.8 s（500 帧 ≈ 21 个迭代；跟拍相机每步一次 3 浮点 GPU→CPU 同步，约 +0.2 s），录完回到 ~3.7 s |
| 均摊开销 | — | ~45 s / 100 迭代（约 12% 占空比） |

**与 6h 监控闭环联动：** 监控 `scripts/monitor_tb_check.py` 与自动调参 `scripts/autotune.py` 的重启
命令都通过环境变量 `MON_EXTRA_TRAIN_ARGS`（训练附加参数）透传这些参数，因此自动续训 / 自动调参
重启后录像参数**不会丢失**；默认值为空 = 完全保持旧行为，其他战役不受影响（消融安全）：

```bash
# scripts/monitor_tb_check_d30w_ht10x.sh 内（该战役已启用）
export MON_EXTRA_TRAIN_ARGS="--video --video_length 500 --video_interval 2400 --camera_view side"
# 做无录像对照：export MON_EXTRA_TRAIN_ARGS=""
```

**跟拍相机（follow camera，跟拍相机）原理：** `RecordVideo` 的帧来自
`env.cfg.viewer.cam_prim_path`（默认 `/OmniverseKit_Persp`，即 Kit 视口相机，1280×720），这是一台
**固定机位**相机——20096 个环境铺满整片地形网格时，机器狗几秒内就走出了画面。`train.py` 的
`FollowCameraWrapper`（移植自 `play.py` 已验证的 `_follow_camera()`）在**录像期间**每步把这台相机
搬到 `env_0` 机器狗身上（`side`：侧方 2.2 m、上方 1.1 m，看向机首、不随偏航角（yaw）旋转；
`rear`：身后 2.2 m 追拍、随偏航角转动；`free`：首帧定机位后完全不动）。非录像期间不搬机位、
零开销。日志会打印 `[INFO] Follow camera (跟拍相机) enabled for training videos: view=side`。

**验收（2026-10-14 实测）：**

```bash
V=<run>/videos/train/rl-video-step-0.mp4
ffprobe -v error -show_entries stream=width,height,nb_frames,avg_frame_rate \
        -show_entries format=duration,size -of default=noprint_wrappers=1 $V
# 期望：1280x720, nb_frames=500, duration=10.0, ~12 MB（固定机位全景只有 ~0.8 MB）
for t in 0 2.5 5 7.5 9.9; do ffmpeg -v error -ss $t -i $V -frames:v 1 -y /tmp/fr_$t.png; done
```

判读：跟拍生效时，画面中心区域在**整段 10 s 内**都保持高方差（实测 `centre_std ≈ 93–103`，即机器狗
一直在画面里）；固定机位下机器狗走远后中心会退化成平坦地形（方差骤降）。

> **已知小瑕疵：** 每段第 1 帧是 RTX（实时光追）渲染预热帧（全黑，IsaacLab 在空数据时返回零图），
> 500 帧里占 1 帧（20 ms），不影响判读。

> 训练内录像只跟随 **`env_0`** 一个环境；要看清步态细节、指定地形与命令速度，用
> `scripts/rsl_rl/play.py`（`--terrain` / `--cmd_x` / `--camera_view`，见下一节）。

### 1. 复杂地形回放与录像

`scripts/rsl_rl/play.py` 用训练好的 checkpoint（检查点）目视回放并录制视频（video）。
地形由 `--terrain`（地形）选择，预设（terrain presets，地形预设）统一放在
`scripts/rsl_rl/terrain_presets.py`，子地形（sub-terrain）参数**从各机器人自己的 task cfg 读取**，
因此轮足机器人不会被要求爬超过其轮半径的台阶。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--terrain` | `play` | `play`（任务 play 配置）、`flat`（平地）、`random_rough`（随机粗糙）、`stairs`（楼梯）、`complex`（混合复杂地形：flat + random_rough + pyramid_stairs，5 行 × 12 列，出生覆盖全部难度行）。 |
| `--stair_height MIN MAX` | 读 task cfg | 覆盖楼梯踏步高度（米）。默认从 task cfg 读取：`lingsi_d30w` 与 GO2 现已**一致**为 `0.05 0.23`（2026-10-14 起，严格消融对照）。轮足保守测试可显式 `--stair_height 0.03 0.10`（轮半径 0.095 m）。 |
| `--video` | 关闭 | 录制视频，自动开启 `--enable_cameras`（相机渲染）。 |
| `--video_length` | 200 | 录制步数；`render_fps = 1/step_dt = 50`，故 750 步 ≈ 15 s。 |
| `--video_tag` | `play` | 视频写入 `<run>/videos/<tag>/`，不同地形的录像互不覆盖。 |
| `--camera_view` | `side` | `side`（侧面跟拍）/ `rear`（身后追拍）/ `free`（自由视角，首帧定机位后不跟随，配 `--camera_eye` / `--camera_target`）。 |
| `--env_cfg_file` | 无 | **用该 run 保存的 `params/velocity_env_cfg.py` 快照回放**。当 task cfg 在训练后被改动（例如给 critic（价值网络）观测加了 `height_scanner`（高度扫描传感器），观测维度从 76 变 263）时，直接加载旧 checkpoint 会报 `size mismatch for critic.0.weight`，此时必须用本参数。 |
| `--cmd_x / --cmd_y / --cmd_z MIN MAX` | play 全范围 | 覆盖速度命令范围，例如只测前进 `--cmd_x 0.3 0.8`。 |
| `--no_standing` | 关闭 | 关闭站立环境（standing envs），保证每个机器人都持续行走（录像推荐）。 |
| `--no_curriculum` | 关闭 | 关闭课程项（curriculum terms），地形难度在回放中保持不变（录像推荐，且不会污染 `curriculum_state.json`）。 |
| `--episode_length_s` | 无（用 cfg 的 20 s） | 覆盖 episode 长度（`env_cfg.episode_length_s`，默认 20 s = 1000 步）。录 30 s（1500 帧）时设 `35`，整段不会出现锁步复位（lockstep reset，机器狗同时回到出生点）。不带该参数 = 行为与旧版逐字一致。 |

```bash
# 自动选择最新 checkpoint
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-Go2-Velocity

# 或指定训练运行目录
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-Go2-Velocity --load_run RUN_ID

conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py \
    --task Unitree-GeesunDog-Dog1-Velocity --load_run 2026-10-13_10-07-28


logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-14_16-12-31
# 复杂地形录像（lingsi_d30w 轮足，2026-10-14 实测）：
# 必须用 --env_cfg_file 指向该 run 的快照（该 run 训练时没有 height_scanner），
# 并用 --stair_height 0.03 0.10 把台阶压到轮足能爬的范围。
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/play.py --headless --video --video_length 3050 --video_tag stairs \
    --camera_view side --num_envs 4 --no_standing --no_curriculum \
    --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --checkpoint logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-14_16-12-31/model_2800.pt \
    --env_cfg_file logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-14_16-12-31/params/velocity_env_cfg.py \
    --terrain stairs --stair_height 0.03 0.30 \
    --cmd_x 0.1 0.1 --cmd_y -0.1 0.1 --cmd_z -0.3 0.3
# 输出：<run>/videos/complex/rl-video-step-0.mp4（1280x720, 50 fps）
# 分地形定位短板：把 --terrain 换成 stairs / random_rough，并换 --video_tag 同名
```

观察要点：
- 机器人能否稳定行走
- 是否能适应不同地形
- 步态是否自然
- 是否出现侧翻、摔倒或明显打滑

> **注意：** 录像需要 GPU 渲染，同一时刻只能有一个 Isaac Sim 实例（见「关键契约」），录像前先停训练。
> 用 `ffprobe -show_entries stream=width,height,nb_frames -show_entries format=duration <mp4>` 校验产出。

#### 楼梯演示录像（lingsi_d30w 楼梯 + height_scanner 演示，2026-10-14 起）

楼梯 run（训练批次）训练完成后，按下面命令录楼梯。**必须带 `--env_cfg_file`**：楼梯 run 训练时 critic（价值网络）
观测含 `height_scanner`（高度扫描传感器）共 263 维，而当前 task cfg 若与之不同，直接加载 checkpoint（检查点）会报
`size mismatch for critic.0.weight`；`--env_cfg_file` 让回放用该 run 自己的 `params/velocity_env_cfg.py` 快照，维度自然对齐。

```bash
# 0) 先停训练（同一 GPU 只能跑一个 IsaacSim 实例）
pkill -f 'train[.]py.*Unitree-GeesunDog-LingsiD30W-Velocity'

# 1) 楼梯录像：侧向跟拍（默认），750 步 ≈ 15 s，4 个环境降低渲染负担
RUN=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/<RUN_ID>
python scripts/rsl_rl/play.py --headless --video --video_length 750 --video_tag stairs \
    --camera_view side --num_envs 4 --no_standing --no_curriculum \
    --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --checkpoint $RUN/model_<ITER>.pt \
    --env_cfg_file $RUN/params/velocity_env_cfg.py \
    --terrain stairs --cmd_x 0.1 0.1 --cmd_y -0.1 0.1 --cmd_z -0.3 0.3
# 输出：<RUN>/videos/stairs/rl-video-step-0.mp4（1280x720, 50 fps）

# 2) 自由视角版：看整段金字塔楼梯的全局构图（机位固定，Kit 视口可自由拖动）
python scripts/rsl_rl/play.py --headless --video --video_length 750 --video_tag stairs_free \
    --camera_view free --camera_eye 6.0 6.0 2.2 --camera_target 0.0 0.0 0.2 \
    --num_envs 4 --no_standing --no_curriculum \
    --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --checkpoint $RUN/model_<ITER>.pt --env_cfg_file $RUN/params/velocity_env_cfg.py \
    --terrain stairs --cmd_x 0.2 0.6
# 日志会打印 [INFO] Free camera (自由视角): eye=[...] target=[...]

# 3) 逐地形录像：--terrain 换 flat / random_rough / complex，并把 --video_tag 改成同名（避免互相覆盖）
# 4) 校验产出
ffprobe -show_entries stream=width,height,nb_frames -show_entries format=duration \
    $RUN/videos/stairs/rl-video-step-0.mp4
```

要点：
- `--video_tag`（视频标签）**必须按地形改名**，否则 `videos/<tag>/` 互相覆盖。
- `--num_envs 4`：录像走 RTX（实时光追）渲染，环境数多会显著增显存并拖慢。
- `--no_standing`（关闭站立环境）保证机器人在录像里持续行走；`--no_curriculum`（关闭课程）保证地形难度在回放中不变，且**不会污染** `curriculum_state.json`（课程状态文件）。
- 楼梯难度：`--terrain stairs` 是 5 行 × 4 列网格、出生随机到最难行（`difficulty=1.0`），踏步高即 task cfg 的 `step_height_range` 上限（现与 GO2 一致 0.23 m）。想只看低难度楼梯：加 `--stair_height 0.03 0.10`。
- 目视判读：机器人是否抬腿把轮心抬过踏步、轮子是否打滑/顶住踏步边缘、`base_contact`（机身接触）与侧翻是否出现。

#### 四段标准录像组（15 s / 30 s，2026-10-15 实测固化）

同一 checkpoint（检查点）一次录满 4 种地形，用于「目视验证 + 定位短板」。以 `model_15300.pt`
（run `2026-10-15_01-16-28`，stairs 楼梯 + `height_scanner` 高度扫描传感器 + 10x 网络）为例：

| `--video_tag`（视频标签） | `--terrain`（地形） | `--cmd_x`（前进命令 m/s） | 帧数 / 时长 |
|---|---|---|---|
| `stairs_<ITER>` | `stairs`（0.05–0.23 m，与 GO2 严格消融） | `0.2 0.4` | 749 / 15.0 s |
| `stairs_low_<ITER>` | `stairs` + `--stair_height 0.03 0.10`（轮半径 0.095 m 保守上限） | `0.3 0.5` | 749 / 15.0 s |
| `flat_<ITER>` | `flat`（平地） | `0.4 0.5` | 749 / 15.0 s |
| `rough_<ITER>` | `random_rough`（随机粗糙，noise 0.01–0.03 m） | `0.3 0.5` | 749 / 15.0 s |

30 s 长版：`--video_length 1500 --episode_length_s 35`，tag 加 `_30s` 后缀（1499 帧 / 29.98 s）。

```bash
RUN=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-15_01-16-28
COMMON="--headless --video --video_length 1500 --episode_length_s 35 --num_envs 4 \
        --no_standing --no_curriculum --camera_view side \
        --task Unitree-GeesunDog-LingsiD30W-Velocity \
        --checkpoint $RUN/model_15300.pt --env_cfg_file $RUN/params/velocity_env_cfg.py"
python scripts/rsl_rl/play.py $COMMON --video_tag stairs_15300_30s --terrain stairs \
    --cmd_x 0.2 0.4 --cmd_y -0.1 0.1 --cmd_z -0.5 0.5
# 其余三段：把 --video_tag / --terrain / --cmd_x 换成上表值
```

> **固化脚本（2026-10-15）：** 上面这组命令已固化为 **`scripts/tests/play_shiping_luzhi.sh`**
> （bash 脚本：段间 45 s 冷却 + `timeout 600` 兜底 + 自动 `ffprobe` 产出校验 + 课程状态文件未被污染的核对）。
> 运行方式：`bash scripts/tests/play_shiping_luzhi.sh`；后台跑：
> `nohup bash scripts/tests/play_shiping_luzhi.sh > /tmp/play_shiping_luzhi.out 2>&1 &`。
>
> ⚠️ **它是 shell 脚本，不是 Python。** 用 `python scripts/tests/play_shiping_luzhi.sh` 执行会报
> `SyntaxError: unterminated string literal (detected at line 3)` —— 因为 `COMMON="..."` 的跨行赋值是
> shell 语法，Python 词法分析器看到跨行的双引号字符串就报未闭合。文件名后缀也必须是小写 `.sh`
> （不要用 `.PY` 后缀，`.PY` 会被当成 Python 文件）。
>
> 实测产出（2026-10-15 10:02，`model_15300.pt`）：`videos/stairs_15300_30s/rl-video-step-0.mp4`
> = 1280×720 / 50 fps / **1499 帧 / 29.98 s**，与 `--video_length 1500 --episode_length_s 35` 设计一致
> （30 s 片段内无锁步复位 mid-clip reset）。



> **串行录像必须段间冷却 45 s（2026-10-15 实测）：** 上一段 Isaac Sim 退出后 GPU 上下文尚未释放就启动下一段，
> 会卡在渲染初始化——主线程 0% CPU、`carb.taskloop` 单线程 94% CPU 空转 12 min 且不产出 `videos/<tag>/`。
> 修法：段间 `sleep 45`，并给每段加 `timeout 600` 兜底。
>
> **产出校验（三段式）：**
> `ffprobe -show_entries stream=width,height,nb_frames -show_entries format=duration <mp4>` → 1280×720 / 50 fps / 1499 帧 / 29.98 s；
> `ffmpeg -i <mp4> -vf "signalstats,metadata=print:key=lavfi.signalstats.YAVG" -f null -` → 黑帧数应为 0（平均亮度 ~175）；
> `ls -la logs/rsl_rl/<exp>/curriculum_state.json terrain_levels_state.json` → mtime 必须早于录像时间（证明 `--no_curriculum` 未污染课程状态）。
>
> 已知瑕疵：每段首帧是 RTX（实时光追）预热帧；`conda run` 的 stdout 缓冲会截断日志尾部 INFO 行，以 `ffprobe` 为准。

### 2. 定量行走与力矩测试

> 脚本原名 `test_flat_walk.py`，2026-10-14 更名为 **`test_walk_torque.py`**（行走性能 + 逐关节力矩统计），
> 因为它的产出早已不只测平地：逐关节 Peak（峰值）/ P99（99 分位）/ RMS（均方根）力矩 + 前进速度 +
> 高度方差 + XY/yaw 跟踪误差 + 成功率。CSV（逗号分隔表格）文件名与内容格式不变（`<terrain>_terrain_stats.csv`）。

```bash
# 平地基线
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-Go2-Velocity \
    --terrain flat \
    --steps 500

# 复杂地形压力测试
conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-Go2-Velocity \
    --terrain complex \
    --steps 1000

conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-GeesunDog-Dog1-Velocity \
    --terrain complex \
    --steps 1000    

# 分地形定位短板
for terrain in random_rough stairs; do
    conda run -n env_isaaclab_sim51 python scripts/rsl_rl/test_walk_torque.py \
        --task Unitree-Go2-Velocity --terrain "$terrain" --steps 1000
done
```

检查 body-frame 速度误差、无提前终止成功率、高度方差和各关节 Peak/P99/RMS 力矩。

上述命令默认自动加载最新 checkpoint。指定模型时，增加：
`--checkpoint logs/rsl_rl/unitree_go2_velocity/RUN_ID/model_7300.pt`。

### 3. TensorBoard

```bash
tensorboard --logdir logs/rsl_rl   # 必须是 logs/rsl_rl 本身，见下方 TEXT 说明
```

> **TEXT 页（曲线中文说明）**：logdir 必须是 `logs/rsl_rl` **本身**，不能写子目录（如
> `logs/rsl_rl/unitree_go2_velocity`）。中文说明以独立 run `00_曲线中文说明` 的形式放在
> `logs/rsl_rl/` 顶层，与各训练 run 同级；用子目录作 logdir 时左侧 run 列表里列不出它，
> **TEXT 页就是空白**。刷新说明：
>
> ```bash
> python scripts/tb_notes.py          # 重写（幂等）；--list 只在终端打印对照表
> ```
>
> 备注内容同时覆盖 GO2 与 GeesunDog D30W 两套基准（回合长度跑满值、跟踪误差水位、fps 量级、
> 奖励权重、地形种类都不同，**不可跨机器人横比**），维护在 `scripts/tb_notes.py` 的 `NOTES`
> 字典里，是曲线释义的单一事实来源。

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
（`joint_fr_hip`/`base_link`/`joint_fr_wheel`），mesh（网格）引用改写为绝对路径，并把 effort/velocity
（力矩/角速度）上限归一化为 URDF 原值，可直接加载：

```bash
python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --headless --num_steps 400
# 轮关节按 --wheel_speed 匀速自转（默认 10 rad/s，0 = 锁死只动腿）
# GUI 渲染（一直运行直到关窗；D30W calf（小腿）限位 [0.536, 2.775] rad，calf 幅度取小避免触限位）：
python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --num_steps 0 --root_z 1.0 \
    --calf_base 0.8 --calf_amp_deg 15 --wheel_speed 10
```

**PD 参数：** 执行器配置 `UnitreeActuatorCfg_D30W`
（`unitree_actuators.py`，与 GO2/dog1 隔离），effort/velocity（力矩/角速度）上限**以厂家 URDF
（`lingsi_d30w.urdf`）的 `<limit>` 为准**（2026-10-14 用户确认，取代 2026-10-13 的“以 Excel 为准”），
PD 增益取**厂家 2026-10-14 给出的推荐工作点**（Excel 新增列原文：`KP 最大500,推荐200`、
`KD 最大5,推荐5`、轮子 `KP 最大500,厂家说没有此设置`、`KD 最大5,推荐3`）：

| 关节组 | 型号 | 力矩上限 (N·m) | 角速度上限 (rad/s) | KP（上限 500 / **推荐 200**） | KD（上限 5 / **推荐 5**） |
| --- | --- | --- | --- | --- | --- |
| hip/thigh（髋/大腿） | LS100_WLA/WLH | 72 | 27 | **200** | **5** |
| calf（小腿） | LS100_WLK | 136 | 14 | **200** | **5** |
| wheel（轮） | LS75_WL | 20 | 65 | **无（厂家：没有此设置）** → 仿真 stiffness=0 | **3** + armature（转子惯量）0.01 |

**⚠ 厂家 URDF 自带 limit 与 Excel 的口径差异（2026-10-13 记录，2026-10-14 翻转决策）：** 厂家 URDF
（`A01mw (3).urdf`，已同步为 `lingsi_d30w.urdf`）的 `<limit>` 与 `D30W关节电气参数.xlsx` **并不一致**。
2026-10-13 曾按用户确认以 Excel 为准覆盖；**2026-10-14 用户重新确认 effort/velocity 以 URDF 为准
（PD 参数不变）**，即下表“URDF（采用）”列：

| 关节组 | URDF 厂家 limit（采用） | Excel（弃用） | 差异说明 |
| --- | --- | --- | --- |
| hip/thigh（髋/大腿） | 72 N·m / 27 rad/s | 120 N·m / 40 rad/s | Excel 激进 ~1.7×（疑为连续额定 vs 峰值口径） |
| calf（小腿） | 136 N·m / 14 rad/s | 200 N·m / 20 rad/s | Excel 激进 ~1.5×（同上） |
| wheel（轮） | 20 N·m / 65 rad/s | 14 N·m / 65 rad/s | URDF 略高（厂家轮子口径可能是峰值） |

另：新导出 URDF 的 `leg3_hl_joint0`（左后髋）自带 `effort="100" velocity="20"`，与其余三个 hip 的
72/27 不一致（疑为厂家笔误），按用户确认（2026-10-14）统一归一到 72/27，保持四腿对称。

生效代码共两处，改口径时**必须两处同步**：
1. `unitree.py::_prepare_geesun_dog_urdf()` 内三条 `re.sub` 把 URDF `<limit>` 归一化为 URDF 口径值
   （兼容两版 URDF 写法 72/27、136/14、20/65 与 100/20、160/15、14/65，分别映射到 72/27、136/14、20/65）；
2. `unitree_actuators.py::UnitreeActuatorCfg_D30W` 的力矩-速度曲线（X1/X2 拐点、Y1/Y2 饱和力矩
   = 72）+ `unitree.py` 各关节组实例覆盖（calf Y=136、wheel Y=20）。

**sim2real（仿真到实机）注意：** 现在仿真侧力矩/速度上限与 URDF 一致，若实机驱动保护也按 URDF
口径（72/136/20 N·m）执行则无口径错配；但若实机实际能输出 Excel 口径（120/200 N·m），当前策略
只会用到 URDF 以内、偏保守的力矩。

> **为什么不用 Excel 的 KP=500/KD=5 最大值（2026-10-13 实测调参记录，**该轮的采用值
> KP=100/KD=2 已被 2026-10-14 厂家推荐值 KP=200/KD=5 取代，见下方判定**）：** Excel 给的是**上限**
> 而非推荐值。显式 PD（explicit PD，力矩 = KP·误差 + KD·误差速度）在 dt=5 ms（毫秒）下对本机的
> 小关节惯量会踩进**离散负阻尼区**（b·dt/J ≥ 2）：从精确保时的静止开始，0.1 N·m 级重力微扰在
> 5 步内被指数放大到力矩饱和（±120 N·m，当时 Y=120；现 Y=72 则饱和于 ±72）bang-bang（来回打满），腿 0.5 s 内被甩开 ±0.6 rad。
> 实测矩阵（空中 PD 追踪，`--print_contact`）：KP=500/KD=5 发散、KP=60/KD=5 发散、轮速度伺服
> b=5 轮速 0.5 s 内 ±20 rad/s（b·dt/J≈5）；**KP=100/KD=2 + 轮 b=1/armature 0.01 稳定**
> （地面静立 2 s 下沉 <1 cm、水平漂移 <15 cm 后收敛，是训练关心的工况；空中无接触工况仍有
> 慢漂移，留给 RL 策略闭环纠正；KP=69/KD=1.38（dog1 同款）则空中精确静止但地面半蹲至 z≈0.36，
> 二选一取地面表现）。trunk 碰撞体也已缩小（厂家 mesh 凸包
> 罩住髋/大腿体积，去穿插力 ~80 N·m 会把腿炸开）。
> 调参脚本：`python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --headless \
> --num_steps 300 --root_z 1.5 --amp_deg 0 --wheel_speed 0 --stiffness <KP> --damping <KD>`；
> 诊断开关 `D30W_NO_COLLISION=1` 可临时移除全部碰撞体隔离接触力。

> **厂家推荐工作点 KP=200/KD=5 + 轮 KD=3 的实测判定（2026-10-14，空中 PD 追踪**
> `--root_z 1.5 --amp_deg 0`，日志 `/tmp/pd_air_200_5.log`**）：** 基座 z 稳定在 1.487–1.501 m
> （无发散、无坠落），**未**触发 2026-10-13 记录的离散负阻尼爆炸（b·dt/J ≥ 2）——轮组
> KD·dt/J = 3×0.005/0.01 = **1.5**，低于阈值 2 但余量只有 1.33×（旧 KD=1 为 0.5，余量 4×）。
> 代价是**力矩饱和**：hip/thigh 频繁打满 ±72 N·m（KP=200 → 误差 0.36 rad 即饱和），calf 峰值
> 92 N·m（上限 136，未饱和），轮组**恒 ±20 N·m 饱和**（KD=3 → 速度误差 >6.7 rad/s 即饱和）；
> 关节在目标附近振荡（hip ±0.45 rad、thigh −0.65…−0.13、calf 0.525…1.15 rad），轮角因无 KP
> （无位置保持）自由累积至 3.5 rad。**结论：厂家值可用（不发散），但比旧值 KP=100/KD=2 更硬、
> 饱和更频繁 → 策略需要更大的动作平滑约束；实机侧这是 1 kHz（毫秒）电流环带宽内的板载伺服
> 增益，仿真侧是 dt=5 ms 显式 PD，两者等效性以实机标定为准。** 换 PD 后必须 **fresh（重训）**：
> 被控对象（plant）已变，续训等于中途换分布。

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
tensorboard --logdir logs/rsl_rl   # 注意：必须是 logs/rsl_rl，不能写子目录，否则 TEXT 页的中文说明是空白
# 4. 与 dog1 的消融对照只改一个变量：--task 任务名
#    （Unitree-GeesunDog-Dog1-Velocity ↔ Unitree-GeesunDog-LingsiD30W-Velocity），
#    其余全不动；用 diff 核对两个 velocity_env_cfg.py 的差异是否只有资产/足部/动作项
```
**lingsi_d30w 楼梯 + height_scanner（高度扫描传感器）快速演示（2026-10-14 起）：** 为快速演示复杂地形能力，
在 lingsi_d30w 上启用了 `pyramid_stairs`（金字塔楼梯）与 `height_scanner`（高度扫描传感器）。run（训练批次）
目录、课程状态文件与监控闭环全部与基线隔离，基线曲线与 `curriculum_state.json`（课程状态文件）全程未被改动：

| 项目 | 基线（flat / random_rough） | 本次演示（stairs + height_scanner） |
| --- | --- | --- |
| `experiment_name`（实验名） | `unitree_geesun_lingsi_d30w` | `unitree_geesun_lingsi_d30w_ht_stairs` |
| 子地形（`proportion` 比例自动归一化后） | flat 33% / random_rough 67% | flat 20% / random_rough 40% / pyramid_stairs 40% |
| 楼梯台阶高 | 无（楼梯被禁用） | `step_height_range=(0.05, 0.23)` m —— **与 GO2 逐字一致**（2026-10-14 起，严格消融对照）。D30W 轮子半径 0.095 m，0.23 m 踏步 = 轮径 1.21×，需靠 12 个腿关节把轮心抬过踏步 → 预期楼梯成功率显著低于 GO2，这正是要观测的消融差异 |
| `height_scanner`（高度扫描传感器） | 关闭 | **critic-only privileged obs（仅特权评论家观测）**：critic 观测 263 维（含 187 维高度网格，0.1 m 分辨率 / 1.6×1.0 m）；policy（策略）观测**不变** |
| 课程状态文件 | `logs/rsl_rl/unitree_geesun_lingsi_d30w/curriculum_state.json` | `logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs/curriculum_state.json` |
| 启动方式 | 可 resume（续训） | **必须 fresh（重训）**：critic 观测 +187 维使 value（价值）网络输入层 shape 变化，旧 checkpoint（检查点）无法加载 |
| 速度命令起点 | 已推进到 ±0.9 m/s | 从 cfg 的 ±0.1 m/s 重新起步（状态文件隔离，避免楼梯上命令跑赢能力） |

```bash
# 1. 训练（fresh，切勿加 --resume）
./unitree_rl_lab.sh -t --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 4096
# 2. 6h 监控闭环（独立 state：outputs/monitor_d30w_ht/、outputs/autotune_d30w_ht/）
nohup bash scripts/monitor_tb_check_d30w_ht.sh >> outputs/monitor_d30w_ht/monitor.log 2>&1 &
# 3. 曲线（新增 Curriculum/terrain_performance_by_type/pyramid_stairs_{level,error_xy,error_yaw,success_rate}）
tensorboard --logdir logs/rsl_rl   # 注意：必须是 logs/rsl_rl，不能写子目录，否则 TEXT 页的中文说明是空白
# 4. 验证：单独回放楼梯地形，再跑全地形验收
python scripts/rsl_rl/test_walk_torque.py --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --terrain stairs --steps 1000
for terrain in flat random_rough stairs complex; do
  python scripts/rsl_rl/test_walk_torque.py --task Unitree-GeesunDog-LingsiD30W-Velocity --terrain "$terrain" --steps 1000
done
```

> **演示结束后的回滚（2 处）**：把 `rsl_rl_ppo_cfg.py` 的 `experiment_name` 改回
> `unitree_geesun_lingsi_d30w`，把 `lingsi_d30w/velocity_env_cfg.py` 的 `state_file` 改回
> `logs/rsl_rl/unitree_geesun_lingsi_d30w/curriculum_state.json`；楼梯与 height_scanner 按需保留或注释。
>
> **height_scanner 收益评估口径**：本演示是 critic-only（仅特权观测），只改善 value（价值）估计与训练
> 稳定性，策略本身看不到高度 → 实机 Realsense D435i / MID360 部署**不需要**高度输入。若要评估
> "策略真正使用高度"，把 `height_scan` 观测项从 `CriticCfg` 移到 `PolicyCfg`（policy 观测 +187 维），
> 并保留本次 critic-only 演示作为对照组（ablation，消融）。
>
> **同一 GPU 只能跑一个 IsaacSim（仿真器）实例**：本演示与 dog1 / 基线 d30w 训练互斥，切换前先停旧进程。

**10× 网络规模消融（2026-10-14 起，`unitree_geesun_lingsi_d30w_ht_stairs_10x`）：** 在上面 stairs +
height_scanner（高度扫描传感器）演示的基础上，**只**把网络宽度从 `512-256-128` 放大 10 倍到
`1536-1024-512`，并把 `--num_envs` 从 4096 提到 20096；楼梯、height_scanner、奖励项、课程项与全部
PPO（近端策略优化）超参一律不动 → 与 `unitree_geesun_lingsi_d30w_ht_stairs` 的唯一差异就是网络规模
（ablation，消融）。

| 项目 | ht_stairs（对照组） | ht_stairs_10x（本次） |
| --- | --- | --- |
| `actor_hidden_dims` / `critic_hidden_dims`（隐藏层） | [512, 256, 128] | **[1536, 1024, 512]** |
| 参数量（actor 演员 + critic 评论家 + noise std 噪声标准差） | 495,521 | **4,700,705**（9.5×） |
| 网络输入维度 | policy 57 / critic 263 | policy 57 / critic 263（**不变**） |
| `--num_envs`（并行环境数） | 4096 | **20096** |
| 每迭代耗时 | 0.98 s | 3.63 s |
| 吞吐 | 99,925 steps/s | **139,293 steps/s**（+39%） |
| 显存 | ~28 GB | **20.1 GB / 32.6 GB** |
| run 目录 / 课程状态 / 监控 state | `unitree_geesun_lingsi_d30w_ht_stairs` | `unitree_geesun_lingsi_d30w_ht_stairs_10x` |

```bash
# 1. 训练（fresh 重训，切勿 --resume：网络 shape 变了，旧 checkpoint 检查点无法加载）
GEESUN_DOG_VARIANT=lingsi_d30w python scripts/rsl_rl/train.py --headless \
    --task Unitree-GeesunDog-LingsiD30W-Velocity --num_envs 20096 \
    --video --video_length 500 --video_interval 2400 --camera_view side
# 2. 6h 监控闭环（独立 state：outputs/monitor_d30w_ht10x/、outputs/autotune_d30w_ht10x/）
nohup bash scripts/monitor_tb_check_d30w_ht10x.sh >> outputs/monitor_d30w_ht10x/monitor.log 2>&1 &
# 2b. 停止守护进程（daemon，后台监控循环）：先杀它的 sleep 子进程，再杀循环本体，避免孤儿 sleep
MON_PID=$(pgrep -f 'monitor_tb_check_d30w_ht10x[.]sh')
[ -n "$MON_PID" ] && { pkill -P "$MON_PID" sleep; kill "$MON_PID"; } || true   # 空则跳过（幂等，set -e 下也安全）
pgrep -af 'monitor_tb_check'      # 期望：无输出（rc=1 = 无残留）
ps -eo pid,etime,args | grep -E 'monitor_tb_check|train[.]py|play[.]py' | grep -v grep   # 期望：无输出
# 重启守护进程（改过 MON_EXTRA_TRAIN_ARGS 后必须重启才生效）：
#   nohup bash scripts/monitor_tb_check_d30w_ht10x.sh >> outputs/monitor_d30w_ht10x/monitor.log 2>&1 &

# 3. 曲线（与对照组并排看）
tensorboard --logdir logs/rsl_rl   # 注意：必须是 logs/rsl_rl，不能写子目录，否则 TEXT 页的中文说明是空白
# 4. 验证：先单独回放楼梯，再跑全地形验收
python scripts/rsl_rl/test_walk_torque.py --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --terrain stairs --steps 1000
```

> **为什么墙钟（wall-clock，实际耗时）只慢 3.7 倍而不是 9.5 倍**：每迭代约 94% 的时间花在 PhysX（物理引擎）
> 仿真上，与网络规模无关。`--num_envs` 提到 20096 后每迭代样本量 ×4.9，learning（学习）时间从 0.057 s
> 涨到 0.902 s（15.8×），但 collection（数据采集）只从 0.927 s 涨到 2.56 s，于是**吞吐反而提升 39%**。
>
> **必须盯的崩塌（collapse）信号**：`Loss/learning_rate` 贴到 1e-5 触底、`Policy/mean_noise_std` 不收缩、
> `Curriculum/lin_vel_cmd_levels/x_max` 冻结在 ±0.1 —— 这是 KL-adaptive（KL 自适应）学习率崩塌的历史模式
> （G1 2026-09-07 与 GO2 ht 消融都出现过）。监控的 autotune（自动调参）会自动降 LR（学习率）/ 提
> `desired_kl`（期望 KL 阈值）；**不要**靠缩小网络宽度来救，否则消融对照失效。
>
> **回滚（3 处）**：`experiment_name` 改回 `unitree_geesun_lingsi_d30w`、`state_file` 改回
> `logs/rsl_rl/unitree_geesun_lingsi_d30w/curriculum_state.json`、`actor_hidden_dims`/`critic_hidden_dims`
> 按需改回 `[512, 256, 128]`。




## 课程联动训练经验（2026-10-15）：双向爬坡原理与成功思路

> lingsi_d30w（D30W 轮足）ht_stairs_10x 战役实战总结。验证数据：run
> `2026-10-15_01-16-28`，`terrain_levels`（地形等级均值）0.52→6.0，`x_max`（纵向速度指令
> 范围上界）0.2→0.45，全程升降并存（3301 个采样点中升 341 / 降 90）。

### 双向爬坡（bidirectional climb）是什么原理

**定义**：`terrain_levels` 是每个 env（并行环境）的当前地形难度等级，每 episode（回合）
结束时按表现**双向滞回（hysteresis）调整**：

```text
episode 结束，对该 env 判定（terrain_levels_vel_strict）：
  存活走完 且 err_xy < 0.22 且 err_yaw < 0.30  →  level + 1   （升级，门槛严）
  摔倒  或  err_xy > 0.40 或  err_yaw > 0.45  →  level - 1   （降级，门槛宽）
  其余                                          →  不动        （滞回带内稳定停留）
```

**为什么"双向"是课程成立的关键**：

| 形态 | 后果 | 实例 |
|---|---|---|
| 只升不降 | 虚假繁荣：运气好/过拟合的 env 卡在过难地形，学不动也掉不下来 | — |
| 只降不升 | **单向坍缩**：偶发摔倒逐步把所有 env 拖回 level 0 | 2026-10-14 实测 `terrain_levels` 0.51→0.087（P0 修复前 `move_down` 漏闸） |
| **双向滞回** | 每个 env 始终停留在"略难但可完成"的难度（ZPD 最近发展区） | 修复后升 341 / 降 90，均值螺旋上爬 0.52→6.0 |

升阈值（0.22）严于降阈值（0.40）构成**滞回带**：临界难度的 env 不在升级/降级边界上抖动
（反复升降浪费样本），而是稳定停留直到能力真正超过上界。整体均值的"升多降少"就是能力
增长的外在曲线——**爬坡速度 = 策略学习速度**，这正是课程学习（curriculum learning）的
自适应机制。

### 命令-地形联动（2026-10-14 拍板，全部默认关闭、仅 lingsi_d30w 启用）

只靠双向滞回还不够：地形难度会跑在速度能力前面（err 阈值是绝对值，低速下太宽松）。
解决方案是两个课程的三重联动：

1. **命令课程先行**：`min_x_max_for_move_up=0.3` —— `x_max` 未到 0.3 m/s 前地形
   **双向冻结**（`gate_open` 闸住 move_up 与 move_down，真冻结、零漂移）；
2. **解冻后爬坡**：`x_max ≥ 0.3` 后地形恢复双向滞回升降；
3. **爬坡让路**：`cmd_freeze_windows=2` —— terrain 均值每 +1 级（`cmd_freeze_level_gain`），
   x 指令范围冻结 2 个评估窗口（不升不降、`streak` 清零），让策略在新难度稳定后再扩速度；
   TB 曲线 `Curriculum/lin_vel_cmd_levels/x_frozen` 可见触发（实测触发 588 个采样点、峰值 2）。

配套修复（缺一不可）：

- **评估窗口**：`min_env_steps` 12000→6000。原值对应 ~500 iterations（迭代），大于多数 run
  长度，门控评估从未触发、`x_max` 永远卡 0.1（run 碎片化的根因之一）；
- **terrain_levels sidecar（方案 A）**：每 1000 全局步写 `terrain_levels_state.json`
  （含 num_envs / max_level 元数据），resume（续训）恢复等级与 `env_origins`，不再从
  `max_init_terrain_level`（0–2）重爬；fresh（重训）由 train.py 删除。num_envs / 地形行数
  不匹配或文件损坏时自动降级为随机初始化（WARN，不中断）。

### 验证方法（TB 四条曲线即可判定闭环健康）

```text
Curriculum/lin_vel_cmd_levels/streak     累计→清零→再攒（评估窗口在工作）
Curriculum/lin_vel_cmd_levels/x_max      阶梯上升，到 0.3 是 terrain 解冻闸
Curriculum/terrain_levels                x_max<0.3 时应水平直线（冻结）；解冻后螺旋上爬（升>降）
Curriculum/lin_vel_cmd_levels/x_frozen   terrain 每 +1 级短暂 =2 再归 0
```

消融开关：`min_x_max_for_move_up=0.0` 或 `cmd_freeze_windows=0` 即回到旧单变量行为，
配合 dog1/GO2 不传新参数（默认全关），对照实验干净。更多曲线释义见
`doc/training_monitoring.md` §4 与 `outputs/monitor/curves.md`。

## 提交历史导出（commit history export）

两个零依赖（只用标准库）导出脚本，便于做变更审计（change audit，变更审计）：

| 脚本 | 范围 | 输出 |
|---|---|---|
| `scripts/tools/export_commits_xlsx.py` | **全仓库**全部提交（commit，提交） | `outputs/commits/commits_<日期>.xlsx`（Excel，Excel 表格） |
| `scripts/tools/export_file_history.py`（2026-10-14 新增） | **单个文件**的提交历史（`git log --follow`） | `doc/<文件名>_changelog.md`（含逐提交增/删行数、hunk（代码块）上下文定位、提交正文、当前未提交改动） |

```bash
# 默认目标：assets/robots/unitree.py -> doc/unitree.py_changelog.md
python scripts/tools/export_file_history.py
# 任意文件 + 自定义输出
python scripts/tools/export_file_history.py --file scripts/rsl_rl/play.py --out doc/play_py_changelog.md
python scripts/tools/export_file_history.py --no-working      # 不附「当前未提交改动」段
```

已生成的历史文档：[doc/unitree.py_changelog.md](doc/unitree.py_changelog.md)（`unitree.py` 共 10 次提交触及）。

## 部署
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

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
- [传感器仿真建模：Airy 96线激光雷达（2026-10-15）](#传感器仿真建模airy-96线激光雷达2026-10-15)
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

**sidecar（旁路状态文件）规则**（`scripts/rsl_rl/train.py:470-489`）：`--resume`（续训）时
`terrain_levels_state.json`（地形等级）与 `curriculum_state.json`（速度命令范围）**被保留并加载**，
只有 fresh（重训）才删除它们（删除前先复制 `*.last` 兜底）。默认按 `experiment_name` 目录共享、
**不属于某个 run**；文件名来自各课程项的 `state_file` 参数（2026-10-20 起 B/C/D 三臂各用自己的
一份，见下文「sidecar 新格式」）：

| 情形 | 后果 |
|---|---|
| 从**旧 run** 续训（例：`--load_run 2026-10-14_23-26-00`，其最新 checkpoint 只到 `model_7900.pt`） | 旧策略被直接灌入最新战役的 sidecar（实测 `terrain_levels` 均值 6.006、`x_max` ±0.5、`step` 178000）→ 大面积摔倒 → 等级雪崩，并把雪崩结果**写回同一个 json**，反向污染最新战役状态（2026-10-12 崩溃模式的复现路径） |
| 改 `--num_envs`（并行环境数）后续训 | **2026-10-20 修复后**：`layout`（地形网格指纹）相同 → 走 **by type** 路径，每个 env 从自己地形类型的等级池重采样，`terrain_levels` / `pyramid_stairs_level`（金字塔楼梯难度等级）**不降级**；只有 `layout` 变了 / 文件缺 `levels_by_type`（2026-10-20 前的老文件）才 `[WARN] ... keeping the random initial levels` 从 `max_init_terrain_level` 重爬（修复前：改 `--num_envs` 必降级，实测 5.05→0.49，见下节） |

跨 run / 回退消融前，必须先备份并移走两个 sidecar：

```bash
cd logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
mv curriculum_state.json     curriculum_state.json.bak_<ITER>
mv terrain_levels_state.json terrain_levels_state.json.bak_<ITER>
# B/C/D 臂各用自己的文件名（terrain_levels_state_airy_B.json 等），要移走的是对应臂的那一对
# 实验结束后按原名逐字移回（课程项按仓库相对路径读取 state_file，改文件名必须同步改 cfg）
```

**sidecar 新格式：保存 `pyramid_stairs_level`（金字塔楼梯难度等级）（2026-10-20）**

事故实测：B 臂（`-AiryReplace`）4096 envs 跑完 10000 迭代后，用 `--num_envs 3096` 续训 →
`Curriculum/terrain_performance_by_type/pyramid_stairs_level` 从 **5.05 掉到 0.49**、
`Curriculum/lin_vel_cmd_levels/x_max` 从 **0.3 掉到 0.1**。原因两条叠加：
① 旧 `_load_terrain_state` 要求 `num_envs` 逐字相等，4096→3096 不等 → 随机初始化（均值 =
`max_init_terrain_level` 的一半 = 0.5）→ 再把这个"归零"结果写回同一个 json；
② 四臂共用一个实验目录 → 共用同一对 sidecar，A 臂（20096 envs）随后把同一个文件覆盖掉。

修复（改动最小，GO2 / dog1 / A 臂行为逐字不变）：

| 位置 | 改动 |
|---|---|
| `mdp/curriculums.py::_save_terrain_state` | sidecar 增写 4 个字段：`by_type`（**逐地形平均等级**，`by_type["pyramid_stairs"]` 就是 TB 上的 `pyramid_stairs_level`）、`levels_by_type`（逐地形等级池）、`types`、`layout`（`num_rows`/`num_cols`/`proportion` 指纹）。旧字段 `levels`/`num_envs`/`max_level`/`step`/`ts` 逐字保留 → 老文件仍可读 |
| `mdp/curriculums.py::_load_terrain_state` | 两条恢复路径：**exact**（`num_envs` 相同 → 逐环境精确恢复）与 **by type**（`num_envs` 变了但 `layout` 相同 → 每个 env 从**自己地形类型**的等级池重采样，`pyramid_stairs_level` 原样回来、不降级）。`layout` 变了 / 文件损坏 / 老文件缺 `levels_by_type` → `[WARN]` + 随机初始化，绝不中断训练 |
| `scripts/rsl_rl/train.py` | fresh（重训）删 sidecar 前先复制 `*.last` 兜底；按**当前 cfg 的 `state_file`** 定位（不再硬编码文件名）；启动时打印 `[INFO] <term> sidecar (旁路状态文件): <绝对路径>` |
| `lingsi_d30w/velocity_env_cfg.py::_isolate_curriculum_sidecars` | B/C/D 三臂各用**自己的** sidecar：`terrain_levels_state_airy_B.json` / `curriculum_state_airy_B.json`（C/D 同理）；**A 臂保持原名** → 已训 run 与 checkpoint 不受影响（消融安全） |

自检与重建（都不启动 Isaac Sim，秒级）：

```bash
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
# 1) sidecar 读写自检：同 env 数精确恢复 / 跨 env 数按类型恢复(楼梯等级不降) /
#    老格式兼容 / layout 变化退回随机 / 损坏文件不抛异常  —— 期望 RESULT: ALL PASS，exit 0
$PY scripts/diagnose/check_terrain_state_sidecar.py

# 2) 从 TB 曲线重建丢失的 sidecar（读 Curriculum/terrain_performance_by_type/*_level 与
#    Curriculum/command_ranges/*，写 terrain_levels_state_<arm>.json + curriculum_state_<arm>.json，
#    写前自动备份 *.pre_rebuild_<时间戳>，写完自动验证 3096 与 4096 envs 都能恢复）
$PY scripts/diagnose/rebuild_terrain_state_from_tb.py \
    --tb_run logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-20_01-03-41_airy_B_replace \
    --arm airy_B --num_envs 3096 --step 240000
# 实测输出：by_type {'flat': 6.05, 'random_rough': 6.04, 'pyramid_stairs': 4.94}
#          command ranges x ±0.30 / y ±0.10 / z ±1.0，restore check 全 PASS
# ⚠ 语义：重建的是"逐地形等级分布"（均值与 TB 一致），不是原始 env→等级配对。
#   用它恢复丢失的 sidecar，不要拿它做审计。--dry_run 可先看不落盘。
```

> **续训时怎么确认等级真的接上了**：启动日志必须出现
> `[INFO] Restored terrain levels (exact|by type, ...) ... | flat=... pyramid_stairs=5.05 ...`；
> 只看到 `[WARN] ... keeping the random initial levels` = 等级没接上（`layout` 变了、
> 文件缺失或 `max_level` 不一致），此时**不要**开跑，先跑上面的重建脚本。
> 训练中途每 `state_save_interval`（默认 1000 全局步）写一次 sidecar，所以
> `ls -l logs/rsl_rl/<exp>/terrain_levels_state*.json` 的 mtime 在推进 = 正在保存。




### 0. 训练时录制视频（in-training video recording）——**已重新启用（re-enabled，2026-10-14 23:45，5 s 短片）**

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
    --resume  \
    --video --video_length 250 --video_interval 10000 --video_start_frac 0.8 \
    --video_start_episode_frac 0.85 --camera_view diag --camera_distance 0.57 --camera_height 3 --camera_focal 21  \
    --load_run 2026-10-15_01-16-28

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

> **站立不动刷分目视检查（stand-still reward-hacking visual check）一键脚本：**
> `bash scripts/tests/standstill_play_check.sh` 封装了上述参数（恒定 `--cmd_x 0.5 0.5` + `--no_standing`
> + `--no_curriculum` + 自动选取最新 checkpoint 与 cfg 快照），按 `TERRAIN`（默认 `flat stairs`）逐地形
> 录像并抽帧到 `outputs/sst_<terrain>_f40.png` / `_f300.png`。判读：机身沿 +x 前进（景物后退）= 通过；
> 原地踏步 / 腿部抽动 / 蹲伏不动 = 刷分复发。定量判据见 `scripts/tests/validate_wheel_lock_flat.sh`
> （`mean_fwd_along_cmd_ms > 0.10` 等）。前置条件同下文「前置检查」：GPU 空闲才能跑，训练中会自动 ABORT。

> **`--checkpoint`（检查点路径）必须是完整路径 —— 这是 play（回放）最常见的崩溃原因。**
> `play.py` 把它交给 Isaac Lab 的 `retrieve_file_path`（文件定位工具），该函数只认「本地已存在的路径」
> 或 Nucleus URL，找不到就抛 `FileNotFoundError: Unable to find the file: /model_10400.pt`。
> **路径以 `/` 开头 = shell 变量为空**：粘贴本 README 的命令块时只贴了 `python ...` 那几行、漏掉了上面的
> `EXP=...` / `RUN=...` 赋值，`--checkpoint=$RUN/model_10400.pt` 就展开成 `/model_10400.pt`（2026-10-20 实测）。
> 2026-10-20 起 `play.py:resolve_play_checkpoint()` 会拦住它：打印解析结果 + 空变量提示 + 每个 run 的最新
> checkpoint 候选清单，然后干净 `exit(1)`（不再抛 traceback）；并支持**只给文件名**
> `--checkpoint model_10400.pt`，自动在 `<experiment_dir>/*/model_10400.pt` 里取最新 run。
>
> ```bash
> # 0) 回放前先确认 checkpoint 真的存在（秒级，不启动仿真器）
> EXP=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
> ls -dt $EXP/*/ | head -4                      # 最新 run 目录
> ls -t  $EXP/<run_id>/model_*.pt | head -3     # 该 run 的最新 checkpoint
> # 1) 从仓库根目录运行（相对路径按 CWD 解析），并粘贴整块命令（含 EXP= 赋值行）
> cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
> $PY scripts/rsl_rl/play.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity \
>     --checkpoint $EXP/<run_id>/model_10400.pt
> # 2) 也可只给文件名（新逻辑自动定位到最新 run 的同名 checkpoint）
> $PY scripts/rsl_rl/play.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity \
>     --checkpoint model_10400.pt
> ```


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

#### Airy 消融四臂（A/B/C/D）的 PLAY（回放）与录像 —— 2026-10-20 实测通过

四臂共用**同一个** experiment 目录 `logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x`
（目录由 `rsl_rl_ppo_cfg.py` 的 `experiment_name` 决定，`--run_name` 只决定 run 前缀），
所以 **play 必须显式 `--checkpoint` 指定臂，且 `--task` 必须与 checkpoint 同臂**，
否则 policy（策略）/ critic（价值网络）输入维度不匹配 → `size mismatch for critic.0.weight`。

当前进度（2026-10-20 22:22 更新）：**A `2026-10-20_19-03-11_airy_A_baseline`（20096 envs，续训到
`model_10400.pt`，✓ 已训完可测）**、**B `2026-10-20_01-03-41_airy_B_replace`（4096 envs，10000 迭代跑满，
`model_9999.pt`）**、D `2026-10-19_22-55-51_airy_D_proprio`（只跑了 1000 迭代，`model_999.pt`，
**地形课程全程冻结在 0.5054**，见下文「D 臂闸门」）；C（`-AiryStacked`）尚无有效 run。
旧 run：A `2026-10-19_17-54-03_airy_A_baseline`。

```bash
# 0) 前置检查（pre-flight check）：GPU 空闲 + 停 6h 守护进程（daemon）——见本节开头
ps -eo pid,etime,args | grep -E 'monitor_tb_check|train[.]py|play[.]py' | grep -v grep
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader   # 期望 ~2 GiB / 32.6 GiB

# 1) 单段录像（已实测通过）：B 臂 + 平地 + 斜后方高俯拍跟拍，5 s 短片
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
EXP=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
RUN=$EXP/2026-10-20_01-03-41_airy_B_replace
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY -u scripts/rsl_rl/play.py --headless \
    --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace \
    --checkpoint $RUN/model_9999.pt \
    --num_envs 4 --no_standing --no_curriculum \
    --video --video_length 250 --video_tag B_flat --camera_view diag \
    --terrain flat --cmd_x 0.2 0.3 --cmd_y -0.1 0.1 --cmd_z -0.3 0.3
# 实测产出：$RUN/videos/B_flat/rl-video-step-0.mp4 = 1280x720 / 50 fps / 249 帧 / 4.98 s / 1.5 MB
# 日志里必须出现这两行，才证明加载的确实是 B 臂（critic 796 维 = 本体 76 + airy_bev 720）：
#   [INFO]: Parsing configuration from: ...velocity_env_cfg:RobotPlayEnvCfgAiryReplace
#   | 8 | airy_bev | (720,) |
```

**四段录像组（B 臂，30 s/段，段间冷却 45 s）**：把 `--video_tag` / `--terrain` / `--cmd_x` 依次换成
`stairs_B`/`stairs`/`0.2 0.3`、`rough_B`/`random_rough`/`0.2 0.3`、`flat_B`/`flat`/`0.2 0.3`、
`complex_B`/`complex`/`0.2 0.3`，其余参数逐字不变（同 checkpoint、同 `--num_envs 4`），
并把 `--video_length 1500 --episode_length_s 35` 换成 30 s 长版。

**相机机位速查（camera rig，抬高摄像头 / 更换视角）** —— 参数全部来自 `play.py:34-88` 与 `_follow_camera()`（`play.py:359-412`）：

| 参数 | 默认（按视角） | 作用 |
|---|---|---|
| `--camera_view` | `side` | `side`（侧向跟拍，不随偏航角转）/ `rear`（身后追拍，随偏航角转）/ `diag`（斜后方高俯拍，随偏航角转）/ `free`（自由视角，机位只设一次） |
| `--camera_height` | side/rear 1.1，diag 1.2 | **抬高摄像头**：相机高于机身根节点的垂直偏移（米） |
| `--camera_distance` | side/rear 2.2，diag 0.57 | 水平偏移（米）；与 height 一起决定俯角 = `atan(height/distance)` |
| `--camera_focal` | side/rear 0（不改），diag 21 | 焦距（毫米）：**越小越广角**；抬高后想看清机器要**调大**（收窄视场角），录完自动恢复 |
| `--camera_eye` / `--camera_target` | 出生点斜上方 3.5 / 1.6 m | 仅 `free` 用：初始机位与注视点（世界坐标，米） |

抬高后的实测几何（1280×720，Kit 默认传感器宽 20.955 mm）：`focal 18.15 → 视场角 60.0°/36.0°`、`21 → 53.0°/31.4°`、`35 → 33.3°/19.1°`；`diag h=1.2/d=0.57 → 俯角 64.6°、距离 1.33 m`，`h=3.5/d=1.2 → 俯角 71.1°、距离 3.70 m`（机器在垂直视场里从 61% 缩到 22% → 需配 `--camera_focal 35` 把机器拉回画面）。

```bash
# 抬高摄像头（斜后方高俯拍，3.5 m 高 + 收窄视场角把机器拉大）
$PY scripts/rsl_rl/play.py --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace \
    --checkpoint $RUN/model_9999.pt \
    --camera_view diag --camera_height 3.5 --camera_distance 1.2 --camera_focal 35

# 更换视角：身后追拍 / 侧向跟拍抬高版 / 自由视角（Kit 视口可自由拖动）
$PY scripts/rsl_rl/play.py --task ...-AiryReplace --checkpoint $RUN/model_9999.pt \
    --camera_view rear --camera_height 1.6
$PY scripts/rsl_rl/play.py --task ...-AiryReplace --checkpoint $RUN/model_9999.pt \
    --camera_view side --camera_height 3.0 --camera_distance 3.0 --camera_focal 35
$PY scripts/rsl_rl/play.py --task ...-AiryReplace --checkpoint $RUN/model_9999.pt \
    --camera_view free --camera_eye 6 6 3.0 --camera_target 0 0 0.3
```

> **⚠ GUI（图形界面，不带 `--headless`）里手动转视角会被覆盖：** `_follow_camera()` 在**每一步**都调用
> （`play.py:425`，与 `--video` 无关），所以你在 Kit 视口里拖动/旋转的机位会在下一步被搬回机器身上。
> **想在窗口里自由看，必须 `--camera_view free`**（机位只在首帧设一次，之后完全不动）。
> 相机参数是启动时解析的 argparse（命令行解析）参数，**没有热键**，改机位必须重启 `play.py`。
> 跟拍永远跟 **`env_0`** 那台机器狗。
>
> **固化对照脚本（2026-10-20）：** `scripts/tests/play_camera_rigs.sh` —— 一次跑完
> `cam_diag_h12`（基准）/ `cam_diag_h35`（抬高）/ `cam_rear` / `cam_side_h30` / `cam_free` 五种机位，
> 段间 45 s 冷却 + `timeout 600` 兜底 + `ffprobe` 产出校验 + **centre_std 构图判据**
> （画面中心 40%×40% 区域亮度标准差，机器狗在画面里时应明显偏高）。
> 运行：`bash scripts/tests/play_camera_rigs.sh`（脚本会先自检「有 train.py/play.py 在跑就直接退出」）。



**三个必踩的坑（2026-10-20 实测）**

| 坑 | 现象 | 正确做法 |
|---|---|---|
| **`--env_cfg_file`（配置快照回放）对 B/C/D 有害** | `snapshot_cfg.py:53-54` 取 `play_cfgs[0]`，而 run 快照里**只有 `RobotPlayEnvCfg`（A 臂，critic 263 维）的名字以 `PlayEnvCfg` 结尾**（B/C/D 的类名是 `RobotPlayEnvCfgAiryReplace` 等，结尾不是 `PlayEnvCfg`）→ 快照回放实际加载的是 **A 臂配置** → `size mismatch for critic.0.weight` | B/C/D **不要加 `--env_cfg_file`**，直接用 `--task ...-AiryReplace` / `-AiryStacked` / `-ProprioOnly`；只有 A 臂在 task cfg 漂移后才需要 `--env_cfg_file` |
| **play 默认命令范围 = `limit_ranges` = ±1.0 m/s** | `RobotPlayEnvCfg*.__post_init__` 把 `ranges` 覆盖成 `limit_ranges`；而 B 臂训练时 `x_max` 只爬到 **0.30 m/s 就冻结**（`gated_lin_vel_cmd_levels` 的 `lin_increment=0.05` + `cmd_freeze_windows=2`）→ 用默认命令回放 = 逼策略跑它从未见过的 1.0 m/s，看起来像「策略废了」 | 录像必须显式 `--cmd_x`，且**不超过该臂 TB 上的 `Curriculum/lin_vel_cmd_levels/x_max`**（B 臂 = ±0.3） |
| **Airy 激光雷达显存** | B/C 的 `airy_front` 是 43200 rays/env，4096 envs 时 ~26.8 GB；play 走 RTX（实时光追）渲染再 +4 GB | play/录像固定 `--num_envs 4`（最多 16），并带 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`（可扩展显存段） |

**B 臂训练结果（TB 末 50 迭代均值，run `2026-10-20_01-03-41_airy_B_replace`，10000 迭代）**

| 指标 | 值 | 判读 |
|---|---|---|
| `Train/mean_reward` | 28.56 | 已收敛 |
| `Train/mean_episode_length` | 931 / 1000 | 接近跑满 |
| `Metrics/base_velocity/error_vel_xy` / `_yaw` | 0.192 m/s / 0.242 rad/s | 达标（验收线 0.25 / 0.35） |
| `Episode_Termination/time_out` / `base_contact` | 0.853 / 0.000 | 无机身触地 |
| `Curriculum/terrain_levels` | 5.59 | 已到中高难度 |
| `Curriculum/lin_vel_cmd_levels/x_max` | **0.300（全程最大值也是 0.300）** | 速度课程 10000 迭代只爬到 ±0.3 就冻结 → **与 A/D 臂对比必须按同命令范围比** |
| `pyramid_stairs_success_rate`（楼梯成功率） | **0.641** | **短板**：远低于 flat 0.999 / random_rough 0.994 |
| `flat` / `random_rough` success_rate | 0.999 / 0.994 | 达标 |

→ 录像重点看楼梯（`--terrain stairs`），定量测试重点也跑楼梯：

```bash
# 注意：test_walk_torque.py 没有 --cmd_x；它默认把命令钳到 ±0.25 m/s（在 B 臂训练过的 ±0.3 以内），
# 加 --full_command_range 才会用 ±1.0 m/s（超出 B 臂训练范围，结果不可与 TB 对照）
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY -u scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace \
    --checkpoint $RUN/model_9999.pt \
    --terrain stairs --num_envs 16 --steps 1000
for t in flat random_rough stairs complex; do
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY -u scripts/rsl_rl/test_walk_torque.py \
      --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace \
      --checkpoint $RUN/model_9999.pt --terrain "$t" --num_envs 16 --steps 1000
done
```



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
- [ ] 课程状态可续训：`Curriculum/terrain_performance_by_type/pyramid_stairs_level`（金字塔楼梯难度等级）已写入 sidecar（旁路状态文件）`terrain_levels_state*.json` 的 `by_type`，且 `--resume`（续训）日志出现 `Restored terrain levels (exact|by type, ...)`（改 `--num_envs` 后也不降级）
- [ ] 自检通过：`python scripts/diagnose/check_terrain_state_sidecar.py` → `RESULT: ALL PASS`（exit 0）
- [ ] editable 安装（可编辑安装）确实指向本仓库：`python -c "import unitree_rl_lab; print(unitree_rl_lab.__file__)"` 输出 `<本仓库>/source/unitree_rl_lab/unitree_rl_lab/__init__.py`（`pip show` 的 `Location` 显示 `~/.local/lib/python3.10/site-packages` 属正常，看 `Editable project location` 与 import 结果）
- [ ] 回放（play）加载的确实是目标臂：日志出现 `[INFO]: Parsing configuration from: ...velocity_env_cfg:RobotPlayEnvCfg<Arm>` 与观测维度表（A 臂 76 维本体 / B 臂 796 = 本体 76 + `airy_bev` 720），且 `--checkpoint` 打印出的绝对路径属于预期 run 目录


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
> ⚠️ **2026-10-16 实测订正（覆盖 2026-10-15 的错误结论）：`offset` 的正确值就是默认的 `0.5`**
> （lingsi_d30w 与 GO2 两个任务已同步修正）。
> `mdp.height_scan` 返回 `sensor_pos_w.z − hit_z − offset`。传感器确实吊在 `base_link` 上方 20 m
> （`OffsetCfg pos=(0,0,20)`），**但这个 20 m 只抬高射线起点，不会进入 `pos_w`** ——
> `scripts/diagnose/check_height_scanner_values.py` 实测 `pos_w z = [0.610, 0.610, 0.640]`（= 机身高度），
> `ray_hits_w z ∈ [0.000, 0.524]`。因此：
> - **`offset=0.5`（正确）** → 原始值 `0.61 − hit_z − 0.5 ∈ [-0.41, +0.11]`，`clip=(-1.0, 1.0)` 原样通过 → **活项**。
> - **`offset=20.5`（2026-10-15 的错误"修复"）** → 原始值 ≈ `−19.9`，被 `clip` **钉成 187 个常数 −1.0**
>   （实测 187/187 贴 clip 下界，跑 20 步仍是）→ **死项**。
>
> 教训：10-15 那次"修复"的前提假设 `pos_w = base_z + 20 = 20.61` 是错的，反而把一个正常的观测项改坏了。
> **凡是用 `offset=20.5` 训出来的 checkpoint，其 187 维 height_scanner 都是常数 ⇒ 等价于 D（盲）基线，
> 不能当作 A 基线使用，必须重训。** 维度不变（187）→ shape 兼容，但语义是"常数 vs 地形"之别。
>
> **验证一条命令（exit 0 = ALIVE，exit 1 = SATURATED）**：
>
> ```bash
> python scripts/diagnose/verify_height_scan_alive.py --headless --num_envs 16 --offset 20.5
> # 打印逐项实测维度（policy 57 / critic A 263、B 796、C 983、D 76）
> # 打印 height_scanner 的 raw 与 clipped 的 min/max/std 与"被钉在 clip 边界"的比例
> # 产物：outputs/verify_height_scan/stats.json
> ```
>
> 判据：`clipped.std ≥ 0.02` 且 `frac_at_upper_clip < 0.99` → 该项真正携带地形信息。
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

1. **命令课程先行**：`min_x_max_for_move_up = 0.2`（`lingsi_d30w/velocity_env_cfg.py:517` 现值；
   本文旧版写的 0.3 是当时的设计值，**已下调为 0.2**）—— `x_max` 未到 0.2 m/s 前地形
   **双向冻结**（`gate_open` 闸住 move_up 与 move_down，真冻结、零漂移）；
2. **解冻后爬坡**：`x_max ≥ 0.2` 后地形恢复双向滞回升降；
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
Curriculum/lin_vel_cmd_levels/x_max      阶梯上升，到 0.2 是 terrain 解冻闸（cfg 现值）
Curriculum/terrain_levels                x_max<0.2 时应水平直线（冻结）；解冻后螺旋上爬（升>降）
Curriculum/lin_vel_cmd_levels/x_frozen   terrain 每 +1 级短暂 =2 再归 0
```

消融开关：`min_x_max_for_move_up=0.0` 或 `cmd_freeze_windows=0` 即回到旧单变量行为，
配合 dog1/GO2 不传新参数（默认全关），对照实验干净。更多曲线释义见
`doc/training_monitoring.md` §4 与 `outputs/monitor/curves.md`。

### 奖励修正（2026-10-15）：feet_air_time（腾空时间）治本抬腿，防 reward hacking（奖励作弊）

**背景**：pyramid_stairs（金字塔楼梯）上策略找到作弊解——侧向滑行下楼而非抬腿攀爬。
根因是 `feet_air_time` **反抬腿**：IsaacLab 公式 `sum((air_time - threshold) × 首次触地)`，
原 `threshold=0.5` 下轮子正常抬升腾空 0.1~0.3 s，每次落地都 `(air_time-0.5)<0` **倒扣**
（TB 实测 `Episode_Reward/feet_air_time` = -0.006，贡献为负）。

**修正**（`lingsi_d30w/velocity_env_cfg.py`，dog1/GO2 不动）：

| 参数 | 原值 | 现值 | 理由 |
|---|---|---|---|
| `weight` | 0.1 | **0.5** | 让抬腿在楼梯奖励兑现前就有收益 |
| `threshold` | 0.5 | **0.02**（2026-10-15 三次：0.5→0.1→0.05→**0.02**） | 0.1 时该项仍为负（多数轮抬腾空 <0.1 s）；0.05 时残余 −0.0015 来自 0.02–0.05 s 的短腾空被倒扣，0.02 才把它们转正（`velocity_env_cfg.py:431-442` 注释） |

**验收指标**（每 6 h 看四条曲线，防作弊转移）：`Episode_Reward/feet_air_time` 转正（治本信号）、
`pyramid_stairs_success_rate` > 0.85、`Episode_Reward/feet_slide`（脚滑惩罚）下降、
`track_lin_vel_xy`（线速度跟踪）不明显变差（变差=引入兔子跳等新作弊）。候选后续项：
`air_time_variance`（-1.0，抑制交替抬腿）放松到 -0.5；对准侧滑则加 `track_ang_vel_z` 权重
（0.75→1.2，仅当定量确认 hack 形态是转向侧滑）。

**训练时开启录像**（2026-10-15 起恢复常规）：5 s 短片、diag（斜后方高俯拍）跟拍，每 100 迭代一段：

```bash
python -u scripts/rsl_rl/train.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity \
  --num_envs 20096 --resume --load_run <RUN> --checkpoint model_<N>.pt \
  --video --video_length 250 --video_interval 2400 --video_start_frac 0.5 \
  --video_start_episode_frac 0.35 --camera_view diag --camera_distance 0.57 \
  --camera_height 1.2 --camera_focal 21
```

## 传感器仿真建模：Airy 96线激光雷达（2026-10-15）

在仿真里建模实机传感器（D30W 轮腿式平台），接入 policy（策略）观测并做消融评估。
**详细实测记录见 `source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/sensors/AIRY_PERFORMANCE.md`**，
本节只给结论与复现方式。

### 一、硬件规格与建模决策

| 项 | 实机 PRO 版 | 仿真建模 | 说明 |
|---|---|---|---|
| 激光雷达数量 | **2 台**（头部 + 尾部） | **1 台**（头部） | **实测约束**，见第三节 |
| 线数（垂直） | 96 | 96 | 不可降，这是台阶高度分辨率的来源 |
| 视场角 | 水平 360° × 垂直 90° 半球 | 同（**朝下**，已验证） | |
| 测距 | 30 m @ 10% 反射率 | `max_distance=30.0` | 近裁剪 0.2 m |
| 水平角分辨率 | 未公开（数字扫描） | **0.8°** | 唯一可调旋钮，只影响显存 |
| 摄像头 | 2 个，130° 广角 640×360 @ 30fps，普通 RGB | **暂不建模** | 无深度；渲染路线会把训练规模打到几百 envs |

**路线选择：光线投射（`MultiMeshRayCasterCfg` + `LidarPatternCfg`），不渲染图像** —— 保住 4096 envs 训练规模。

⚠️ **必须用 `MultiMeshRayCasterCfg`，不能用 `RayCasterCfg`**：
`RayCaster` 在只给一个 `mesh_prim_paths` 时**只读该路径下第一个匹配的 `UsdGeomMesh`**，
其余网格被静默丢弃。实测：地面先生成时 94% 命中点落在地面，`z > 0.10 m` 的障碍完全检测不到。
对只扫地面的 `height_scanner` 够用，对 LiDAR 完全不可用。

**半球朝向已实测确认为「朝下」**（规格只写"垂直90°半球"，未指明哪个半球，是唯一未验证假设）：

```bash
python scripts/diagnose/verify_airy_lidar.py --headless --envs 1
# [VERDICT] DOWN: ground covered out to 15.11 m -> the 90 deg hemisphere points DOWN
```

若实机确认是朝上，只改 `airy_cfg.py` 的 `AIRY_VERTICAL_FOV_RANGE = (0.0, 90.0)`，其余不动。

### 二、BEV 观测：720 维极坐标最大高度栅格

点云 86,400 rays/env 无法直接进观测，故投影为**极坐标最大高度栅格**：
36 方位扇区（360° 全向，10°/bin）× 20 距离环（log 间距，近密远疏）= **720 维**。

关键设计：**高度取世界系 z**（绝对障碍高度，不随机器人俯仰抖动），**方位/距离才转 body frame**（跟随航向）。

几何精度实测（`scripts/diagnose/verify_airy_bev.py`，4/4 通过）：

```
step 0.15 m@3m  → 实测 0.150（误差 0）      low box 0.30 m@5m → 实测 0.277
tall_obstacles_saturate_at_sensor_height   forward_rising_profile(step<box<wall)
```

⚠️ **固有限制：高度天花板 = 传感器安装高度（0.5 m）**。墙（2.0 m）与高箱（0.9 m）实测都是 0.500，
**不是缺陷而是物理正确** —— 半球朝下时不可能看到高于自身安装高度物体的顶面。
对爬楼梯无影响（台阶 0~0.2 m），但将来若需感知"高于 0.5 m 的障碍"（上高台、越栏杆），
朝下半球的 Airy 做不到，需调整安装高度或改双半球。

### 三、性能实测（RTX 5090 / 32 GB，50 Hz 预算 = 20 ms/step）

| envs | h_res | rays/env | 总 rays | ms/step | Mrays/s | 占预算 | 显存 | 结果 |
|---|---|---|---|---|---|---|---|---|
| 512 | 0.4° | 86,400 | 44.2 M | 0.35 | 125,392 | 1.8% | — | OK |
| 4096 | 0.4° | 86,400 | 353.9 M | 0.39 | 901,361 | 2.0% | 需再分配 3.96 GiB 失败 | ❌ OOM |
| **4096** | **0.8°** | **43,200** | **176.9 M** | **0.44** | **398,382** | **2.2%** | **26.2 / 32.6 GB** | ✅ |

**三个结论**：

1. **算力完全可行，余量约 25 倍** —— 4096 envs 下只占控制预算 ~2%
2. **512→4096 开销几乎不变**（0.35→0.39 ms），GPU 并行已饱和。
   ⚠️ 反过来 **64 envs 反而更慢（1.53 ms）**，是小规模固定开销主导 ——
   **小规模测量数字不能用来外推，必须在目标 env 数上实测**
3. **真正的瓶颈是显存**，且是硬约束

由此确定两项参数：

- **`AIRY_HORIZONTAL_RES`: 0.4° → 0.8°**。降分辨率**不省算力**（96 条垂直线才是计算主导），
  纯粹省显存，且精度无损：0.8° 时一个 10° 方位 bin 仍有 **12.5 个采样点**，
  栅格取 bin 内**最大值**，台阶棱边是面状目标而非点状目标；命中率 `0.4°→98.68%`、`0.8°→98.68%` 完全一致。
- **LiDAR 实例数：2 台 → 1 台**。Airy 本身 360° 全向，1 台已覆盖前后，
  第 2 台**不增加任何信息**却要多吃 ~8~12 GB → 必然 OOM。这是实测硬约束，不是建模偷懒。

⚠️ **显存不能用"rays × 3 × 4 bytes × 2 buffers"估算**：该朴素公式对实测 26.2 GB 只算出 **4.0 GB**
（漏掉 per-env mesh BVH 与 ray-info 缓冲，**低估 6.6 倍**），是比没有保护更危险的假保护。
代码里改用两点实测标定 `2.0 GB + 1.4e-7 × rays × envs`，且在高 ray 数处故意高估，宁可误报也不静默 OOM。

⚠️ **初始化还有第二个硬成本：`MultiMeshRayCasterCfg` 的 mesh 去重是 O(num_envs) 的**（2026-10-16 实测）。
`mesh_prim_paths` 里若含 `{ENV_REGEX_NS}/Robot`（为近场自遮挡），它会对**每个 env 的机器人 mesh 做一次 USD 去重扫描**，
实测 **~1 s/env**（26 核满载）：4096 envs → **~68 分钟**才出第一条 `Learning iteration`；
若沿用基线的 20096 envs 则要 **~5.5 小时**，且每 env 的机器人 BVH 会把显存推过 4096-env 的 26.2 GB 标定值
（那次标定是**不含机器人**的）。所以 4096 envs + 含机器人 mesh 这条路同时踩中"慢"和"可能 OOM"两个坑；
配置注释里"OOM 时可去掉 robot path，只损失近场自遮挡"是经过这次实测才确认的取舍。

⚠️ **两个 Isaac Sim 进程并发 = C++ 静默 abort**（无 Traceback，日志停在 `Starting the simulation`）：
一个卡在 `simulation_app.close()` 的诊断脚本没退出，就足以让随后启动的训练进程无声死亡。
**任何诊断脚本跑完必须 `os._exit(0)`**，且同一时刻只允许一个 Isaac Sim 实例。

### 四、消融配置（4 个 task 已注册并通过冒烟测试）

四个 task **共享同一份 policy 观测（实测 57 维）**，只改 critic 特权观测，
因此 actor 结构不变、已训 checkpoint 的 actor 可复用：

| 配置 | task id 后缀 | critic 外部感知 | critic 维度（实测） |
|---|---|---|---|
| **A** 基线 | `""`（现有 task） | height_scanner 187 | **263** |
| **B** 替代 | `-AiryReplace` | Airy BEV 720（无 height_scanner） | **796** |
| **C** 叠加 | `-AiryStacked` | 187 + 720 | **983** |
| **D** 下界 | `-ProprioOnly` | 无 | **76** |

- **B 是终点形态**：去掉仿真特权信息，感知形状与实机一致，可真正 sim2real
- **D 是下界**：完全无外部感知的性能下限，LiDAR 必须超过它才有意义
- ⚠️ 改 critic 观测会改变 value net 输入层，**四个配置都必须从头训**，checkpoint 之间不可迁移

冒烟测试结果（4/4 通过，实测维度而非推导）：

```
config             pol   crit  act           hits   bev_std  bev_max  ms/step  verdict
A baseline          57    263   16              -       nan      nan    32.42  OK
B airy_replace      57    796   16 161351062/1382400    0.1947    0.960    36.17  OK
C airy_stacked      57    983   16    161351048/1382400    0.1947    0.942    38.65  OK
D proprio_only      57     76   16              -       nan      nan    31.02  OK
proprio_only : 只用本体?
```

⚠️ **基线必须保持零改动**：LiDAR 只经 `RobotSceneCfgAiry`（scene 子类）引入，仅 B/C 使用。
三个原因：① 消融前提是 A 不带 LiDAR；② 基线改动会让**所有已训 checkpoint 作废**（263→983）；
③ 基线白占 ~26 GB 显存读一个它不用的传感器。

### 五、复现命令

```bash
# 传感器建模 + 半球朝向 + 几何精度
python scripts/diagnose/verify_airy_lidar.py --headless --envs 1

# 性能实测（务必在目标 env 数上跑，小规模数字不可外推）
python scripts/diagnose/verify_airy_lidar.py --headless --envs 4096 --horizontal_res 0.8

# BEV 栅格 vs 已知几何
python scripts/diagnose/verify_airy_bev.py --headless

# 4 个配置的端到端冒烟（真实建 env 并 step）
python scripts/diagnose/smoke_env_obs.py --headless --num_envs 32 --steps 30

# 4 个配置的严格消融训练（同 seed / 同超参 / 同  iters次数，只改 critic 特权观测）
# ⚠️ 必须串行：两个 Isaac Sim 进程并发会 C++ 静默 abort（见上文）
# ⚠️ env 数不对称（LiDAR 显存硬上限）：无 LiDAR 的 A/D 用 20096（与参考 ht_stairs_10x 同尺度），
#    带 Airy 传感器的 B/C 受 43200 射线/env 限制，4096 已近 32 GB 天花板 → A/D 每迭代样本量是 B/C 的 5×。
#    消融按“固定迭代数的最终性能”对比（已披露）；--video 再占 ~4 GB（B/C 逼近上限，慎用于小显存卡）。
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
COMMON="--headless --seed 42 --max_iterations 20000 --video --video_length 250 --video_interval 1000 --camera_view diag"



$PY scripts/rsl_rl/train.py $COMMON --task Unitree-GeesunDog-LingsiD30W-Velocity             --num_envs 20096 --run_name airy_A_baseline --video_start_frac 0.5    --resume  --load_run  2026-10-20_16-22-39_airy_A_baseline  --video --video_length 500 --video_interval 10000 --camera_view side



$PY scripts/rsl_rl/train.py $COMMON --task Unitree-GeesunDog-LingsiD30W-Velocity-ProprioOnly --num_envs 20096 --run_name airy_D_proprio


export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
$PY scripts/rsl_rl/train.py $COMMON --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace --num_envs 3096 --run_name airy_B_replace  --video_start_frac 0.5   --resume  --load_run 2026-10-20_01-03-41_airy_B_replace  --video --video_length 500 --video_interval 10000 --camera_view side

$PY scripts/rsl_rl/train.py $COMMON --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryStacked --num_envs 3096 --run_name airy_C_stacked

# ─────────────────────────────────────────────────────────────
# 【B 臂续训必须保住 pyramid_stairs_level（金字塔楼梯难度等级）】2026-10-20
# 上面那条 B 命令（--num_envs 3096 续训 4096 envs 的 run）在修复前会把楼梯等级 5.05 打到 0.49、
# x_max 0.3 打到 0.1（sidecar 的 num_envs 校验失败 → 随机初始化 → 写回覆盖，见「验证训练结果 §前置检查」）。
# 开跑前确认 B 臂自己的 sidecar（旁路状态文件）在位且数值对：
EXP=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
ls -l $EXP/terrain_levels_state_airy_B.json $EXP/curriculum_state_airy_B.json
$PY - <<'EOF'
import json
d = json.load(open("logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/terrain_levels_state_airy_B.json"))
print("by_type:", d["by_type"], "| num_envs:", d["num_envs"], "| max_level:", d["max_level"])
print("layout:", d["layout"])
EOF
# 期望 by_type 里 pyramid_stairs ≈ 5.05、layout = {num_rows 10, num_cols 20,
#       sub_terrains {flat 0.1, random_rough 0.2, pyramid_stairs 0.2}}（必须与 train cfg 逐字相同）
# 缺文件或值不对 → 先重建再训练：
$PY scripts/diagnose/rebuild_terrain_state_from_tb.py \
    --tb_run $EXP/2026-10-20_01-03-41_airy_B_replace --arm airy_B --num_envs 3096 --step 240000
# 启动日志两条判定（缺一不可）：
#   [INFO] terrain_levels sidecar (旁路状态文件): .../terrain_levels_state_airy_B.json
#   [INFO] Restored terrain levels (exact|by type, ...) ... | flat=... pyramid_stairs=4.94 ...
# 跑起来后 TB：pyramid_stairs_level 从 ~5 起步（不是 0.5）、x_max 从 0.3 起步（不是 0.1）。
# ─────────────────────────────────────────────────────────────


# 或直接交给排队脚本（等当前 B 跑完自动接 A → D → C，见 scripts/train_airy_ablation_queue.sh）
setsid nohup bash scripts/train_airy_ablation_queue.sh > outputs/train_airy_queue_stdout.log 2>&1 &

# ─────────────────────────────────────────────────────────────
# 【每臂独立迭代数】v1 与 v2 均已支持（2026-10-19 升级）
#   两个脚本功能完全相同，区别只在“训练进行中该动哪个”：训练在跑时绝不能动正在运行的那个文件
#   （bash 持有它的 fd），要用另一个副本启动；没有队列在跑时两者任选，v1 是主文件。
# 脚本顶部给每组一个默认迭代数（iteration），互不影响：
#     ITER_A=10000   ITER_D=10000   ITER_B=10000   ITER_C=10000     ← 改脚本里这 4 行
# 优先级：命令行第 1 参数 > MAX_ITER 环境变量 > 各臂自己的 ITER_*（后两者都不给 → 用各臂默认）
#   例：ITER_B=ITER_C=50000 做“等样本量”对比（B/C 只有 4096 envs，样本量是 A/D 的 1/5）
# run 行第 5 个参数 = 额外 CLI 参数串（续跑用）：
#     run "Unitree-GeesunDog-LingsiD30W-Velocity" airy_A_baseline 20096 "$ITER_A" \
#         "--resume --load_run 2026-10-19_16-36-14_airy_A_baseline --load_checkpoint model_900"
#   resume（续跑）不会删课程 sidecar（课程状态文件），地形等级与速度课程可接上。
setsid nohup bash scripts/train_airy_ablation_queue.sh > outputs/train_airy_queue_stdout.log 2>&1 &
bash scripts/train_airy_ablation_queue.sh 200          # 全局覆盖：四组都只跑 200 迭代（冒烟测试）
setsid nohup bash scripts/train_airy_ablation_queue_v2.sh > outputs/train_airy_queue_stdout.log 2>&1 &
bash scripts/train_airy_ablation_queue_v2.sh 200      # 全局覆盖：四组都只跑 200 迭代（冒烟测试）
# 队列日志现在会打印每臂的 envs 数与迭代数，便于核对消融配置：
#   [queue] ... === airy_B_replace (Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace, 4096 envs, 55555 iters) start ===
# video_interval（录像间隔）随迭代数自适应 → 短训（如 200 迭代）也能录到视频。
# 空跑自检（dry run，不启动真训练）：把脚本里 PY 换成 echo 包装、QLOG 指到 /tmp，
#   再 bash 副本，检查每臂 --max_iterations 是否等于各自 ITER_*、覆盖是否生效。
# ⚠️ 绝不要边跑边编辑“正在运行的脚本文件”：bash 进程持有该脚本的 fd（看 /proc/<pid>/fd/255），
#    改文件会让它的读取偏移错位，后续行可能从中间开始解析（语法错乱 / 漏跑 / 意外接力）。
#    训练进行中要改配置 → 新建脚本文件（如 v2）；等没有队列在跑时再 cp 覆盖回旧文件名。

# ─────────────────────────────────────────────────────────────
# 【B/C 组启动即崩（CUDA OOM，显存溢出）根因与修复】2026-10-20
# 症状：airy_B_replace / airy_C_stacked 在启动后 19~54 秒退出；队列日志记 exit code 0 但没有
#       Learning iteration（学习迭代）行 —— 之前被误判为"两个 Isaac Sim 并发硬 abort"。
# 根因（两处叠加；4096 envs × 43200 rays/env，Airy 激光雷达基线已占 26.8 GB）：
#   1) sensors/airy_bev.py 旧实现把距离分箱写成广播比较 (r.unsqueeze(-1) >= edge_inner).sum(-1)，
#      物化 (N, B, n_dist) 中间张量（3.3 GiB bool / 13.2 GiB float 级），外加逐 env 的 4096 次
#      scatter 调用。已修：torch.searchsorted(edges[:-1], r, right=True)（O(B) 显存）+ 每个
#      ray-chunk 一次向量化 scatter_reduce_。实测 4096×43200 峰值额外显存 3.04 GiB（chunk=8192），
#      且与旧实现逐位相同（bit-identical）。
#   2) Isaac Lab ray_caster.py:287 每步都要 quat_w.repeat(1, num_rays)（2.83 GiB）+ 输出（2.12 GiB），
#      而 PyTorch 缓存分配器有 1.6 GiB reserved-but-unallocated 碎片 → 1.98 GiB 分配失败。
#      已修：PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True（可扩展显存段），已写进两个队列脚本。
# 自检（纯 torch，不启动 Isaac Sim；对比新旧实现 + 显存探针）：
/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/diagnose/check_airy_bev_mem.py
#   期望：quat=False/True bit-identical、chunk=1 == chunk=8192 bit-identical、
#         new impl peak extra VRAM @ 4096x43200 ≈ 3.04 GiB、old impl OOM（即被修掉的 bug）
# 端到端冒烟（2026-10-20 实测通过）：
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY scripts/rsl_rl/train.py --headless \
    --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace --num_envs 4096 --seed 42 \
    --max_iterations 20 --run_name airy_B_smoke
#   实测：B 组 20/20 迭代完成、零 OOM、峰值显存 31839 MiB、6.73~7.00 s/iter
#         C 组（AiryStacked，多 height_scanner 187 维）20/20 完成、零 OOM、峰值 31885 MiB
# ⚠️ 显存余量只剩 ~0.7 GiB：B/C 组不要再加 --video（录像额外 ~4 GB），不要提高 num_envs，
#    也不要与 A/D（20096 envs）并发 —— 必须串行。

# ─────────────────────────────────────────────────────────────
# 【队列健康自检 / 挂起死锁排障】（2026-10-19 实测教训）
# 现象：queue（排队）脚本"在跑"，但 outputs/train_airy_A_baseline.log 数小时零输出、
#       没有任何 "Learning iteration"（学习迭代）行；GPU 只占 ~3.3 GB、利用率 <10%。
# 根因：训练进程被 SIGTSTP（Ctrl+Z）挂起后 STAT 是 T（stopped，已停止），而排队循环
#       `while pgrep -f "train.py --headless"; do sleep 15; done` 里 pgrep 仍然匹配 →
#       队列永远等不到"上一个训练结束"，形成死锁；挂起进程还占着显存不放。
#       此时再启动 queue 脚本只会堆积更多卡住的实例（每个将来都会重复跑一遍 A）。
ps -eo pid,stat,etime,time,cmd | grep -E 'train_airy_ablation_queue|train.py --headless' | grep -v grep
# 期望：queue 脚本恰好 1 个（STAT=Ss），训练进程 1 个且 STAT=Rl（Running，运行中）；出现 T 即被挂起。
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv   # 20096 envs 满场景应 ~25 GB / 70%+
grep -c 'Learning iteration' outputs/train_airy_A_baseline.log    # 必须持续增长
tail -2 outputs/train_airy_queue.log                               # 有 start 无 exit code = 该组未结束
# 恢复步骤（挂起的训练若 0 迭代、无 run 目录，直接杀无损失）：
#   kill -9 <queue 的 pid> <train.py 的 pid>
#   cp outputs/curriculum_sidecar_backup/*.json logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/
#   setsid nohup bash scripts/train_airy_ablation_queue.sh 10000 > outputs/train_airy_queue_stdout.log 2>&1 &
# 注意 1：绝不要在交互终端里前台跑该脚本（Ctrl+Z 或关闭终端都会杀掉训练）；必须 setsid nohup 脱离终端。
# 注意 2：初始化耗时参考 —— 20096 envs 从启动到第一条 Learning iteration 约 8 分钟，期间日志停在
#         PhysX 的 enable_external_forces_every_iteration 警告行属正常，不要误判为卡死。
# 注意 3：fresh（非 --resume）训练会删共享 experiment 目录下的 curriculum_state.json /
#         terrain_levels_state.json（课程状态文件），脚本末尾自动还原；中途被杀需手动 cp 还原。

# height_scanner 活项自检（exit 0 = ALIVE，exit 1 = DEAD/被 clip 钉住）
python scripts/diagnose/check_height_scanner_values.py --headless --num_envs 8 --steps 20

# height_scanner 空间高度图验证（楼梯）：证明 187 格在 pyramid_stairs 上构成真实高度图而非常数
#   exit 0 = RESOLVED（足迹跨地形高度分化）；exit 1 = FLAT。强制单块满难度楼梯 + 悬停读取 17x11 网格
#   实测（2026-10-16）：ray_hits_w z 跨 0.00~1.38 m，obs 187 格 +0.51~-0.87、std≈0.39 -> RESOLVED
python scripts/diagnose/check_height_scanner_stairs.py --headless --num_envs 1 --hover_z 1.0

# 训练后逐 arm 保存 height_scanner 的 高度差 / 均值 / 方差（落盘 outputs/height_scanner_stats/<arm>.json）
#   A/C 有该项（应 alive、variance>0）；B 被 Airy 替代、D 纯本体 -> 该项缺失（present=false）
#   fast_terrain（flat+pyramid_stairs 1x2）秒级启动，保证网格有起伏；具体数值随落点/难度浮动，看 alive 判定与趋势
python scripts/diagnose/save_height_scanner_stats.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity              # -> A_baseline.json
python scripts/diagnose/save_height_scanner_stats.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryStacked    # -> AiryStacked.json
python scripts/diagnose/save_height_scanner_stats.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace    # -> AiryReplace.json
python scripts/diagnose/save_height_scanner_stats.py --headless --task Unitree-GeesunDog-LingsiD30W-Velocity-ProprioOnly    # -> ProprioOnly.json

# ─────────────────────────────────────────────────────────────
# 测试 / 回放（play.py）
# ⚠️ 必须显式 --checkpoint：play.py 默认在该 experiment 目录下挑“最新 run + 最新 model”，
#    而 unitree_geesun_lingsi_d30w_ht_stairs_10x 混了 A/B/C/D 四组，不指定会挑错 arm。
# ⚠️ --task 必须与 checkpoint 同 arm，否则 policy 输入维度不匹配 → size mismatch。
# ⚠️ 消融进度（2026-10-19 实测）：A、D 各已完成 2000 iters（迭代数）——run 目录
#    2026-10-16_19-59-33_airy_A_baseline / 2026-10-16_22-07-45_airy_D_proprio（均到 1999/2000）；
#    B、C 至今无有效结果（启动后 19~52 秒即退出，队列日志记 exit code 0 但无 Learning iteration 行），
#    对应测试需先跑上面的 train 块。A 的 10000 iters 长训自 2026-10-19_16-36-14_airy_A_baseline 起进行中。
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
EXP=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
# 查所有 run 与最新 checkpoint：
#   ls -t $EXP | head ; ls $EXP/<RUN>/model_*.pt | sort | tail -1

# A 基线（已训完 10400 迭代，✓ 可测）——楼梯 + 自由视角，2026-10-20 实测通过
# ⚠ 任务名**没有** -airy_A_baseline 后缀：run_name（运行名）不是 task id 的一部分，
#    注册任务只有 -Velocity(A) / -AiryReplace(B) / -AiryStacked(C) / -ProprioOnly(D) 四个
#    （见 lingsi_d30w/__init__.py 的 _register 调用）
# ⚠ 该 run 的 checkpoint 是 100 的整数倍（model_7300 … model_10400），**没有 model_9999.pt**
RUN=$EXP/2026-10-21_00-51-44_airy_A_baseline

/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/rsl_rl/play.py \
  --task Unitree-GeesunDog-LingsiD30W-Velocity \
  --checkpoint $RUN/model_20399.pt \
  --num_envs 4 --no_standing --no_curriculum --real-time \
  --camera_view side --camera_eye 6 6 3.0 --camera_target 0 0 0.3 \
  --terrain stairs --cmd_x 0.2 0.4 --cmd_y -0.1 0.1 --cmd_z -0.3 0.3 --episode_length_s 35 
#   实测日志三行（缺一不可，证明"确实是 A 臂 + 楼梯已生成 + 维度匹配"）：
#   [INFO]: Parsing configuration from: ...velocity_env_cfg:RobotPlayEnvCfg
#   [INFO] Terrain mode: stairs (5x4 grid: stairs x 1.0)
#   Actor MLP: Linear(in_features=57 … out_features=16) / Critic MLP: Linear(in_features=263 …)
# 产物：$RUN/videos/stairs_A_10400/rl-video-step-0.mp4 = 1280x720 / 50 fps / 499 帧 / 9.98 s
# 楼梯 + 自由视角（GUI 里自由转视角）的完整命令见下一节「A 臂楼梯回放 + 自由视角」

# B Airy 替代（⚠ 先训练 airy_B_replace）  --headless
$PY scripts/rsl_rl/play.py \
  --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace  --video_start_frac 0.5 --terrain complex \
  --checkpoint $EXP/2026-10-21_00-51-44_airy_A_baseline/model_20399.pt

# C Airy 堆叠（⚠ 先训练 airy_C_stacked）
$PY scripts/rsl_rl/play.py --headless \
  --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryStacked \
  --checkpoint $EXP/<airy_C_stacked_RUN>/model_XXXX.pt

# D 纯本体感知（训练中，把 XXXX 换成 ls $EXP/2026-10-16_18-10-19_airy_D_proprio 的最大编号）
$PY scripts/rsl_rl/play.py --headless \
  --task Unitree-GeesunDog-LingsiD30W-Velocity-ProprioOnly \
  --checkpoint $EXP/2026-10-16_18-10-19_airy_D_proprio/model_XXXX.pt

# 可选 flags：--num_envs 256（并行加速统计） / --video --camera_view diag（录视频） / --real-time
```

#### A 臂楼梯回放 + 自由视角（free camera，自由视角）——2026-10-20 实测通过

**① 为什么默认回放里"没有楼梯"（根因，已逐行核对 IsaacLab 源码）**

`RobotPlayEnvCfg.__post_init__`（`lingsi_d30w/velocity_env_cfg.py:641-642`）把地形网格压成
**2 行 × 1 列**，而 `RobotEnvCfg.__post_init__` 同时把 `terrain_generator.curriculum = True`
（同文件 630 行）。IsaacLab 在 `curriculum=True` 时走
`terrains/terrain_generator.py::_generate_curriculum_terrains()`，它是**按列**分配子地形的：

```python
sub_index = np.min(np.where(index / self.cfg.num_cols + 0.001 < np.cumsum(proportions))[0])
```

`num_cols = 1` → 只有 `index = 0` → `0.001 < cumsum[0] = 0.1667`（flat 归一化比例 1/6）
→ `sub_index = 0` = **flat**。于是整张 play 网格 = **2 格全平地**，
楼梯与 random_rough（随机粗糙）**一个都不会生成**（确定性结论，不是"随机没抽到"）。

→ 要测楼梯必须显式 **`--terrain stairs`**：地形预设（terrain preset，地形预设）把整个
`terrain_generator` 替换成 **5 行 × 4 列全楼梯**（`scripts/rsl_rl/terrain_presets.py:107-121`），
并把 `max_init_terrain_level` 设为 `num_rows-1 = 4` → 出生随机铺满全部难度行；
踏步高取 task cfg 的 `step_height_range=(0.05, 0.23)` m（与 GO2 逐字一致）。
启动日志必须出现这一行，才证明楼梯真的生成了：

```
[INFO] Terrain mode: stairs (5x4 grid: stairs x 1.0)
```

**② 自由调整视角（GUI，图形界面）——只有 `free` 可行**

```bash
# GUI（去掉 --headless）+ --camera_view free：机位只在首帧设一次，之后完全不动，
# 可在 Kit 视口（viewport，图形窗口）里自由拖动 / 旋转 / 缩放
DISPLAY=:1 $PY scripts/rsl_rl/play.py \
  --task Unitree-GeesunDog-LingsiD30W-Velocity \
  --checkpoint $RUN/model_10400.pt \
  --num_envs 4 --no_standing --no_curriculum --real-time \
  --camera_view free --camera_eye 6 6 3.0 --camera_target 0 0 0.3 \
  --terrain stairs --cmd_x 0.2 0.4 --cmd_y -0.1 0.1 --cmd_z -0.3 0.3
```

| 需求 | 参数 | 原因 |
|---|---|---|
| 一眼看全 5×4 楼梯场 | `--camera_view free --camera_eye 6 6 3.0 --camera_target 0 0 0.3` | 2026-10-20 实测机位：整场楼梯入画，机器狗在画面内 |
| 窗口里手动拖动/旋转不被覆盖 | **必须 `free`** | `side`/`rear`/`diag` 每步都调用 `_follow_camera()`（`play.py:425`），手动机位下一步就被搬回机器身上 |
| 慢动作看清抬腿/打滑 | `--real-time` | 默认是尽快仿真（远快于实时）；该参数按 `step_dt = 0.02` → 50 Hz 节流 |
| 抬高机位 | `free`：直接写 `--camera_eye` 的 z；跟拍：`--camera_height` | `free` 不受 height/distance 约束，高度就是 eye 的 z |
| 同时录像 | `--video --video_length 500 --video_tag stairs_A_10400` | 录像走同一台视口相机；实测 499 帧 / 9.98 s / 440 KB / 零黑帧 |

> 楼梯难度旋钮：`--stair_height 0.03 0.10` = 轮半径 0.095 m 的保守上限（只看低难度台阶）；
> 不带 = task cfg 的 0.05–0.23 m（与 GO2 严格消融对照）。
> `--cmd_x` 必须 ≤ 该臂 TB 上的 `Curriculum/lin_vel_cmd_levels/x_max`（A 臂 = **±0.45 m/s**）
> → 楼梯测试用 `--cmd_x 0.2 0.4`。
> 同一 GPU（图形处理器）只能跑一个 Isaac Sim 实例，GUI 回放前先停训练与守护进程（见「前置检查」）。

**③ A 臂训练结果（TensorBoard 末 50 迭代均值，run `2026-10-20_19-03-11_airy_A_baseline`，iter 7300→10400）**

| 指标 | 值 | 判读 |
|---|---|---|
| `Train/mean_reward` | 26.49 | 已收敛 |
| `Train/mean_episode_length` | 958 / 1000 | 接近跑满 |
| `Metrics/base_velocity/error_vel_xy` / `_yaw` | 0.216 m/s / 0.312 rad/s | 达标（验收线 0.25 / 0.35） |
| `Episode_Termination/time_out` | 0.897 | **低于验收线 0.99** |
| `Episode_Termination/bad_orientation`（摔倒终止） | 0.104 | **超验收线 0.01 约 10 倍 → 未过验收** |
| `Episode_Termination/base_contact`（机身触地） | 0.000 | 达标 |
| `Curriculum/terrain_levels`（地形难度均值） | 5.89 | 中高难度 |
| `Curriculum/lin_vel_cmd_levels/x_max` | 0.450（全程最大也是 0.450） | 比 B 臂 0.300 高 50% → **与 B/D 对比必须按同命令范围比** |
| `flat` level / success_rate / err_xy | 5.98 / 1.000 / 0.089 | 达标 |
| `random_rough` level / success_rate / err_xy | 6.01 / 0.9997 / 0.102 | 达标 |
| `pyramid_stairs` level / success_rate / err_xy / err_yaw | 5.73 / **0.659** / 0.137 / 0.206 | **短板：楼梯成功率 0.659 ≪ 验收线 0.90** |

→ 与 B 臂（楼梯成功率 0.641、`x_max` 0.30）几乎持平：**在楼梯这一项上 `height_scanner`（高度扫描传感器）
相对 Airy BEV 没有明显收益**；两臂楼梯成功率都远低于 flat / random_rough（≈1.0）。
录像与定量测试都应重点跑楼梯（`--terrain stairs`）。


**⑤ 楼梯定量测试实测（2026-10-20 23:01，`model_10400.pt`，`--terrain stairs --num_envs 16 --steps 1000`）**

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY -u scripts/rsl_rl/test_walk_torque.py \
    --headless --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --checkpoint $RUN/model_10400.pt --terrain stairs --num_envs 16 --steps 1000
# 产物：<run>/stairs_terrain_stats.csv（逐关节 Peak/P99/RMS + 行走指标）
```

| 指标 | 实测值 | 判读 |
|---|---|---|
| `success_rate`（成功率） | **0.875** | 看着达标 |
| `average_forward_velocity_ms`（平均前进速度） | **0.011 m/s** | **机器狗在楼梯上基本停住不动** |
| `mean_error_xy_ms` / `mean_error_yaw_rads` | 0.117 / 0.155 | 低于 0.25 / 0.35 判据 |
| `height_variance_m2`（高度方差） | 0.00093 | 几乎没有上下起伏（没在爬） |
| `ALL (pooled)` Peak / P99 / RMS 力矩 | 61.13 / 20.21 / 6.96 N·m | calf 峰值最高 61.1（上限 136，未饱和） |
| **轮子（wheel）峰值力矩** | fl 19.96 / fr 14.31 / **hl 20.00** / hr 19.66 N·m | **3/4 个轮子打满 20 N·m 上限 → 力矩饱和（torque saturation，力矩饱和）** |

> **⚠ 判据漏洞（本次实测暴露）：** `test_walk_torque.py:250` 与课程门控
> （`curriculums.py:450-451`，`success_xy = 0.25`）的成功判据都是
> "存活到超时 + `err_xy < 0.25` + `err_yaw < 0.35`"——**站着不动也能通过**：
> 命令在 ±0.25 m/s 内均匀随机，静止时 `err_xy = |cmd| ≈ 0.125 < 0.25`
> → 成功率 87.5%、判定 "Stable"，而真实前进速度只有 0.011 m/s。
> 同理 `gated_lin_vel_cmd_levels` 的 `x_max` 也会因"静止即达标"继续爬
> （实测每 500 迭代 +0.05，一路到 0.45 m/s）。
> **修法（改动最小，一处一条判据）**：给成功判据加前进位移下限，例如
> `forward_ok = mean(base_lin_vel_x) >= 0.5 * |cmd_x|`，与现有三条判据取与（AND）；
> 测试脚本与课程各改一处，A/B/C/D 四臂同步生效。
>
> **楼梯失败的物理口径：** 踏步 0.23 m > 轮径 0.19 m，必须靠 12 个腿关节把轮心抬过踏步；
> 轮子 effort 上限 20 N·m（URDF 口径，`UnitreeActuatorCfg_D30W` 的 wheel `Y=20`）在楼梯接触工况下
> **已饱和**，轮子既出不了牵引也抬不起机身；腿侧未饱和（hip/thigh 峰值 26–43 / 上限 72，
> calf 峰值 61 / 上限 136）→ **瓶颈不在腿的力矩上限，而在策略没学会抬腿过踏步**
> （`Episode_Reward/feet_air_time` 末段仅 +0.0036，抬腿收益太弱）。


**④ D 臂闸门：`terrain_levels` 全程冻结的根因（2026-10-20 实测）**

D 臂 run `2026-10-19_22-55-51_airy_D_proprio`（1000 迭代）的 `Curriculum/terrain_levels`
**全程恒为 0.5054**、`x_max` 恒为 0.100→0.1021。原因：`terrain_levels_vel_strict` 里
`gate_open = x_max >= min_x_max_for_move_up`，而 cfg 的 `min_x_max_for_move_up = 0.2`
（`lingsi_d30w/velocity_env_cfg.py:517`，**不是本文旧版写的 0.3**）；`x_max` 从 0.1 起步、
每档 `lin_increment = 0.05`，1000 迭代内没爬到 0.2 → 闸门从未打开 → 地形**双向冻结**
（`mdp/curriculums.py:227-232`；冻结是设计行为，不是 bug）。
判据：TB 上 `Curriculum/terrain_levels` 是一条水平直线 **且** `x_max < 0.2` = 闸门未开
→ **该 run 不能用于消融结论**（D 臂与 A 臂同为 20096 envs，建议 ≥ 3000 迭代再看曲线）。


产物落在 `outputs/verify_airy*/`（`stats.json` / `bev.png` / 点云 CSV·PLY）。

> ⚠️ **fresh run 会删掉共享实验目录的两个 curriculum sidecar**（`curriculum_state.json` /
> `terrain_levels_state.json`，`train.py` 只对 `--resume` 保留）。做消融前先按上文「跨 run / 回退消融」
> 小节的规则备份；本仓库已把 `unitree_geesun_lingsi_d30w_ht_stairs_10x` 的原始值存到
> `outputs/curriculum_sidecar_backup/`（20096 envs / terrain mean 0.50 / step 0 /
> 命令范围 `[-0.6,0.6] [-0.1,0.1] [-1.0,1.0]`）。

### 六、踩坑记录（都是实测踩出来的，别照抄直觉）

1. **`RayCasterCfg` 只读第一个网格** —— 94% 命中落在地面，障碍全丢。必须用 `MultiMeshRayCasterCfg`
2. **半球朝向靠猜会全错** —— 必须渲染俯视图/侧视图用"地面覆盖半径"判定
3. **`imshow` + `extent` 把 log 间距的距离环线性铺开** —— 台阶 r=3 被画到 y≈9，
   数据正确但图**误导判断**。必须用 `pcolormesh` 按真实 bin 边界绘制
4. **显存估算公式低估 6.6 倍** —— 朴素公式给出假保护，`0.4°` 时断言不触发但实际 OOM。必须实测标定
5. **同进程建第 2 个 env 触发 `UsdExpiredPrimAccessError`（C++ abort，Python 无法捕获）** ——
   每个配置必须独立子进程；且 `simulation_app.close()` 会挂起，需 `os._exit(0)`
6. **`MultiMeshRayCasterCfg` 的 mesh 去重是 O(num_envs)** —— `mesh_prim_paths` 含机器人时
   ~1 s/env，4096 envs 光初始化就要 ~68 分钟（20096 envs 要 5.5 小时），显存也会越过标定值
7. **两个 Isaac Sim 进程并发 = C++ 静默 abort** —— 无 Traceback，日志停在 `Starting the simulation`。
   一个没退出的诊断脚本就足以杀死随后启动的训练。诊断脚本一律 `os._exit(0)`，同一时刻只跑一个实例
8. **`--run_name` 生效但实验目录由 `agent_cfg.experiment_name` 决定** —— D30W 各 task 共用
   `logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x`，run 名前加时间戳区分；
   且 **fresh run 会删掉该目录的两个 curriculum sidecar**，消融前必须先备份
6. **`um.group_obs_term_dims` 不存在** —— 真实属性是私有的 `om._group_obs_term_dim`
7. **`env.num_actions` 不存在** —— 用 `sum(env.action_manager.action_term_dim)`
8. **D30W 是 16 个驱动关节，不是 12** —— policy 57 维、action 16 维，实测得来，不要按 12 推算

### 七、尚未实施

- **域随机化**：`AIRY_RANDOMISATION` 已定义外参 ±3 cm/±2°、测距噪声、丢点率 0~15%、延迟 0~50 ms
  等范围，但**尚未接入** `randomize_ray_caster` 事件项
- **policy 接入**：当前仅 critic 观测，policy 仍是 57 维 proprioception。
  接入 policy 会让**所有旧 checkpoint 作废**
- **4096 envs 是临界点**：LiDAR 本身 26.2/32.6 GB，尚未计入 D30W articulation buffers，
  真实训练大概率要降到 2048 envs
- **RGB 摄像头**：已确认暂不接入策略

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



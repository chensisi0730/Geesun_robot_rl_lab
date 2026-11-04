# Unitree RL Lab

[![IsaacSim](https://img.shields.io/badge/IsaacSim-5.1.0-silver.svg)](https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html)
[![Isaac Lab](https://img.shields.io/badge/IsaacLab-2.3.0-silver)](https://isaac-sim.github.io/IsaacLab)
[![License](https://img.shields.io/badge/license-Apache2.0-yellow.svg)](https://opensource.org/license/apache-2-0)
[![Discord](https://img.shields.io/badge/-Discord-5865F2?style=flat&logo=Discord&logoColor=white)](https://discord.gg/ZwcVwxv5rq)


## 项目概述

本项目基于 [IsaacLab](https://github.com/isaac-sim/IsaacLab) 构建，提供了一套面向宇树（Unitree）机器人的强化学习环境。

目前支持宇树 **Go2**、**H1** 和 **G1-29dof** 机器人。

<div align="center">

| <div align="center"> Isaac Lab </div> | <div align="center">  Mujoco </div> |  <div align="center"> 实机 </div> |
|--- | --- | --- |
| [<img src="https://oss-global-cdn.unitree.com/static/d879adac250648c587d3681e90658b49_480x397.gif" width="240px">](g1_sim.gif) | [<img src="https://oss-global-cdn.unitree.com/static/3c88e045ab124c3ab9c761a99cb5e71f_480x397.gif" width="240px">](g1_mujoco.gif) | [<img src="https://oss-global-cdn.unitree.com/static/6c17c6cf52ec4e26bbfab1fbf591adb2_480x270.gif" width="240px">](g1_real.gif) |

</div>

## 安装

- 按照[安装指南](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html)安装 Isaac Lab。
- 安装 Unitree RL 的 IsaacLab 独立环境。

  - 将本仓库克隆或复制到 Isaac Lab 安装目录之外（即不要放在 `IsaacLab` 目录内）：

    ```bash
    git clone https://github.com/unitreerobotics/unitree_rl_lab.git
    ```
  - 使用已安装 Isaac Lab 的 Python 解释器，以可编辑模式安装本库：

    ```bash
    conda activate env_isaaclab_sim5
    ./unitree_rl_lab.sh -i
    # 重启 shell 以激活环境变更。
    ```
- 下载宇树机器人描述文件

  *方式一：使用 USD 文件*
  - 从 [unitree_model](https://huggingface.co/datasets/unitreerobotics/unitree_model/tree/main) 下载宇树 USD 文件，并保持目录结构不变
    ```bash
    git clone https://huggingface.co/datasets/unitreerobotics/unitree_model
    ```
  - 在 `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py` 中配置 `UNITREE_MODEL_DIR`。

    ```bash
    UNITREE_MODEL_DIR = "</home/user/projects/unitree_usd>"
    ```

  *方式二：使用 URDF 文件 [推荐]* 仅适用于 IsaacSim >= 5.0
  - 从 [unitree_ros](https://github.com/unitreerobotics/unitree_ros) 下载宇树机器人 URDF 文件
      ```
      git clone https://github.com/unitreerobotics/unitree_ros.git
      ```
  - 在 `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py` 中配置 `UNITREE_ROS_DIR`。
    ```bash
    UNITREE_ROS_DIR = "</home/user/projects/unitree_ros/unitree_ros>"
    ```
  - [可选]：如果希望使用 URDF 文件，请修改 *robot_cfg.spawn*



- 通过以下方式验证环境是否安装正确：

  - 列出可用的任务：

    ```bash
    ./unitree_rl_lab.sh -l # 比 isaaclab 自带命令更快的版本
    ```
  - 运行一个任务：
    g1：平地  2026-07-08_14-09-16
    GO2：平地 unitree_go2_velocity/2026-07-08_21-46-54

    ```bash
    ./unitree_rl_lab.sh -t --task Unitree-G1-29dof-Velocity # 支持任务名自动补全
    # 等价于
    python scripts/rsl_rl/train.py --headless --task Unitree-G1-29dof-Velocity --num_envs 22000 --resume 

    python scripts/rsl_rl/train.py --headless --task Unitree-Go2-Velocity --num_envs 8000 --resume


    tensorboard --logdir logs/rsl_rl/

    ```
  - 使用训练好的策略进行推理：

    ```bash
    ./unitree_rl_lab.sh -p --task Unitree-G1-29dof-Velocity # 支持任务名自动补全
    # 等价于
    python scripts/rsl_rl/play.py --task Unitree-G1-29dof-Velocity
    ```

## 部署

模型训练完成后，需要先在 Mujoco 中对训练好的策略进行 sim2sim（仿真到仿真）验证，以测试模型性能。
然后再进行 sim2real（仿真到实机）部署。

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

### Sim2Sim（仿真到仿真）

安装 [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco?tab=readme-ov-file#installation)。

- 将 `/simulate/config.yaml` 中的 `robot` 设置为 g1
- 将 `domain_id` 设置为 0
- 将 `enable_elastic_hand` 设置为 1
- 将 `use_joystck` 设置为 1

```bash
# 启动仿真
cd unitree_mujoco/simulate/build
./unitree_mujoco
# ./unitree_mujoco -i 0 -n eth0 -r g1 -s scene_29dof.xml # 备选启动方式
```

```bash
cd unitree_rl_lab/deploy/robots/g1_29dof/build
./g1_ctrl
# 1. 按下 [L2 + 上] 使机器人站立
# 2. 点击 mujoco 窗口，然后按 8 让机器人脚部接触地面
# 3. 按下 [R1 + X] 运行策略
# 4. 点击 mujoco 窗口，然后按 9 关闭弹性吊带
```

### Sim2Real（仿真到实机）

你可以直接使用该程序控制机器人，但请确保机载控制程序已经关闭。

```bash
./g1_ctrl --network eth0 # eth0 为网卡名称
```

## 致谢

本仓库的建立离不开以下开源项目的支持与贡献。特别感谢：

- [IsaacLab](https://github.com/isaac-sim/IsaacLab)：训练与运行代码的基础框架。
- [mujoco](https://github.com/google-deepmind/mujoco.git)：提供强大的仿真功能。
- [robot_lab](https://github.com/fan-ziqi/robot_lab)：参考了其项目结构与部分实现。
- [whole_body_tracking](https://github.com/HybridRobotics/whole_body_tracking)：用于动作跟踪的通用人形机器人控制框架。

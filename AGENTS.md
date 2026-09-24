# 仓库指南

## 项目结构与模块组织

- `source/unitree_rl_lab/unitree_rl_lab/` 包含可安装的 Python 包、机器人资产、任务定义、MDP 项和配置。
- `scripts/` 提供运行入口，包括 `list_envs.py`、RSL-RL 训练/推理、动作模仿转换和回放工具，以及 `geesun_dog/move_geesun_dog.py`（将 `unitree_model/geesun_dog` 的 dog1 URDF 导入 Isaac Sim 并驱动全部 12 个关节；URDF 的空 hip 网格、零限位等问题在 `assets/robots/unitree.py` 中自动修复）。
- `deploy/` 包含 C++ sim2real 控制器、各机器人配置和随附的 ONNX Runtime 依赖。
- `unitree_model/` 存放 Unitree USD 资产（如已提供）；`logs/` 和 `outputs/` 保存生成的运行结果，不应作为源代码编辑。
- `docker/` 包含容器构建与编排文件；`doc/` 包含许可证和项目文档。

## 构建、测试与开发命令

请使用兼容 IsaacLab 且已安装 Isaac Sim 的 Conda 环境（Python 3.10+）。

```bash
conda activate env_isaaclab
./unitree_rl_lab.sh -i                         # editable install and shell setup
./unitree_rl_lab.sh -l                         # list registered tasks
./unitree_rl_lab.sh -t --task Unitree-G1-29dof-Velocity --num_envs 12000
./unitree_rl_lab.sh -p --task Unitree-G1-29dof-Velocity
```

训练检查点写入 `logs/rsl_rl/`；使用 `tensorboard --logdir logs/rsl_rl/` 查看 TensorBoard。进行 C++ 部署时，在已安装 CMake、Unitree SDK2、Boost、yaml-cpp 和 Eigen 的环境中配置并构建指定目录，例如 `deploy/robots/g1_29dof/`。

## 编码风格与命名约定

Python 使用 4 个空格缩进、Black 格式化（120 列限制）、采用 Black 配置的 isort，以及 Flake8。函数和模块使用 `snake_case`，类使用 `PascalCase`；任务和配置名称应清晰，并与现有注册名称保持一致。C++ 遵循相邻代码风格，使用 C++17；机器人专属代码放在 `deploy/robots/<robot>/` 下。

提交变更前运行 `pre-commit run --all-files` 执行全部本地检查。除非明确需要，否则不要将生成的日志、检查点和模型二进制文件提交到仓库。

## 测试指南

当前没有专门的单元测试套件。请通过列出受影响的任务、运行一段短时无头训练或推理，并检查控制台输出及生成文件来验证变更。对于新增的可复用 Python 工具，条件允许时应同时添加针对性测试。

## 提交与拉取请求指南

近期提交使用简短的祈使式描述（通常为中文），例如 `更新README.md，添加...`。每个提交应聚焦单一变更，并说明受影响的机器人或任务。拉取请求应包含简明摘要、验证命令及结果、涉及的配置或检查点路径，以及行为/视觉变更的截图或 TensorBoard 证据。如有对应 issue 请关联，并注明所需的 IsaacLab/IsaacSim 或硬件环境。

## 配置与安全

在 `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py` 中将 `UNITREE_MODEL_DIR` 或 `UNITREE_ROS_DIR` 设置为本地资产路径。不要提交私钥、机器凭据或大型生成文件；连接实体机器人前，务必仔细检查部署配置。


实体机器人是G1 edu u6-zl旗舰版D ，配备因时五指灵巧手RH56DFTP，12个自由度，上半身手臂14个DOF;下半身腿部12个DOF，腰部3个DOF，整机自由度是41。,有深度相机Intel Realsense D435i 和3D激光雷达LIVOX-MID360，
GO2是GO2 EDU-ZL ，3D激光雷达MI3-360,
在CONDA环境env_isaaclab_sim51中，训练G1和GO2在复杂地形行走和速度跟踪的能力，评估启用 height_scanner的收益和风险。
守护进程scripts/monitor_tb_check.py，每4个小时监控TensorBoard里面的各项训练曲线，发现训练曲线恶化后，自动停止训练，并修改代码，调整超参数，重新训练。
要求改动尽量小，方便做消融对照实验。
GeesunDog的URDF文件有问题，不要训练。
训练完成后，如何验证训练结果？`unitree_rl_lab` 的 editable 安装实际没有指向本仓库的问题还存在吗
用中文思考和回答。考虑更新文档手册README.md，添加验证训练结果的步骤。
每次回答最后回复“汪汪”。
总结整个地形和terrain_levels 和lin_vel_cmd_levels的设计逻辑，使用图表展示；
terrain_levels 和lin_vel_cmd_levels的升级和降级的逻辑是什么？他们之间的关系是什么？如何稳定提高terrain_levels和lin_vel_cmd_levels？
检查TensorBoard里面的各项训练曲线，列出每种地形的情况下，训练的情况，给出改进方案。



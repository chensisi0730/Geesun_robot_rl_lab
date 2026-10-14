实体机器人是G1 edu u6-zl旗舰版D ，配备因时五指灵巧手RH56DFTP，12个自由度，上半身手臂14个DOF;下半身腿部12个DOF，腰部3个DOF，整机自由度是41。,有深度相机Intel Realsense D435i 和3D激光雷达LIVOX-MID360，
GO2是GO2 EDU-ZL ，3D激光雷达MI3-360,
在CONDA环境env_isaaclab_sim51中，训练G1和GO2在复杂地形行走和速度跟踪的能力，评估启用 height_scanner（高度扫描传感器）的收益和风险。
守护进程scripts/monitor_tb_check.py，每6个小时监控TensorBoard（张量可视化面板）里面的各项训练曲线，发现训练曲线恶化后，自动停止训练，并修改代码，调整超参数，重新训练。
要求改动尽量小，方便做消融对照实验。

训练完成后，如何验证训练结果？见下文「验证训练结果」。`unitree_rl_lab` 的 editable（可编辑）安装已正确指向本仓库 source/unitree_rl_lab/（2026-10-12 验证，旧问题不存在了）。
用中文思考和回答。

总结整个地形和terrain_levels 和lin_vel_cmd_levels的设计逻辑，使用图表展示；见 doc/training_monitoring.md §4。
terrain_levels 和lin_vel_cmd_levels的升级和降级的逻辑是什么？他们之间的关系是什么？如何稳定提高terrain_levels和lin_vel_cmd_levels？
课程terrain_levels升级后，lin_vel_cmd_levels需要重置为0,是否合理？

检查TensorBoard里面的各项训练曲线，列出每种地形的情况下，训练的情况，给出改进方案。
<!-- 没有mmproj，不支持图像。 -->
每次回答最后回复“汪汪AGENT”。考虑更新文档手册README.md，添加验证训练结果的步骤。英文的名词每次出现必须要备注中文名称

---

## 环境与验证过的命令

- conda 环境（Python 3.11）：`/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python`；训练/监控/测试全部用它。
- 训练：`python scripts/rsl_rl/train.py --headless --task <TASK> --num_envs <N>`。
  - 任务 id（gym 注册名）：`Unitree-Go2-Velocity`（GO2）、`Unitree-G1-29dof-Velocity`（G1）、`Unitree-GeesunDog-Velocity`（GeesunDog 狗）、`Unitree-H1-Velocity`（H1）。
  - run（训练批次）目录：`logs/rsl_rl/<experiment_name>/<YYYY-MM-DD_HH-MM-SS>/`；checkpoint（检查点）`model_<iter>.pt` 每 100 迭代存一次。
  - 当前惯例：GO2 `--num_envs 18000`；GeesunDog `--num_envs 24096`（2026-10-12 起）。
- 训练曲线：`tensorboard --logdir logs/rsl_rl/`；逐项中文释义见 `outputs/monitor/curves.md` 与 `scripts/tb_notes.py`。

## 验证训练结果

见 README「验证训练结果」章节（目视行走 + 定量行走/力矩测试 + TensorBoard + 验收清单）：

```bash
python scripts/rsl_rl/test_flat_walk.py --task <TASK> --terrain flat --steps 500
for terrain in flat random_rough stairs complex; do
  python scripts/rsl_rl/test_flat_walk.py --task <TASK> --terrain "$terrain" --steps 1000
done
```

## 监控守护进程（6 小时闭环）

- GO2 战役：`scripts/monitor_tb_check.py`（默认参数即 GO2；state（状态）在 `outputs/monitor/`、`outputs/autotune/`）。
- GeesunDog 战役：`nohup bash scripts/monitor_tb_check_dog.sh >> outputs/monitor_dog/monitor.log 2>&1 &`（独立 state 在 `outputs/monitor_dog/`、`outputs/autotune_dog/`）。
- 自动处置链：曲线恶化 → 停止训练 → 改一个超参数（备份 + diff + py_compile（语法校验））→ 重启（PPO（近端策略优化）类参数 resume（续训），奖励/课程类 fresh（重训））；恶化类规则豁免动作预算（2026-10-10 起）。
- 关闭自动调参：`touch outputs/autotune[_dog]/DISABLED`；只看计划：`python scripts/autotune.py --dry-run`；回滚：`--rollback`。

## 关键契约（非显而易见）

- **同一 GPU 只能跑一个 IsaacSim 实例**（两个实例互抢 GPU 与 kit 键值库，会互相杀死）；切换训练前先停旧进程。
- 监控会 auto-resume（自动续训）旧 run：手动暂停某战役时写 `stop_marker` 到对应 `outputs/monitor*/state.json`（新 run 写 TensorBoard 数据后标记自动清除）。
- GeesunDog 变体（variant，变体）由环境变量 `GEESUN_DOG_VARIANT` 选择（`dog1` 默认 / `lingsi_d30w` 轮足）；URDF 自动修复后转 USD（通用场景描述）到 `/tmp/IsaacLab/geesun_dog/`；PPO 配置类 `UnitreeGeesunDogPPORunnerCfg`（超参与 `BasePPORunnerCfg` 一致，独立声明只为限定 autotune 的编辑范围）。
- 地形定义在各机器人 `tasks/locomotion/robots/<robot>/velocity_env_cfg.py` 的 `COBBLESTONE_ROAD_CFG`；子地形 `proportion`（比例）会被 IsaacLab 自动归一化，删子地形不用手调比例。
- 监控/autotune 的战役参数可由环境变量覆盖（`MON_RUNS_GLOB`/`MON_TASK`/`MON_NUM_ENVS`/`MON_LOG_PREFIX`/`MON_DIR`/`AUTOTUNE_DIR`/`AUTOTUNE_ENV_FILE`/`AUTOTUNE_PPO_SCOPE`），一份代码可盯多个战役。

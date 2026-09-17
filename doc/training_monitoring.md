# 训练监控与结果验证手册（GO2 / G1 速度任务）

## 1. 4 小时自动监控

`scripts/monitor_tb_check.py` 每 4 小时检查一次最新训练 run（`logs/rsl_rl/unitree_go2_velocity/` 下最新目录）：

1. **进程存活**：训练进程死亡时自动从最新 checkpoint resume（10 分钟冷却防崩溃循环；无 checkpoint 时只告警不自动重启，日志 `/tmp/train_go2_auto.log`）；
   若存在 overflow 停止标记（见 2.）则**抑制自动 resume**，需人工重启；
2. **PhysX Overflow**：PhysX patch 溢出**没有 TensorBoard 标签**，唯一观察渠道是训练日志中的
   `Patch buffer overflow` 告警。监控脚本增量统计各 `/tmp/train_go2_v*.log` 新增条数（首次见到的日志只建基线不计数，避免旧 run 的历史误报）；
   **发现任意新增行立即终止训练**：对匹配 `train.py.*Unitree-Go2-Velocity` 的进程组发 SIGTERM
   （15 s 宽限后 SIGKILL），并在 `state.json` 写入 `stop_marker`（含原因与日志证据）以抑制自动 resume；
   当最新 run 目录出现晚于停止时刻的 tfevents 写入（人工已重启）时标记自动清除，恢复正常崩溃自愈。
   防御性保护：只杀匹配到的进程组，pgid≤1 与监控自身进程组永不触碰；
3. **TensorBoard 快照**：课程、速度误差、reward、终止率、value loss、学习率、噪声和 FPS 最近 200 迭代；
4. **异常标志**：进程死亡、overflow、time_out <0.85、bad_orientation >2%、LR 长期在下限、地形提升时 reward 下跌或误差上升，以及**价值函数发散保护**：最近 200 迭代 `Loss/value_function` 中位数 > 100 时判定为发散，立即终止训练并写 `stop_marker`（抑制自动 resume，需人工处理），避免反复复活一个已经坏掉的 run。

启动方式（与训练进程解耦，nohup 常驻）：

```bash
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
nohup bash -c 'while true; do \
  /home/css/miniconda3/envs/env_isaaclab_sim5/bin/python scripts/monitor_tb_check.py \
  >> outputs/monitor/monitor.log 2>&1; sleep 14400; done' >/dev/null 2>&1 &
```

输出：

- `outputs/monitor/report.md`：每次检查追加一节（进程状态、overflow 计数、曲线表、flags）；
- `outputs/monitor/state.json`：日志偏移量、上次快照、上次自动重启时间、`stop_marker` 停止标记（删除 `stop_marker` 键或删整个文件即重置基线）；
- `outputs/monitor/monitor.log`：每次检查的单行摘要。

手动运行一次：`conda run -n env_isaaclab_sim5 python scripts/monitor_tb_check.py`

注意：刚 resume 的前 ~50 个迭代存在启动瞬态（time_out/mean_reward 偏低），阈值规则在样本
数 <50 时不触发告警，属正常现象，无需干预。

**Overflow 自动停止后的处理流程**：

1. 查看 `outputs/monitor/report.md` 最新一节的 `AUTO-STOP ...` action 行（含被杀的 pgid/pid、
   信号、日志证据）与 `stop_marker` 行；
2. `grep -c 'Patch buffer overflow' /tmp/train_go2_v*.log` 确认量级（v3 历史值 98145）；
3. 按 §2/§3.1 判断根因（num_envs 过大、地形碰撞网格过密、场景构建期分配低估）并调整配置；
4. 人工重新启动训练（新 run）——监控检测到新 run 的 tfevents 写入后自动清除 `stop_marker`，
   恢复正常崩溃自愈；在此之前进程死亡只告警不自动重启。

## 2. TensorBoard 判读要点

- `Metrics/base_velocity/error_vel_*` 和课程门控均使用 episode 逐步误差真均值。课程在 command reset
  之前执行，因此直接读取 running sums；读取尚未结算的 `metrics` 会得到旧零值并导致错误升级。
- `Episode_Reward` 对短 episode 会低估，不作为收敛主判据。核心判据：
  velocity error、time_out、LR、terrain/speed curriculum 进度、日志 overflow 计数。
- GO2 线速度命令范围由 `gated_lin_vel_cmd_levels` 控制（`velocity_env_cfg.py`）：初始固定
  `±0.25 m/s`，统计窗口按**训练时长**而非回合数定义（`min_env_steps=12000` 个环境步 ≈ 500 迭代，
  且 ≥ `min_episodes=4000` 个回合），窗口内**成功率**（存活到 time_out 且回合平均
  `error_vel_xy < 0.25`、`error_vel_yaw < 0.35`）连续 `hold=2` 个窗口 ≥ `0.9` 时，才把 x 范围
  按 `+0.05 m/s` 放宽一次；y 范围保持不变（两轴解耦）。**不要**再按 track reward 单指标升级——
  旧实现每 ~2.7h 无条件 +0.1，速度涨到 ±0.65 时价值函数发散（value_loss 峰值 1.7e5），地形课程
  随之退化。升级后的范围写入 `logs/rsl_rl/unitree_go2_velocity/curriculum_state.json`
  （checkpoint 不保存命令范围），崩溃/自动 resume 不会悄悄回退课程；fresh run 由 train.py 删除该文件。
  注意：用大量并行 env（22000）时若把窗口设成回合计会瞬间跑满，所以这里必须用 `min_env_steps`。
- **地形等级同样不在 checkpoint 中**：resume 后地形按 `min/max_init_terrain_level`（GO2 为 0–2）
  重新初始化，不回滚到重启前的平均等级。最高等级环境会随机回到较低行，因此平均值不必达到 8–9。
- GO2 的严格地形课程使用 `0.22/0.30` 升级阈值和 `0.40/0.45` 降级阈值，并按 terrain type 记录结果。

## 3. 训练结果验证步骤

训练完成（或检查点可用）后按以下顺序验证：

### 3.1 训练曲线终检

```bash
tensorboard --logdir logs/rsl_rl/unitree_go2_velocity/
```

- `Curriculum/lin_vel_cmd_levels/x_max` 只在门控达标时阶梯上升，`.../success_rate` 应稳定在高位；
- 各 `Curriculum/terrain_performance_by_type/*` 无明显退化；
- `time_out >= 0.99`、`bad_orientation <= 0.01`、`error_vel_xy <= 0.25`、`error_vel_yaw <= 0.35`；
- 训练日志 `grep -c 'Patch buffer overflow' <log>` 为 0（或远低于 v3 的 98145）。

### 3.2 仿真回放（headless play）

```bash
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
source /home/css/miniconda3/etc/profile.d/conda.sh && conda activate env_isaaclab_sim5
python scripts/rsl_rl/play.py --headless --task Unitree-Go2-Velocity \
  --num_envs 22000 --load_run <run_name> --checkpoint model_<iter>.pt
```

- 多 env 回放，观察 `time_out` 比例与速度跟踪（play 日志打印 mean reward / episode length）；
- 需要可视化时用 `--video`（少量 env）或去掉 `--headless` 打开 Isaac Sim 窗口。

### 3.3 分地形覆盖度检查

```bash
for terrain in flat random_rough boxes stairs complex; do
  python scripts/rsl_rl/test_flat_walk.py --task Unitree-Go2-Velocity \
    --terrain "$terrain" --steps 1000 --checkpoint <checkpoint-path>
done
```

阶段 1 默认保持 `±0.25 m/s`；阶段 2 完成后增加 `--full_command_range` 做压力测试。

### 3.4 Sim2Real 部署（真机前）

1. `deploy/robots/go2_edu/`（对应机器人目录）构建 C++ 控制器，确认观测顺序与
   `play.py` 一致、policy ONNX 由最新 checkpoint 转换；
2. 真机先低增益/短距离验证：平地面 → 台阶 → 粗糙地形，逐级提高速度命令；
3. 连接实体机器人前仔细核对部署配置（相机/IMU 标定、关节映射、控制频率 50Hz）。

### 3.5 重启后快速验证

1. 本次课程定义已改变，应启动新 run；不要直接续训速度范围已经扩大的旧 run；
2. TB `Curriculum/lin_vel_cmd_levels/x_max` 从 `0.25` 起步，`.../success_rate` 未达门控前不上升；
3. `Curriculum/command_ranges/*` 显示 x/y 命令边界均为 `±0.25 m/s`；
4. `Curriculum/terrain_performance_by_type/*` 标签在 episode reset 后出现；
5. `grep -c 'Patch buffer overflow' <新日志>` 为 0。

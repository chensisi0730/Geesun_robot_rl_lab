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
3. **TensorBoard 快照**：`Curriculum/terrain_levels`、`Curriculum/lin_vel_cmd_levels`、`Metrics/base_velocity/error_vel_{xy,yaw}`、`Train/mean_reward`、`Episode_Termination/time_out`、`Loss/learning_rate`、`Perf/total_fps` 最近 200 迭代的 min/med/max；
4. **异常标志**（相对上次快照）：进程死亡、新增 overflow、time_out 中位 <0.85、LR 在 1e-5 停留 >25%、mean_reward 腰斩、level 与 range 冻结 >5.5h。

启动方式（与训练进程解耦，nohup 常驻）：

```bash
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
nohup bash -c 'while true; do \
  /home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/monitor_tb_check.py \
  >> outputs/monitor/monitor.log 2>&1; sleep 14400; done' >/dev/null 2>&1 &
```

输出：

- `outputs/monitor/report.md`：每次检查追加一节（进程状态、overflow 计数、曲线表、flags）；
- `outputs/monitor/state.json`：日志偏移量、上次快照、上次自动重启时间、`stop_marker` 停止标记（删除 `stop_marker` 键或删整个文件即重置基线）；
- `outputs/monitor/monitor.log`：每次检查的单行摘要。

手动运行一次：`/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/monitor_tb_check.py`

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

- `Metrics/base_velocity/error_vel_*` 是**单命令周期均值的约 2×**（episode 20s 含 2 次 10s 重采样，
  isaaclab `UniformVelocityCommand._update_metrics` 按 `Σerror/max_command_step` 累积）。
  课程门控内部使用修正后的真实均值；对照阈值时记得 TB 值 ≈ 2× 真实值。
- `Episode_Reward` 对短 episode 会低估，不作为收敛主判据。核心判据：
  velocity error、time_out、LR、terrain/speed curriculum 进度、日志 overflow 计数。
- 速度课程每次 +0.05 扩张会在 reward/entropy/LR 上造成锯齿瞬态（KL 尖峰），约 200 迭代内
  自行恢复；仅当 LR 连续 >500 迭代钉在 1e-5 时才考虑把扩张步长降到 0.03。
- **速度课程状态不在 checkpoint 中**（rsl-rl checkpoint 只保存 model/optimizer/iter，`infos=None`）。
  GO2 已用 sidecar JSON 解决：`lin_vel_cmd_levels` 的 `state_file` 参数把 range 与门控缓冲
  （`_lin_vel_curric`）在每个评估窗口后原子写入 `logs/rsl_rl/unitree_go2_velocity/curriculum_state.json`，
  resume 进程首次课程调用时自动读回（新 run 日志开头应出现 `[curriculum] restored _lin_vel_curric ...`）；
  `train.py` 对非 resume 的新 run 删除该文件，防止误继承。手工 bootstrap（如从 v5 终点 0.25 起步、
  避免 ~10–12h 重爬）：直接写该 JSON（`ranges` ±0.25、`gate` 清零），再 `--resume` 启动即可。
  G1/H1/GeesunDog 默认 `state_file=None`，行为不变，可作消融对照。
- **地形等级同样不在 checkpoint 中**：resume 后地形按 `min/max_init_terrain_level`（GO2 为 0–2）
  重新初始化，不回滚到重启前的平均等级（v6 起点 ~2.0 即新初始化分布的结果）。当前离目标（8–9）
  尚远可接受，接近目标后再考虑持久化。
- 地形课程 `terrain_levels_vel_fixed`：`window_div` 缩短评估窗口（默认 1 = 原行为；
  GO2 用 10），解决稳态评估样本只有 ~num_envs/max_episode_length 个 env、等级几乎不爬升的问题。
  G1/geesun/h1 仍走 `terrain_levels_vel` 别名（默认参数），行为不变，可作消融对照。

## 3. 训练结果验证步骤

训练完成（或检查点可用）后按以下顺序验证：

### 3.1 训练曲线终检

```bash
tensorboard --logdir logs/rsl_rl/unitree_go2_velocity/
```

- `Curriculum/lin_vel_cmd_levels` 达到目标 range（GO2 1.0）；
- `Curriculum/terrain_levels` 爬到 8–9（20cm 楼梯全覆盖）；
- `Episode_Termination/time_out` ≥ 0.9；`Metrics/error_vel_*` 在 range 上限处稳定；
- 训练日志 `grep -c 'Patch buffer overflow' <log>` 为 0（或远低于 v3 的 98145）。

### 3.2 仿真回放（headless play）

```bash
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
source /home/css/miniconda3/etc/profile.d/conda.sh && conda activate env_isaaclab_sim51
python scripts/rsl_rl/play.py --headless --task Unitree-Go2-Velocity \
  --num_envs 22000 --load_run <run_name> --checkpoint model_<iter>.pt
```

- 多 env 回放，观察 `time_out` 比例与速度跟踪（play 日志打印 mean reward / episode length）；
- 需要可视化时用 `--video`（少量 env）或去掉 `--headless` 打开 Isaac Sim 窗口。

### 3.3 课程覆盖度检查

- 地形：确认 `terrain_generator` 行 0–9 全部生成（stairs 行在 9），play 时 env 落在高层
  地形仍能稳定行走（楼梯/坡道不后退、不跌倒）；
- 速度：play 时命令 range 拉满（±1.0 m/s、±0.5–1.0 rad/s），验证跟踪误差分布。

### 3.4 Sim2Real 部署（真机前）

1. `deploy/robots/go2_edu/`（对应机器人目录）构建 C++ 控制器，确认观测顺序与
   `play.py` 一致、policy ONNX 由最新 checkpoint 转换；
2. 真机先低增益/短距离验证：平地面 → 台阶 → 粗糙地形，逐级提高速度命令；
3. 连接实体机器人前仔细核对部署配置（相机/IMU 标定、关节映射、控制频率 50Hz）。

### 3.5 Resume / 重启后快速验证（速度课程 sidecar 生效确认）

1. 新 run 日志开头（首个迭代完成前）出现
   `[curriculum] restored _lin_vel_curric from .../curriculum_state.json: ranges=...`；
2. TB `Curriculum/lin_vel_cmd_levels` 第一个点即等于重启前 range（如 0.25），而不是 0.1；
3. `cat logs/rsl_rl/unitree_go2_velocity/curriculum_state.json`：`ts`/`env_step` 随每个评估窗口
   更新（22000 envs 下约 7 分钟/窗），`gate.n` 每窗 +1，满 16 窗（~2h）触发一次课程评估；
   文件损坏时训练回退到 cfg 默认并打印 WARNING，不会崩溃；
4. `grep -c 'Patch buffer overflow' <新日志>` 为 0。
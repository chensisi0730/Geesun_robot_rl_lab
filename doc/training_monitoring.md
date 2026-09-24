# 训练监控与结果验证手册（GO2 / G1 速度任务）

## 1. 6 小时自动监控

`scripts/monitor_tb_check.py` 每 6 小时检查一次最新训练 run（`logs/rsl_rl/unitree_go2_velocity/` 下最新目录）：

1. **进程存活**：训练进程死亡时自动从最新 checkpoint resume（10 分钟冷却防崩溃循环；无 checkpoint 时只告警不自动重启，日志 `/tmp/train_go2_auto.log`）；
   若存在 overflow 停止标记（见 2.）则**抑制自动 resume**，需人工重启；
2. **PhysX Overflow**：PhysX patch 溢出**没有 TensorBoard 标签**，唯一观察渠道是训练日志中的
   `Patch buffer overflow` 告警。监控脚本增量统计各 `/tmp/train_go2_v*.log` 新增条数（首次见到的日志只建基线不计数，避免旧 run 的历史误报）；
   **发现任意新增行立即终止训练**：对匹配 `train.py.*Unitree-Go2-Velocity` 的进程组发 SIGTERM
   （15 s 宽限后 SIGKILL），并在 `state.json` 写入 `stop_marker`（含原因与日志证据）以抑制自动 resume；
   当最新 run 目录出现晚于停止时刻的 tfevents 写入（人工已重启）时标记自动清除，恢复正常崩溃自愈。
   防御性保护：只杀匹配到的进程组，pgid≤1 与监控自身进程组永不触碰；
3. **TensorBoard 快照**：课程、速度误差、reward、终止率、value loss、学习率、噪声和 FPS 最近 200 迭代；
4. **异常标志**：进程死亡、overflow、time_out <0.85、bad_orientation >2%、LR 长期在下限、地形提升时 reward 下跌或误差上升，以及**价值函数发散保护**：最近 200 迭代 `Loss/value_function` 中位数 > 100 时判定为发散，交给 autotune 将 PPO 学习率减半（下限 `2e-4`），随后 fresh 重训，避免续训已经发散的 checkpoint。
5. **瞬态恶化容忍**（`terrain_levels`、`Loss/value_function` 等短时下降但会自行恢复的情形）：
   - **单次不动作**：value loss 尖峰、terrain_levels 下降单次检查只报 `WARN ... tolerated`，须在下一次检查（6 小时后）**复现**才升级为 CRITICAL/动作；自行恢复的恶化永远不会中断训练；
   - **同 run 确认**：价值函数"持续发散"的确认要求两次检查属于同一个 run，fresh 重训后需重新观察；
   - **跨 run 不对比**：run 切换后的 reward/terrain 对比直接跳过（fresh 重启会把课程归零、reward 基线改变），报告中以 `note: cross-check comparison skipped` 注明，避免误报"terrain +5.9, err_xy 恶化"这类假象；
   - **autotune 恶化类动作二次确认**：曲线恶化/摔倒率上升触发的"停训+调参+重启"动作需连续 2 次检查复现（`CONFIRM_CHECKS = 2`，状态记在 `outputs/autotune/state.json` 的 `pending_confirm`）；价值函数发散类动作除外（本身已要求连续 2 个 200 迭代窗口超阈值），plateau 类调参动作除外（非破坏性，自带冷却）。

启动方式（与训练进程解耦，nohup 常驻）：

```bash
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
nohup bash -c 'while true; do sleep 21600; \
  /home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/monitor_tb_check.py \
  >> outputs/monitor/monitor.log 2>&1; done' >/dev/null 2>&1 &
```

（`sleep` 放在前面：重启守护进程时不会立即重复检查，保持 6 小时节拍。）

输出：

- `outputs/monitor/report.md`：每次检查追加一节（进程状态、overflow 计数、曲线表、flags）；
- `outputs/monitor/state.json`：日志偏移量、上次快照、上次自动重启时间、`stop_marker` 停止标记（删除 `stop_marker` 键或删整个文件即重置基线）；
- `outputs/monitor/monitor.log`：每次检查的单行摘要。

手动运行一次：`conda run -n env_isaaclab_sim51 python scripts/monitor_tb_check.py`

注意：刚 resume 的前 ~50 个迭代存在启动瞬态（time_out/mean_reward 偏低），阈值规则在样本
数 <50 时不触发告警，属正常现象，无需干预。

**Overflow 自动停止后的处理流程**：

1. 查看 `outputs/monitor/report.md` 最新一节的 `AUTO-STOP ...` action 行（含被杀的 pgid/pid、
   信号、日志证据）与 `stop_marker` 行；
2. `grep -c 'Patch buffer overflow' /tmp/train_go2_v*.log` 确认量级（v3 历史值 98145）；
3. 按 §2/§3.1 判断根因（num_envs 过大、地形碰撞网格过密、场景构建期分配低估）并调整配置；
4. 人工重新启动训练（新 run）——监控检测到新 run 的 tfevents 写入后自动清除 `stop_marker`，
   恢复正常崩溃自愈；在此之前进程死亡只告警不自动重启。

### 1.1 全曲线报告 + 自动调参闭环（autotune）

- **全曲线**：每次检查把**所有** TensorBoard scalar（不只关键项）写入
  `outputs/monitor/curves.md`：窗口 min/med/max/last 与窗口内相对变化（trend），用于快速定位
  哪些项仍在涨、哪些已平台。
- **自动调参**：训练存活且无 `stop_marker` 时，监控以**子进程**方式调用
  `scripts/autotune.py`（因此随时编辑 `autotune.py` 的旋钮/规则，下一次检查即生效）：
  1. 读取最新 run 的全曲线，诊断：平台（`plateau`）、yaw/lin 门控卡住、探索塌缩
     （`mean_noise_std<0.2`）、LR 贴底、跌倒率上升和曲线恶化（`degrading`）；
  2. 按 `decide()` 中的**优先级规则**每次只改**一个**小旋钮（便于消融），旋钮注册表 `KNOBS`
     覆盖 PPO 超参、课程阈值/增量、奖励权重；
  3. 停止当前训练 → 备份并改写配置源码（备份 + unified diff + `py_compile` 校验）
     → 重启：**PPO 类旋钮 `--resume` 续训**，**奖励/课程/重置噪声类旋钮全新训练**（`restart` 字段）。
     修改、编译或启动失败时自动恢复源码，并尝试从原 run 最新 checkpoint 恢复训练；价值函数发散时
     学习率变更也使用 fresh 重训。
- **安全护栏**：`MIN_START_ITERS=1500` 之前不动；两次动作间隔 ≥ `MIN_ITERS_BETWEEN_ACTIONS=600`
  迭代且墙钟时间 ≥ 3 小时；迭代冷却按 run 独立计算，fresh run 的 step 归零不会被旧 run 卡住；
  全局上限 `MAX_ACTIONS=16`，每个旋钮有独立预算；`init_noise_std`/`entropy_coef`/`desired_kl`
  等"加压"规则还额外要求 **plateau 且课程未解锁到上限**，避免打扰已收敛的良好 run。
- **恶化判据**：使用最近 400 迭代前/后四分位数的中位数比较。单条噪声曲线不会触发重训；需
  reward 下降 ≥20% 且至少一项（xy/yaw 误差上升 ≥15%、time_out 下降 ≥10%、bad_orientation
  上升 ≥25%）同时恶化，或至少两项非 reward 指标同时恶化。触发后按主要恶化项每次只修改一个
  有界超参，顺序执行停止训练、备份/修改/语法校验、fresh 或 resume 重训，并记录完整 ledger。
- **人工控制**：
  - 关闭自动调参：`touch outputs/autotune/DISABLED`（删除即恢复）；
  - 只看计划不改：`python scripts/autotune.py --dry-run`；
  - 查看/调整旋钮当前值：`python scripts/autotune.py --list`；
  - 回滚最近一次改动并重启：`python scripts/autotune.py --rollback`；
  - 审计：`outputs/autotune/ledger.jsonl`（逐条动作/旧值/新值/原因/备份路径）、
    `outputs/autotune/state.json`、源码备份在 `outputs/autotune/backups/`。

### 1.2 曲线中文备注（TensorBoard TEXT 页显示）

TensorBoard 曲线卡片没有备注字段，中文说明通过 **TEXT 面板**显示：

```bash
/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/tb_notes.py   # 生成/刷新中文备注
```

然后在 TensorBoard（`--logdir logs/rsl_rl/`）顶部切到 **TEXT** 页，左侧勾选 run
**`00_曲线中文说明`**：`00_使用说明（先看这条）` 是分组速查 + 判读口诀，其余每个 tag
一条备注（中文名 / 含义 / 判读方式），覆盖全部 65 条训练曲线。备注的唯一来源是
`scripts/tb_notes.py` 的 `NOTES` 字典，修改后重跑即刷新；`--list` 可在终端打印对照表。
说明 run 与训练 run 同级（`logs/rsl_rl/00_曲线中文说明/`），不会被监控的
`logs/rsl_rl/unitree_go2_velocity` 扫描到，对训练与监控零影响。

## 2. TensorBoard 判读要点

- `Metrics/base_velocity/error_vel_*` 和课程门控均使用 episode 逐步误差真均值。课程在 command reset
  之前执行，因此直接读取 running sums；读取尚未结算的 `metrics` 会得到旧零值并导致错误升级。
- `Episode_Reward` 对短 episode 会低估，不作为收敛主判据。核心判据：
  velocity error、time_out、LR、terrain/speed curriculum 进度、日志 overflow 计数。
- GO2 命令范围由 `gated_lin_vel_cmd_levels`（`velocity_env_cfg.py`）控制：线速度初始
  `±0.25 m/s`、偏航初始 `±0.5 rad/s`。统计窗口按**训练时长**而非回合数定义
  （`min_env_steps=12000` 个环境步 且 ≥ `min_episodes=4000` 个回合）。**线性轴与偏航轴独立门控**
  （旧实现把 xy 与 yaw 合成一个成功率，yaw 跟不上时整个课程死锁，fresh Go2 run 就是这样卡住的）：
  - x 范围：窗口内线性成功率（存活到 time_out 且 `error_vel_xy < 0.25`）≥ `0.9` 且 time_out 率
    ≥ `0.9`，连续 `hold=2` 个窗口后按 `+0.05 m/s` 放宽；y 范围始终冻结；
  - 偏航范围：窗口内偏航成功率（存活且 `error_vel_yaw < 0.35`）≥ `0.9` 且 time_out 率 ≥ `0.9`，
    连续 `hold=2` 个窗口后 `ang_vel_z` 按 `+0.1 rad/s` 放宽，上限 `±1.0 rad/s`。
  **不要**再按 track reward 单指标升级——旧实现每 ~2.7h 无条件 +0.1，速度涨到 ±0.65 时价值函数
  发散（value_loss 峰值 1.7e5），地形课程随之退化。升级后的范围（`lin_vel_x`/`lin_vel_y`/
  `ang_vel_z`）写入 `logs/rsl_rl/unitree_go2_velocity/curriculum_state.json`
  （checkpoint 不保存命令范围），崩溃/自动 resume 不会悄悄回退课程；fresh run 由 train.py 删除该文件。
  注意：用大量并行 env（22000）时若把窗口设成回合计会瞬间跑满，所以这里必须用 `min_env_steps`。
- PPO 探索配置（`agents/rsl_rl_ppo_cfg.py:UnitreeGo2PPORunnerCfg`）需保留足够探索压力：
  `init_noise_std=0.8`、`entropy_coef=0.01`、`desired_kl=0.01`、`learning_rate=8e-4`。早期一版把
  这些减半（0.5/0.005/0.005/3e-4），fresh run 在数百迭代内探索噪声就塌缩到 ~0.1，卡在「忽略 yaw」
  的局部最优（`error_vel_yaw≈0.9`）。
- **地形等级同样不在 checkpoint 中**：resume 后地形按 `min/max_init_terrain_level`（GO2 为 0–2）
  重新初始化，不回滚到重启前的平均等级。最高等级环境会随机回到较低行，因此平均值不必达到 8–9。
- GO2 的严格地形课程使用 `0.22/0.30` 升级阈值和 `0.40/0.45` 降级阈值，并按 terrain type 记录结果。

## 3. 训练结果验证步骤

训练完成（或检查点可用）后按以下顺序验证：

### 3.1 训练曲线终检

```bash
tensorboard --logdir logs/rsl_rl/unitree_go2_velocity/
```

- `Curriculum/lin_vel_cmd_levels/x_max`（线速度）与 `.../z_max`（偏航）只在各自门控达标时阶梯上升，
  `.../success_rate` 与 `.../yaw_success_rate` 应稳定在高位；
- 各 `Curriculum/terrain_performance_by_type/*` 无明显退化；
- `time_out >= 0.99`、`bad_orientation <= 0.01`、`error_vel_xy <= 0.25`、`error_vel_yaw <= 0.35`；
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

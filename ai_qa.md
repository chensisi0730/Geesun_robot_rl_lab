

## 现在能爬多高的楼梯？

**直接答案：当前 v5 run（terrain level = 2.0）中，机器人实际接触过的楼梯最高约 10 cm（8.6–10.4 cm），且任意时刻只有约 25% 的 env 落在楼梯瓦片上。地形生成器的物理上限是 23 cm。**

### 推导链（全部已验证到代码行）

**① 地形网格布局**（`terrain_generator.py:235-257`，GO2 为 10 行 × 20 列，每瓦片 8m×8m）：
- **列 → 地形类型**（按 proportion 固定分配，与难度无关）：
  | 列 | 地形 | 占比 |
  |---|---|---|
  | 0–2 | flat | 15% |
  | 3–7 | random_rough | 25% |
  | 8–14 | boxes | 35% |
  | **15–19** | **pyramid_stairs** | **25%** |
- **行 = 地形等级（level 直接索引行，不是 0..L 的集合）**：`env_origins = terrain_origins[level, col]`（`terrain_importer.py:329`），difficulty = (row + η)/10，η~U(0,1)

**② 台阶高度公式**（`hf_terrains.py:177`）：
```
step_height = 0.05 + difficulty × (0.23 − 0.05)
```

**③ 各等级对应的台阶高度**：

| 地形等级 (行) | difficulty | 台阶高度 | 金字塔总高（每侧≈8 步×0.3m 宽） |
|---|---|---|---|
| 0 | 0.0–0.1 | 5.0–6.8 cm | ~0.4–0.5 m |
| 1 | 0.1–0.2 | 6.8–8.6 cm | ~0.5–0.7 m |
| **2（v5 当前）** | **0.2–0.3** | **8.6–10.4 cm** | **~0.7–0.8 m** |
| 3 | 0.3–0.4 | 10.4–12.2 cm | ~0.8–1.0 m |
| 5 | 0.5–0.6 | 14.0–16.2 cm | ~1.1–1.3 m |
| 7 | 0.7–0.8 | 17.6–19.4 cm | ~1.4–1.6 m |
| 9（上限） | 0.9–1.0 | 21.2–23.0 cm | ~1.7–1.8 m |

（金字塔中央是 3m 宽平地，两侧 2.5m 阶梯各约 8 级；boxes 瓦片同理按 difficulty 缩放，level 2 时方块高 8–9.5 cm。）

### 当前 v5 实时状态（s≈17950，754 迭代）

| 指标 | 值 | 含义 |
|---|---|---|
| `terrain_levels` | 2.002 | ~100% env 在 level 2（8.6–10.4 cm 楼梯 / 8–9.5 cm 方块） |
| `error_vel_xy / yaw` | 0.117 / 0.186 | **均低于地形升级门限（0.2 / 0.3）** → 下一批窗口评估后 level 应升到 3 |
| `lin_vel_cmd_levels` | 0.1 | 速度课程仍在攒 16 样本缓冲（~670 迭代后首次评估） |
| `learning_rate` | 3.8e-4 | 健康 |
| PhysX 溢出 | 0 | — |

### 结论与建议

1. **短期（未来几千迭代）**：terrain 将升到 level 3 → 楼梯 10.4–12.2 cm。之后每升一级台阶高增 ~1.8 cm。
2. **想让 GO2 学会 15–20 cm 楼梯**：让课程自然爬到 level 5–7 即可（无需改配置），前提是速度课程同步推进、误差保持在门限内。按当前节奏（level 2 起步 + 误差达标），预计数小时到一天内可见 level 4–5。
3. **不建议**直接把 `step_height_range` 上限提到 0.23 以上：GO2 EDU 硬件实测爬坡能力通常在 15–20 cm 台阶附近，sim 里 23 cm 的满难度（level 9）已略超硬件包线，sim2real 迁移时该档策略大概率失效。
4. 若想**现在就验证楼梯能力**，可以起一个 `play.py` 推理（加载 v5 最新 checkpoint，手动把 env 放到 level 2 的楼梯列 15–19 上观察），但 10 cm 台阶属于平地策略的附带能力，不是专门强化过的。

**一句话：现在 ~10 cm；地形课程健康推进的话，接下来每天大约能多学会 1–2 cm 台阶高度，1 周左右可覆盖 15 cm。**



# PhysX 溢出（PhysX Overflow）是什么

## 一、概念

Isaac Sim 使用 PhysX 的 **GPU 并行仿真**跑 RL 训练（成百上千个环境同时做物理仿真）。PhysX 的 GPU 端缓冲区（接触点流、碰撞栈、堆内存等）是**启动时静态预分配的，不能动态扩容**。当某一步物理仿真产生的**接触点 / 碰撞对 / 数据量超过这些缓冲区容量**（或显存不够）时，PhysX 只能**丢弃超出部分**并打印警告——这就是 “PhysX 溢出”。

仓库内 IsaacLab v2.3.0 的官方配置文档也明确说明了这一点（`IsaacLab_v2.3.0/source/isaaclab_physx/isaaclab_physx/physics/physx_manager_cfg.py` 第 29–33 行）：

> "Unlike CPU PhysX, the GPU simulation feature is unable to dynamically grow all the buffers. … **If insufficient buffer sizes are provided, the simulation will fail with errors and lead to adverse behaviors.**"

## 二、为什么本仓库容易触发（结合当前上下文）

| 因素 | 现状 |
|---|---|
| `num_envs` | 任务默认 `4096`，但 README 中 Go2 训练用的是 `--num_envs 12000`（12000 × 13 个 GO2 连杆 ≈ 15 万刚体） |
| 地形 | GO2 使用复杂粗糙地形（`random_rough` / `boxes` / `pyramid_stairs`），是典型的 **contact-rich** 场景，接触量远超平地 |
| 传感器 | 两个任务都挂了 `contact_forces`（history_length=3）+ `height_scanner`（160 条射线/环境），每步物理负载更高 |
| 缓冲区默认值 | `gpu_max_rigid_contact_count = 2**23`，`gpu_max_rigid_patch_count = 5*2**15 ≈ 164k`（偏小），`gpu_collision_stack_size = 2**26` |
| 显存 | RTX 5090 共 32GB，当前训练已占 **28GB（98% 利用率）**，几乎没有余量，Isaac Sim 视口 / Realsense / 其他进程都会挤占 |

## 三、溢出的后果（对训练的影响）

1. **接触点被丢弃** → 机器人视觉上“打滑”、“穿过地面”、脚部抖动，物理行为失真；
2. **观测数据残缺** → contact forces 出现 0/缺失值，策略学到错误特征，奖励曲线跳变、训练不稳定甚至 NaN；
3. **显存型溢出（OOM）** → 仿真步骤失败，严重时进程直接崩溃。

## 四、如何判断是否发生了溢出

- **训练控制台**：出现 `omni.physx` 相关的 overflow / contact count 超过 buffer 的警告；
- **`nvidia-smi`**：显存占用贴着 32GB 上限（如现在 28GB+）；
- **TensorBoard / 可视化**：reward 曲线突然异常跳变、NaN；回放时机器人穿模、滑倒。

## 五、处理办法（改动最小，不破坏 height_scanner 消融对照）

按优先级：

1. **先降 `num_envs`**（12000 → 4096 甚至 2048）复跑，确认警告是否消失——最快定位手段；
2. **保持大环境数则调大 GPU 缓冲区**，在任务 `SimulationCfg.physics` 中显式设置（Isaac Lab 官方 contact-rich 场景示例 `tacsl_sensor.py` / `gear_assembly_env_cfg.py` 就是这么做的）：
   ```python
   physics=PhysxCfg(
       gpu_collision_stack_size=2**30,
       gpu_max_rigid_contact_count=2**25,
       gpu_max_rigid_patch_count=2**22,
   )
   ```
   注意：这是**仿真容量参数，不改变物理语义**，对消融实验无影响——但要求 on/off 两组保持相同参数；
3. **释放显存**：训练时用 `--headless`，关闭 Isaac Sim 视口、Realsense 等占用 GPU 的进程。

## 六、后续可做（切换 Act 模式后）

1. 在 `README.md` 增加一节 **“PhysX 溢出识别与处理”**（判断方法 + 上面的缓冲区参数）；
2. 按 AGENTS.md 要求补充 **“训练完成后验证训练结果”的步骤**（headless 回放检查、TensorBoard 指标、ONNX 导出与 C++ 部署验证）；
3. 如确认当前 12000 环境训练触发了溢出，将 `PhysxCfg` 参数加入 G1/GO2 velocity 任务的仿真配置（最小改动）。

## 结论：会。两者是完全独立的资源

`Patch buffer overflow` 报的是 **PhysX GPU 内部一个固定大小的碰撞管线池（narrowphase patch pool）耗尽**，与整机显存剩余多少无关。

### 机制（用本仓库 v3 的真实日志佐证）

v3（`/tmp/train_go2_v3.log`，Isaac Sim 4.5）中的原始报错：

```
[Error] [omni.physx.plugin] PhysX error: Patch buffer overflow detected,
please increase its size to at least 328668 in the scene desc!
  FILE .../gpunarrowphase/src/PxgNarrowphaseCore.cpp, LINE 1639
```

关键点：

1. **来源是 `gpunarrowphase`**（GPU 窄相碰撞检测核心）：PhysX 在**场景创建时**按 scene desc 里估计的物理对象数预分配一个固定大小的 patch 池（broadphase/narrowphase 管线用），它通常只有几百 MB 量级，是 32GB 显存里很小的一块。
2. **不会因为有空闲显存就自动扩大**：池大小在场景初始化时定死；实际碰撞对象/候选对需求超过估计值就报错。报错文案也印证了这点——"please increase its size to at least **328668** in the **scene desc**"，要的是把场景描述里的**池配置**调大，而不是显存不足。空闲显存只能防"分配失败"，防不了"池耗尽"。
3. **报错但不致命，这才是最危险的**：v3 里该错误从进程启动 52 秒（首个物理步，场景初始化阶段）开始**每个物理步都刷**，累计 98145 行、持续约 2h52m，而训练一直在跑、checkpoint 正常保存。超出的 patch 会被静默跳过 → 部分碰撞对不计算 → 个别 env 的机器人可能穿地/丢接触，**训练数据被污染而 TB 曲线看起来"正常"**——比直接崩溃更隐蔽。

### 与本仓库现状的关系

| run | Isaac Sim | overflow 行数 |
|---|---|---|
| v3（09-11） | 4.5 | **98145**（每步报错，场景初始化即触发 → 是"构建期分配低估"，不是运行期泄漏） |
| v4 / v5 / v6 / v7（当前 22000 envs + 现地形配置） | 4.5 | **0**（当前配置在池容量内） |

所以当前 v7（22000 envs、headless）显存占用远低于 32GB、overflow=0，两个指标都健康；监控脚本里 `overflow_new` 计数就是专门盯这个唯一观察渠道的（它没有 TB 标签）。

### 如果将来再触发（如增大 num_envs、换更复杂地形、场景加物理对象）

1. 先 `grep -c 'Patch buffer overflow' <log>` 确认（文档 §3.1/§3.5 的验收标准是 0）；
2. 降低单场景碰撞对象量：减少 num_envs、简化地形碰撞网格（减少细分/凸块）；
3. 根因方向：让 Isaac Sim 在首步物理模拟前的对象统计覆盖全部物理对象（场景图在第一个 physics step 前构建完整），使自动分配 ≥ 实际需求（v3 里需求 328668 个 patch）。

## 检查结论：**发生过，且影响是实质性的**

## 一、直接证据（控制台日志）

| 运行 | 溢出次数 | 备注 |
|---|---|---|
| **GO2 v3**（`2026-09-11_13-03-52`，num_envs=22000，`gpu_max_rigid_patch_count=327680`） | **98,145 次** | 从 t≈52s 起**每一步都溢出**，持续到运行结束；PhysX 需求 328K~367K，缓冲区 327680 始终不够；触发 “Exceeding maximum number of PhysX errors (1000)”；最后 **core dump 崩溃**（`[Error] [carb]` + “已放弃（核心已转储）”） |
| GO2 v4（`15-56-40`）、v5（`20-58-17`，运行中）、v2、resume、test2、G1（09-07） | **0 次** | 干净 |

错误原文（`/tmp/train_go2_v3.log`）：
```
[Error] [omni.physx.plugin] PhysX error: Patch buffer overflow detected,
please increase its size to at least 328668 in the scene desc!
```

## 二、TensorBoard 曲线反映出的影响（num_envs 均为 22000）

所有曲线**无 NaN、无悬崖式尖峰**——溢出的危害是**物理质量静默劣化**（接触 patch 被丢弃 → 接触力/摩擦系统性被低估），而不是崩溃：

| 运行 | 缓冲区 | 迭代范围 | reward | ep_len | time_out | bad_ori | err_xy | err_yaw |
|---|---|---|---|---|---|---|---|---|
| **v3（溢出）** | 327680 | 17200→18200 | 35→**24** ↓ | ~994 | 0.993 | 0.006 | 0.224 | 0.26 |
| **v4（已修，但接着 18200 训）** | 1310720 | 18200→19900 | 35→**7** ↓↓ | ~983 | 0.968 | 0.029 | **0.327** | **0.38** |
| **v5（已修，从干净点 17200 重跑，进行中）** | 1310720 | 17200→17600+ | →**36.6** ↑ | 1000 | 0.997 | 0.003 | **0.117** | **0.17** |

**关键对照推理**（v3/v4/v5 构成了一组天然对照实验）：
- v3：全程 98K 次溢出 → 奖励从 35 衰减到 24，跟踪误差从 0.12 涨到 0.22；
- v4：溢出已修复，但**接着被污染的检查点 18200 继续训** → 奖励继续衰减到 7，err_xy 升到 0.33，1700 迭代未恢复；
- v5：**与 v4 相同课程（`terrain_levels_vel_fixed`）、相同缓冲区**，唯一区别是起点换回干净检查点 17200 → 奖励 36.6 且仍在爬升，各项误差只有 v3 的一半左右。

⇒ 结论：溢出对策略的污染**真实存在且持续**（策略在错误接触动力学上学到了错误的动作-后果映射）；课程切换不是 v4 衰减的原因（v5 用同样课程表现良好）。

## 三、根因与现状

- **根因**：22000 环境 + GO2 粗糙地形下单步接触 patch 需求 ~328K–367K，而 v3 的缓冲区 327680 仅比默认值大 2 倍，**刚好差一点**（需求最小值 328,668 只比它大 0.3%，但永不够）；
- **已修复**（v4/v5 的 `params/env.yaml` diff）：`gpu_max_rigid_patch_count: 327680 → 1310720`（4 倍，余量 ~3.5 倍）+ 课程 `terrain_levels_vel → terrain_levels_vel_fixed`；
- **当前 v5 运行**（~22:03 已存 model_17600，GPU 98% 在训）：至今 **0 次溢出**，曲线健康（time_out 0.997、bad_ori 0.003）。

## 四、建议

1. **模型选择**：18200–19900 检查点（v4 线）疑似被 v3 溢出污染，**v5 线（17200+）是干净线**；等 v5 训完，建议对两线做回放对比验证（也可直接弃用 v4 线）；
2. **保持** `gpu_max_rigid_patch_count=1310720`；今后若再提高 num_envs 或地形复杂度，按 `需求 ≈ num_envs × ~16 patches` 重新估算；
3. **加入验证流程**：每次训练后 `grep -c 'Patch buffer overflow' <训练日志>` 必须为 0，非 0 则该检查点区间视为受污染；
4. **附带发现（与溢出无关）**：G1 09-07 的运行（`train_test2.log`）无任何溢出，但曲线显示训练失败——`bad_orientation≈0.98`、平均 ep_len≈6 步、`time_out≈0`，即 G1 基本站不起来，属独立问题，建议另行排查 G1 任务配置（动作尺度/初始姿态/地形）。

（本次为 Plan 模式，只做了只读检查；如需我把“PhysX 溢出检查 + 训练结果验证步骤”写入 README 文档，请切换到 Act 模式。）


# RL 的输出是什么？如何给到 PD 控制？

结合本仓库（G1 29dof / GO2 velocity 任务）的实际代码，结论如下：

## 监控要点（后续检查）
指标	预期
Curriculum/terrain_levels	应随能力提升上升（旧 run 是 4.94→1.2 一路降）
Metrics/base_velocity/error_vel_xy	稳态 < 0.15 后速度课程才会解锁
Curriculum/lin_vel_cmd_levels	缓慢 0.1→1.0 爬升（每次 +0.1，每 1000 步判定一次）
Episode_Termination/time_out	应 > 95%（旧 run 97%）
## 一、RL（actor 网络）的输出

__输出是"目标关节位置角"的增量（无量纲动作），不是力矩。__

以 G1 为例（`source/.../tasks/locomotion/robots/g1/29dof/velocity_env_cfg.py` 约 L183-187）：

```python
class ActionsCfg:
    JointPositionAction = mdp.JointPositionActionCfg(
        asset_name="robot", joint_names=[".*"], scale=0.25, use_default_offset=True
    )
```

actor 网络输出 __29 个动作值__（每个关节一个，原始值大致在 [-1, 1]），含义是"相对默认站姿的关节角偏移量"。网络本身不直接输出力矩、速度或位置绝对值——它只学"该往哪偏、偏多少"。

## 二、从网络输出到 PD 目标位置的映射

仿真侧（IsaacLab）和部署侧（`deploy/` C++）用的是同一套 `scale + offset` 变换：

```javascript
target_pos[i] = raw_action[i] * scale[i] + offset[i]     （可选 clip）
```

- __offset__ = 默认关节位置（`use_default_offset=True`，即站立构型，如髋 pitch -0.1、膝 0.3、踝 -0.25 …），对应 `deploy.yaml` 里的 `actions.JointPositionAction.offset / default_joint_pos`；
- __scale = 0.25__：限制单步动作最多让关节偏离默认站姿 ±0.25 rad，保证安全；
- C++ 部署侧由 `deploy/include/isaaclab/envs/mdp/actions/joint_actions.h` 中的 `JointAction::process_actions()` 实现（scale → offset → clip），与 `deploy.yaml` 中 `actions` 段一致。

## 三、如何接入 PD 控制

__关键：RL 输出不进入力矩，而是作为 Unitree 底层关节电机的位置模式目标角 q。__ 真正的 PD 由 Unitree SDK2 电机固件完成（或部署程序显式下发 kp/kd）：

```javascript
tau = kp * (q_target - q) + kd * (0 - q̇)
```

流程（见 `deploy/robots/g1_29dof/src/State_RLBase.cpp` L55-60，GO2 的 `State_RLBase.cpp` 相同）：

```cpp
void State_RLBase::run() {
    auto action = env->action_manager->processed_actions();   // ONNX 推理 → scale+offset
    for (int i(0); i < env->robot->data.joint_ids_map.size(); i++) {
        lowcmd->msg_.motor_cmd()[env->robot->data.joint_ids_map[i]].q() = action[i];
    }
}
```

- `kp / kd` 来自 `deploy.yaml`（如 G1：髋/膝 kp=100~200、kd=2~5；踝 kp=40、kd=10），在 mimic 版 `State_Mimic.cpp` L164-167 中显式写入 `motor_cmd().kp()/kd()`，velocity 部署则依赖电机预设的 PD 参数（应与训练时 `unitree.py` 中的 stiffness/damping 一致）；
- `joint_ids_map` 负责把"策略关节顺序"映射到 Unitree LowCmd 的 motor 槽位。

## 四、完整闭环链路

```javascript
IMU/编码器(500Hz) → 观测构造(base_ang_vel×0.2, projected_gravity, vel_cmd,
                          joint_pos_rel, joint_vel_rel×0.05, last_action; history=5)
→ ONNX actor (policy.onnx, step_dt=0.02s 即 50Hz)
→ raw action[29] → ×scale(0.25) + offset(默认站姿) → target q[29]
→ LowCmd.motor_cmd[i].q = target_q   （kp/kd 由 PD 参数提供）
→ Unitree 电机固件位置模式: tau = kp(q*-q) - kd·q̇ → 关节执行
```

__要点总结：__ RL 学的是"目标姿态/动作增量"，PD 是固定的低层跟踪器（kp/kd 写死在部署配置里）；RL 只需以 ~50 Hz 更新 `q*`，电机内部 PD 以高频闭环跟踪。这也是为什么训练时的 action_scale、默认站姿 offset、kp/kd 必须与真机部署完全一致——三者任何一项不匹配都会造成 sim2real 行为偏差（如动作被静默截断、步态僵硬或抖动）。




# 把 action_scale / offset / kp/kd 设成一致，困难吗？

**结论先说：单纯"参数写一样"是容易的（本仓库已经基本做到了）；真正的困难在于——就算数值完全相同，仿真里执行的 PD 和真机电机固件里的 PD 也不是同一个东西。** 下面分三层讲。

## 一、"抄对数"这一层 —— 不难，但有几个坑

以 G1-29dof 为例，三处参数分别写在不同地方：

| 参数 | 训练侧 | 部署侧 |
|---|---|---|
| action_scale=0.25、offset（默认站姿） | `velocity_env_cfg.py` 的 `ActionsCfg` + `unitree.py` 的 `init_state.joint_pos` | `deploy.yaml` 的 `actions.JointPositionAction.scale/offset` |
| kp/kd | `unitree.py` actuator 配置（如 GO2: stiffness=25, damping=0.5） | `deploy.yaml` 的 `stiffness/damping`，或电机预设值 |

数值抄对不难，但实践中容易出偏差的点：

1. **两处独立维护、无单一事实来源**。训练侧是 Python configclass，部署侧是手写 YAML，改一边忘另一边是最常见的出错方式。本仓库里 `deploy.yaml` 的 offset/scale 和 `unitree.py` 默认站姿目前是一致的（髋 -0.1/+0.1、膝 0.3/0.8、踝 -1.5/-0.25），但没有任何自动化检查保证它们同步。
2. **关节顺序映射**。`joint_ids_map` / `joint_sdk_names` 决定第 i 个动作对应哪个电机槽位，scale/offset/kp 数组是按这个顺序排的——顺序错一位，机器人姿态直接崩，且这种错误不易从日志发现（往往只是"走得怪"）。
3. **offset 的语义对齐**：训练侧 `use_default_offset=True` 用的是 USD init_state；部署侧 offset 是手写在 YAML 里的。如果改了默认站姿只改一处，网络输出的目标角就整体平移了，表现为机器人"半蹲或弓背走路"。
4. **scale 必须严格一致**：scale 是唯一一个"训练时策略已经把它学进权重里"的参数——scale 变了等于换了动作空间，checkpoint 直接作废，这是三者中唯一改了就不可复用的。

## 二、真困难所在 —— "数值相同 ≠ 动力学等价"

即使 scale/offset/kp/kd 逐项对齐，仿真和实机的执行器模型仍有本质差异：

1. **PD 的执行时机与延迟**
   - 训练侧（`UnitreeActuator(DelayedPDActuator)`）是理想 PD：每个物理步（5ms）直接算 `τ = kp(q*-q) + kd(0-q̇)`，无采样-保持、无量化。
   - 真机：策略 50Hz 下发 `q*`，电机固件内部以 1kHz+ 做 PD；且 LowCmd/LowState 各有通信延迟和丢包（网络抖动、重发）。仿真里这条"动作→力矩"链路是零延迟的。
2. **仿真侧额外加了真机没有的东西**：`UnitreeActuatorCfg` 里的 `armature`（一阶惯性项）、`Fs/Fd` 摩擦模型、T-N 曲线力矩限幅（X1/X2/Y1/Y2）——这些是刻意模仿电机特性，但只是近似；而真机还有减速器非线性、齿轮间隙、温升导致的性能漂移。
3. **kp/kd 的"名义一致"陷阱**：仿真里 kp=25/damping=0.5 是一个连续时间理想环节；真机电机的位置模式内部可能叠加了速度环、力矩限幅、软限位，同样的 kp 数值在两侧产生的实际响应带宽并不相同。尤其 G1 踝部（kp=40, kd=10）这种"高增益+低刚度"组合，仿真里稳定不代表实机不抖。
4. **默认站姿 offset 的物理可达性**：USD 的 init_state 是纯几何设定；真机上机器人能否精确停在完全相同的关节角（重力补偿能力、软限位范围），需要上电后实测确认。

## 三、工程建议（改动尽量小的前提下）

1. **以 `deploy.yaml` 为单一事实来源**：训练配置里凡与部署重复的量（scale、offset、kp/kd），在注释中注明来源是 `config/policy/*/params/deploy.yaml`；改参数时先改 YAML 再同步 Python，或写个小脚本从 YAML 生成/校验。
2. **加一致性检查**：CI 或训练启动时比对 `ActionsCfg`（scale、default offset）与对应 `deploy.yaml` 的 `actions` 段，不一致就报错——几十行代码就能把最高频的人为错误挡住。
3. **不要追求 kp/kd"数值相同"就结束**，而是做行为验证：用真机录一段静止站立的 LowState（q、q̇），和仿真里同样的 `q*` 目标跑出的轨迹对比收敛速度/超调；或直接用 Unitree 官方提供的电机特性参数填训练侧的 X1/X2/Y1/Y2/armature，而不是拍脑袋。
4. **scale 一旦定死就不要动**：它被烙进策略权重里，重训成本高；offset/kp/kd 不一致顶多让机器人"姿态不对、动作发软"，而 scale 不一致会直接让动作空间错位。
5. **首次上真机前**：先用 `deploy.yaml` 的 offset 值做静态站立测试（不给速度指令），确认默认站姿可达且不抖；再逐步放开速度指令范围（本仓库 G1 velocity 训练时 ranges 是 ±0.1，limit_ranges 才是 ±0.5~1.0，真机调试正好可以利用这个 curriculum 分级）。

一句话总结：**"抄对数"只是十分钟的活，真正的 sim2real gap 在 PD 执行链路的延迟、非理想性和电机特性上——这部分靠"参数一致"消不掉，只能靠行为级对比（同指令下的 q/q̇ 轨迹对照）来确认。**

# PD 参数运行在哪里？

**核心答案：PD（位置模式）真正执行的位置是 Unitree 每个关节电机内部的固件里，不在训练代码、也不在部署 C++ 程序里。** kp/kd 数值只是"配置"，分布在四个地方，最终生效点只有一个。

## 一、四个存放/使用位置

### 1. 仿真侧：Isaac Sim 的 Python actuator（训练中）
- 文件：`source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py`（如 GO2: `stiffness=25.0, damping=0.5`）、`unitree_actuators.py`
- **运行位置**：Isaac Sim 物理引擎的每个物理步（G1 任务 sim.dt=5ms）里，由 `UnitreeActuator.compute()`（继承 `DelayedPDActuator`）执行：

```python
τ = kp*(q* − q) + kd*(0 − q̇)      # 理想 PD，零延迟、无量化
→ 再叠加 armature/摩擦/T-N 限幅 → 关节力矩
```

这是"仿真的 PD"，只在训练时存在于 GPU 仿真器内。

### 2. 部署侧：`deploy.yaml`（只是数据）
- `config/policy/*/params/deploy.yaml` 里的 `stiffness/damping` 数组——它**本身不执行任何计算**，只是被 C++ 程序加载后写进 LowCmd 的候选值。

### 3. 部署侧：C++ 进程（只是"搬运工"）
- `deploy/robots/*/src/State_RLBase.cpp` / `State_Mimic.cpp`：以策略频率（G1 step_dt=0.02s，即 50Hz；GO2 类似）把 `motor_cmd[i].q()` 填好发出。
- **只有 mimic 分支显式写 kp/kd**（`State_Mimic.cpp:164-167`）：

```cpp
lowcmd->msg_.motor_cmd()[i].kp() = env->robot->data.joint_stiffness[i];
lowcmd->msg_.motor_cmd()[i].kd() = env->robot->data.joint_damping[i];
```

- velocity 分支（`State_RLBase.cpp:26-31`）只写 `q()`，**kp/kd 不在这份代码里下发**——依赖电机当前已生效的参数。

### 4. 真正执行 PD 的地方：电机固件 ✅
- Unitree M107/GO2HV/N5020 等关节电机的 MCU 收到 LowCmd（Unitree 总线，~500Hz）后，在**电机内部以 1kHz+ 的高频控制环**执行位置模式：

```
τ = kp*(q_cmd − q_meas) + kd*(0 − q̇_meas)   ← 运行在电机 MCU 里
```

然后按 T-N 曲线限幅、输出电流。这是唯一"真正闭环跟踪目标角"的地方。

## 二、完整信号链（谁在哪里跑）

```
[PC, C++进程, 50Hz]        [网线/CAN]        [电机MCU, ≥1kHz]
ONNX推理 → scale+offset     LowCmd            ┌─────────────┐
→ motor_cmd[i].q = q*  ───► (motor_cmd:      │ PD位置环执行 │
   (mimic分支还带kp/kd)    q,kp,kd,tau) ───► │ τ=kp(q*-q)   │
                                             │ +kd(0-q̇),限幅│
LowState ◄──────────────────── 回传q,q̇,τ     └─────────────┘
```

## 三、由此产生的两个实用要点

1. **velocity 部署不写 kp/kd，意味着真机 PD 参数取决于电机当前状态**：上电默认值、或之前某次 `motor_cmd.kp()/kd()` 下发的残留。所以首次真机调试前应该像 mimic 分支那样显式下发一次与训练一致的 kp/kd（改动很小：在 velocity 的 `State_RLBase::run()` 里加两行，或直接复用 `data.joint_stiffness/damping`）。
2. **仿真侧的 PD 是"替身"**：训练时它替代的是电机固件那个环。两者数值相同但执行环境不同（5ms 理想离散 vs 1kHz+ 硬件），这就是上一轮说的 sim2real gap 的物理根源——所以验证方式不是比对代码，而是同指令下对比 q/q̇ 轨迹收敛行为。

# 这两行代表什么？——"仿真电机模型"的完整数学定义

这段是我对 `UnitreeActuator.compute()`（`source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree_actuators.py:56-88`）的简写。它代表**在 Isaac Sim 里，每个物理步（G1 是 5ms），仿真器如何把"RL 给的目标关节角 q*"换算成真正施加到刚体上的力矩 τ**。逐符号解释：

## 第一行：PD 位置环

```
τ = kp*(q* − q) + kd*(0 − q̇)
```

| 符号 | 含义 |
|---|---|
| `q` | **当前**关节角（仿真器积分出来的状态量） |
| `q̇` | **当前**关节角速度 |
| `q*` | RL 动作经 scale+offset 后的**目标**关节角（上一轮说的 `processed_actions()`） |
| `0` | 目标角速度——注意是 0！位置模式只跟踪角度，不要求速度 |
| `kp` | 位置增益：偏差越大，回正力矩越强（决定响应快慢/刚度感） |
| `kd` | 速度阻尼项：抑制振荡、吸收冲击（没有它系统会来回抖） |

物理意义：**弹簧 + 阻尼器**。`kp*(q*−q)` 像一根把关节拉向目标角的"弹簧"，`kd*(0−q̇)` 像一个粘在关节上的"油缸"。两者合成力矩 τ 后，由刚体动力学 `J·q̈ = τ + 重力项 + 接触力...` 决定下一时刻的 q、q̇——即 PD 不直接控制角度，而是通过**出力矩**间接让角度收敛到 q*。

"零延迟、无量化"的意思：仿真里这条链路在物理步内瞬时算完（不像真机有 50Hz 指令更新 + 通信延迟），数值是 float32/64 连续量（不像电机固件有电流环离散化和 ADC 量化）。

## 第二行：叠加非理想项 → 最终力矩

```
τ_final = clip_TN( τ_PD − friction )      ← "再叠加 armature/摩擦/T-N 限幅"的展开
```

对应代码里的三个环节，各自模仿真机电机的哪个特性：

1. **摩擦**（`unitree_actuators.py:65-67`）：
   ```python
   τ_final -= Fs·tanh(q̇/Va) + Fd·q̇
   ```
   模仿齿轮/轴承的静摩擦（低速时 tanh≈饱和，需要克服"起步阻力"）和动摩擦（与速度成正比）。没有它仿真机器人会"太顺滑"。

2. **T-N 曲线限幅**（`_clip_effort`, L75-83）：
   ```python
   τ_final = clip(τ, −max_effort, +max_effort)
   max_effort = Y1/Y2 (|q̇|<X1 时) → 线性下降到 X2 处为 0
   ```
   就是电机手册里的"扭矩-转速特性曲线"：低速段能出峰值扭矩（Y1=同向、Y2=反向），转速超过 X1 后力矩能力随速度线性衰减，到 X2（空载最高速）时出力矩为零。防止仿真机器人做出真机电机做不到的"高速+大力"动作。

3. **armature（一阶惯性）**：`DelayedPDActuator` 里 `kp/q̇` 项会乘以 `1/(1+kd/armature)` 类的等效形式，模仿电机转子+减速器惯量造成的 PD 响应延迟——真机的 kp/kd 不是"瞬时生效"的。

## 一句话总结

这两行代表**仿真里"假想电机固件"的执行模型**：

```
q*(RL目标) ──[理想PD: 弹簧+阻尼]──► τ_ideal
τ_ideal ──[减摩擦项][按T-N曲线限幅][armature惯性修正]──► τ_final → 施加到关节刚体
```

它的存在目的只有一个：**让训练时的"动作→实际运动"链条尽可能像真机电机**，这样 RL 学到的策略（什么时候给多大的 q*）在真机上才有效。这也是为什么 `unitree_actuators.py` 里每个电机型号（M107-24、N5020-16…）都填了厂商手册的 X1/X2/Y1/Y2/armature——这些数就是"仿真替身"和真机之间的相似度来源。
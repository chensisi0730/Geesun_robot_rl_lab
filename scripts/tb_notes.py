#!/usr/bin/env python
"""为 TensorBoard 训练曲线生成中文备注（在 TensorBoard 的 TEXT 面板中显示）。

TensorBoard 的曲线卡片本身没有"备注/描述"字段，可显示富文本的通道是 TEXT 插件：
本脚本把每条曲线 tag 的中文名、含义和判读方式写成 text 事件，输出到一个独立 run
（默认 ``logs/rsl_rl/00_曲线中文说明``，与训练 run 同级，**不会**被 monitor_tb_check
的 ``logs/rsl_rl/unitree_go2_velocity*`` glob 扫描到，对监控零影响）。

可见结构是**按曲线前缀分的 8 组**（见 ``GROUPS``），每组 1 个 tag，组内逐条列出细粒度 tag：
细粒度写法有 68 个 tag，TEXT 页左侧列表太长，容易被当成"页面是空的"。细粒度对照表没有丢，
``--list`` 仍打印全量，并会指出「未挂组」的 tag。

用法::

    python scripts/tb_notes.py            # 重写说明 run（幂等，先清空旧内容）
    python scripts/tb_notes.py --list     # 只在终端打印全量细粒度对照表 + 未挂组检查

然后打开 TensorBoard，切到顶部 **TEXT** 页，左侧勾选 run ``00_曲线中文说明``，
**再点开左侧 tag 列表里的任意一个分组条目**，右侧正文才显示（TEXT 页不像 SCALARS 页
勾选即出图，这一步最容易被漏掉）。logdir 必须是 ``logs/rsl_rl`` 本身，不能是
``logs/rsl_rl/<experiment_name>``——用子目录时左侧根本列不出说明 run。

也可以把这里维护的 ``NOTES`` 当作曲线释义的单一事实来源（``--list`` 输出可直接复制）。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "logs" / "rsl_rl" / "00_曲线中文说明"

# ---------------------------------------------------------------------------
# 中文备注：tag -> markdown（中文名 / 含义 / 判读）。未列出的 tag 会写"暂无说明"占位。
# ---------------------------------------------------------------------------
NOTES: dict[str, str] = {
    # -------------------------------------------------------------- 课程
    "Curriculum/command_ranges/x_max": "**前进速度指令上限**\n课程允许的最大前进速度（m/s），目标上限 ±1.0。\n判读：随课程单调加宽；长期不动=课程卡住。",
    "Curriculum/command_ranges/x_min": "**前进速度指令下限**\n课程允许的最大后退速度（m/s）。",
    "Curriculum/command_ranges/y_max": "**侧向速度指令上限**\n最大侧移速度（m/s）。",
    "Curriculum/command_ranges/y_min": "**侧向速度指令下限**\n最大反向侧移速度（m/s）。",
    "Curriculum/command_ranges/z_max": "**偏航角速度指令上限**\n最大转向角速度（rad/s），目标上限 ±1.0。",
    "Curriculum/command_ranges/z_min": "**偏航角速度指令下限**\n最大反向转向角速度（rad/s）。",
    "Curriculum/terrain_levels": "**地形难度等级**（课程核心指标）\n机器人当前被分配的地形难度，成功率达标自动升级。\n判读：台阶式上升为健康；短暂回落后会自行恢复（监控已容忍，不会中断训练）；持续横盘=卡关。",
    "Curriculum/lin_vel_cmd_levels/mean_err_xy": "**线速度指令课程：平均 XY 跟踪误差**\n各难度档位下的平均平面速度跟踪误差（m/s，越小越好）。",
    "Curriculum/lin_vel_cmd_levels/mean_err_yaw": "**线速度指令课程：平均偏航跟踪误差**\n各档位下的平均转向跟踪误差（rad/s，越小越好）。",
    "Curriculum/lin_vel_cmd_levels/streak": "**连续达标计数**\n连续满足解锁条件的次数，达到阈值后加宽指令范围。",
    "Curriculum/lin_vel_cmd_levels/success_rate": "**线速度达标率**\n跟踪误差进入容差的回合占比；高于 min_success_rate（默认 0.9）才解锁下一档。",
    "Curriculum/lin_vel_cmd_levels/time_out_rate": "**满时长率（指令课程）**\n跑满回合时长未摔倒的占比。",
    "Curriculum/lin_vel_cmd_levels/x_max": "**当前前进指令上限**\n实时生效的最大前进速度（m/s）。",
    "Curriculum/lin_vel_cmd_levels/x_frozen": "**前进指令冻结标记**（D30W 楼梯战役新增）\n=1 表示 x 指令范围被冻结（不升不降）：地形等级每 +1.0 级就会冻结 2 个评估窗口，"
    "让策略先在新地形上站稳再继续加宽。\n判读：频繁在 0/1 之间跳变 = 地形等级在反复升降（课程震荡），应先稳住 terrain_levels。",
    "Curriculum/lin_vel_cmd_levels/y_max": "**当前侧向指令上限**\n实时生效的最大侧移速度（m/s）。",
    "Curriculum/lin_vel_cmd_levels/yaw_streak": "**偏航连续达标计数**\n转向课程的连续达标次数。",
    "Curriculum/lin_vel_cmd_levels/yaw_success_rate": "**偏航达标率**\n转向跟踪达标回合占比，高于阈值才加宽偏航范围。",
    "Curriculum/lin_vel_cmd_levels/z_max": "**当前偏航指令上限**\n实时生效的最大转向角速度（rad/s）。",
    # ------------------------------------------------ 分地形统计
    "Curriculum/terrain_performance_by_type/flat_level": "**平地：难度等级**\n平地地形上的课程等级。",
    "Curriculum/terrain_performance_by_type/flat_error_xy": "**平地：XY 跟踪误差**（m/s）",
    "Curriculum/terrain_performance_by_type/flat_error_yaw": "**平地：偏航跟踪误差**（rad/s）",
    "Curriculum/terrain_performance_by_type/flat_success_rate": "**平地：成功率**\n判读：平地应最高（>0.95），明显偏低说明基础步态有问题。",
    "Curriculum/terrain_performance_by_type/boxes_level": "**箱体地形：难度等级**（仅 GO2 地形；D30W/GeesunDog 任务无 boxes 地形，不会出现该曲线）",
    "Curriculum/terrain_performance_by_type/boxes_error_xy": "**箱体地形：XY 跟踪误差**（m/s，仅 GO2 地形）",
    "Curriculum/terrain_performance_by_type/boxes_error_yaw": "**箱体地形：偏航跟踪误差**（rad/s，仅 GO2 地形）",
    "Curriculum/terrain_performance_by_type/boxes_success_rate": "**箱体地形：成功率**（仅 GO2 地形）\n判读：通常低于平地，随训练爬升。",
    "Curriculum/terrain_performance_by_type/pyramid_stairs_level": "**金字塔台阶：难度等级**",
    "Curriculum/terrain_performance_by_type/pyramid_stairs_error_xy": "**金字塔台阶：XY 跟踪误差**（m/s）",
    "Curriculum/terrain_performance_by_type/pyramid_stairs_error_yaw": "**金字塔台阶：偏航跟踪误差**（rad/s）",
    "Curriculum/terrain_performance_by_type/pyramid_stairs_success_rate": "**金字塔台阶：成功率**",
    "Curriculum/terrain_performance_by_type/random_rough_level": "**随机粗糙地形：难度等级**",
    "Curriculum/terrain_performance_by_type/random_rough_error_xy": "**随机粗糙地形：XY 跟踪误差**（m/s）",
    "Curriculum/terrain_performance_by_type/random_rough_error_yaw": "**随机粗糙地形：偏航跟踪误差**（rad/s）",
    "Curriculum/terrain_performance_by_type/random_rough_success_rate": "**随机粗糙地形：成功率**",
    # ---------------------------------------------------- 奖励分量
    "Episode_Reward/track_lin_vel_xy": "**奖励：线速度跟踪**（主要正向项）\n跟踪目标速度的指数奖励。\n判读：越大越好，约占总奖励主体；下跌=跟踪能力退化。",
    "Episode_Reward/track_ang_vel_z": "**奖励：偏航角速度跟踪**（正向项）\n跟踪目标转向速率的指数奖励，越大越好。",
    "Episode_Reward/flat_orientation_l2": "**奖励：机身水平姿态惩罚**\nroll/pitch 偏离水平的惩罚（负值）。\n判读：绝对值变大=机身越歪。权重按机器人而异：GO2 -3.5，GeesunDog D30W -2.5。",
    "Episode_Reward/action_rate": "**奖励：动作平滑惩罚**\n相邻时刻动作变化的惩罚（负值），鼓励平滑控制。",
    "Episode_Reward/air_time_variance": "**奖励：腾空时间方差惩罚**\n四条腿腾空时间不均匀的惩罚，鼓励节奏稳定的步态。",
    "Episode_Reward/base_angular_velocity": "**奖励：本体角速度偏离惩罚**\n身体晃动（自旋/俯仰角速度）的惩罚。",
    "Episode_Reward/base_linear_velocity": "**奖励：本体线速度偏离惩罚**\n与目标速度无关的多余移动的惩罚。",
    "Episode_Reward/dof_pos_limits": "**奖励：关节限位惩罚**\n关节逼近机械限位的惩罚。",
    "Episode_Reward/energy": "**奖励：能耗惩罚**\n力矩×角速度的能耗惩罚，鼓励省力。",
    "Episode_Reward/feet_air_time": "**奖励：抬脚时长奖励**\n鼓励迈腿腾空（正值，过大会导致踢腿步态）。",
    "Episode_Reward/feet_slide": "**奖励：脚滑惩罚**\n触地期脚底打滑的惩罚。",
    "Episode_Reward/joint_acc": "**奖励：关节加速度惩罚**\n关节急动的惩罚。",
    "Episode_Reward/joint_pos": "**奖励：关节位置惩罚**\n偏离默认站姿的惩罚。",
    "Episode_Reward/joint_torques": "**奖励：关节力矩惩罚**\n大力矩输出的惩罚。",
    "Episode_Reward/joint_vel": "**奖励：关节速度惩罚**\n关节高速运动的惩罚。",
    "Episode_Reward/undesired_contacts": "**奖励：不期望接触惩罚**\n脚以外部位（膝/机身）触地的惩罚。",
    # ---------------------------------------------------- 回合终止
    "Episode_Termination/time_out": "**终止：跑满时长占比**\n回合正常到期结束（没摔倒）的占比。\n判读：**越高越好**，>0.85 健康；持续 <0.85 说明摔倒/歪倒偏多。",
    "Episode_Termination/bad_orientation": "**终止：姿态不正占比**\nroll/pitch 超限（0.8 rad）被提前终止的回合占比。\n判读：目标 <2%；GO2 监控阈值 0.02。D30W 轮腿式在楼梯战役实测 **0.108**（iter 15321）——"
"这是该形态在pyramid_stairs 上的主要失败形式，且因为 `base_contact=0`（不摔）所以失败几乎全部表现为"
"「卡在踏步上不动」，须与 `pyramid_stairs_success_rate` 一起看。",
    "Episode_Termination/base_contact": "**终止：机身触地占比**\n趴倒/摔翻导致机身着地的回合占比（越低越好）。",
    # -------------------------------------------------------- 损失
    "Loss/value_function": "**损失：价值网络（critic）**\n预测未来回报的回归误差。\n判读：正常 0.01~0.05；**>100 = 发散**（会触发自动降学习率+重训）；**回落≈0 但 reward/回合长度崩溃 = 塌缩假象**，两者都要看。",
    "Loss/surrogate": "**损失：PPO 代理损失**\n策略更新的目标函数变化量，小幅波动正常。",
    "Loss/entropy": "**损失：策略熵**\n策略随机性（探索度）。\n判读：持续走低→探索塌缩风险；autotune 会在平台期加大 entropy_coef。",
    "Loss/learning_rate": "**学习率（KL 自适应）**\n按实测 KL 散度自动增减。\n判读：**长期钉在 1e-5**（监控 lr_pin 指标）说明策略更新过猛被反复抑制；06:03 那类窗口会随恢复解除。",
    # ---------------------------------------------------- 跟踪误差
    "Metrics/base_velocity/error_vel_xy": "**跟踪误差：平面线速度**\n实际 vs 目标 XY 速度误差（m/s，越小越好）。\n判读基准**按机器人而异**：GO2 0.25~0.30；GeesunDog D30W 约 0.20。fresh 重启初期偏高会自愈。",
    "Metrics/base_velocity/error_vel_yaw": "**跟踪误差：偏航角速度**\n实际 vs 目标转向速率误差（rad/s，越小越好）。",
    # -------------------------------------------------------- 性能
    "Perf/total_fps": "**性能：总吞吐**\n环境+训练总帧率（FPS），与 `num_envs`（环境数）成正比，**不可跨机器人横比**：GO2 约 5.5 万；"
    "GeesunDog D30W 楼梯战役（4096 envs）实测约 13.5 万。骤降才是异常，需查 GPU/进程。",
    "Perf/collection time": "**性能：采样耗时**\n每次迭代 rollout 的秒数。",
    "Perf/learning_time": "**性能：学习耗时**\n每次迭代 PPO 更新的秒数。",
    # -------------------------------------------------- 探索与总体
    "Policy/mean_noise_std": "**探索：动作噪声标准差**\n策略高斯噪声强度。\n判读：过低（<0.2）= 探索塌缩；持续偏高 = 策略不收敛。",
    "Train/mean_reward": "**总回报**（最核心健康指标）\n所有奖励分量之和的回合均值。\n判读：稳步上行为健康；腰斩以上跌幅监控会告警；**跌到 0 以下且伴随回合骤短 = 策略崩溃**。",
    "Train/mean_reward/time": "**总回报（横轴=墙钟时间）**\n同上，观察真实时间效率用。",
    "Train/mean_episode_length": "**平均回合长度**（步）\n判读：先对号入座再判好坏——**跑满值 = `episode_length_s` × 50**，GO2 约 940 步，"
    "GeesunDog D30W 为 **1000 步**（episode_length_s=20）。骤降到几十步=策略趴地/摔倒，即使 value_loss 归 0 也算假恢复。",
    "Train/mean_episode_length/time": "**平均回合长度（横轴=墙钟时间）**",
}

# ---------------------------------------------------------------------------
# TEXT 页的可见结构：按曲线前缀分 8 组，每组 1 个 tag，组内逐条列出细粒度 tag。
#
# 为什么分组（2026-10-15）：细粒度写法有 68 个 tag，TEXT 页左侧 tag 列表太长，
# 容易让人以为"页面是空的"，也找不到要看的那条。分组后左侧只有 8 个条目，
# 一次点开就能看到全部中文说明。细粒度对照表并没有丢，`--list` 仍打印全量。
#
# 新增曲线时的正确做法：先在 NOTES 里补一条，再把 tag 名挂到对应分组里，
# 否则它不会出现在 TEXT 页（`--list` 会显示 "未挂组"）。
# ---------------------------------------------------------------------------
GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "01_课程 Curriculum",
        "课程学习（curriculum）：地形难度与速度指令范围随成功率自动晋升。**这是最该盯的一组。**",
        [
            "Curriculum/terrain_levels",
            "Curriculum/lin_vel_cmd_levels/x_max",
            "Curriculum/lin_vel_cmd_levels/y_max",
            "Curriculum/lin_vel_cmd_levels/z_max",
            "Curriculum/lin_vel_cmd_levels/x_frozen",
            "Curriculum/lin_vel_cmd_levels/success_rate",
            "Curriculum/lin_vel_cmd_levels/yaw_success_rate",
            "Curriculum/lin_vel_cmd_levels/mean_err_xy",
            "Curriculum/lin_vel_cmd_levels/mean_err_yaw",
            "Curriculum/lin_vel_cmd_levels/streak",
            "Curriculum/lin_vel_cmd_levels/yaw_streak",
            "Curriculum/lin_vel_cmd_levels/time_out_rate",
            "Curriculum/command_ranges/x_min",
            "Curriculum/command_ranges/x_max",
            "Curriculum/command_ranges/y_min",
            "Curriculum/command_ranges/y_max",
            "Curriculum/command_ranges/z_min",
            "Curriculum/command_ranges/z_max",
            "Curriculum/terrain_performance_by_type/flat_level",
            "Curriculum/terrain_performance_by_type/flat_error_xy",
            "Curriculum/terrain_performance_by_type/flat_error_yaw",
            "Curriculum/terrain_performance_by_type/flat_success_rate",
            "Curriculum/terrain_performance_by_type/random_rough_level",
            "Curriculum/terrain_performance_by_type/random_rough_error_xy",
            "Curriculum/terrain_performance_by_type/random_rough_error_yaw",
            "Curriculum/terrain_performance_by_type/random_rough_success_rate",
            "Curriculum/terrain_performance_by_type/pyramid_stairs_level",
            "Curriculum/terrain_performance_by_type/pyramid_stairs_error_xy",
            "Curriculum/terrain_performance_by_type/pyramid_stairs_error_yaw",
            "Curriculum/terrain_performance_by_type/pyramid_stairs_success_rate",
            "Curriculum/terrain_performance_by_type/boxes_level",
            "Curriculum/terrain_performance_by_type/boxes_error_xy",
            "Curriculum/terrain_performance_by_type/boxes_error_yaw",
            "Curriculum/terrain_performance_by_type/boxes_success_rate",
        ],
    ),
    (
        "02_奖励 Episode_Reward",
        "各奖励分量的回合累计值（负值 = 惩罚项）。看的是**相对变化**：某项突然恶化 = 对应能力退化。",
        [
            "Episode_Reward/track_lin_vel_xy",
            "Episode_Reward/track_ang_vel_z",
            "Episode_Reward/flat_orientation_l2",
            "Episode_Reward/base_linear_velocity",
            "Episode_Reward/base_angular_velocity",
            "Episode_Reward/joint_pos",
            "Episode_Reward/joint_vel",
            "Episode_Reward/joint_acc",
            "Episode_Reward/joint_torques",
            "Episode_Reward/dof_pos_limits",
            "Episode_Reward/action_rate",
            "Episode_Reward/energy",
            "Episode_Reward/feet_air_time",
            "Episode_Reward/feet_slide",
            "Episode_Reward/air_time_variance",
            "Episode_Reward/undesired_contacts",
        ],
    ),
    (
        "03_终止 Episode_Termination",
        "回合提前终止原因占比。**time_out（跑满时长）越高越好，其余越低越好。**"
        "轮腿式 D30W 的失败几乎全部落在 bad_orientation 上（见 bad_orientation 条目）。",
        [
            "Episode_Termination/time_out",
            "Episode_Termination/bad_orientation",
            "Episode_Termination/base_contact",
        ],
    ),
    (
        "04_损失与学习率 Loss",
        "PPO 损失、策略熵（探索度）与 KL 自适应学习率。**发散和塌缩是两种完全不同的病，别混。**",
        [
            "Loss/value_function",
            "Loss/surrogate",
            "Loss/entropy",
            "Loss/learning_rate",
        ],
    ),
    (
        "05_跟踪误差 Metrics",
        "速度跟踪误差，越小越好。这是判断「策略是否真的在跟上命令」的量化口径。",
        [
            "Metrics/base_velocity/error_vel_xy",
            "Metrics/base_velocity/error_vel_yaw",
        ],
    ),
    (
        "06_性能 Perf",
        "训练吞吐性能。**fps 与 `num_envs`（环境数）成正比，不可跨机器人横比。**",
        [
            "Perf/total_fps",
            "Perf/collection time",
            "Perf/learning_time",
        ],
    ),
    (
        "07_探索 Policy",
        "探索噪声强度。过低 = 探索塌缩（策略锁死在一个局部最优，撞到台阶就不动了）。",
        ["Policy/mean_noise_std"],
    ),
    (
        "08_总体 Train",
        "总回报与平均回合长度——**最核心的两个健康指标**。回合长度要先对号入座再判好坏："
        "跑满值 = `episode_length_s` × 50。",
        [
            "Train/mean_reward",
            "Train/mean_reward/time",
            "Train/mean_episode_length",
            "Train/mean_episode_length/time",
        ],
    ),
]

OVERVIEW = (
    "# 曲线中文说明（使用指南）\n\n"
    "这里是 TensorBoard 全部训练曲线的中文备注，**按曲线前缀分成 8 组**，"
    "覆盖 GO2 与 GeesunDog D30W 两套基准。\n\n"
    "**⚠ 怎么才能看到内容（三步，缺一步就是空白）**\n\n"
    "1. 顶部导航切到 **TEXT** 页\n"
    "2. 左侧 run 列表勾选 **`00_曲线中文说明`**\n"
    "3. **左侧还会出现第二个 tag 列表，必须点开其中任意一个条目，右侧正文才显示**\n"
    "\n"
    "第 3 步最容易被忽略：TEXT 页不像 SCALARS 页那样勾选即出图，"
    "68 个（或现在 8 个）条目摆在那里不点开，右侧就是空的。\n"
    "另外 TensorBoard 的 `--reload` 只重载**数据**，页面仍需浏览器**手动刷新**。\n\n"
    "**8 个分组一览**\n\n"
    "1. `01_课程 Curriculum` —— 地形难度与速度指令范围随成功率自动晋升（最该盯）\n"
    "2. `02_奖励 Episode_Reward` —— 各奖励分量的回合累计（负值 = 惩罚项）\n"
    "3. `03_终止 Episode_Termination` —— 回合提前终止原因占比\n"
    "4. `04_损失与学习率 Loss` —— PPO 损失、策略熵与自适应学习率\n"
    "5. `05_跟踪误差 Metrics` —— 速度跟踪误差（越小越好）\n"
    "6. `06_性能 Perf` —— 训练吞吐性能\n"
    "7. `07_探索 Policy` —— 探索噪声强度\n"
    "8. `08_总体 Train` —— 总回报与平均回合长度（最核心的两个健康指标）\n\n"
    "**⚠ 左侧 run 列表里根本没有本页？检查 logdir**\n\n"
    "本页 run 位于 `logs/rsl_rl/00_曲线中文说明/`，与各训练 run **同级**，"
    "所以 TensorBoard 必须以 `logs/rsl_rl` 为 logdir 启动：\n\n"
    "```bash\n"
    "tensorboard --logdir logs/rsl_rl          # ✅ 同时看到曲线和本页 TEXT\n"
    "tensorboard --logdir logs/rsl_rl/<exp>    # ❌ 只能看到该实验的曲线，本页列不出来\n"
    "```\n\n"
    "**机器人差异对照**（同一 tag 在不同机器人上的正常水位不同，勿跨机器人横比）\n\n"
    "- `Train/mean_episode_length` 跑满值：GO2 ≈940 步；**D30W 1000 步**（`episode_length_s=20`）\n"
    "- `Metrics/base_velocity/error_vel_xy` 水平：GO2 0.25~0.30；**D30W ≈0.20**\n"
    "- `Perf/total_fps` 量级：GO2 ≈5.5 万；**D30W ≈13.5 万**（4096 envs）\n"
    "- `Episode_Reward/flat_orientation_l2` 权重：GO2 -3.5；**D30W -2.5**\n"
    "- 地形种类：GO2 有 `boxes`（箱体）；**D30W 无 boxes**，只有 flat / random_rough / pyramid_stairs\n\n"
    "**四个最常用的判读口诀**\n\n"
    "1. `Train/mean_reward` 上升 + `Train/mean_episode_length` 逼近该机器人的跑满值 = 训练健康\n"
    "2. `Loss/value_function` 落在 0.01~0.05 = critic 正常；>100 是发散；"
    "归 0 但回报/回合长度崩溃是塌缩假象\n"
    "3. `Curriculum/terrain_levels` 短暂回落会自愈（监控已容忍）；持续横盘才是卡关\n"
    "4. 分地形 `*_success_rate` 必须**逐地形**看：求平均会把短板抹平。"
    "D30W 楼梯战役实测 flat/random_rough = 1.00 而 pyramid_stairs = 0.735，平均值毫无意义\n\n"
    "维护：`scripts/tb_notes.py` 的 `NOTES` 是备注唯一来源、`GROUPS` 是可见结构。"
    "新增曲线要改两处（补 `NOTES` + 挂到 `GROUPS`），改完重跑本脚本即可刷新；"
    "`--list` 打印全量细粒度对照表，并列出「未挂组」的 tag 防止漏。\n"
)


def _render_group(desc: str, tags: list[str]) -> str:
    """Render one group as a single markdown blob for the TEXT dashboard.

    ``NOTES`` entries are written as ``**中文名**（单位）\\n含义\\n判读：...``; here the first
    line becomes the inline title and the rest becomes one indented paragraph. Markdown table
    syntax is deliberately avoided: TensorBoard renders text notes with Python-Markdown,
    which has no table extension, so pipes would show up verbatim.
    """
    lines = [f"# {desc}", ""]
    for tag in tags:
        note = NOTES.get(tag)
        if note is None:
            lines.append(f"- **`{tag}`** —— ⚠ 暂无说明（NOTES 里缺这一条）")
            continue
        parts = [p.strip() for p in note.split("\n") if p.strip()]
        title = parts[0].replace("**", "")
        lines.append(f"- **`{tag}`** —— {title}")
        for extra in parts[1:]:
            lines.append(f"  - {extra}")
    return "\n".join(lines)


def grouped_tags() -> set[str]:
    """Every fine-grained tag referenced by :data:`GROUPS`."""
    return {tag for _title, _desc, tags in GROUPS for tag in tags}


def build(out: Path) -> int:
    from torch.utils.tensorboard import SummaryWriter

    if out.exists():  # 幂等重写，避免重复运行后 TEXT 页出现重复条目
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    w = SummaryWriter(log_dir=str(out))
    w.add_text("00_使用说明（先看这条）", OVERVIEW, 0)
    for title, desc, tags in GROUPS:
        w.add_text(title, _render_group(desc, tags), 0)
    w.flush()
    w.close()
    return len(GROUPS) + 1


def main() -> int:
    ap = argparse.ArgumentParser(description="在 TensorBoard TEXT 面板显示曲线中文备注")
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT), help="说明 run 的输出目录")
    ap.add_argument("--list", action="store_true", help="仅打印对照表，不写事件文件")
    args = ap.parse_args()

    if args.list:
        for title, _desc, tags in GROUPS:
            print(f"\n### {title}  ({len(tags)} 条)")
            for tag in tags:
                note = NOTES.get(tag)
                head = note.splitlines()[0].replace("**", "") if note else "⚠ 暂无说明"
                print(f"  {tag}\n      {head}")
        orphans = sorted(set(NOTES) - grouped_tags())
        print(f"\n合计 {len(NOTES)} 条备注，分 {len(GROUPS)} 组。")
        print(f"未挂组的 tag（不会出现在 TEXT 页）: {orphans or '无'}")
        return 0

    n = build(Path(args.out))
    print(f"written {n} text notes ({len(NOTES)} 条细粒度备注 -> {len(GROUPS)} 组）-> {args.out}")
    print("打开 TensorBoard（--logdir logs/rsl_rl），切到 TEXT 页，勾选 run '00_曲线中文说明'，")
    print("再在左侧 tag 列表点开任意一个分组条目即可看到正文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""为 TensorBoard 训练曲线生成中文备注（在 TensorBoard 的 TEXT 面板中显示）。

TensorBoard 的曲线卡片本身没有"备注/描述"字段，可显示富文本的通道是 TEXT 插件：
本脚本把每条曲线 tag 的中文名、含义和判读方式写成 text 事件，输出到一个独立 run
（默认 ``logs/rsl_rl/00_曲线中文说明``，与训练 run 同级，**不会**被 monitor_tb_check
的 ``logs/rsl_rl/unitree_go2_velocity`` 扫描到，对监控零影响）。

用法::

    python scripts/tb_notes.py            # 重写说明 run（幂等，先清空旧内容）
    python scripts/tb_notes.py --list     # 只在终端打印对照表

然后打开 TensorBoard（任意 --logdir logs/rsl_rl/ 的实例），切到顶部 **TEXT** 页，
左侧勾选 run ``00_曲线中文说明``，即可看到每条曲线的中文备注。

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
    "Curriculum/lin_vel_cmd_levels/y_max": "**当前侧向指令上限**\n实时生效的最大侧移速度（m/s）。",
    "Curriculum/lin_vel_cmd_levels/yaw_streak": "**偏航连续达标计数**\n转向课程的连续达标次数。",
    "Curriculum/lin_vel_cmd_levels/yaw_success_rate": "**偏航达标率**\n转向跟踪达标回合占比，高于阈值才加宽偏航范围。",
    "Curriculum/lin_vel_cmd_levels/z_max": "**当前偏航指令上限**\n实时生效的最大转向角速度（rad/s）。",
    # ------------------------------------------------ 分地形统计
    "Curriculum/terrain_performance_by_type/flat_level": "**平地：难度等级**\n平地地形上的课程等级。",
    "Curriculum/terrain_performance_by_type/flat_error_xy": "**平地：XY 跟踪误差**（m/s）",
    "Curriculum/terrain_performance_by_type/flat_error_yaw": "**平地：偏航跟踪误差**（rad/s）",
    "Curriculum/terrain_performance_by_type/flat_success_rate": "**平地：成功率**\n判读：平地应最高（>0.95），明显偏低说明基础步态有问题。",
    "Curriculum/terrain_performance_by_type/boxes_level": "**箱体地形：难度等级**\n跨越箱体障碍的难度。",
    "Curriculum/terrain_performance_by_type/boxes_error_xy": "**箱体地形：XY 跟踪误差**（m/s）",
    "Curriculum/terrain_performance_by_type/boxes_error_yaw": "**箱体地形：偏航跟踪误差**（rad/s）",
    "Curriculum/terrain_performance_by_type/boxes_success_rate": "**箱体地形：成功率**\n判读：通常低于平地，随训练爬升。",
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
    "Episode_Reward/flat_orientation_l2": "**奖励：机身水平姿态惩罚**\nroll/pitch 偏离水平的惩罚（负值）。\n判读：绝对值变大=机身越歪；autotune 用它压制摔倒率（当前权重 -3.5）。",
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
    "Episode_Termination/bad_orientation": "**终止：姿态不正占比**\nroll/pitch 超限被提前终止的回合占比。\n判读：目标 <2%；监控阈值 0.02，当前历史偏高是主要待改进项。",
    "Episode_Termination/base_contact": "**终止：机身触地占比**\n趴倒/摔翻导致机身着地的回合占比（越低越好）。",
    # -------------------------------------------------------- 损失
    "Loss/value_function": "**损失：价值网络（critic）**\n预测未来回报的回归误差。\n判读：正常 0.01~0.05；**>100 = 发散**（会触发自动降学习率+重训）；**回落≈0 但 reward/回合长度崩溃 = 塌缩假象**，两者都要看。",
    "Loss/surrogate": "**损失：PPO 代理损失**\n策略更新的目标函数变化量，小幅波动正常。",
    "Loss/entropy": "**损失：策略熵**\n策略随机性（探索度）。\n判读：持续走低→探索塌缩风险；autotune 会在平台期加大 entropy_coef。",
    "Loss/learning_rate": "**学习率（KL 自适应）**\n按实测 KL 散度自动增减。\n判读：**长期钉在 1e-5**（监控 lr_pin 指标）说明策略更新过猛被反复抑制；06:03 那类窗口会随恢复解除。",
    # ---------------------------------------------------- 跟踪误差
    "Metrics/base_velocity/error_vel_xy": "**跟踪误差：平面线速度**\n实际 vs 目标 XY 速度误差（m/s，越小越好）。\n判读：0.25~0.30 为当前水平；fresh 重启初期偏高会自愈。",
    "Metrics/base_velocity/error_vel_yaw": "**跟踪误差：偏航角速度**\n实际 vs 目标转向速率误差（rad/s，越小越好）。",
    # -------------------------------------------------------- 性能
    "Perf/total_fps": "**性能：总吞吐**\n环境+训练总帧率（FPS），约 5.5 万为正常；骤降需查 GPU/进程。",
    "Perf/collection time": "**性能：采样耗时**\n每次迭代 rollout 的秒数。",
    "Perf/learning_time": "**性能：学习耗时**\n每次迭代 PPO 更新的秒数。",
    # -------------------------------------------------- 探索与总体
    "Policy/mean_noise_std": "**探索：动作噪声标准差**\n策略高斯噪声强度。\n判读：过低（<0.2）= 探索塌缩；持续偏高 = 策略不收敛。",
    "Train/mean_reward": "**总回报**（最核心健康指标）\n所有奖励分量之和的回合均值。\n判读：稳步上行为健康；腰斩以上跌幅监控会告警；**跌到 0 以下且伴随回合骤短 = 策略崩溃**。",
    "Train/mean_reward/time": "**总回报（横轴=墙钟时间）**\n同上，观察真实时间效率用。",
    "Train/mean_episode_length": "**平均回合长度**（步）\n判读：约 940 步=跑满全程；骤降到几十步=策略趴地/摔倒，即使 value_loss 归 0 也算假恢复。",
    "Train/mean_episode_length/time": "**平均回合长度（横轴=墙钟时间）**",
}

OVERVIEW = (
    "# 曲线中文说明（使用指南）\n\n"
    "这里是 TensorBoard 全部训练曲线的中文备注。**切到本页左侧勾选 run `00_曲线中文说明`**，"
    "每条曲线 tag 对应一条备注；看曲线时在 SCALARS 页对照 tag 名即可。\n\n"
    "**曲线分组速查**\n\n"
    "- `Curriculum/*` —— 课程学习：地形难度与速度指令范围随成功率自动晋升\n"
    "- `Episode_Reward/*` —— 各奖励分量的回合累计（负值 = 惩罚项）\n"
    "- `Episode_Termination/*` —— 回合提前终止原因占比（time_out 越高越好，其余越低越好）\n"
    "- `Loss/*` —— PPO 损失、策略熵与自适应学习率\n"
    "- `Metrics/base_velocity/*` —— 速度跟踪误差（越小越好）\n"
    "- `Perf/*` —— 训练吞吐性能\n"
    "- `Policy/mean_noise_std` —— 探索噪声强度\n"
    "- `Train/*` —— 总回报与平均回合长度（最核心的两个健康指标）\n\n"
    "**三个最常用的判读口诀**\n\n"
    "1. `Train/mean_reward` 上升 + `Train/mean_episode_length` ≈ 940 = 训练健康\n"
    "2. `Loss/value_function` 落在 0.01~0.05 = critic 正常；>100 是发散；归 0 但回报/回合长度崩溃是塌缩假象\n"
    "3. `Curriculum/terrain_levels` 短暂回落会自愈（监控已容忍）；持续横盘才是卡关\n\n"
    "维护：`scripts/tb_notes.py` 的 `NOTES` 字典即备注唯一来源，修改后重跑该脚本即可刷新。\n"
)


def build(out: Path) -> int:
    from torch.utils.tensorboard import SummaryWriter

    if out.exists():  # 幂等重写，避免重复运行后 TEXT 页出现重复条目
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    w = SummaryWriter(log_dir=str(out))
    w.add_text("00_使用说明（先看这条）", OVERVIEW, 0)
    for tag, note in NOTES.items():
        w.add_text(tag, note, 0)
    w.flush()
    w.close()
    return len(NOTES) + 1


def main() -> int:
    ap = argparse.ArgumentParser(description="在 TensorBoard TEXT 面板显示曲线中文备注")
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT), help="说明 run 的输出目录")
    ap.add_argument("--list", action="store_true", help="仅打印对照表，不写事件文件")
    args = ap.parse_args()

    if args.list:
        for tag, note in NOTES.items():
            print(f"{tag}\n    {note.splitlines()[0].lstrip('*')}")
        return 0

    n = build(Path(args.out))
    print(f"written {n} text notes -> {args.out}")
    print("打开 TensorBoard（--logdir logs/rsl_rl/），切到 TEXT 页，勾选 run '00_曲线中文说明' 查看。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

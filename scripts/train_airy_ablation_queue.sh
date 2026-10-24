#!/bin/bash
# =============================================================================
# Airy 消融实验四组（A / D / B / C）串行训练排队脚本
# =============================================================================
#
# 【脚本作用】
#   按顺序依次训练四个消融配置，前一组跑完再自动接下一组：
#     A 基线       Unitree-GeesunDog-LingsiD30W-Velocity            （含 height_scanner 187 维）
#     D 纯本体     ...-Velocity-ProprioOnly                         （无任何外部感知）
#     B Airy替代   ...-Velocity-AiryReplace                         （用 Airy BEV 720 替换 height_scanner）
#     C Airy堆叠   ...-Velocity-AiryStacked                         （height_scanner 187 + Airy BEV 720）
#
# 【为什么必须串行】
#   两个 Isaac Sim 进程同时跑会在 C++ 层直接硬 abort（无 Python 报错栈），所以只能一组一组来。
#
# 【为什么 env 数不一致（LiDAR 显存上限）】
#   - A / D 不带 LiDAR  -> 20096 envs（与参考 ht_stairs_10x 同尺度，吃满空闲显存）
#   - B / C 带 43200 条射线的 Airy 传感器 -> 4096 envs 已是 32GB 卡上 ~26GB 的天花板
#   因此 A/D 每个迭代见到的样本量是 B/C 的 5 倍；消融按“固定迭代数的最终性能”对比（已披露）。
#   若要做严格等数据对比：要么四组都设 4096，要么 B/C 训 5 倍迭代。
#
# 【怎么改迭代数量】  ← 每个任务可单独设置（v1 于 2026-10-19 升级，与 v2 同功能）
#   改下面 4 行，四组互不影响：
#       ITER_A=10000   ITER_D=10000   ITER_B=10000   ITER_C=10000
#   优先级：命令行第 1 参数 > MAX_ITER 环境变量 > 各臂自己的 ITER_*（后两者都不给 → 用各臂默认）
#   全局覆盖两种写法（不改文件，临时冒烟测试）：
#       bash scripts/train_airy_ablation_queue.sh 2000            # 四组都只跑 2000 迭代
#       MAX_ITER=2000 bash scripts/train_airy_ablation_queue.sh   # 环境变量方式
#   等样本量对比：B/C 只有 4096 envs（样本量是 A/D 的 1/5），要等数据量就把 ITER_B / ITER_C 设 50000。
#   只跑部分组：把对应 run 行行首加 # 注释掉。
#   续跑（--resume）：给 run 传第 5 个参数 = 额外 CLI 参数串，例如
#       run "Unitree-GeesunDog-LingsiD30W-Velocity" airy_A_baseline 20096 "$ITER_A" \
#           "--resume --load_run 2026-10-19_16-36-14_airy_A_baseline --load_checkpoint model_900"
#   ⚠️ 训练进行中不要编辑本文件：bash 进程持有脚本 fd（/proc/<pid>/fd/255），改文件会让它的
#      读取偏移错位，后续行可能从中间解析。要改配置就新建脚本文件（如 train_airy_ablation_queue_v2.sh）。
#
# 【怎么用】
#   后台启动（推荐，训练很久）：
#       setsid nohup bash scripts/train_airy_ablation_queue.sh > outputs/train_airy_queue_stdout.log 2>&1 &
#   看进度：
#       tail -f outputs/train_airy_queue.log          # 排队调度日志
#       tail -f outputs/train_airy_A_baseline.log     # 某一组的训练日志
#
# 【注意】每个 FRESH（非 --resume）训练会删掉共享 experiment 目录下的两个课程 sidecar 文件，
#   脚本末尾会把原始课程的 curriculum_state.json / terrain_levels_state.json 还原回去，
#   以保证改配置前的旧 run 仍能 --resume。
# =============================================================================

set -u
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
# B/C 组（带 Airy 激光雷达）在 4096 envs 下峰值显存 ~31.1 GiB / 32.6 GiB，PyTorch 缓存分配器的
# 碎片（实测 1.6 GiB reserved-but-unallocated）会让 ray_caster.py:287 的 quat_w.repeat 分配失败。
# expandable_segments（可扩展显存段）消除该碎片，实测 B 组 4096 envs 从 OOM 变为跑通。
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
QLOG=outputs/train_airy_queue.log

# ---- 每臂默认迭代数（iteration，改这 4 行，四组互不影响）----
ITER_A=500    # A 基线      Unitree-GeesunDog-LingsiD30W-Velocity（height_scanner 高度扫描器 187 维）
ITER_D=5000    # D 纯本体    ...-Velocity-ProprioOnly（无任何外部感知）
ITER_B=10000    # B Airy替代  ...-Velocity-AiryReplace（Airy BEV 720 替换 height_scanner）
ITER_C=10000    # C Airy堆叠  ...-Velocity-AiryStacked（height_scanner 187 + Airy BEV 720）

# ---- 全局覆盖（可选）：命令行第 1 参数优先于 MAX_ITER 环境变量；都不给则用各臂默认 ----
OVERRIDE="${1:-${MAX_ITER:-}}"

# 录像参数：video_interval（录像间隔）在 run() 里随该臂迭代数自适应，短训也能录到视频
VID_BASE="--video --video_length 250 --camera_view diag"

run () {  # $1 = task id, $2 = run name, $3 = num_envs, $4 = 该臂默认迭代数, $5 = 额外 CLI 参数（可空，如 --resume ...）
    local it="${OVERRIDE:-$4}"
    local extra="${5:-}"
    # 不要和正在运行的训练重叠
    while pgrep -f "train.py --headless" > /dev/null; do sleep 15; done
    # 归档上一轮同名日志，避免 ">" 直接覆盖掉历史训练日志
    [ -f "outputs/train_$2.log" ] && mv "outputs/train_$2.log" "outputs/train_${2}_$(date +%m%d-%H%M)_old.log"
    echo "[queue] $(date '+%F %T') === $2 ($1, $3 envs, $it iters) start ===" >> "$QLOG"
    "$PY" scripts/rsl_rl/train.py --headless --task "$1" --num_envs "$3" --seed 42 \
        --max_iterations "$it" $VID_BASE --video_interval "$it" --run_name "$2" $extra > "outputs/train_$2.log" 2>&1
    echo "[queue] $(date '+%F %T') === $2 exit code $? ===" >> "$QLOG"
}

# run "Unitree-GeesunDog-LingsiD30W-Velocity"             airy_A_baseline 20096 "$ITER_A"
# run "Unitree-GeesunDog-LingsiD30W-Velocity-ProprioOnly" airy_D_proprio  20096 "$ITER_D"
run "Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace" airy_B_replace   4096  "$ITER_B"
run "Unitree-GeesunDog-LingsiD30W-Velocity-AiryStacked" airy_C_stacked   4096  "$ITER_C"

# 每个 FRESH 训练会删掉共享 experiment 目录下的两个课程 sidecar；这里还原原始值，
# 保证改配置前的旧 run 仍能 --resume。数值来自首次被删除前从其自身日志读回。
# 2026-10-20: B/C/D 三臂现在各用自己的 sidecar（terrain_levels_state_airy_B.json 等，
# velocity_env_cfg.py::_isolate_curriculum_sidecars），fresh 训练会删掉它们 → 一并还原，
# 否则 pyramid_stairs_level（金字塔楼梯难度等级）与 x_max 会在下一次 fresh 后再次归零。
EXP=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
cp outputs/curriculum_sidecar_backup/curriculum_state.json     "$EXP/" 2>/dev/null
cp outputs/curriculum_sidecar_backup/terrain_levels_state.json "$EXP/" 2>/dev/null
for arm in airy_B airy_C airy_D; do
  cp "outputs/curriculum_sidecar_backup/terrain_levels_state_${arm}.json" "$EXP/" 2>/dev/null
  cp "outputs/curriculum_sidecar_backup/curriculum_state_${arm}.json"     "$EXP/" 2>/dev/null
done
echo "[queue] $(date '+%F %T') all arms done; original sidecars restored" >> "$QLOG"


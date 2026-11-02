#!/bin/bash
# ============================================================================
# validate_stair_climb.sh (原名 P5.sh, 2026-11-02 更名; 日志原名 /tmp/pv.log -> /tmp/stair_climb.log):
# 可视化 + 数值 双重验证"策略能否爬楼梯"
#
# 对齐说明 (2026-11-02 修正):
#   训练地形 = inverted pyramid (坑底出生, 向前=上爬), step_height_range=(0.02,0.23),
#              num_rows=10, difficulty=(row+eta)/10, 训练能力标定在 row 6
#              -> 踏步高 = 0.02 + 6/9 * 0.21 = 0.160 m
#   本脚本  = --terrain stairs --stair_level 6 --stairs_dir up
#              --stair_level 6 走 stair_level_to_height(): h = lo + 6/9*(hi-lo) = 0.160 m 固定
#              (不能用 GEESUN_D30W_STAIRS_DIR=up 代替 --stairs_dir: 前者只改 task cfg,
#               play 的地形由 apply_terrain() 按 --stairs_dir 重建, 默认值是 down!)
#
# 判读标准 (dz = 基座世界高度 - 地形原点高度 = 相对出生点坑底地面的高度):
#   站立 dz ≈ 0.63 m 是基准; 爬上一级 0.16 m 台阶 -> dz 稳定升到 ≈0.79 且不回落到 0.63
#   max(dz) <= 0.65  -> 没有爬升;  max(dz) >= 0.75 -> 真的爬上去过
# ============================================================================
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab || exit 1
export GEESUN_D30W_STEP_H=0.02,0.23   # 让 task cfg 的台阶范围与训练一致(供 stair_level 映射)
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
CK=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-30_11-47-02_airy_A_climb_ladder_v2/model_14300.pt
: > /tmp/stair_climb.log
for i in 1 2; do
  echo "===== RUN $i =====" >> /tmp/stair_climb.log
  timeout 260 $PY scripts/rsl_rl/play.py --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --checkpoint $CK --num_envs 3 \
    --terrain stairs --stair_level 6 --stairs_dir up \
    --cmd_x 0.5 0.5 --cmd_y 0 0 --cmd_z 0 0 --no_standing \
    --video --video_length 900 --video_tag up_lvl6_$i \
    --camera_view side --camera_distance 2.5 --camera_height 0.9 \
    --probe >> /tmp/stair_climb.log 2>&1
done
echo DONE

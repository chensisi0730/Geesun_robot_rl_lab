#!/bin/bash
# 可视化爬楼测试: 跟拍相机(侧视 2.5m/高0.9m) + 数值探针同时输出
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab || exit 1
export GEESUN_D30W_STEP_H=0.02,0.23
export GEESUN_D30W_STAIRS_DIR=up
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
CK=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x/2026-10-30_11-47-02_airy_A_climb_ladder_v2/model_14300.pt
: > /tmp/pv.log
for i in 1 2; do
  echo "===== RUN $i =====" >> /tmp/pv.log
  timeout 260 $PY scripts/rsl_rl/play.py --task Unitree-GeesunDog-LingsiD30W-Velocity \
    --checkpoint $CK --num_envs 3 --terrain stairs --stair_height 0.15 0.22 \
    --cmd_x 0.5 0.5 --cmd_y 0 0 --cmd_z 0 0 --no_standing \
    --video --video_length 900 --video_tag vis$i \
    --camera_view side --camera_distance 2.5 --camera_height 0.9 \
    --probe >> /tmp/pv.log 2>&1
done
echo DONE

#!/usr/bin/env bash
# ============================================================================
# 锁轮 D30W 平地大命令验证 (wheel-lock flat + large-command validation)
#
# !!! THIS IS A BASH SCRIPT, NOT PYTHON. Run with: bash scripts/tests/validate_wheel_lock_flat.sh
#
# 目的：回答"锁轮 D30W 到底能不能走"—— 纯平地 + 恒定大前进命令下，
#   V1 锁轮 + 无惩罚   vs   V2 自由轮 + 无惩罚（同一份权重）
#   V1 能走  → 物理可行，问题在奖励口径（命令范围/跟踪 std/离地奖励门控/课程门限）
#   V1 不能、V2 能 → 锁轮（被刹住的圆柱支撑）本身是物理障碍
#   V1/V2 都不能 → 与锁轮无关，是策略/奖励问题
#
# 判据（写在 test_walk_torque.py 产出的 CSV / TensorBoard Eval/<tag>/* 里）：
#   mean_fwd_along_cmd_ms > 0.10        沿指令方向确有前进（核心）
#   forward_ok_fraction  > 0.50          前进占比
#   mean_error_xy_ms    < 0.15           跟踪质量
#
# 前置条件（pre-flight）：GPU 空闲、无其它 Isaac Sim 实例（两个并发 = C++ 静默 abort）。
# 段间冷却 45 s：上一段退出后 GPU 上下文未释放就启动下一段会卡在渲染初始化。
#
# 用法：
#   bash scripts/tests/validate_wheel_lock_flat.sh                 # 用最新 run 的最新 ckpt
#   CKPT=<path/to/model_21000.pt> bash scripts/tests/validate_wheel_lock_flat.sh
#   CMD_X="0.3 0.3" CMD_Y="-0.1 0.1" CMD_Z="-0.3 0.3" bash .../validate_wheel_lock_flat.sh
# ============================================================================
set -u
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
mkdir -p outputs

PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
TASK=${TASK:-Unitree-GeesunDog-LingsiD30W-Velocity}
NUM_ENVS=${NUM_ENVS:-64}
STEPS=${STEPS:-500}
VIDEO_LEN=${VIDEO_LEN:-500}
if [ -z "${CMD_X:-}" ]; then CMD_X="0.3 0.3"; fi
if [ -z "${CMD_Y:-}" ]; then CMD_Y="-0.1 0.1"; fi
if [ -z "${CMD_Z:-}" ]; then CMD_Z="-0.3 0.3"; fi

# 权重：默认取最新 run 里最新的 model_*.pt
if [ -z "${CKPT:-}" ]; then
  for d in $(ls -dt logs/rsl_rl/*/*/ 2>/dev/null); do
    c=$(ls -t "$d"model_*.pt 2>/dev/null | head -1)
    if [ -n "$c" ]; then CKPT="$c"; break; fi
  done
fi
if [ -z "${CKPT:-}" ] || [ ! -f "$CKPT" ]; then
  echo "[ABORT] 找不到 checkpoint（用 CKPT=<path> 指定）"
  exit 1
fi
RUN_DIR=$(dirname "$CKPT")
echo "[INFO] task=$TASK"
echo "[INFO] checkpoint=$CKPT"
echo "[INFO] commands: x=$CMD_X y=$CMD_Y z=$CMD_Z (num_envs=$NUM_ENVS, steps=$STEPS)"

# 同一时刻只允许一个 Isaac Sim 实例
if pgrep -f 'train[.]py|play[.]py' > /dev/null; then
  echo "[ABORT] 检测到 train.py / play.py 正在运行（同一 GPU 只能跑一个 Isaac Sim 实例）。"
  echo "        训练请手动 kill（checkpoint 会保留）：kill -KILL <pid>"
  exit 1
fi
if command -v nvidia-smi > /dev/null; then
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  if [ "${USED:-0}" -gt 2000 ]; then
    echo "[WARN] GPU 显存已占用 ${USED} MiB（残留上下文？），建议等 45 s 再跑"
  fi
fi

# ---------------------------------------------------------------- 1) V1 定量：锁轮 + 无惩罚
echo "[INFO] === V1 定量：锁轮 + 无惩罚 (GEESUN_D30W_JOINT_POS=0, 轮锁默认开) ==="
GEESUN_D30W_JOINT_POS=0 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True timeout 1800 \
  "$PY" -u scripts/rsl_rl/test_walk_torque.py --headless --task "$TASK" --checkpoint "$CKPT" \
  --terrain flat --cmd_x $CMD_X --cmd_y $CMD_Y --cmd_z $CMD_Z --no_standing \
  --tb_tag flat_lock_jp0 --num_envs "$NUM_ENVS" --steps "$STEPS" \
  > outputs/validate_wheel_lock_flat_lock_jp0.log 2>&1
echo "[INFO] V1 定量 exit=$?  log: outputs/validate_wheel_lock_flat_lock_jp0.log"
sleep 45

# ---------------------------------------------------------------- 2) V2 定量：自由轮 + 无惩罚
echo "[INFO] === V2 定量：自由轮 + 无惩罚 (GEESUN_D30W_WHEEL_LOCK=0) ==="
GEESUN_D30W_WHEEL_LOCK=0 GEESUN_D30W_JOINT_POS=0 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True timeout 1800 \
  "$PY" -u scripts/rsl_rl/test_walk_torque.py --headless --task "$TASK" --checkpoint "$CKPT" \
  --terrain flat --cmd_x $CMD_X --cmd_y $CMD_Y --cmd_z $CMD_Z --no_standing \
  --tb_tag flat_free_jp0 --num_envs "$NUM_ENVS" --steps "$STEPS" \
  > outputs/validate_wheel_lock_flat_free_jp0.log 2>&1
echo "[INFO] V2 定量 exit=$?  log: outputs/validate_wheel_lock_flat_free_jp0.log"
sleep 45

# ---------------------------------------------------------------- 3/4) 录像：肉眼确认是否真迈步
echo "[INFO] === V1 录像：锁轮 + 无惩罚 ==="
GEESUN_D30W_JOINT_POS=0 timeout 1800 \
  "$PY" -u scripts/rsl_rl/play.py --headless --video --video_length "$VIDEO_LEN" \
  --task "$TASK" --checkpoint "$CKPT" --terrain flat \
  --cmd_x $CMD_X --cmd_y $CMD_Y --cmd_z $CMD_Z --no_standing --no_curriculum \
  --video_tag flat_lock_jp0 \
  --camera_view side --camera_distance 0.57 --camera_height 1.2 --camera_focal 21 \
  > outputs/validate_wheel_lock_flat_video_lock.log 2>&1
echo "[INFO] V1 录像 exit=$?  log: outputs/validate_wheel_lock_flat_video_lock.log"
sleep 45

echo "[INFO] === V2 录像：自由轮 + 无惩罚 ==="
GEESUN_D30W_WHEEL_LOCK=0 GEESUN_D30W_JOINT_POS=0 timeout 1800 \
  "$PY" -u scripts/rsl_rl/play.py --headless --video --video_length "$VIDEO_LEN" \
  --task "$TASK" --checkpoint "$CKPT" --terrain flat \
  --cmd_x $CMD_X --cmd_y $CMD_Y --cmd_z $CMD_Z --no_standing --no_curriculum \
  --video_tag flat_free_jp0 \
  --camera_view side --camera_distance 0.57 --camera_height 1.2 --camera_focal 21 \
  > outputs/validate_wheel_lock_flat_video_free.log 2>&1
echo "[INFO] V2 录像 exit=$?  log: outputs/validate_wheel_lock_flat_video_free.log"

# ---------------------------------------------------------------- 汇总
CSV_LOCK="$RUN_DIR/flat_lock_jp0_terrain_stats.csv"
CSV_FREE="$RUN_DIR/flat_free_jp0_terrain_stats.csv"
metric() { awk -F, -v k="$2" '$1==k {print $2; exit}' "$1" 2>/dev/null; }

echo ""
echo "[VERIFY] 对照表（平地, 恒定 x 命令）"
printf "  %-26s %14s %14s\n" "metric" "V1 锁轮" "V2 自由轮"
for k in mean_fwd_along_cmd_ms average_forward_velocity_ms forward_ok_fraction \
         mean_error_xy_ms mean_error_yaw_rads mean_cmd_abs_x_ms success_rate average_height_m; do
  printf "  %-26s %14s %14s\n" "$k" "$(metric "$CSV_LOCK" "$k")" "$(metric "$CSV_FREE" "$k")"
done
echo "  CSV: $CSV_LOCK"
echo "        $CSV_FREE"
echo ""
echo "[VERIFY] 生效设置（从 CSV 读回，防止参数被静默忽略）"
for f in "$CSV_LOCK" "$CSV_FREE"; do
  [ -f "$f" ] || continue
  echo "  $(basename "$f"):"
  for k in eval_tag command_lin_vel_x command_lin_vel_y command_ang_vel_z rel_standing_envs wheel_locked; do
    printf "    %-22s %s\n" "$k" "$(metric "$f" "$k")"
  done
done

# 抽帧供目视
for tag in flat_lock_jp0 flat_free_jp0; do
  V=$(ls -t "$RUN_DIR/videos/$tag"/*.mp4 2>/dev/null | head -1)
  if [ -n "$V" ]; then
    ffmpeg -y -v error -i "$V" -vf "select=eq(n\,40)" -vframes 1 "outputs/wl_${tag}_f40.png" 2>/dev/null
    ffmpeg -y -v error -i "$V" -vf "select=eq(n\,300)" -vframes 1 "outputs/wl_${tag}_f300.png" 2>/dev/null
    echo "[VERIFY] 抽帧: outputs/wl_${tag}_f40.png, outputs/wl_${tag}_f300.png  (源 $V)"
  else
    echo "[VERIFY] 未找到录像: $RUN_DIR/videos/$tag/*.mp4"
  fi
done
echo ""
echo "[VERIFY] TensorBoard: 标签 Eval/flat_lock_jp0/* 与 Eval/flat_free_jp0/* 已写入 $RUN_DIR"

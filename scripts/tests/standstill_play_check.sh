#!/usr/bin/env bash
# ============================================================================
# 站立不动刷分目视回放检查 (stand-still reward-hacking visual check via play)
#
# !!! THIS IS A BASH SCRIPT, NOT PYTHON. Run with: bash scripts/tests/standstill_play_check.sh
#
# 目的：用 play.py 目视回放检查策略是否"站立不动刷分"（stand-still reward hacking）。
#   恒定大前进命令（--cmd_x 0.5 0.5）+ --no_standing（禁站立环境）+ --no_curriculum（冻结
#   地形等级）下，机器人应当真实前进。若原地踏步 / 拖腿 / 摇摆不前，即为刷分复发。
#
# 判读（录像肉眼看 + 抽帧）：
#   通过：机身持续沿 +x 前进，画面中景物后退
#   刷分：机身基本不动、腿部原地抽动（feet_clearance 抬腿刷分）或蹲伏不动
#   注意：仅目视。定量判据（mean_fwd_along_cmd_ms > 0.10 等）见 validate_wheel_lock_flat.sh
#         / test_walk_torque.py，本脚本是它的目视前置筛查。
#
# 前置条件（pre-flight）：GPU 空闲、无其它 Isaac Sim 实例（两个并发 = C++ 静默 abort）。
# 段间冷却 4 s：上一段退出后 GPU 上下文未释放就启动下一段会卡在渲染初始化。
#
# 用法：
#   bash scripts/tests/standstill_play_check.sh                      # 最新 ckpt，flat + stairs 各一段
#   TERRAIN=flat bash scripts/tests/standstill_play_check.sh         # 只跑平地
#   CKPT=<path/to/model_21000.pt> bash .../standstill_play_check.sh  # 指定权重
#   CMD_X="0.3 0.3" NUM_ENVS=16 VIDEO_LEN=800 bash .../standstill_play_check.sh
#
# 楼梯参数（仅对 stairs / complex 地形生效）：
#   STAIR_DIR=up bash .../standstill_play_check.sh        # 上楼梯（出生坑底，向前爬升）
#   STAIR_DIR=down bash .../standstill_play_check.sh      # 下楼梯（默认；出生塔顶平台，向前下行）
#   STAIR_LEVEL=9 bash .../standstill_play_check.sh       # 楼梯等级 0-9（9=0.23 m 最高，0=0.05 m）
#   TERRAIN=stairs STAIR_DIR=up STAIR_LEVEL=9 bash scripts/tests/standstill_play_check.sh    # 只测上楼梯 5 级
#   TERRAIN=stairs STAIR_DIR=down STAIR_LEVEL=5 bash scripts/tests/standstill_play_check.sh    # 只测上楼梯 5 级

# ============================================================================
set -u
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
mkdir -p outputs

PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
TASK=${TASK:-Unitree-GeesunDog-LingsiD30W-Velocity}
NUM_ENVS=${NUM_ENVS:-8}
VIDEO_LEN=${VIDEO_LEN:-1000}
if [ -z "${CMD_X:-}" ]; then CMD_X="0.5 0.5"; fi
if [ -z "${CMD_Y:-}" ]; then CMD_Y="0 0"; fi
if [ -z "${CMD_Z:-}" ]; then CMD_Z="0 0"; fi
if [ -z "${TERRAIN:-}" ]; then TERRAIN="flat stairs"; fi
# 楼梯方向（上/下）与楼梯等级（0-9，对应训练 terrain_levels 同标度；空 = 用训练全范围 0.05-0.23 m）
if [ -z "${STAIR_DIR:-}" ]; then STAIR_DIR="down"; fi
if [ -z "${STAIR_LEVEL:-}" ]; then STAIR_LEVEL=""; fi

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

# 训练 run 的 cfg 快照（params/velocity_env_cfg.py）：task cfg 后续改动（如 height_scanner
# 高度扫描加入观测）会与旧权重的观测维度不匹配，快照可避免加载失败。
ENV_CFG_ARGS=()
SNAP="$RUN_DIR/params/velocity_env_cfg.py"
if [ -f "$SNAP" ]; then
  ENV_CFG_ARGS=(--env_cfg_file "$SNAP")
  echo "[INFO] env cfg snapshot (cfg 快照): $SNAP"
else
  echo "[INFO] 未找到 cfg 快照（$SNAP），使用当前注册的 task cfg"
fi

echo "[INFO] task=$TASK"
echo "[INFO] checkpoint=$CKPT"
echo "[INFO] commands: x=$CMD_X y=$CMD_Y z=$CMD_Z (num_envs=$NUM_ENVS, video_length=$VIDEO_LEN)"
echo "[INFO] terrains: $TERRAIN  stairs_dir=$STAIR_DIR  stair_level=${STAIR_LEVEL:-全范围 0.05-0.23 m}"

# 同一时刻只允许一个 Isaac Sim 实例
if pgrep -f 'train[.]py|play[.]py|test_walk_torque[.]py' > /dev/null; then
  echo "[ABORT] 检测到 train.py / play.py / test_walk_torque.py 正在运行（同一 GPU 只能跑一个 Isaac Sim 实例）。"
  echo "        训练请手动 kill（checkpoint 会保留）：kill -KILL <pid>"
  exit 1
fi
if command -v nvidia-smi > /dev/null; then
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  if [ "${USED:-0}" -gt 2000 ]; then
    echo "[WARN] GPU 显存已占用 ${USED} MiB（残留上下文？），建议等 4 s 再跑"
  fi
fi

# ---------------------------------------------------------------- 逐地形目视回放
TAGS=""
for ter in $TERRAIN; do
  # 楼梯方向/等级只对 stairs / complex 地形有意义
  STAIR_ARGS=()
  tag="standstill_${ter}"
  case "$ter" in
    stairs|complex)
      STAIR_ARGS+=(--stairs_dir "$STAIR_DIR")
      [ -n "$STAIR_LEVEL" ] && STAIR_ARGS+=(--stair_level "$STAIR_LEVEL")
      tag="standstill_${ter}_${STAIR_DIR}${STAIR_LEVEL:+_lv$STAIR_LEVEL}"
      ;;
  esac
  echo "[INFO] === 目视回放：terrain=$ter${STAIR_ARGS:+ (${STAIR_ARGS[*]})}, 恒定 x 命令 ==="
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True timeout 1800 \
    "$PY" -u scripts/rsl_rl/play.py --headless --video --video_length "$VIDEO_LEN" \
    --task "$TASK" --checkpoint "$CKPT" "${ENV_CFG_ARGS[@]}" --terrain "$ter" \
    --cmd_x $CMD_X --cmd_y $CMD_Y --cmd_z $CMD_Z --no_standing --no_curriculum \
    "${STAIR_ARGS[@]}" \
    --video_tag "$tag" \
    --camera_view side --camera_distance 0.57 --camera_height 1.2 --camera_focal 21 \
    > "outputs/standstill_play_${tag#standstill_}.log" 2>&1
  echo "[INFO] $ter 回放 exit=$?  log: outputs/standstill_play_${tag#standstill_}.log"
  TAGS="$TAGS $tag"
  sleep 4
done

# ---------------------------------------------------------------- 抽帧供目视
echo ""
echo "[VERIFY] 抽帧（肉眼判读：机身是否沿 +x 前进，景物是否后退）"
for tag in $TAGS; do
  V=$(ls -t "$RUN_DIR/videos/$tag"/*.mp4 2>/dev/null | head -1)
  if [ -n "$V" ]; then
    ffmpeg -y -v error -i "$V" -vf "select=eq(n\,40)" -vframes 1 "outputs/sst_${tag}_f40.png" 2>/dev/null
    ffmpeg -y -v error -i "$V" -vf "select=eq(n\,300)" -vframes 1 "outputs/sst_${tag}_f300.png" 2>/dev/null
    echo "  $tag: outputs/sst_${tag}_f40.png, outputs/sst_${tag}_f300.png  (源 $V)"
  else
    echo "  $tag: [WARN] 未找到录像（看 outputs/standstill_play_*.log）"
  fi
done
echo ""
echo "[VERIFY] 判读标准："
echo "  通过 = 机身持续前进（f40 -> f300 位置明显前移，景物后退）"
echo "  刷分 = 原地踏步 / 腿部抽动 / 蹲伏不动（feet_clearance 抬腿刷分或站立不动）"
echo "  楼梯方向：STAIR_DIR=up 上楼梯看爬升能力（f40 在坑底 -> f300 已爬升台阶）；"
echo "            STAIR_DIR=down 下楼梯看下台阶稳定性（机身不栽跟头 = bad_orientation 不触发）"
echo "  楼梯等级：STAIR_LEVEL 越高台阶越高（9=0.23 m），低等级通过后逐级加测"
echo "  刷分复发时的定量确认：bash scripts/tests/validate_wheel_lock_flat.sh"
echo "  （mean_fwd_along_cmd_ms > 0.10, forward_ok_fraction > 0.50, mean_error_xy_ms < 0.15）"

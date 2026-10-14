#!/usr/bin/env bash
# 6-hourly TensorBoard health check + auto-tune loop for the lingsi_d30w (D30W wheel-legged)
# campaign. Same code base as the Go2/dog1 monitor (scripts/monitor_tb_check.py), isolated via
# environment variables: own task variant, own training log prefix, own state dirs.
#
# Start (daemonized):
#   nohup bash scripts/monitor_tb_check_d30w.sh >> outputs/monitor_d30w/monitor.log 2>&1 &
#
# Stop: kill the loop; the stop_marker in outputs/monitor_d30w/state.json re-arms on next launch.
set -u
cd "$(dirname "$0")/.."

PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python

# --- campaign: lingsi_d30w (D30W wheel-legged), PD/actuator params from D30W关节电气参数.xlsx ---
# GEESUN_DOG_VARIANT is informational only - the lingsi_d30w task pins its own asset variant.
export GEESUN_DOG_VARIANT=lingsi_d30w
export MON_RUNS_GLOB="unitree_geesun_lingsi_d30w/*"
export MON_TASK="Unitree-GeesunDog-LingsiD30W-Velocity"
export MON_NUM_ENVS=24096
export MON_LOG_PREFIX="/tmp/train_d30w_v"
export MON_RESUME_LOG="/tmp/train_d30w_auto.log"
export MON_TRAIN_PATTERN='train\.py.*Unitree-GeesunDog-LingsiD30W-Velocity'
export MON_DIR="outputs/monitor_d30w"
export AUTOTUNE_DIR="outputs/autotune_d30w"
# autotune knobs edit the lingsi_d30w task's own env cfg + PPO class (dedicated to this
# variant, not shared with dog1 or Go2), so this campaign can auto-tune concurrently.
export AUTOTUNE_ENV_FILE="source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/robots/geesun_dog/lingsi_d30w/velocity_env_cfg.py"
export AUTOTUNE_PPO_SCOPE="class UnitreeGeesunDogLingsiD30WPPORunnerCfg"

mkdir -p "$MON_DIR"
while true; do
  "$PY" scripts/monitor_tb_check.py >> "$MON_DIR/monitor.log" 2>&1
  sleep 21600
done

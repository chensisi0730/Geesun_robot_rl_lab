#!/usr/bin/env bash
# 6-hourly TensorBoard health check + auto-tune loop for the GeesunDog (dog1) FLAT-terrain
# campaign. Same code base as the Go2 monitor (scripts/monitor_tb_check.py), isolated via
# environment variables: own task, own training log glob, own state dirs, own knob scope.
#
# Start (daemonized):
#   nohup bash scripts/monitor_tb_check_dog.sh >> outputs/monitor_dog/monitor.log 2>&1 &
#
# Stop: kill the loop; to re-arm the Go2 monitor later, remove the stop_marker from
# outputs/monitor/state.json (or just relaunch a Go2 run - the marker clears itself).
set -u
cd "$(dirname "$0")/.."

PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python

# --- campaign: GeesunDog dog1, flat terrain only (velocity_env_cfg sub_terrains = flat) ---
# GEESUN_DOG_VARIANT is informational only - the dog1 task pins its own asset variant.
export GEESUN_DOG_VARIANT=dog1
export MON_RUNS_GLOB="unitree_geesun_dog1/*"
export MON_TASK="Unitree-GeesunDog-Dog1-Velocity"
export MON_NUM_ENVS=24096
export MON_LOG_PREFIX="/tmp/train_dog_v"
export MON_RESUME_LOG="/tmp/train_dog_auto.log"
export MON_TRAIN_PATTERN='train\.py.*Unitree-GeesunDog-Dog1-Velocity'
export MON_DIR="outputs/monitor_dog"
export AUTOTUNE_DIR="outputs/autotune_dog"
# autotune knobs edit the dog1 task's own env cfg + PPO class (dedicated to this variant, not
# shared with lingsi_d30w or Go2), so this campaign can auto-tune concurrently with the others.
export AUTOTUNE_ENV_FILE="source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/robots/geesun_dog/dog1/velocity_env_cfg.py"
export AUTOTUNE_PPO_SCOPE="class UnitreeGeesunDogDog1PPORunnerCfg"

mkdir -p "$MON_DIR"
while true; do
  "$PY" scripts/monitor_tb_check.py >> "$MON_DIR/monitor.log" 2>&1
  sleep 21600
done

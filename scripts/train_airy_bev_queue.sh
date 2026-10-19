#!/bin/bash
# Re-run of the Airy BEV arm (config B, -AiryReplace) AFTER the mesh_prim_paths fix.
#
# The first two B attempts both died silently (no Python Traceback): the 20 m OffsetCfg is fine, but
# listing "{ENV_REGEX_NS}/Robot" in mesh_prim_paths made MultiMeshRayCasterCfg dedup one USD mesh
# per env at ~1 s/env - ~68 min of init at 4096 envs and then a hard crash. mesh_prim_paths is now
# terrain-only ("/World/ground"), which is the configuration the 26.2 GB VRAM measurement and the
# verify_airy_lidar.py 4096-env run were calibrated on.
#
# This script waits for the A -> D -> C queue to finish first: two concurrent Isaac Sim instances
# hard-abort each other (C++ abort, no traceback), so runs must stay serial.
set -u
PY=/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python
cd /home/css/work/unitree/rl/Geesun_robot_rl_lab
QLOG=outputs/train_airy_queue.log

echo "[bev-queue] $(date '+%F %T') waiting for the A/D/C queue (pid 1176750) to exit" >> "$QLOG"
while kill -0 1176750 2>/dev/null; do sleep 30; done

# belt and braces: never start while a training is still alive
while pgrep -f "train.py --headless" > /dev/null; do sleep 15; done

echo "[bev-queue] $(date '+%F %T') === airy_B_replace start (terrain-only mesh_prim_paths) ===" >> "$QLOG"
"$PY" scripts/rsl_rl/train.py --headless \
    --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryReplace \
    --num_envs 4096 --seed 42 --max_iterations 10000 --run_name airy_B_replace \
    > outputs/train_airy_B_replace.log 2>&1
echo "[bev-queue] $(date '+%F %T') === airy_B_replace exit code $? ===" >> "$QLOG"

# every fresh run deletes the shared experiment's curriculum sidecars; restore the originals
EXP=logs/rsl_rl/unitree_geesun_lingsi_d30w_ht_stairs_10x
cp outputs/curriculum_sidecar_backup/curriculum_state.json     "$EXP/" 2>/dev/null
cp outputs/curriculum_sidecar_backup/terrain_levels_state.json "$EXP/" 2>/dev/null
echo "[bev-queue] $(date '+%F %T') done; original sidecars restored" >> "$QLOG"

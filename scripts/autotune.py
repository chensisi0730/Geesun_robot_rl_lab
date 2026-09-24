#!/usr/bin/env python
"""Rule-based auto-tuner for the GO2 velocity training loop.

The 6-hourly monitor (``scripts/monitor_tb_check.py``) invokes this script as a **subprocess**,
so any edit to the rules / knob registry below takes effect on the next check without
restarting the monitor ("随时调整代码重新训练").

What it does
------------
1. Loads *all* TensorBoard scalars of the newest run (via :mod:`tb_curves`).
2. Diagnoses health: curve degradation, plateau, stuck curricula, exploration collapse,
   LR pinned, and falls.
3. Picks **one** small, bounded knob change from the priority rules in :func:`decide`
   (one change per action -> easy to ablate, matching the repo's ablation requirement).
4. Stops the current training, applies the edit to the config source (backup + unified diff
   + ``py_compile`` guard), and relaunches:
     * PPO knobs  -> ``--resume`` from the newest checkpoint of the current run;
     * env knobs (reward / curriculum / ranges) -> fresh run (curriculum state is reset).
5. Records every action in ``outputs/autotune/ledger.jsonl`` and ``state.json``.

Safety
------
* Kill switch: create ``outputs/autotune/DISABLED`` to stop all automatic actions.
* ``--dry-run`` prints the plan without touching anything.
* ``--rollback`` restores the newest backup and relaunches.
* Transient tolerance: degradation-class actions must reproduce at ``CONFIRM_CHECKS``
  consecutive checks of the same run before training is stopped/restarted; a one-off dip
  (terrain_levels, value_function, ...) that recovers is only recorded in the state/ledger.
* Global cap ``MAX_ACTIONS`` and per-knob budgets; ``MIN_START_ITERS`` /
  ``MIN_ITERS_BETWEEN_ACTIONS`` / ``MIN_SECONDS_BETWEEN_ACTIONS`` prevent acting on
  startup transients or thrashing. Iteration cooldowns are run-local because fresh runs
  reset their TensorBoard step to zero.
* Edits are scoped to the class/section they belong to and are rejected if the file no
  longer compiles. Any edit/compile/launch failure restores the source backup and attempts
  to resume the stopped run from its latest checkpoint.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import tb_curves as tbc

REPO = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO / "logs" / "rsl_rl" / "unitree_go2_velocity"
AUTODIR = REPO / "outputs" / "autotune"
BACKUP_DIR = AUTODIR / "backups"
LEDGER = AUTODIR / "ledger.jsonl"
STATE_PATH = AUTODIR / "state.json"
DISABLE_FILE = AUTODIR / "DISABLED"

PY = sys.executable
TASK = "Unitree-Go2-Velocity"
NUM_ENVS = 22000
TRAIN_PATTERN = r"train\.py.*Unitree-Go2-Velocity"
ISAACLAB_PATH = "/home/css/work/unitree/rl/unitree_Robert/isaaclab/IsaacLab"
PROXY = "http://127.0.0.1:7897"

# ---------------------------------------------------------------------------
# Tunable knob registry.  `restart` decides the relaunch mode:
#   "resume" -> PPO/algorithm knobs that are safe to continue from a checkpoint
#   "fresh"  -> reward / curriculum / range / reset-noise knobs that change the MDP
# Edit/add entries here (and the rules in `decide`) to change the tuning policy.
# ---------------------------------------------------------------------------
PPO_FILE = "source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/agents/rsl_rl_ppo_cfg.py"
ENV_FILE = "source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py"
PPO_SCOPE = "class UnitreeGo2PPORunnerCfg"

KNOBS: dict[str, dict] = {
    # NOTE: patterns are line-anchored (^ + re.MULTILINE) so they never match the example
    # values that appear inside class docstrings/comments.
    # -- PPO --
    "init_noise_std": dict(
        file=PPO_FILE, scope=PPO_SCOPE, pattern=r"^\s*(init_noise_std=)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=0.2, lo=0.3, hi=1.5, fmt="{:.2f}", restart="fresh",
        desc="PPO initial exploration std (fresh: checkpoint stores its own std)",
    ),
    "entropy_coef": dict(
        file=PPO_FILE, scope=PPO_SCOPE, pattern=r"^\s*(entropy_coef=)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=0.005, lo=0.002, hi=0.03, fmt="{:.4g}", restart="resume",
        desc="PPO entropy bonus",
    ),
    "learning_rate": dict(
        file=PPO_FILE, scope=PPO_SCOPE, pattern=r"^\s*(learning_rate=)(?P<v>[0-9.eE+-]+)",
        kind=float, op="mul", arg=0.5, lo=2.0e-4, hi=2.0e-3, fmt="{:.1e}", restart="fresh",
        desc="PPO learning rate (reduced after value-function divergence)",
    ),
    "desired_kl": dict(
        file=PPO_FILE, scope=PPO_SCOPE, pattern=r"^\s*(desired_kl=)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=0.005, lo=0.003, hi=0.03, fmt="{:.4g}", restart="resume",
        desc="KL-adaptive LR target (higher = LR collapses less)",
    ),
    # -- reward --
    "track_ang_vel_z": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(func=mdp\.track_ang_vel_z_exp, weight=)(?P<v>-?[0-9.]+)",
        kind=float, op="add", arg=0.25, lo=0.3, hi=2.5, fmt="{:.2f}", restart="fresh",
        desc="yaw tracking reward weight",
    ),
    "track_lin_vel_xy": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(func=mdp\.track_lin_vel_xy_exp, weight=)(?P<v>-?[0-9.]+)",
        kind=float, op="add", arg=0.25, lo=0.5, hi=3.0, fmt="{:.2f}", restart="fresh",
        desc="linear tracking reward weight",
    ),
    "flat_orientation_l2": dict(
        file=ENV_FILE, scope=None,
        pattern=r"^\s*(flat_orientation_l2 = RewTerm\(func=mdp\.flat_orientation_l2, weight=)(?P<v>-?[0-9.]+)",
        kind=float, op="add", arg=-0.5, lo=-6.0, hi=0.0, fmt="{:.2f}", restart="fresh",
        desc="roll/pitch penalty (more negative = more stable)",
    ),
    # -- curriculum --
    "success_yaw": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(\"success_yaw\":\s*)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=0.05, lo=0.2, hi=0.6, fmt="{:.2f}", restart="fresh",
        desc="yaw gate success threshold (higher = easier to advance)",
    ),
    "success_xy": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(\"success_xy\":\s*)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=0.05, lo=0.15, hi=0.5, fmt="{:.2f}", restart="fresh",
        desc="lin gate success threshold (higher = easier to advance)",
    ),
    "min_success_rate": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(\"min_success_rate\":\s*)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=-0.05, lo=0.6, hi=0.95, fmt="{:.2f}", restart="fresh",
        desc="gate success rate required to widen the command range",
    ),
    "lin_increment": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(\"lin_increment\":\s*)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=-0.01, lo=0.01, hi=0.1, fmt="{:.3g}", restart="fresh",
        desc="per-unlock linear velocity step (smaller = smoother)",
    ),
    "yaw_increment": dict(
        file=ENV_FILE, scope=None, pattern=r"^\s*(\"yaw_increment\":\s*)(?P<v>[0-9.]+)",
        kind=float, op="add", arg=-0.02, lo=0.02, hi=0.2, fmt="{:.3g}", restart="fresh",
        desc="per-unlock yaw velocity step (smaller = smoother)",
    ),
}

# ---------------------------------------------------------------------------
# Decision thresholds (edit freely).
# ---------------------------------------------------------------------------
WINDOW = 400                  # iterations used for trend/plateau detection
MIN_START_ITERS = 1500        # never act before this many iterations
MIN_ITERS_BETWEEN_ACTIONS = 600
MIN_SECONDS_BETWEEN_ACTIONS = 3 * 60 * 60
MAX_ACTIONS = 16              # global cap across the whole campaign

# A single noisy scalar must never restart an expensive run. Degradation requires either
# reward to fall together with another adverse curve, or at least two non-reward curves to
# worsen over the same window. Thresholds are relative changes between the first and last
# quarters of WINDOW (see tb_curves.trend).
REWARD_DEGRADE_REL = -0.20
TRACKING_DEGRADE_REL = 0.15
TIMEOUT_DEGRADE_REL = -0.10
FALL_DEGRADE_REL = 0.25
VALUE_LOSS_ABORT = 100.0
VALUE_LOSS_WINDOW = 200
MIN_DIVERGENCE_SAMPLES = 50
LAUNCH_GRACE_S = 3.0

# Transient tolerance for degradation-class actions (curve degradation / rising falls): the
# observation must repeat at two consecutive checks (6 h apart) before training is stopped
# and restarted. Curves such as terrain_levels or value_function often dip briefly and
# recover on their own; a one-off observation is recorded but never acted upon. Exempt:
# the value-divergence rule (already needs two consecutive elevated 200-iteration windows)
# and plateau/learning-pressure rules (non-destructive, own cooldowns).
CONFIRM_CHECKS = 2


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# TensorBoard / diagnosis
# ---------------------------------------------------------------------------
def latest_run_dir() -> Path | None:
    best: tuple[float, Path] | None = None
    if RUNS_ROOT.exists():
        for d in RUNS_ROOT.iterdir():
            if not d.is_dir():
                continue
            mts = [p.stat().st_mtime for p in d.glob("events.out.tfevents.*")]
            if mts and (best is None or max(mts) > best[0]):
                best = (max(mts), d)
    return best[1] if best else None


def _last(tb, tag, default=None):
    pts = tb.get(tag, [])
    return pts[-1][1] if pts else default


def _policy_step(tb: dict) -> int:
    """Return the RL iteration, excluding RSL-RL's ``*/time`` wall-time x-axis tags."""
    for tag in ("Train/mean_reward", "Loss/value_function", "Policy/mean_noise_std"):
        points = tb.get(tag, [])
        if points:
            return points[-1][0]
    return max(
        (points[-1][0] for tag, points in tb.items() if points and not tag.endswith("/time")),
        default=0,
    )


def diagnose(tb: dict) -> dict:
    f: dict = {}
    f["step"] = _policy_step(tb)
    f["reward"] = _last(tb, "Train/mean_reward")
    f["err_xy"] = _last(tb, "Metrics/base_velocity/error_vel_xy")
    f["err_yaw"] = _last(tb, "Metrics/base_velocity/error_vel_yaw")
    f["x_max"] = _last(tb, "Curriculum/lin_vel_cmd_levels/x_max")
    f["z_max"] = _last(tb, "Curriculum/lin_vel_cmd_levels/z_max")
    f["lin_rate"] = _last(tb, "Curriculum/lin_vel_cmd_levels/success_rate")
    f["yaw_rate"] = _last(tb, "Curriculum/lin_vel_cmd_levels/yaw_success_rate")
    f["noise_std"] = _last(tb, "Policy/mean_noise_std")
    f["bad_orient"] = tbc.median(tbc.window(tb.get("Episode_Termination/bad_orientation", []), WINDOW))
    f["reward_med"] = tbc.median(tbc.window(tb.get("Train/mean_reward", []), WINDOW))
    f["err_xy_med"] = tbc.median(tbc.window(tb.get("Metrics/base_velocity/error_vel_xy", []), WINDOW))
    f["err_yaw_med"] = tbc.median(tbc.window(tb.get("Metrics/base_velocity/error_vel_yaw", []), WINDOW))
    f["time_out_med"] = tbc.median(tbc.window(tb.get("Episode_Termination/time_out", []), WINDOW))
    value_loss = tbc.window(tb.get("Loss/value_function", []), VALUE_LOSS_WINDOW)
    f["value_loss_med"] = tbc.median(value_loss)
    # Transient tolerance: also require the *preceding* 200-iteration window to be already
    # elevated (> 10% of the abort threshold). A single-window spike usually recovers on its
    # own and must not burn the LR-reduction + fresh-restart action (a fresh restart also
    # drops the terrain curriculum to 0); a sustained divergence is caught at the next
    # 6-hourly check at the latest.
    prev_value_loss = tbc.window(tb.get("Loss/value_function", []), VALUE_LOSS_WINDOW * 2)
    f["value_loss_prev_med"] = tbc.median(prev_value_loss[:-VALUE_LOSS_WINDOW])
    f["value_diverged"] = (
        len(value_loss) >= MIN_DIVERGENCE_SAMPLES
        and f["value_loss_med"] is not None
        and f["value_loss_med"] > VALUE_LOSS_ABORT
        and (f["value_loss_prev_med"] is None or f["value_loss_prev_med"] > VALUE_LOSS_ABORT / 10.0)
    )
    lr = tbc.window(tb.get("Loss/learning_rate", []), WINDOW)
    f["lr_pinned_frac"] = round(sum(1 for v in lr if v <= 1.1e-5) / len(lr), 3) if lr else 0.0

    f["reward_flat"] = tbc.is_flat(tb.get("Train/mean_reward", []), WINDOW, 0.03)
    f["err_xy_flat"] = tbc.is_flat(tb.get("Metrics/base_velocity/error_vel_xy", []), WINDOW, 0.03)
    f["err_yaw_flat"] = tbc.is_flat(tb.get("Metrics/base_velocity/error_vel_yaw", []), WINDOW, 0.03)
    f["x_flat"] = tbc.is_flat(tb.get("Curriculum/lin_vel_cmd_levels/x_max", []), WINDOW, 0.001)
    f["z_flat"] = tbc.is_flat(tb.get("Curriculum/lin_vel_cmd_levels/z_max", []), WINDOW, 0.001)
    _, f["reward_rel"] = tbc.trend(tb.get("Train/mean_reward", []), WINDOW)
    _, f["err_xy_rel"] = tbc.trend(tb.get("Metrics/base_velocity/error_vel_xy", []), WINDOW)
    _, f["err_yaw_rel"] = tbc.trend(tb.get("Metrics/base_velocity/error_vel_yaw", []), WINDOW)
    _, f["time_out_rel"] = tbc.trend(tb.get("Episode_Termination/time_out", []), WINDOW)
    _, f["bad_orient_rel"] = tbc.trend(tb.get("Episode_Termination/bad_orientation", []), WINDOW)
    f["trend_samples"] = min(
        len(tb.get("Train/mean_reward", [])),
        len(tb.get("Metrics/base_velocity/error_vel_xy", [])),
        len(tb.get("Metrics/base_velocity/error_vel_yaw", [])),
        len(tb.get("Episode_Termination/time_out", [])),
        len(tb.get("Episode_Termination/bad_orientation", [])),
        WINDOW,
    )

    reward_down = f["reward_rel"] <= REWARD_DEGRADE_REL
    adverse = []
    if f["err_xy_rel"] >= TRACKING_DEGRADE_REL:
        adverse.append(f"err_xy {f['err_xy_rel']:+.0%}")
    if f["err_yaw_rel"] >= TRACKING_DEGRADE_REL:
        adverse.append(f"err_yaw {f['err_yaw_rel']:+.0%}")
    if f["time_out_rel"] <= TIMEOUT_DEGRADE_REL:
        adverse.append(f"time_out {f['time_out_rel']:+.0%}")
    if (f["bad_orient"] or 0.0) > 0.02 and f["bad_orient_rel"] >= FALL_DEGRADE_REL:
        adverse.append(f"bad_orientation {f['bad_orient_rel']:+.0%}")
    f["degradation_reasons"] = ([f"reward {f['reward_rel']:+.0%}"] if reward_down else []) + adverse
    if f["value_diverged"]:
        f["degradation_reasons"].insert(0, f"value_loss median {f['value_loss_med']:.3g}")
    enough_trend = f["trend_samples"] >= WINDOW // 2
    f["degrading"] = f["value_diverged"] or (
        enough_trend and ((reward_down and bool(adverse)) or len(adverse) >= 2)
    )

    f["plateau"] = (
        f["reward_flat"] and f["err_xy_flat"] and f["err_yaw_flat"] and f["x_flat"] and f["z_flat"]
    )
    f["yaw_stuck"] = bool(
        f["z_flat"] and f["yaw_rate"] is not None and f["yaw_rate"] < 0.6 and (f["err_yaw"] or 0.0) > 0.4
    )
    f["lin_stuck"] = bool(
        f["x_flat"] and f["lin_rate"] is not None and f["lin_rate"] < 0.6 and (f["err_xy"] or 0.0) > 0.3
    )
    f["exploration_collapsed"] = f["noise_std"] is not None and f["noise_std"] < 0.2
    f["falls_rising"] = (f["bad_orient"] or 0.0) > 0.02 and f["bad_orient_rel"] > 0.1
    # Command curriculum still has room left (limits are +-1.0 m/s and +-1.0 rad/s).
    f["range_incomplete"] = (f["x_max"] is None or f["x_max"] < 0.9) or (f["z_max"] is None or f["z_max"] < 0.9)
    return f


# ---------------------------------------------------------------------------
# Knob read / write
# ---------------------------------------------------------------------------
def _scope_bounds(text: str, scope: str | None) -> tuple[int, int]:
    if not scope:
        return 0, len(text)
    m = re.search(re.escape(scope), text)
    if not m:
        raise RuntimeError(f"scope {scope!r} not found")
    nxt = re.search(r"\n(?=@configclass|class |def )", text[m.end():])
    end = m.end() + nxt.start() + 1 if nxt else len(text)
    return m.start(), end


def read_knob(name: str) -> float:
    knob = KNOBS[name]
    text = (REPO / knob["file"]).read_text()
    s, e = _scope_bounds(text, knob.get("scope"))
    m = re.search(knob["pattern"], text[s:e], re.MULTILINE)
    if not m:
        raise RuntimeError(f"pattern for knob {name!r} not found in {knob['file']}")
    return float(m.group("v"))


def _format_value(knob: dict, value: float) -> str:
    if knob["kind"] is int:
        return str(int(round(value)))
    return knob.get("fmt", "{}").format(value)


def _new_value(knob: dict, old: float) -> float:
    v = old + knob["arg"] if knob["op"] == "add" else old * knob["arg"]
    v = max(knob["lo"], min(knob["hi"], v))
    return int(round(v)) if knob["kind"] is int else v


def set_knob(name: str, value: float, tag: str) -> tuple[float, Path, Path]:
    """Backup and rewrite one knob. Returns ``(old_value, backup_path, diff_path)``."""
    knob = KNOBS[name]
    path = REPO / knob["file"]
    text = path.read_text()
    s, e = _scope_bounds(text, knob.get("scope"))
    seg = text[s:e]
    m = re.search(knob["pattern"], seg, re.MULTILINE)
    if not m:
        raise RuntimeError(f"pattern for knob {name!r} not found in {knob['file']}")
    old = float(m.group("v"))
    backup = BACKUP_DIR / tag / knob["file"]
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    new_seg = seg[: m.start("v")] + _format_value(knob, value) + seg[m.end("v"):]
    new_text = text[:s] + new_seg + text[e:]
    path.write_text(new_text)
    diff_path = BACKUP_DIR / tag / "change.diff"
    diff_path.write_text(
        "".join(
            difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{knob['file']}",
                tofile=f"b/{knob['file']}",
            )
        )
    )
    return old, backup, diff_path


def _compile_guard() -> tuple[bool, str]:
    files = sorted({str(REPO / k["file"]) for k in KNOBS.values()})
    r = subprocess.run([PY, "-m", "py_compile", *files], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


# ---------------------------------------------------------------------------
# Decision rules (priority order, one knob per action)
# ---------------------------------------------------------------------------
def _used(state: dict, knob: str) -> int:
    return sum(1 for a in state.get("actions", []) if a.get("knob") == knob and a.get("status") != "reverted")


def decide(f: dict, state: dict):
    def pick(knob: str, reason: str, budget: int):
        if _used(state, knob) >= budget:
            return None
        old = read_knob(knob)
        new = _new_value(KNOBS[knob], old)
        if abs(new - old) < 1e-12:
            return None
        return {"knob": knob, "old": old, "new": new, "reason": reason}

    # Learning-pressure rules additionally require plateau + unfinished curriculum, so a
    # healthy converged run (high noise is not needed once everything is maxed) is left alone.
    # The 5th tuple field marks degradation-class rules: those need CONFIRM_CHECKS consecutive
    # observations (see the confirmation gate in main) because their action stops + restarts
    # training and curve dips may recover on their own.
    learning_stalled = f["plateau"] and f["range_incomplete"]
    degradation = ", ".join(f["degradation_reasons"])
    rules = [
        (f["value_diverged"], "learning_rate",
         f"value function diverged, sustained (last {VALUE_LOSS_WINDOW} median={f['value_loss_med']:.3g}, "
         f"prev window median={'%.3g' % f['value_loss_prev_med'] if f['value_loss_prev_med'] is not None else 'n/a'})", 3, False),
        (f["degrading"] and "bad_orientation" in degradation, "flat_orientation_l2",
         f"curve degradation ({degradation})", 2, True),
        (f["degrading"] and "err_yaw" in degradation, "track_ang_vel_z",
         f"curve degradation ({degradation})", 2, True),
        (f["degrading"] and "err_xy" in degradation, "track_lin_vel_xy",
         f"curve degradation ({degradation})", 2, True),
        (learning_stalled and f["exploration_collapsed"], "init_noise_std",
         "plateaued with collapsed exploration (mean_noise_std<0.2)", 1, False),
        (learning_stalled and f["lr_pinned_frac"] > 0.4, "desired_kl",
         "plateaued with adaptive LR pinned at its floor", 2, False),
        (f["falls_rising"], "flat_orientation_l2", "fall rate rising", 2, True),
        (f["yaw_stuck"], "track_ang_vel_z", "yaw gate stuck + poor yaw tracking", 2, False),
        (f["lin_stuck"], "track_lin_vel_xy", "lin gate stuck + poor xy tracking", 2, False),
        (f["plateau"] and f["yaw_stuck"], "success_yaw", "yaw gate stuck -> relax yaw threshold", 2, False),
        (f["plateau"] and f["lin_stuck"], "success_xy", "lin gate stuck -> relax xy threshold", 2, False),
        (learning_stalled, "entropy_coef", "plateaued -> more exploration bonus", 2, False),
        (learning_stalled, "desired_kl", "plateaued -> allow larger policy updates", 3, False),
    ]
    for cond, knob, reason, budget, needs_confirm in rules:
        if cond:
            act = pick(knob, reason, budget)
            if act:
                act["needs_confirm"] = needs_confirm
                return act
    return None


# ---------------------------------------------------------------------------
# Process control
# ---------------------------------------------------------------------------
def train_pids() -> list[int]:
    r = subprocess.run(["pgrep", "-f", TRAIN_PATTERN], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


def stop_training(timeout: float = 25.0) -> str:
    """SIGTERM (then SIGKILL) only the pids matching the training command line.

    Deliberately avoids ``killpg`` so the interactive terminal / monitor process group is
    never touched.
    """
    pids = train_pids()
    if not pids:
        return "no training process found (already stopped)"
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + timeout
    while time.time() < deadline and train_pids():
        time.sleep(1)
    left = train_pids()
    for pid in left:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    if left:
        time.sleep(2)
    return f"stopped pids {pids}" + (f" (SIGKILL for {left})" if left else " (SIGTERM)")


def latest_checkpoint(run_dir: Path) -> Path | None:
    ckpts = sorted(
        run_dir.glob("model_*.pt"),
        key=lambda p: int(p.stem.rsplit("_", 1)[-1]),
    )
    return ckpts[-1] if ckpts else None


def _next_log() -> Path:
    i = 1
    while Path(f"/tmp/train_go2_v{i}.log").exists():
        i += 1
    return Path(f"/tmp/train_go2_v{i}.log")


def launch(run_dir: Path, mode: str) -> tuple[int, Path, str]:
    env = dict(os.environ, ISAACLAB_PATH=ISAACLAB_PATH, http_proxy=PROXY, https_proxy=PROXY)
    cmd = [PY, str(REPO / "scripts" / "rsl_rl" / "train.py"), "--headless",
           "--task", TASK, "--num_envs", str(NUM_ENVS)]
    if mode == "resume":
        ckpt = latest_checkpoint(run_dir)
        if ckpt is None:
            mode = "fresh"
        else:
            cmd += ["--resume", "--load_run", run_dir.name, "--checkpoint", ckpt.name]
    log = _next_log()
    with open(log, "ab") as fh:
        proc = subprocess.Popen(
            cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True, env=env
        )
    time.sleep(LAUNCH_GRACE_S)
    return_code = proc.poll()
    if return_code is not None:
        raise RuntimeError(f"training exited during startup (exit={return_code}, log={log})")
    return proc.pid, log, mode


# ---------------------------------------------------------------------------
# State / ledger
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"actions": [], "last_action_step": -10**9, "last_action_ts": 0.0}


def cooldown_reason(f: dict, state: dict, run_name: str, now: float | None = None) -> str | None:
    """Return a guard reason, keeping iteration cooldowns local to one TensorBoard run."""
    if f["step"] < MIN_START_ITERS:
        return f"too early: step {f['step']} < {MIN_START_ITERS}"
    now = time.time() if now is None else now
    elapsed = now - state.get("last_action_ts", 0.0)
    if elapsed < MIN_SECONDS_BETWEEN_ACTIONS:
        return f"wall-clock cooldown active ({elapsed / 3600:.1f}h < {MIN_SECONDS_BETWEEN_ACTIONS / 3600:.1f}h)"
    actions = state.get("actions", [])
    last_run = state.get("last_action_run")
    if last_run is None and actions:
        last_run = actions[-1].get("run")
    if last_run == run_name and f["step"] - state.get("last_action_step", -10**9) < MIN_ITERS_BETWEEN_ACTIONS:
        return "iteration cooldown active"
    if len([a for a in actions if a.get("status") == "applied"]) >= MAX_ACTIONS:
        return f"global action cap reached ({MAX_ACTIONS})"
    return None


def observation(f: dict, run_name: str) -> dict:
    return {
        "run": run_name,
        "step": f["step"],
        "reward": f["reward_med"],
        "err_xy": f["err_xy_med"],
        "err_yaw": f["err_yaw_med"],
        "time_out": f["time_out_med"],
        "bad_orientation": f["bad_orient"],
        "value_loss": f["value_loss_med"],
        "value_diverged": f["value_diverged"],
        "degrading": f["degrading"],
        "degradation_reasons": f["degradation_reasons"],
        "ts": time.time(),
    }


def save_state(state: dict) -> None:
    AUTODIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def append_ledger(entry: dict) -> None:
    AUTODIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


def recover_after_failed_action(run_dir: Path, knob: str, backup: Path | None, error: Exception) -> str:
    """Restore source if necessary and resume the run stopped for an unsuccessful edit."""
    restored = "no source change to restore"
    if backup is not None and backup.exists():
        shutil.copy2(backup, REPO / KNOBS[knob]["file"])
        restored = f"restored {backup}"
    try:
        pid, logf, mode = launch(run_dir, "resume")
        recovery = f"recovered training pid={pid} mode={mode} log={logf}"
    except Exception as recovery_error:
        recovery = f"RECOVERY FAILED: {recovery_error!r}"
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": "apply_failed",
        "run": run_dir.name,
        "knob": knob,
        "error": repr(error),
        "restored": restored,
        "recovery": recovery,
        "status": "failed",
    }
    append_ledger(entry)
    return f"APPLY FAILED: {error!r}; {restored}; {recovery}"


def rollback() -> int:
    state = load_state()
    acts = [a for a in state.get("actions", []) if a.get("status") == "applied"]
    if not acts:
        log("nothing to roll back")
        return 0
    last = acts[-1]
    backup = Path(last["backup"])
    if not backup.exists():
        log(f"backup missing: {backup}")
        return 1
    target = REPO / last["file"]
    shutil.copy2(backup, target)
    last["status"] = "reverted"
    save_state(state)
    append_ledger({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "rollback",
                   "knob": last["knob"], "restored_from": str(backup)})
    log(f"rolled back {last['knob']} to {last['old']}")
    if train_pids():
        log(stop_training())
        pid, logf, mode = launch(latest_run_dir(), KNOBS[last["knob"]]["restart"])
        log(f"relaunched (pid {pid}, mode {mode}) -> {logf}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Rule-based auto-tuner for GO2 velocity training.")
    ap.add_argument("--run-dir", type=str, default=None)
    ap.add_argument("--dry-run", action="store_true", help="diagnose + print the plan, change nothing")
    ap.add_argument("--force", action="store_true", help="ignore cooldowns / start-iteration guard")
    ap.add_argument("--rollback", action="store_true", help="restore the newest backup and relaunch")
    ap.add_argument("--list", action="store_true", help="print current knob values and exit")
    args = ap.parse_args()

    if args.list:
        for name, knob in KNOBS.items():
            try:
                log(f"{name:22s} = {read_knob(name):g}  [{knob['restart']:6s}] {knob['desc']}")
            except Exception as exc:
                log(f"{name:22s} = ? ({exc})")
        return 0

    if args.rollback:
        return rollback()

    if DISABLE_FILE.exists():
        log(f"DISABLED by {DISABLE_FILE}")
        return 0

    run_dir = Path(args.run_dir) if args.run_dir else latest_run_dir()
    if run_dir is None:
        log("no run dir found")
        return 0
    tb = tbc.load_scalars(run_dir)
    f = diagnose(tb)
    log(f"run={run_dir.name} step={f['step']} reward={f['reward']} "
        f"err_xy={f['err_xy']} err_yaw={f['err_yaw']} noise_std={f['noise_std']} "
        f"x_max={f['x_max']} z_max={f['z_max']} lr_pin={f['lr_pinned_frac']}")
    log(f"flags: degrading={f['degrading']} value_diverged={f['value_diverged']} "
        f"reasons={f['degradation_reasons']} plateau={f['plateau']} "
        f"yaw_stuck={f['yaw_stuck']} lin_stuck={f['lin_stuck']} "
        f"exploration_collapsed={f['exploration_collapsed']} falls_rising={f['falls_rising']}")

    state = load_state()
    if not args.force:
        guard = cooldown_reason(f, state, run_dir.name)
        if guard:
            if not args.dry_run:
                state["last_observation"] = observation(f, run_dir.name)
                save_state(state)
            log(guard)
            return 0

    action = decide(f, state)
    if action is None:
        log("no intervention needed")
        state.pop("pending_confirm", None)  # the degradation did not reproduce -> forgive
        if not args.dry_run:
            state["last_observation"] = observation(f, run_dir.name)
            save_state(state)
        return 0

    # Transient tolerance gate: degradation-class actions must be observed at CONFIRM_CHECKS
    # consecutive checks of the same run before stopping/restarting training.
    if action.get("needs_confirm") and not args.force:
        pend = state.get("pending_confirm") or {}
        count = pend.get("count", 0) + 1 if (
            pend.get("knob") == action["knob"] and pend.get("run") == run_dir.name
        ) else 1
        if count < CONFIRM_CHECKS:
            log(f"PLAN (pending {count}/{CONFIRM_CHECKS}): {action['knob']} {action['old']:g} -> "
                f"{action['new']:g} ({action['reason']}) - transient tolerated, confirm at the next check")
            if not args.dry_run:
                state["pending_confirm"] = {
                    "knob": action["knob"], "run": run_dir.name, "count": count,
                    "reason": action["reason"], "ts": time.time(),
                }
                state["last_observation"] = observation(f, run_dir.name)
                save_state(state)
            return 0
        log(f"degradation confirmed at {count}/{CONFIRM_CHECKS} consecutive checks - acting")

    log(f"PLAN: {action['knob']} {action['old']:g} -> {action['new']:g} ({action['reason']}) "
        f"restart={KNOBS[action['knob']]['restart']}")

    if args.dry_run:
        log("dry-run: nothing changed")
        return 0

    tag = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_dir.name}"
    stop_msg = stop_training()
    log(stop_msg)
    backup: Path | None = None
    try:
        old, backup, diff_path = set_knob(action["knob"], action["new"], tag)
        ok, err = _compile_guard()
        if not ok:
            raise RuntimeError(f"compile guard failed: {err}")
        pid, logf, mode = launch(run_dir, KNOBS[action["knob"]]["restart"])
    except Exception as exc:
        log(recover_after_failed_action(run_dir, action["knob"], backup, exc))
        return 1
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run": run_dir.name, "step": f["step"], "knob": action["knob"],
        "old": old, "new": action["new"], "reason": action["reason"],
        "restart": mode, "file": KNOBS[action["knob"]]["file"], "backup": str(backup),
        "diff": str(diff_path),
        "new_pid": pid, "log": str(logf), "status": "applied",
        "findings": {k: f[k] for k in ("reward", "err_xy", "err_yaw", "noise_std", "x_max", "z_max")},
    }
    state.setdefault("actions", []).append(entry)
    state["last_action_step"] = f["step"]
    state["last_action_run"] = run_dir.name
    state["last_action_ts"] = time.time()
    state.pop("pending_confirm", None)
    state["last_observation"] = observation(f, run_dir.name)
    save_state(state)
    append_ledger(entry)
    log(f"APPLIED: {action['knob']}={action['new']:g}; relaunched mode={mode} pid={pid} log={logf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

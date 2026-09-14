#!/usr/bin/env python
"""4-hourly health check for the GO2 velocity RL run.

Run manually or from the nohup loop::

    nohup bash -c 'while true; do $PY scripts/monitor_tb_check.py >> outputs/monitor/monitor.log 2>&1; sleep 14400; done' &

Per check it
  1. verifies the training process is alive -- if dead, auto-resumes from the latest
     checkpoint of the newest run dir (crash-loop guard: at most one auto-resume per 10 min);
     auto-resume is SUPPRESSED while a stop marker is set (see 2.);
  2. counts *new* "Patch buffer overflow" lines since the previous check in /tmp/train_go2_v*.log
     (PhysX overflow has no TensorBoard tag -- the log is the only observation channel);
     on ANY new overflow line it IMMEDIATELY stops the training process group
     (SIGTERM, SIGKILL after 15 s) and sets a stop marker so the poisoned run is not
     auto-resumed (marker auto-clears once a newer run writes TensorBoard data);
  3. snapshots the key TensorBoard curves (last 200 iterations) of the newest run dir;
  4. raises anomaly flags against the previous snapshot (frozen curriculum, LR pinned at the
     floor, time_out collapse, reward drop, new PhysX overflow).

Human-readable report: outputs/monitor/report.md (appended).
Persistent state (log offsets, previous snapshot, last auto-resume time, stop marker): outputs/monitor/state.json.
"""

from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO / "logs" / "rsl_rl" / "unitree_go2_velocity"
MON_DIR = REPO / "outputs" / "monitor"
STATE_PATH = MON_DIR / "state.json"
REPORT_PATH = MON_DIR / "report.md"

PY = "/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python"
TASK = "Unitree-Go2-Velocity"
NUM_ENVS = 22000
LOG_GLOB = "/tmp/train_go2_v*.log"
TRAIN_PATTERN = r"train\.py.*Unitree-Go2-Velocity"
LAST_N = 200  # iterations considered for the snapshot
RESUME_COOLDOWN_S = 600  # crash-loop guard for auto-resume

# TensorBoard tag -> short key used in the snapshot/report
KEY_TAGS = {
    "Curriculum/terrain_levels": "level",
    "Curriculum/lin_vel_cmd_levels": "range",
    "Metrics/base_velocity/error_vel_xy": "err_xy",
    "Metrics/base_velocity/error_vel_yaw": "err_yaw",
    "Train/mean_reward": "reward",
    "Episode_Termination/time_out": "time_out",
    "Loss/learning_rate": "lr",
    "Perf/total_fps": "fps",
}
SNAP_KEYS = ("level", "range", "err_xy", "err_yaw", "reward", "time_out", "lr", "fps")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def train_pids() -> list[int]:
    r = subprocess.run(["pgrep", "-f", TRAIN_PATTERN], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


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


def load_tb(run_dir: Path) -> dict[str, list[tuple[int, float]]]:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    ea = EventAccumulator(str(run_dir), size_guidance={"scalars": 0})
    ea.Reload()
    out: dict[str, list[tuple[int, float]]] = {}
    for tag in ea.Tags().get("scalars", []):
        out[tag] = [(e.step, e.value) for e in ea.Scalars(tag)]
    return out


def summarize(points: list[tuple[int, float]]) -> dict | None:
    if not points:
        return None
    vals = [v for _, v in points[-LAST_N:]]
    s = sorted(vals)
    return {
        "min": round(min(vals), 4),
        "med": round(s[len(s) // 2], 4),
        "max": round(max(vals), 4),
        "last": round(vals[-1], 4),
        "last_step": points[-LAST_N:][-1][0],
        "n": len(vals),
    }


def snapshot(tb: dict[str, list[tuple[int, float]]]) -> dict:
    snap = {}
    for tag, key in KEY_TAGS.items():
        s = summarize(tb.get(tag, []))
        if s is not None:
            snap[key] = s
    lr_pts = tb.get("Loss/learning_rate", [])
    if lr_pts:
        last = [v for _, v in lr_pts[-LAST_N:]]
        snap["lr_pin_frac"] = round(sum(1 for v in last if v <= 1.1e-5) / len(last), 3)
    return snap


def overflow_new(state: dict) -> int:
    """Count 'Patch buffer overflow' lines appended to the training logs since the last check.

    Files seen for the first time are baselined (their history is not counted), so a fresh
    monitor does not flag overflows from older runs (e.g. v3's 98145).
    """
    total = 0
    offs = state.setdefault("log_offsets", {})
    for p in sorted(glob.glob(LOG_GLOB)):
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        off = offs.get(p)
        if off is None:
            offs[p] = size
            continue
        if size < off:  # log rotated/truncated
            offs[p] = size
            continue
        with open(p, "rb") as f:
            f.seek(off)
            chunk = f.read(size - off)
        total += chunk.count(b"Patch buffer overflow")
        offs[p] = size
    return total


def try_auto_resume(state: dict, run_dir: Path | None) -> str:
    last = state.get("auto_resume_at", 0.0)
    if time.time() - last < RESUME_COOLDOWN_S:
        return "cooldown active (crash-loop guard) - manual restart needed"
    ckpts: list[Path] = []
    if run_dir is not None:
        ckpts = sorted(
            (p for p in run_dir.glob("model_*.pt")),
            key=lambda p: int(p.stem.rsplit("_", 1)[-1]),
        )
    if not ckpts:
        return "no checkpoint available - manual restart needed"
    ckpt = ckpts[-1]
    logf = open("/tmp/train_go2_auto.log", "ab")
    env = dict(
        os.environ,
        ISAACLAB_PATH="/home/css/work/unitree/rl/unitree_Robert/isaaclab/IsaacLab",
        https_proxy="http://127.0.0.1:7897",
        http_proxy="http://127.0.0.1:7897",
    )
    cmd = [
        PY, str(REPO / "scripts" / "rsl_rl" / "train.py"), "--headless",
        "--task", TASK, "--num_envs", str(NUM_ENVS),
        "--resume", "--load_run", run_dir.name, "--checkpoint", ckpt.name,
    ]
    subprocess.Popen(cmd, cwd=REPO, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True, env=env)
    state["auto_resume_at"] = time.time()
    return f"auto-resumed from {run_dir.name}/{ckpt.name} (log: /tmp/train_go2_auto.log)"


def stop_training(reason: str) -> str:
    """Stop the training process group (bash wrapper + python + tee): SIGTERM, then SIGKILL.

    Only process groups containing pids that match TRAIN_PATTERN are touched; pgid 1 (init)
    and the monitor's own group are never killed. Returns a human-readable action string.
    """
    pids = train_pids()
    if not pids:
        return "no training process found (already dead) - stop marker set anyway"
    own_pgid = os.getpgid(os.getpid())
    groups: dict[int, list[int]] = {}
    for pid in pids:
        try:
            pgid = os.getpgid(pid)
        except OSError:
            continue
        if pgid <= 1 or pgid == own_pgid:  # defensive: never kill init or our own group
            continue
        groups.setdefault(pgid, []).append(pid)
    if not groups:
        return "DEFENSIVE GUARD: no killable process group found - check manually!"
    for pgid in groups:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    upgraded = False
    deadline = time.time() + 15.0
    while time.time() < deadline and train_pids():
        time.sleep(1)
    if train_pids():
        upgraded = True
        for pid in train_pids():
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
        time.sleep(1)
    sig = "SIGTERM+SIGKILL" if upgraded else "SIGTERM"
    return f"killed pgid(s) {sorted(groups)} pids {pids} with {sig}; reason: {reason}"


def clear_stale_marker(state: dict, run_dir: Path | None) -> str | None:
    """Drop the stop marker once a (re)started run writes data newer than the stop time.

    A manual restart (new run dir, or fresh tfevents in the resumed dir) means the human has
    already acted on the overflow stop, so normal crash auto-resume is allowed again.
    """
    marker = state.get("stop_marker")
    if not marker or run_dir is None:
        return None
    mts = [p.stat().st_mtime for p in run_dir.glob("events.out.tfevents.*")]
    if mts and max(mts) > marker.get("at", 0.0):
        del state["stop_marker"]
        return f"cleared stop marker ({marker.get('reason', '?')}) - newer run activity in {run_dir.name}"
    return None


def overflow_evidence() -> str:
    """Per-log total overflow count + last overflow line (truncated) for the stop record."""
    bits: list[str] = []
    for p in sorted(glob.glob(LOG_GLOB)):
        try:
            size = os.path.getsize(p)
            with open(p, "rb") as f:
                f.seek(max(0, size - 65536))
                tail = f.read()
        except OSError:
            continue
        idx = tail.rfind(b"Patch buffer overflow")
        if idx < 0:
            continue
        r = subprocess.run(["grep", "-c", "Patch buffer overflow", p], capture_output=True, text=True)
        line = tail[: idx + 90]
        line = line[line.rfind(b"\n") + 1 :]
        bits.append(
            f"{os.path.basename(p)}: total={r.stdout.strip() or '?'}, "
            f"last: {line.decode(errors='replace').strip()[:120]}"
        )
    return "; ".join(bits) if bits else "no overflow line found in recent log tails"


def main() -> None:
    MON_DIR.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    prev_snap = state.get("snap", {})
    prev_check = state.get("last_check", 0.0)

    actions: list[str] = []
    flags: list[str] = []

    run_dir = latest_run_dir()
    note = clear_stale_marker(state, run_dir)
    if note:
        actions.append(note)

    pids = train_pids()
    alive = bool(pids)

    ov = overflow_new(state)
    if ov:
        flags.append(f"CRITICAL: {ov} new 'Patch buffer overflow' lines since last check")
        # Any new overflow line means the physics pipeline is broken (narrowphase patch pool
        # exhausted -> silently skipped collisions -> poisoned rollout data): stop now.
        actions.append("AUTO-STOP on new PhysX overflow: " + stop_training(f"{ov} new 'Patch buffer overflow' lines"))
        state["stop_marker"] = {
            "at": time.time(),
            "reason": f"{ov} new 'Patch buffer overflow' lines",
            "evidence": overflow_evidence(),
        }
        pids = train_pids()
        alive = bool(pids)

    if not alive:
        flags.append("CRITICAL: training process DEAD")
        if state.get("stop_marker"):
            actions.append(
                f"auto-resume SUPPRESSED (stop marker: {state['stop_marker'].get('reason', '?')}) - manual restart needed"
            )
        else:
            actions.append("process dead -> " + try_auto_resume(state, run_dir))
    snap: dict = {}
    if run_dir is not None:
        try:
            snap = snapshot(load_tb(run_dir))
        except Exception as e:  # keep the monitor alive even if TB is unreadable
            actions.append(f"TB read failed: {e!r}")

    to = snap.get("time_out", {})
    if to.get("n", 0) >= 50 and to.get("med") is not None and to["med"] < 0.85:
        flags.append(f"WARN: time_out median {to['med']} < 0.85")
    if snap.get("lr", {}).get("n", 0) >= 50 and snap.get("lr_pin_frac", 0.0) > 0.25:
        flags.append(f"WARN: LR pinned at 1e-5 for {snap['lr_pin_frac'] * 100:.0f}% of last {LAST_N} iters")
    prev_reward = prev_snap.get("reward", {}).get("med")
    if (
        prev_reward
        and snap.get("reward", {}).get("n", 0) >= 50
        and snap["reward"]["med"] < 0.6 * prev_reward
    ):
        flags.append(f"WARN: mean_reward {snap['reward']['med']} < 0.6 x previous {prev_reward}")
    if snap and prev_snap:
        d_level = abs(snap.get("level", {}).get("last", 0.0) - prev_snap.get("level", {}).get("last", 0.0))
        d_range = abs(snap.get("range", {}).get("last", 0.0) - prev_snap.get("range", {}).get("last", 0.0))
        hours_since_prev = (time.time() - prev_check) / 3600.0
        if d_level < 0.01 and d_range < 0.01 and hours_since_prev > 5.5:
            flags.append("WARN: level & range frozen over the last check window")

    lines = [f"## {now_str()} check", ""]
    lines.append(f"- process: {'ALIVE (pid ' + ', '.join(map(str, pids)) + ')' if alive else 'DEAD'}")
    for a in actions:
        lines.append(f"- action: {a}")
    lines.append(f"- physx_overflow_new: {ov}")
    if state.get("stop_marker"):
        lines.append(f"- stop_marker: {state['stop_marker'].get('reason', '?')} (auto-resume suppressed)")
    if run_dir is not None:
        step = next((snap[k]["last_step"] for k in SNAP_KEYS if k in snap), None)
        lines.append(f"- run: {run_dir.name} (last step {step})")
    if snap:
        lines += ["", "| metric | last200 min | med | max | last |", "|---|---|---|---|---|"]
        for k in SNAP_KEYS:
            s = snap.get(k)
            if s:
                lines.append(f"| {k} | {s['min']} | {s['med']} | {s['max']} | {s['last']} |")
        if "lr_pin_frac" in snap:
            lines.append(f"- lr_pin_frac(<=1e-5): {snap['lr_pin_frac']}")
    lines += ["", f"- flags: {', '.join(flags) if flags else 'none'}", ""]

    with open(REPORT_PATH, "a") as f:
        f.write("\n".join(lines) + "\n")

    state["snap"] = snap
    state["last_check"] = time.time()
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"[{now_str()}] alive={alive} overflow_new={ov} run={run_dir.name if run_dir else 'N/A'} flags={flags or 'none'}")


if __name__ == "__main__":
    main()
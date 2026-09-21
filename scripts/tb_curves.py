#!/usr/bin/env python
"""TensorBoard curve helpers shared by the monitor and the auto-tuner.

Pure-python (no numpy) so it stays cheap to import from the 4-hourly monitor.
"""

from __future__ import annotations

from pathlib import Path


def load_scalars(run_dir: str | Path) -> dict[str, list[tuple[int, float]]]:
    """Load every scalar tag of the newest tfevents file in ``run_dir``."""
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    ea = EventAccumulator(str(run_dir), size_guidance={"scalars": 0})
    ea.Reload()
    out: dict[str, list[tuple[int, float]]] = {}
    for tag in ea.Tags().get("scalars", []):
        out[tag] = [(e.step, e.value) for e in ea.Scalars(tag)]
    return out


def window(points: list[tuple[int, float]], n: int) -> list[float]:
    return [v for _, v in points[-n:]]


def median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[len(s) // 2]


def trend(points: list[tuple[int, float]], n: int) -> tuple[float, float]:
    """Return ``(slope_per_iter, relative_change)`` over the last ``n`` points.

    The relative change compares the median of the first quarter against the median of the
    last quarter of the window, which is robust to the per-iteration reward noise.
    """
    pts = points[-n:]
    if len(pts) < 4:
        return 0.0, 0.0
    k = max(1, len(pts) // 4)
    first = median([v for _, v in pts[:k]])
    last = median([v for _, v in pts[-k:]])
    steps = pts[-1][0] - pts[0][0]
    slope = (last - first) / steps if steps else 0.0
    denom = max(abs(first), 1e-6)
    return slope, (last - first) / denom


def is_flat(points: list[tuple[int, float]], n: int, rel_tol: float = 0.03) -> bool:
    if len(points[-n:]) < 4:
        return True
    return abs(trend(points, n)[1]) < rel_tol


def stats(points: list[tuple[int, float]], n: int) -> dict | None:
    if not points:
        return None
    vals = window(points, n)
    s = sorted(vals)
    return {
        "min": round(min(vals), 5),
        "med": round(s[len(s) // 2], 5),
        "max": round(max(vals), 5),
        "last": round(vals[-1], 5),
        "n": len(vals),
        "last_step": points[-1][0],
        "rel_change": round(trend(points, n)[1], 5),
    }


def markdown_table(tb: dict[str, list[tuple[int, float]]], n: int, title: str = "All training curves") -> str:
    """One row per scalar tag: window stats plus the relative change (trend) over the window."""
    lines = [f"### {title} (last {n} iterations)", ""]
    if not tb:
        lines.append("_no scalars found_")
        return "\n".join(lines)
    lines += ["| tag | n | min | med | max | last | trend(rel) |", "|---|---|---|---|---|---|---|"]
    for tag in sorted(tb):
        s = stats(tb[tag], n)
        if s is None:
            continue
        lines.append(
            f"| {tag} | {s['n']} | {s['min']} | {s['med']} | {s['max']} | {s['last']} | {s['rel_change']:+.4f} |"
        )
    return "\n".join(lines)

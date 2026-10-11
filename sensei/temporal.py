"""Per-area time series of fill / level posteriors: neighbour smoothing and depletion forecast.

Rows are plain tuples ``(timestamp, fill, p_levels)`` with ``p_levels`` = (p_empty, p_half, p_full).
Smoothing over neighbouring pictures is off by default (``cfg.smoothing_weight = 0``); the series mainly
feeds the staff app's per-area timeline and the "empty in ~N min" forecast (a robust slope of the fill
since the last restock).
"""
from __future__ import annotations

import json
import logging
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

log = logging.getLogger(__name__)

Row = tuple[int, float, tuple[float, float, float]]

EMPTY_LEVEL = 0.10        # fill regarded as "empty" by the forecast
LOOKBACK_S = 3 * 3600     # forecast uses the last hours only
RESTOCK_JUMP = 0.25       # a fill increase above this starts a new depletion segment
MIN_SLOPE = 0.02 / 3600   # slower than 2 %/h -> "not depleting"
MAX_HORIZON_S = 24 * 3600


def _row(ts: Any, fill: Any, p: Any) -> Row:
    pl = tuple(float(x) for x in np.asarray(p, dtype=np.float64).reshape(-1)[:3])
    if len(pl) != 3:
        raise ValueError("p_levels must have 3 values (empty, half, full)")
    return int(ts), float(fill), pl  # type: ignore[return-value]


class AreaSeries:
    """area_id -> rows sorted by timestamp (one row per timestamp; a re-add replaces it)."""

    def __init__(self) -> None:
        self._rows: dict[str, list[Row]] = {}

    def add(self, area_id: str, timestamp: int, fill: float, p_levels: Sequence[float]) -> None:
        rows = self._rows.setdefault(area_id, [])
        r = _row(timestamp, fill, p_levels)
        i = bisect_left([x[0] for x in rows], r[0])
        if i < len(rows) and rows[i][0] == r[0]:
            rows[i] = r
        else:
            rows.insert(i, r)

    def add_many(self, area_ids: Sequence[str], timestamps: Sequence[int], fills: Sequence[float],
                 p_levels: np.ndarray) -> None:
        """Vectorised :meth:`add` (e.g. all fit-time crops)."""
        for a, t, f, p in zip(area_ids, timestamps, fills, np.asarray(p_levels)):
            self.add(a, int(t), float(f), p)

    def areas(self) -> list[str]:
        return list(self._rows)

    def rows(self, area_id: str) -> list[Row]:
        return list(self._rows.get(area_id, []))

    def neighbours(self, area_id: str, ts: int, window_s: int, include_self: bool = False) -> list[Row]:
        """Rows of the area with |t - ts| <= window_s (the row at exactly ``ts`` only if include_self)."""
        rows = self._rows.get(area_id, [])
        times = [r[0] for r in rows]
        lo, hi = bisect_left(times, ts - window_s), bisect_right(times, ts + window_s)
        return [r for r in rows[lo:hi] if include_self or r[0] != ts]

    def before(self, area_id: str, ts: int, lookback_s: int | None = None) -> list[Row]:
        """Rows with t <= ts (and t >= ts - lookback_s when given), oldest first."""
        rows = self._rows.get(area_id, [])
        times = [r[0] for r in rows]
        hi = bisect_right(times, ts)
        lo = 0 if lookback_s is None else bisect_left(times, ts - lookback_s)
        return rows[lo:hi]

    def median_fill(self, area_id: str) -> float | None:
        rows = self._rows.get(area_id)
        return float(np.median([r[1] for r in rows])) if rows else None

    def timeline(self, area_id: str, levels: Sequence[str] = ("empty", "half", "full")) -> list[list]:
        """[[ts, fill, level_name_of_argmax], ...] for the dashboard."""
        return [[t, round(f, 3), levels[int(np.argmax(p))]] for t, f, p in self._rows.get(area_id, [])]

    def __len__(self) -> int:
        return sum(len(v) for v in self._rows.values())

    # persistence (plain JSON)
    def state_dict(self) -> dict[str, list[list]]:
        return {a: [[t, f, list(p)] for t, f, p in rows] for a, rows in self._rows.items()}

    @classmethod
    def from_state(cls, d: dict[str, Iterable]) -> "AreaSeries":
        s = cls()
        for a, rows in d.items():
            for t, f, p in rows:
                s.add(a, t, f, p)
        return s

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.state_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "AreaSeries":
        return cls.from_state(json.loads(Path(path).read_text(encoding="utf-8")))


def smooth(fill_now: float, p_now: Sequence[float], neighbour_rows: Sequence[Row], cfg,
           now_ts: int | None = None) -> tuple[float, np.ndarray]:
    """Blend the frame with its time neighbours.

    Weights: 1 for the frame itself, ``cfg.smoothing_weight * k(dt)`` per neighbour with a
    Gaussian kernel of width ``cfg.smoothing_window_s`` (uniform k when ``now_ts`` is None).
    ``smoothing_weight = 0`` returns the inputs unchanged.
    """
    p_now = np.asarray(p_now, dtype=np.float64)
    sw = float(getattr(cfg, "smoothing_weight", 0.0))
    if sw <= 0 or not neighbour_rows:
        return float(fill_now), p_now
    win = max(float(getattr(cfg, "smoothing_window_s", 300)), 1.0)
    ts = np.array([r[0] for r in neighbour_rows], dtype=np.float64)
    k = np.ones(len(ts)) if now_ts is None else np.exp(-0.5 * ((ts - now_ts) / win) ** 2)
    w = np.concatenate([[1.0], sw * k])
    fills = np.concatenate([[fill_now], [r[1] for r in neighbour_rows]])
    ps = np.vstack([p_now[None, :], np.array([r[2] for r in neighbour_rows], dtype=np.float64)])
    fill = float((w * fills).sum() / w.sum())
    p = (w[:, None] * ps).sum(0)
    return fill, p / p.sum()


def forecast_empty(series_rows: Sequence, now_ts: int, lookback_s: int = LOOKBACK_S,
                   empty_level: float = EMPTY_LEVEL) -> float | None:
    """Seconds until the fill reaches ``empty_level``, from a robust (Theil-Sen) slope.

    Uses rows with t <= now_ts within ``lookback_s``, starting after the last restock jump.
    Returns 0.0 if already empty, None if fewer than 2 points or the area is not depleting.
    Rows are ``(ts, fill, ...)`` tuples or dicts with "timestamp" and "fill".
    """
    pts = []
    for r in series_rows:
        t, f = (r["timestamp"], r["fill"]) if isinstance(r, dict) else (r[0], r[1])
        if now_ts - lookback_s <= t <= now_ts:
            pts.append((int(t), float(f)))
    pts.sort()
    for i in range(len(pts) - 1, 0, -1):  # keep the segment after the last restock
        if pts[i][1] - pts[i - 1][1] > RESTOCK_JUMP:
            pts = pts[i:]
            break
    if len(pts) < 2:
        return None
    t = np.array([p[0] for p in pts], dtype=np.float64)
    f = np.array([p[1] for p in pts], dtype=np.float64)
    i, j = np.triu_indices(len(t), k=1)
    dt = t[j] - t[i]
    ok = dt > 0
    if not ok.any():
        return None
    slope = float(np.median((f[j] - f[i])[ok] / dt[ok]))
    level = float(np.median(f + slope * (now_ts - t)))  # robust level at now
    if level <= empty_level:
        return 0.0
    if slope > -MIN_SLOPE:
        return None
    eta = (level - empty_level) / -slope
    return float(eta) if eta <= MAX_HORIZON_S else None

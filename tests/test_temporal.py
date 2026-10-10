"""temporal.py: series bookkeeping, smoothing and the depletion forecast."""
from __future__ import annotations

import numpy as np
import pytest

from sensei.config import Config
from sensei.temporal import AreaSeries, forecast_empty, smooth

H = 3600
P = (0.1, 0.3, 0.6)


def _series() -> AreaSeries:
    s = AreaSeries()
    for t, f in [(3 * H, 0.5), (0, 1.0), (H, 0.8), (2 * H, 0.65)]:  # added out of order
        s.add("a", t, f, P)
    return s


def test_add_sorted_replace_and_neighbours():
    s = _series()
    assert [r[0] for r in s.rows("a")] == [0, H, 2 * H, 3 * H]
    s.add("a", H, 0.7, (0.2, 0.3, 0.5))  # same timestamp replaces
    assert len(s) == 4 and s.rows("a")[1][1] == 0.7
    assert [r[0] for r in s.neighbours("a", H, H)] == [0, 2 * H]
    assert [r[0] for r in s.neighbours("a", H, H, include_self=True)] == [0, H, 2 * H]
    assert [r[0] for r in s.before("a", 2 * H, lookback_s=H)] == [H, 2 * H]
    assert s.neighbours("missing", 0, H) == [] and s.median_fill("missing") is None
    assert s.timeline("a")[0] == [0, 1.0, "full"]


def test_add_many_and_roundtrip(tmp_path):
    s = AreaSeries()
    s.add_many(["a", "b", "a"], [10, 20, 5], [0.1, 0.2, 0.3], np.array([P, P, P]))
    path = tmp_path / "series.json"
    s.save(path)
    s2 = AreaSeries.load(path)
    assert s2.rows("a") == s.rows("a") and s2.rows("b") == s.rows("b")
    assert AreaSeries.from_state(s.state_dict()).rows("a")[0] == (5, 0.3, P)


def test_smooth_default_is_noop():
    fill, p = smooth(0.4, P, _series().rows("a"), Config(), now_ts=H)
    assert fill == 0.4 and np.allclose(p, P)


def test_smooth_blends_and_decays_with_time():
    cfg = Config(smoothing_weight=1.0, smoothing_window_s=600)
    near = [(1000 + 60, 1.0, (0.0, 0.0, 1.0))]
    far = [(1000 + 6000, 1.0, (0.0, 0.0, 1.0))]
    f_near, p_near = smooth(0.0, (1.0, 0.0, 0.0), near, cfg, now_ts=1000)
    f_far, _ = smooth(0.0, (1.0, 0.0, 0.0), far, cfg, now_ts=1000)
    assert 0.4 < f_near < 0.5 and f_far < 0.01
    assert p_near.sum() == pytest.approx(1.0)


def test_forecast_linear_depletion():
    rows = [(t, 1.0 - 0.2 * t / H, P) for t in (0, H, 2 * H, 3 * H)]  # 1.0 -> 0.4, 20 %/h
    eta = forecast_empty(rows, now_ts=3 * H)
    assert eta == pytest.approx((0.4 - 0.1) / 0.2 * H, rel=1e-6)


def test_forecast_none_cases_and_empty():
    assert forecast_empty([(0, 0.5, P)], now_ts=0) is None                       # one point
    assert forecast_empty([(0, 0.3, P), (H, 0.6, P), (2 * H, 0.9, P)], 2 * H) is None  # restocked / rising
    assert forecast_empty([(0, 0.8, P), (H, 0.8, P)], H) is None                 # flat
    assert forecast_empty([(0, 0.3, P), (H, 0.05, P)], H) == 0.0                 # already empty
    assert forecast_empty([(0, 0.9, P), (H, 0.88, P)], H) is None                # beyond 24 h horizon


def test_forecast_after_restock_and_outlier_and_dicts():
    rows = [(0, 0.2, P), (H, 1.0, P), (2 * H, 0.9, P), (3 * H, 0.8, P)]  # restock at 1 h
    assert forecast_empty(rows, 3 * H) == pytest.approx(0.7 / 0.1 * H, rel=1e-6)
    noisy = [(0, 1.0), (H, 0.9), (2 * H, 0.3), (3 * H, 0.7), (4 * H, 0.6)]  # one dip (occlusion)
    eta = forecast_empty([{"timestamp": t, "fill": f} for t, f in noisy], 4 * H, lookback_s=5 * H)
    assert eta is not None and 4 * H < eta < 6 * H
    assert forecast_empty(rows, 3 * H, lookback_s=H) == pytest.approx(0.7 / 0.1 * H, rel=1e-6)

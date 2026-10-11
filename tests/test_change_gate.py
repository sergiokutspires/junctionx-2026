"""Tests for tools/change_gate.py (pure functions of the change-gate cost study; no dataset needed)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_SPEC = importlib.util.spec_from_file_location("change_gate", Path(__file__).resolve().parents[1] / "tools" / "change_gate.py")
cg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cg)


def _crop(seed: int = 0, size: int = cg.SIZE) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.integers(40, 200, size=(size // 8, size // 8, 3), dtype=np.uint8)
    return np.kron(base, np.ones((8, 8, 1), dtype=np.uint8))


def test_identical_crops_have_zero_components() -> None:
    vis = np.ones((cg.SIZE, cg.SIZE), bool)
    f = cg.area_features(_crop(1), vis)
    assert cg.pair_components(f, f) == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_lighting_gain_is_ignored_but_content_change_is_not() -> None:
    vis = np.ones((cg.SIZE, cg.SIZE), bool)
    img = _crop(2)
    darker = (img.astype(np.float32) * 0.8).astype(np.uint8)
    f0, f_dark, f_other = (cg.area_features(x, vis) for x in (img, darker, _crop(3)))
    gain = cg.pair_components(f0, f_dark)
    other = cg.pair_components(f0, f_other)
    assert gain[0] < 0.1 * other[0]                    # grey component ignores brightness gain
    assert other[0] > 0.1 and other[1] > 1.0 and other[2] > 0.1


def test_too_little_visible_is_not_scorable() -> None:
    vis = np.zeros((cg.SIZE, cg.SIZE), bool)
    vis[:4] = True
    f = cg.area_features(_crop(4), vis)
    assert cg.pair_components(f, f) is None


def test_choose_threshold_never_skips_a_changed_pair_at_zero_miss() -> None:
    rng = np.random.default_rng(0)
    score = np.concatenate([rng.normal(0, 1, 500), rng.normal(1.5, 1, 100)])
    changed = np.r_[np.zeros(500, bool), np.ones(100, bool)]
    tau = cg.choose_threshold(score, changed, 0.0)
    assert not (score[changed] < tau).any()
    assert (score[~changed] < tau).any()
    tau5 = cg.choose_threshold(score, changed, 0.05)
    assert (score[changed] < tau5).sum() <= 5 and tau5 >= tau


def test_summarise_counts_misses_and_points() -> None:
    skip = np.array([True, True, False, False])
    changed = np.array([False, True, True, False])
    loss = np.array([0.0, 3.0, 2.0, 0.0])
    s = cg.summarise(skip, changed, loss)
    assert (s["skipped"], s["changed_skipped"], s["miss_rate"]) == (2, 1, 0.5)
    assert s["points_lost_per_area"] == pytest.approx(0.75)


def test_auc_and_wilson() -> None:
    assert cg.auc(np.array([0.1, 0.2, 0.8, 0.9]), np.array([False, False, True, True])) == 1.0
    assert cg.auc(np.array([1.0, 1.0]), np.array([False, True])) == 0.5
    lo, hi = cg.wilson(0, 289)
    assert lo == 0.0 and 0.005 < hi < 0.02


def test_standardiser_is_monotone_in_each_component() -> None:
    comps = np.abs(np.random.default_rng(5).normal(1, 0.3, size=(200, 3)))
    std = cg.Standardiser.fit(comps)
    base = np.array([1.0, 1.0, 1.0])
    assert std.score(base * np.array([2, 1, 1])) > std.score(base)
    assert std.score(base * np.array([1, 1, 2])) > std.score(base)

"""Tests for sensei.stock on synthetic arrays (no model weights needed) + one real-cache check."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import scoring
from sensei import stock as S
from sensei.config import Config
from sensei.features import CropFeatures, handcrafted, l2n

ROOT = Path(__file__).resolve().parents[1]
G, D, DC = 4, 16, 12
BASES = ["banana", "orange", "apple"]


def _synthetic(n_per_area: int = 12, seed: int = 0):
    """Crops of 6 areas (3 products x 2 cameras): each patch is product or shared surface.

    Returns feats, patches (N,G,G,D), true fill (N,), area_product, text_emb.
    """
    rng = np.random.default_rng(seed)
    basis = np.linalg.qr(rng.normal(size=(D, D)))[0]
    surface_dirs, product_dirs = basis[:2], basis[2:5]
    tb = np.linalg.qr(rng.normal(size=(DC, DC)))[0]
    text_emb = {"surface": tb[:2].astype(np.float32), "produce": tb[2:5].astype(np.float32)}
    keys, fills, patches, clip, ts = [], [], [], [], []
    area_product = {}
    for cam in ("c1", "c2"):
        for b, base in enumerate(BASES):
            area = f"{cam}_{b}"
            area_product[area] = base
            for t in range(n_per_area):
                phi = float(rng.uniform(0, 1))
                is_prod = rng.uniform(size=G * G) < phi
                surf = surface_dirs[rng.integers(0, 2, G * G)]
                p = np.where(is_prod[:, None], product_dirs[b], surf) + 0.05 * rng.normal(size=(G * G, D))
                patches.append(l2n(p).reshape(G, G, D))
                c = phi * text_emb["produce"][b] + (1 - phi) * text_emb["surface"].mean(0)
                clip.append(c + 0.02 * rng.normal(size=DC))
                keys.append((cam, f"{1000 + t}.jpg", area))
                fills.append(is_prod.mean())
                ts.append(1000 + t)
    n = len(keys)
    feats = CropFeatures(keys=keys, timestamps=np.array(ts, np.int64), visible=np.ones(n, np.float32),
                         hand=np.zeros((n, 135), np.float32), clip=l2n(np.array(clip)),
                         patch_visible=np.ones((n, G * G), bool), image_paths=[""] * n)
    return feats, np.array(patches, np.float16), np.array(fills), area_product, text_emb


def _cfg(**kw) -> Config:
    return Config(n_patch_clusters=5, pca_dims=8, **kw)


def _corr(a, b) -> float:
    return float(np.corrcoef(a, b)[0, 1])


def test_patch_coder_spread_marks_surface_clusters():
    feats, patches, _, area_product, _ = _synthetic()
    flat = patches.reshape(-1, D).astype(np.float32)
    groups = np.repeat([area_product[a] for a in feats.area_ids], G * G)
    cams = np.repeat(feats.camera_ids, G * G)
    coder = S.PatchCoder(5, 8, 0).fit(flat, groups, camera_ids=cams)
    codes = coder.encode(patches)
    assert codes.shape == (len(feats), G * G) and codes.dtype == np.int16
    # every cluster is either clearly surface (spread over all products) or clearly product
    assert np.sort(coder.productness)[:2].max() < 0.1 and np.sort(coder.productness)[2:].min() > 0.9


def test_encode_marks_invisible_patches():
    feats, patches, _, area_product, _ = _synthetic()
    coder = S.PatchCoder(5, 8, 0).fit(patches.reshape(-1, D), np.repeat(feats.area_ids, G * G))
    vis = np.ones((len(feats), G * G), bool)
    vis[0, :5] = False
    vis[1] = False
    codes = coder.encode(patches, vis)
    assert (codes[0, :5] == -1).all() and (codes[1] == -1).all()
    raw = S.fill_raw(codes, vis, coder.productness)
    assert np.isnan(raw[1]) and np.isfinite(raw[0])


@pytest.mark.parametrize("with_text", [True, False])
def test_stock_model_deep_tracks_true_fill(with_text):
    feats, patches, true_fill, area_product, text_emb = _synthetic()
    model = S.StockModel()
    model.fit(feats, area_product, _cfg(), patches=patches, text_emb=text_emb if with_text else None)
    assert feats.patch_codes is not None
    f = model.fill(feats)
    assert f.shape == (len(feats),) and np.all((f >= 0) & (f <= 1))
    assert _corr(f, true_fill) > 0.9
    p = model.predict_proba(feats)
    assert p.shape == (len(feats), 3) and np.allclose(p.sum(1), 1, atol=1e-5)
    # posterior is monotone in fill: P(full) up, P(empty) down
    o = np.argsort(f)
    assert _corr(p[o, 2], f[o]) > 0.5 and _corr(p[o, 0], f[o]) < -0.3
    # nearly-empty and nearly-full crops get the right level with best_stock
    lo, hi = np.argmin(true_fill), np.argmax(true_fill)
    assert scoring.best_stock(*p[lo])[1] == "empty"
    assert scoring.best_stock(*p[hi])[1] == "full"


def test_area_that_never_empties_is_not_stretched():
    feats, patches, true_fill, area_product, text_emb = _synthetic()
    model = S.StockModel()
    model.fit(feats, area_product, _cfg(), patches=patches, text_emb=text_emb)
    raw = np.where(np.array(feats.area_ids) == "c1_0", 0.96 + 0.02 * np.sin(np.arange(len(feats))), 0.0)
    raw = np.where(np.array(feats.area_ids) == "c1_0", raw, np.linspace(0, 1, len(feats)))
    model._fit_area_stats(feats.area_ids, raw.astype(np.float32))
    f = model._normalise(feats.area_ids, raw.astype(np.float32))
    assert f[np.array(feats.area_ids) == "c1_0"].min() > 0.8


def test_lite_fallback_and_missing_patches(caplog):
    rng = np.random.default_rng(1)
    crops, keys, truth = [], [], []
    for i in range(30):
        teal = np.zeros((64, 64, 3), np.uint8)
        teal[:] = (20, 150, 140)
        phi = i / 29
        rows = int(64 * phi)
        teal[:rows] = rng.integers(0, 255, (rows, 64, 3))      # textured "produce" on top
        crops.append(handcrafted(teal))
        keys.append(("c1", f"{i}.jpg", f"c1_{i % 3}"))
        truth.append(phi)
    n = len(keys)
    feats = CropFeatures(keys=keys, timestamps=np.arange(n, dtype=np.int64), visible=np.ones(n, np.float32),
                         hand=np.array(crops, np.float32), image_paths=[""] * n)
    model = S.StockModel()
    model.fit(feats, {}, Config(backend="lite"))
    assert model.backend == "lite" and model.coder is None
    f = model.fill(feats)
    assert _corr(f, truth) > 0.8
    p = model.predict_proba(feats)
    assert np.allclose(p.sum(1), 1, atol=1e-5)
    # deep config without patches falls back to lite with a warning, never crashes
    m2 = S.StockModel()
    with caplog.at_level("WARNING"):
        m2.fit(feats, {}, Config(backend="deep"))
    assert m2.backend == "lite" and "lite" in caplog.text
    # an invisible crop gets a valid answer
    feats.visible[0] = 0.0
    assert np.isfinite(model.fill(feats)[0]) and np.isclose(model.predict_proba(feats)[0].sum(), 1)


@pytest.mark.parametrize("backend", ["deep", "lite"])
def test_save_load_roundtrip(tmp_path, backend):
    feats, patches, _, area_product, text_emb = _synthetic()
    model = S.StockModel()
    model.fit(feats, area_product, _cfg(backend=backend),
              patches=patches if backend == "deep" else None, text_emb=text_emb)
    p0, f0 = model.predict_proba(feats), model.fill(feats)
    model.save(tmp_path / "stock")
    json.loads((tmp_path / "stock" / "stock.json").read_text(encoding="utf-8"))   # plain json
    with np.load(tmp_path / "stock" / "stock.npz", allow_pickle=False) as z:     # no pickle
        assert "reference" in z.files
    loaded = S.StockModel.load(tmp_path / "stock")
    fresh = feats.subset(np.arange(len(feats)))
    fresh.patch_codes = None
    loaded.encode(fresh, patches)                      # predict-time path for new crops
    assert np.allclose(loaded.fill(fresh), f0, atol=1e-6)
    assert np.allclose(loaded.predict_proba(fresh), p0, atol=1e-6)
    again = S.StockModel.from_state(model.state_dict())
    assert np.allclose(again.predict_proba(feats), p0, atol=1e-6)


def test_soft_levels_and_rank():
    u = np.linspace(0, 1, 101)
    p = S.soft_levels(u, 0.2, 0.5, 0.05, 0.1)
    assert np.allclose(p.sum(1), 1, atol=1e-5)
    assert np.all(np.diff(p[:, 2]) >= -1e-6) and np.all(np.diff(p[:, 0]) <= 1e-6)
    ref = np.sort(np.array([0.1, 0.2, 0.2, 0.9]))
    r = S.rank_of(np.array([0.0, 0.2, 1.0]), ref)
    assert r[0] < r[1] < r[2] and 0 < r.min() and r.max() < 1
    assert np.allclose(S.rank_of(np.array([0.3]), np.zeros(0)), 0.5)


def test_overrides_via_cfg_extra():
    feats, patches, _, area_product, text_emb = _synthetic()
    model = S.StockModel()
    model.fit(feats, area_product, _cfg(extra={"stock": {"n_clusters": 6, "prior_mix": 0.5}}),
              patches=patches, text_emb=text_emb)
    assert model.coder.n_clusters == 6
    assert model.predict_proba(feats).min() >= 0.5 * model.level_prior.min() - 1e-6


@pytest.mark.skipif(not (ROOT / "cache" / "real" / "feats.npz").is_file(), reason="no real feature cache")
def test_real_cache_lite_runs():
    """The lite path on the real cached features runs end to end (deep is checked in outputs/debug/stock)."""
    feats = CropFeatures.load(ROOT / "cache" / "real" / "feats.npz")
    model = S.StockModel()
    model.fit(feats, {}, Config(backend="lite"))
    p = model.predict_proba(feats)
    assert p.shape == (len(feats), 3) and np.isfinite(p).all()

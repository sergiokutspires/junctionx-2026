"""Tests for sensei/features.py: lite backend on tiny synthetic data + one deep smoke test."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sensei.config import Config
from sensei.data import discover_images, load_planogram
from sensei.features import (HAND_DIM, CropFeatures, Extractor, compute_features, grid_size,
                             handcrafted, iter_crops, patch_visibility)

from .conftest import write_image


def _lite(**kw) -> Config:
    return Config(backend="lite", **kw)


def test_handcrafted_basic():
    red = np.zeros((64, 64, 3), np.uint8)
    red[..., 0] = 220
    grey = np.full((64, 64, 3), 128, np.uint8)
    hr, hg = handcrafted(red), handcrafted(grey)
    assert hr.shape == (HAND_DIM,) and hr.dtype == np.float32
    assert np.isclose(hr[:128].sum(), 1.0) and np.isclose(hg[:128].sum(), 1.0)
    assert hr[-1] > hg[-1]                     # colourfulness
    assert hg[-3] == 1.0                       # all low-saturation
    assert not handcrafted(red, np.zeros((64, 64), bool)).any()
    assert handcrafted(grey[..., 0]).shape == (HAND_DIM,)  # grayscale accepted


def test_patch_visibility():
    m = np.zeros((224, 224), bool)
    m[:, :112] = True
    pv = patch_visibility(m, 16).reshape(16, 16)
    assert pv[:, :8].all() and not pv[:, 8:].any()
    assert patch_visibility(np.ones((100, 100), bool), 7).all()


def test_iter_crops_and_corrupt(tiny_dataset):
    root, plan = tiny_dataset
    areas = load_planogram(plan)
    recs = discover_images(root, areas.keys())
    (root / "1001" / "1751009999.jpg").write_bytes(b"not a jpeg")
    recs = discover_images(root, areas.keys())
    out = list(iter_crops(recs, areas, _lite(crop_size=64)))
    assert len(out) == 6 * 2                   # corrupt image yields nothing
    _key, _ts, crop, vis, _frac, _path = out[0]
    assert crop.shape == (64, 64, 3) and vis.shape == (64, 64)
    partial = [o[4] for o in out if o[0][2] == "1002_1"]
    assert all(0.1 < f < 0.9 for f in partial)  # area partly outside the frame


def test_compute_lite_cache_roundtrip(tiny_dataset, tmp_path: Path):
    root, plan = tiny_dataset
    areas = load_planogram(plan)
    recs = discover_images(root, areas.keys())
    cfg = _lite(crop_size=56)
    feats, patches = compute_features(recs, areas, cfg, cache_dir=tmp_path / "c")
    assert patches is None and feats.clip is None and feats.dino_cls is None
    assert len(feats) == 12 and feats.hand.shape == (12, HAND_DIM)
    assert feats.patch_visible.shape == (12, grid_size(56) ** 2)
    assert feats.timestamps.dtype == np.int64 and len(feats.image_paths) == 12
    i = feats.area_ids.index("1002_1")
    assert 0 < feats.patch_visible[i].mean() < 1

    again, _ = compute_features(recs, areas, cfg, cache_dir=tmp_path / "c")  # cache hit
    assert again.keys == feats.keys and np.array_equal(again.hand, feats.hand)
    other, _ = compute_features(recs, areas, cfg.replace(inset=0.2), cache_dir=tmp_path / "c")
    assert not np.array_equal(other.hand, feats.hand)  # cfg change -> new cache entry

    sub = feats.subset(np.arange(12) % 2 == 0)
    assert len(sub) == 6 and sub.keys == feats.keys[::2] and sub.image_paths == feats.image_paths[::2]
    both = CropFeatures.concat([sub, feats.subset([1])])
    assert len(both) == 7

    feats.patch_codes = np.full((12, grid_size(56) ** 2), -1, np.int16)
    feats.save(tmp_path / "f.npz")
    back = CropFeatures.load(tmp_path / "f.npz")
    assert back.keys == feats.keys and back.clip is None
    assert np.array_equal(back.patch_codes, feats.patch_codes) and back.patch_codes.dtype == np.int16


def test_unicode_path(tmp_path: Path, tiny_planogram: Path):
    areas = load_planogram(tiny_planogram)
    write_image(tmp_path / "imagens_ção" / "1001" / "1751001000.png",
                np.full((180, 320, 3), 90, np.uint8))
    recs = discover_images(tmp_path / "imagens_ção", areas.keys())
    feats, _ = compute_features(recs, areas, _lite(crop_size=28), cache_dir=None)
    assert len(feats) == 2


def _weights_cached(cfg: Config) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return all(isinstance(try_to_load_from_cache(m, "config.json"), str)
               for m in (cfg.clip_model, cfg.dino_model))


@pytest.mark.slow
def test_deep_smoke(real_images_dir, real_areas):
    cfg = Config(backend="deep", device="cpu", batch_size=8)
    if not _weights_cached(cfg):
        pytest.skip("model weights not cached")
    recs = [r for r in discover_images(real_images_dir, real_areas.keys()) if r.camera_id == "6215"][:2]
    ext = Extractor(cfg)
    feats, patches = compute_features(recs, real_areas, cfg, extractor=ext, cache_dir=None)
    n = len(feats)
    assert n == 2 * len(real_areas["6215"])
    assert feats.clip.shape == (n, 512) and feats.dino_cls.shape == (n, 384)
    assert np.allclose(np.linalg.norm(feats.clip, axis=1), 1, atol=1e-3)
    assert patches.shape == (n, 16, 16, 384) and patches.dtype == np.float16
    assert np.allclose(np.linalg.norm(patches[0].astype(np.float32), axis=-1), 1, atol=1e-2)
    txt = ext.clip_text(["a pile of bananas", "a pile of oranges"])
    assert txt.shape == (2, 512) and ext.logit_scale > 1


def test_precision_fields_cache_key_and_legacy_configs(tiny_dataset, monkeypatch):
    from sensei import features
    root, plan = tiny_dataset
    areas = load_planogram(plan)
    recs = discover_images(root, areas.keys())
    fp32 = Config(int8_clip=False, int8_dino=False, bf16=False)
    keys = {features._cache_key(recs, areas, c) for c in
            (fp32, fp32.replace(int8_clip=True), fp32.replace(int8_dino=True), fp32.replace(bf16=True))}
    assert len(keys) == 4                      # int8 / bf16 features never reuse fp32 cache entries
    k = features._cache_key(recs, areas, fp32)
    monkeypatch.setattr(features, "PRECISION_CFG_FIELDS", ())
    assert features._cache_key(recs, areas, fp32) == k   # fp32 keys unchanged: old cache entries stay valid
    # a model config written before these fields existed loads with the precision it was fitted with
    new = Config(int8_clip=True, int8_dino=True, bf16=True)
    old = {f: v for f, v in new.to_dict().items() if f not in ("int8_clip", "int8_dino", "bf16")}
    c = Config.from_dict(old)
    assert not (c.int8_clip or c.int8_dino or c.bf16)
    c = Config.from_dict(new.to_dict())
    assert c.int8_clip and c.int8_dino and c.bf16


@pytest.mark.slow
def test_deep_reduced_precision_close_to_fp32(real_images_dir, real_areas):
    cfg = Config(backend="deep", device="cpu", batch_size=8, int8_clip=False, int8_dino=False, bf16=False)
    if not _weights_cached(cfg):
        pytest.skip("model weights not cached")
    recs = [r for r in discover_images(real_images_dir, real_areas.keys()) if r.camera_id == "6215"][:1]
    ref, ref_p = compute_features(recs, real_areas, cfg, cache_dir=None)
    cos = lambda a, b: (a.astype(np.float32) * b.astype(np.float32)).sum(-1)  # noqa: E731
    bf, bf_p = compute_features(recs, real_areas, cfg.replace(bf16=True), cache_dir=None)
    assert cos(bf.clip, ref.clip).min() > 0.99 and cos(bf.dino_cls, ref.dino_cls).min() > 0.99
    assert cos(bf_p, ref_p).mean() > 0.99
    q, q_p = compute_features(recs, real_areas, cfg.replace(int8_dino=True, bf16=True), cache_dir=None)
    assert q_p.shape == ref_p.shape and cos(q.clip, bf.clip).min() > 0.999   # CLIP stays bf16
    assert cos(q.dino_cls, ref.dino_cls).mean() > 0.9 and cos(q_p, ref_p).mean() > 0.9
    t_q = Extractor(cfg.replace(int8_clip=True)).clip_text(["a pile of bananas"])
    assert np.allclose(t_q, Extractor(cfg).clip_text(["a pile of bananas"]), atol=1e-5)  # text stays fp32

"""ComplianceModel decision logic on synthetic CLIP embeddings + save/load round trip."""
from __future__ import annotations

import numpy as np
import pytest

from sensei.compliance import BASE_PREFIX, EMPTY_KEY, OCCL_KEY, ComplianceModel
from sensei.config import Config
from sensei.data import Area
from sensei.features import HAND_DIM, CropFeatures, l2n
from sensei.products import Catalog

D = 16
QUAD = np.zeros((4, 2), np.float32)
PRODUCTS = [  # area, camera, product id, name
    ("1_1", "1", "11908", "BANANA CAT I CNT KG"),
    ("1_2", "1", "11906", "LARANJA CNT KG"),
    ("2_1", "2", "20001", "MACA GALA CNT KG"),
    ("2_2", "2", "20002", "MACA FUJI CNT KG"),
    ("2_3", "2", "20003", "BATATA VERMELHA CNT KG"),
    ("3_1", "3", "30001", "BATATA DOCE CNT KG"),
]
# one direction per base, per variety, and for empty / occlusion
AXIS = {"banana": 0, "orange": 1, "apple": 2, "potato": 3, "sweet potato": 4,
        EMPTY_KEY: 5, OCCL_KEY: 6, "20001": 7, "20002": 8}


def _e(*parts: tuple[int, float]) -> np.ndarray:
    v = np.zeros(D, np.float32)
    for i, w in parts:
        v[i] += w
    return l2n(v)


@pytest.fixture(scope="module")
def setup():
    areas: dict[str, list[Area]] = {}
    for a, cam, pid, name in PRODUCTS:
        areas.setdefault(cam, []).append(Area(a, cam, pid, name, "S", QUAD))
    cat = Catalog.from_planogram(areas)
    text = {BASE_PREFIX + b: _e((AXIS[b], 1.0)) for b in cat.bases()}
    for pid in cat.ids():
        base_ax = AXIS[cat[pid]["base"]]
        var = [(AXIS[pid], 0.3)] if pid in AXIS else []
        text[pid] = _e((base_ax, 1.0), *var)
    text[EMPTY_KEY] = _e((AXIS[EMPTY_KEY], 1.0))
    text[OCCL_KEY] = _e((AXIS[OCCL_KEY], 1.0))
    return cat, text


def _feats(rows: list[tuple[str, str, np.ndarray, float]]) -> CropFeatures:
    """rows: (camera, area, clip_vector, visible)."""
    n = len(rows)
    return CropFeatures(keys=[(c, f"{1000 + i}.jpg", a) for i, (c, a, _, _) in enumerate(rows)],
                        timestamps=np.arange(n, dtype=np.int64) + 1000,
                        visible=np.array([r[3] for r in rows], np.float32),
                        hand=np.zeros((n, HAND_DIM), np.float32),
                        clip=np.stack([r[2] for r in rows]).astype(np.float32),
                        image_paths=[""] * n)


def _crop(base: str, extra: tuple[int, float] | None = None, noise: float = 0.15, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = _e((AXIS[base], 1.0), *([extra] if extra else [])) + noise * rng.normal(size=D).astype(np.float32) / np.sqrt(D)
    return l2n(v)


def _fit(setup, cfg: Config | None = None) -> ComplianceModel:
    cat, text = setup
    rows = [(c, a, _crop(cat[pid]["base"], seed=i), 1.0) for i, (a, c, pid, _) in enumerate(PRODUCTS)]
    f = _feats(rows)
    m = ComplianceModel()
    m.fit(f, cat.area_product(), cat, text, np.ones(len(f)), cfg or Config())
    return m


def test_compliant_crop_is_compliant(setup):
    m = _fit(setup)
    p, likely = m.predict(_feats([("1", "1_1", _crop("banana"), 1.0)]), np.array([0.9]))
    assert p[0] > 0.9 and likely == [None]


def test_wrong_base_is_flagged_with_same_camera_product(setup):
    m = _fit(setup)
    p, likely = m.predict(_feats([("1", "1_1", _crop("orange"), 1.0)]), np.array([0.9]))
    assert p[0] < 0.5
    assert likely == ["11906"]  # the orange sold on the same camera


def test_empty_low_visibility_and_unknown_area_keep_prior(setup):
    cfg = Config(compliance_prior=0.93)
    m = _fit(setup, cfg)
    f = _feats([("1", "1_1", _crop("orange"), 1.0),     # empty fill
                ("1", "1_1", _crop("orange"), 0.05),    # barely visible
                ("9", "9_1", _crop("orange"), 1.0),     # area not in the planogram
                ("1", "1_1", _crop(EMPTY_KEY), 1.0)])   # CLIP sees an empty crate
    p, likely = m.predict(f, np.array([0.0, 0.9, 0.9, 0.9]))
    assert np.allclose(p, 0.93, atol=0.02)
    assert likely == [None] * 4


def test_variety_and_lookalike_need_strong_evidence(setup):
    m = _fit(setup)
    f = _feats([("2", "2_1", _crop("apple", (AXIS["20002"], 0.1), noise=0), 1.0),  # gala area, slightly fuji-ish
                ("2", "2_3", _crop("potato", (AXIS["sweet potato"], 1.05), noise=0), 1.0)])  # sweet potato a bit ahead
    p, _ = m.predict(f, np.array([0.9, 0.9]))
    assert (p >= 0.5).all()


def test_variety_flipped_on_very_strong_evidence(setup):
    m = _fit(setup)
    p, likely = m.predict(_feats([("2", "2_1", _crop("apple", (AXIS["20002"], 1.0), noise=0), 1.0)]), np.array([0.9]))
    assert p[0] < 0.5 and likely == ["20002"]


def test_lookalike_flipped_when_clear(setup):
    m = _fit(setup)
    p, likely = m.predict(_feats([("2", "2_3", _crop("sweet potato"), 1.0)]), np.array([0.9]))
    assert p[0] < 0.5 and likely == ["30001"]


def test_lite_backend_returns_prior(setup):
    cat, _ = setup
    f = _feats([("1", "1_1", _crop("orange"), 1.0)])
    f.clip = None
    m = ComplianceModel()
    m.fit(f, cat.area_product(), cat, None, np.ones(1), Config(backend="lite"))
    p, likely = m.predict(f, np.ones(1))
    assert p.tolist() == pytest.approx([0.93]) and likely == [None]


def test_fill_length_mismatch_raises(setup):
    m = _fit(setup)
    with pytest.raises(ValueError):
        m.predict(_feats([("1", "1_1", _crop("banana"), 1.0)]), np.ones(3))


def test_params_from_cfg_extra(setup):
    m = _fit(setup, Config(extra={"compliance": {"base_margin": 7.5}}))
    assert m.params["base_margin"] == 7.5


@pytest.mark.parametrize("proto", [0.0, 0.5])
def test_save_load_roundtrip(setup, tmp_path, proto):
    m = _fit(setup, Config(extra={"compliance": {"proto_weight": proto, "proto_min": 1}}))
    f = _feats([("1", "1_1", _crop("orange", seed=5), 1.0), ("2", "2_1", _crop("apple", seed=6), 0.7)])
    fill = np.array([0.8, 0.5])
    p1, l1 = m.predict(f, fill)
    m.save(tmp_path / "model")
    assert (tmp_path / "model" / "compliance.json").is_file()
    assert (tmp_path / "model" / "compliance.npz").is_file()
    m2 = ComplianceModel.load(tmp_path / "model")
    p2, l2 = m2.predict(f, fill)
    np.testing.assert_allclose(p1, p2, atol=1e-6)
    assert l1 == l2
    m3 = ComplianceModel.from_state(m.state_dict())
    np.testing.assert_allclose(m3.predict(f, fill)[0], p1, atol=1e-6)

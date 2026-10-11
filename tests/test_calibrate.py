"""Tests for sensei.calibrate: labelling kit, tile labels, heads, cross-validation (synthetic data)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

import scoring
from sensei import calibrate
from sensei.calibrate import (HeadParams, Heads, cross_validate, export_sheets, fit_heads, format_report,
                              label_arrays, labels_from_tiles, load_labels, predictions_from_probs)
from sensei.config import Config
from sensei.data import load_planogram
from sensei.features import CropFeatures

LEVELS = ("empty", "half", "full")
CAMS, FRAMES, AREAS = 6, 6, 4


# --------------------------------------------------------------------------- synthetic data

def make_data(seed: int = 0, noncompliant: float = 0.12, deep: bool = True):
    """6 cameras x 6 frames x 4 areas. fill, clip, dino, hand and patch codes all carry the level."""
    rng = np.random.default_rng(seed)
    keys, ts, level, comp = [], [], [], []
    for c in range(CAMS):
        for f in range(FRAMES):
            for a in range(AREAS):
                cam = str(7000 + c)
                keys.append((cam, f"{1751000000 + 3600 * f}.jpg", f"{cam}_{a + 1}"))
                ts.append(1751000000 + 3600 * f)
                level.append(rng.choice(3, p=[0.2, 0.3, 0.5]))
                comp.append(rng.random() > noncompliant)
    n = len(keys)
    level, comp = np.array(level), np.array(comp)
    fill = np.clip(level / 2 + rng.normal(0, 0.12, n), 0, 1)
    dirs = rng.normal(size=(3, 40))
    zs_comp = np.clip(np.where(comp, 0.95, 0.15) + rng.normal(0, 0.05, n), 0.01, 0.99)

    def emb(dim):
        x = dirs[level][:, :dim] if dim <= 40 else np.pad(dirs[level], ((0, 0), (0, dim - 40)))
        x = x + rng.normal(0, 0.8, (n, dim))
        return (x / np.linalg.norm(x, axis=1, keepdims=True)).astype(np.float32)

    codes = np.where(rng.random((n, 256)) < (0.15 + 0.35 * level[:, None]), 3, rng.integers(0, 3, (n, 256)))
    feats = CropFeatures(
        keys=keys, timestamps=np.array(ts, np.int64), visible=np.ones(n, np.float32),
        hand=rng.random((n, 20)).astype(np.float32),
        clip=emb(32) if deep else None, dino_cls=emb(24) if deep else None,
        patch_codes=codes.astype(np.int16) if deep else None)
    labels: dict = {}
    for (cam, img, area), lv, ok in zip(keys, level, comp):
        labels.setdefault(cam, {}).setdefault(img, {})[area] = scoring.make_entry(ok, (0.0, 0.5, 1.0)[lv])
    return feats, fill.astype(np.float32), labels, level, comp, zs_comp.astype(np.float32)


@pytest.fixture(scope="module")
def data():
    return make_data()


CFG = Config(backend="deep")


# --------------------------------------------------------------------------- labels

def test_label_arrays_and_load_labels(tmp_path, data):
    feats, _, labels, level, comp, _ = data
    idx, ys, yc = label_arrays(feats, labels)
    assert len(idx) == len(feats) and np.array_equal(ys, level) and np.array_equal(yc, comp)
    # a partial label set only selects its rows; later files override earlier ones
    cam, img, area = feats.keys[5]
    p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
    p1.write_text(json.dumps({cam: {img: {area: scoring.make_entry(True, 0.0)}}}))
    p2.write_text(json.dumps({cam: {img: {area: scoring.make_entry(False, 1.0)}}}))
    merged = load_labels(p1, p2)
    idx, ys, yc = label_arrays(feats, merged)
    assert list(idx) == [5] and ys[0] == 2 and not yc[0]


def test_predictions_from_probs_uses_best_stock():
    keys = [("1", "a.jpg", "1_1"), ("1", "a.jpg", "1_2")]
    p = predictions_from_probs(keys, np.array([[0.1, 0.2, 0.7], [0.5, 0.3, 0.2]]), np.array([0.9, 0.2]))
    assert p["1"]["a.jpg"]["1_1"] == scoring.make_entry(True, scoring.best_stock(0.1, 0.2, 0.7)[0])
    assert p["1"]["a.jpg"]["1_2"]["planogram_compliant"] is False
    assert p["1"]["a.jpg"]["1_2"]["stock_level"] == "empty"


# --------------------------------------------------------------------------- heads

def test_heads_shapes_and_validity(data):
    feats, fill, labels, *_ = data
    heads = fit_heads(feats, fill, labels, CFG)
    ps, pc = heads.stock_proba(feats, fill), heads.compliance_proba(feats, fill)
    assert ps.shape == (len(feats), 3) and pc.shape == (len(feats),)
    assert np.allclose(ps.sum(axis=1), 1, atol=1e-5) and (ps > 0).all()
    assert ((pc > 0) & (pc < 1)).all()
    # the signal is strong enough that in-sample accuracy is well above chance
    assert (ps.argmax(axis=1) == label_arrays(feats, labels)[1]).mean() > 0.7


def test_heads_roundtrip(tmp_path, data):
    feats, fill, labels, _, _, zs_comp = data
    heads = fit_heads(feats, fill, labels, CFG, zs_comp=zs_comp)
    heads.save(tmp_path / "heads")
    assert (tmp_path / "heads" / "heads.json").is_file() and (tmp_path / "heads" / "heads.npz").is_file()
    again = Heads.load(tmp_path / "heads")
    assert np.allclose(heads.stock_proba(feats, fill), again.stock_proba(feats, fill), atol=1e-6)
    assert np.allclose(heads.compliance_proba(feats, fill, zs_comp), again.compliance_proba(feats, fill, zs_comp), atol=1e-6)
    json.loads((tmp_path / "heads" / "heads.json").read_text())  # plain json, no pickle


def test_heads_need_the_same_unsupervised_inputs(data):
    feats, fill, labels, level, _, zs_comp = data
    zs_stock = np.eye(3)[level] * 0.7 + 0.1
    heads = fit_heads(feats, fill, labels, CFG, zs_stock=zs_stock, zs_comp=zs_comp)
    assert heads.stock_proba(feats, fill, zs_stock).shape == (len(feats), 3)
    with pytest.raises(ValueError):
        heads.stock_proba(feats, fill)
    with pytest.raises(ValueError):
        heads.compliance_proba(feats, fill)


def test_compliance_constant_prior_when_a_class_is_rare():
    feats, fill, labels, *_ = make_data(noncompliant=0.0)
    cam, img, area = feats.keys[0]
    labels[cam][img][area] = scoring.make_entry(False, 1.0)  # a single non-compliant example
    heads = fit_heads(feats, fill, labels, CFG)
    assert heads.comp["kind"] == "constant"
    pc = heads.compliance_proba(feats, fill)
    assert np.allclose(pc, pc[0]) and pc[0] > 0.5  # still answers "compliant"


def test_stock_head_handles_missing_class_and_single_class(data):
    feats, fill, labels, level, *_ = data
    keep = np.flatnonzero(level != 0)  # no "empty" examples at all
    sub, labs = feats.subset(keep), labels
    heads = fit_heads(sub, fill[keep], labs, CFG)
    p = heads.stock_proba(feats, fill)
    assert p[:, 0].max() < 0.05 and np.allclose(p.sum(axis=1), 1, atol=1e-5)
    only_full = np.flatnonzero(level == 2)
    heads = fit_heads(feats.subset(only_full), fill[only_full], labels, CFG)
    assert heads.stock["kind"] == "constant"
    assert heads.stock_proba(feats, fill).argmax(axis=1).tolist() == [2] * len(feats)


def test_lite_backend_uses_handcrafted_features():
    feats, fill, labels, level, *_ = make_data(deep=False)
    heads = fit_heads(feats, fill, labels, Config(backend="lite"))
    assert heads.layout["hand"] and not heads.pca
    assert heads.stock_proba(feats, fill).shape == (len(feats), 3)


def test_pca_dims_capped_by_label_count(data):
    feats, fill, labels, *_ = data
    few = {}
    for cam, img, area in feats.keys[:24]:
        few.setdefault(cam, {}).setdefault(img, {})[area] = labels[cam][img][area]
    heads = fit_heads(feats, fill, few, CFG, HeadParams(n_clip=128, n_dino=128))
    assert heads.pca["clip"][1].shape[0] <= 6


def test_fit_without_overlap_raises(data):
    feats, fill, *_ = data
    with pytest.raises(ValueError):
        fit_heads(feats, fill, {"nope": {"x.jpg": {"y": scoring.make_entry(True, 1.0)}}}, CFG)


# --------------------------------------------------------------------------- cross-validation

def test_cross_validate_structure_and_gain(data):
    feats, fill, labels, _, _, zs_comp = data
    zs_stock = np.tile([0.2, 0.3, 0.5], (len(feats), 1))
    rep = cross_validate(feats, fill, labels, CFG, baseline={"p_stock": zs_stock, "p_comp": zs_comp})
    assert rep["n_labelled"] == len(feats)
    cam, tm = rep["schemes"]["camera"], rep["schemes"]["time"]
    assert cam["areas"] == len(feats)                       # every labelled row held out exactly once
    assert tm["areas"] == CAMS * 2 * AREAS                  # last two frames of every camera
    for res in (cam, tm):
        assert {"heads", "baseline", "all_full", "all_half", "all_empty", "train_prior"} <= set(res["methods"])
        h = res["methods"]["heads"]
        assert h["areas"] == res["areas"] and h["max"] == 2 * res["areas"]
        assert h["per_area"] > res["methods"]["all_full"]["per_area"]
        assert h["per_area"] > res["methods"]["all_empty"]["per_area"]
        assert set(res["per_camera"]) == {k[0] for k in feats.keys}
    json.dumps(rep)                                          # json friendly
    assert "heads" in format_report(rep)


def test_cross_validate_matches_scoring_on_constant(data):
    feats, fill, labels, *_ = data
    rep = cross_validate(feats, fill, labels, CFG, schemes=("camera",))
    pred = {c: {i: {a: scoring.make_entry(True, 1.0) for a in areas} for i, areas in imgs.items()}
            for c, imgs in labels.items()}
    assert rep["schemes"]["camera"]["methods"]["all_full"]["total"] == scoring.score(labels, pred)["total"]


def test_time_fold_holds_out_the_latest_frames(data):
    feats, _, labels, *_ = data
    idx, _, _ = label_arrays(feats, labels)
    (name, train, test), = list(calibrate._folds(feats, idx, "time", 2))
    last = {int(t) for t in sorted(set(feats.timestamps))[-2:]}
    assert {int(feats.timestamps[r]) for r in test} == last
    cams = np.array(feats.camera_ids)
    for cam in set(cams):  # per camera, everything trained on is earlier than everything tested on
        assert feats.timestamps[train][cams[train] == cam].max() < feats.timestamps[test][cams[test] == cam].min()


def test_cross_validate_ignores_unlabelled_rows(data):
    feats, fill, labels, *_ = data
    half = {c: dict(list(imgs.items())[:3]) for c, imgs in labels.items()}
    rep = cross_validate(feats, fill, half, CFG, schemes=("camera",))
    assert rep["n_labelled"] == CAMS * 3 * AREAS


# --------------------------------------------------------------------------- sheets + tile labels

@pytest.fixture
def kit(tmp_path, tiny_dataset):
    root, planogram = tiny_dataset
    areas = load_planogram(planogram)
    keys = [(a.camera_id, f"{ts}.jpg", a.area_id) for ts in (1751001000, 1751004600, 1751008200)
            for areas_ in areas.values() for a in areas_]
    out = tmp_path / "labeling"
    manifest = export_sheets(keys, root, areas, out, Config(), per_sheet=5)
    return out, manifest, keys


def test_export_sheets_files(kit):
    out, manifest, keys = kit
    assert manifest["n_tiles"] == len(keys) == 12 and len(manifest["sheets"]) == 3
    for s in manifest["sheets"]:
        assert Image.open(out / s).width <= 1600
    for t in manifest["tiles"]:
        assert (out / t["crop"]).is_file() and (out / t["context"]).is_file()
        assert t["sheet"] == (t["tile"] - 1) // 5 + 1
    disk = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert disk == json.loads(json.dumps(manifest))
    js = (out / "manifest.js").read_text(encoding="utf-8")
    assert js.startswith("window.MANIFEST = ") and json.loads(js[len("window.MANIFEST = "):].rstrip().rstrip(";")) == disk
    assert (out / "labeler.html").is_file()
    accented = next(t for t in manifest["tiles"] if t["area_id"] == "1001_2")
    assert "MAÇÃ" in accented["product_name"] and "apple" in accented["english"]


def test_export_sheets_sampling_is_stratified_and_deterministic(tmp_path, tiny_dataset):
    root, planogram = tiny_dataset
    areas = load_planogram(planogram)
    keys = [(a.camera_id, f"{ts}.jpg", a.area_id) for ts in (1751001000, 1751004600, 1751008200)
            for areas_ in areas.values() for a in areas_]
    fill = np.linspace(0, 1, len(keys))
    a = export_sheets(keys, root, areas, tmp_path / "a", Config(), n=4, fill=fill)
    b = export_sheets(keys, root, areas, tmp_path / "b", Config(), n=4, fill=fill)
    assert [t["fill"] for t in a["tiles"]] == [t["fill"] for t in b["tiles"]]
    fills = sorted(t["fill"] for t in a["tiles"])
    assert fills[0] < 0.3 and fills[-1] > 0.7          # spread over the fill range


def test_export_skips_unknown_areas(tmp_path, tiny_dataset):
    root, planogram = tiny_dataset
    areas = load_planogram(planogram)
    keys = [("1001", "1751001000.jpg", "1001_1"), ("1001", "1751001000.jpg", "9999_9"),
            ("1001", "missing.jpg", "1001_2")]
    m = export_sheets(keys, root, areas, tmp_path / "k", Config())
    assert [t["area_id"] for t in m["tiles"]] == ["1001_1"]


def test_labels_from_tiles(kit):
    out, manifest, keys = kit
    tile_labels = {1: "full", "2": {"level": "half", "wrong": True}, 3: {"stock_level": "empty"},
                   4: {"wrong": True},            # no level -> skipped
                   5: 0.5, 99: "full",            # unknown tile -> skipped
                   6: "bogus"}
    ann = labels_from_tiles(manifest, tile_labels)
    flat = {(c, i, a): e for c, imgs in ann.items() for i, areas in imgs.items() for a, e in areas.items()}
    t = {x["tile"]: (x["camera"], x["image_name"], x["area_id"]) for x in manifest["tiles"]}
    assert set(flat) == {t[1], t[2], t[3], t[5]}
    assert flat[t[1]] == {"planogram_compliant": True, "stock_level": "full", "stock_value": 1.0}
    assert flat[t[2]] == {"planogram_compliant": False, "stock_level": "half", "stock_value": 0.5}
    assert flat[t[3]]["stock_value"] == 0.0 and flat[t[5]]["stock_level"] == "half"
    # the result is directly scorable and accepts a manifest path
    assert scoring.score(ann, ann)["total"] == 2 * len(flat)
    assert labels_from_tiles(out / "manifest.json", {1: "full"}) == labels_from_tiles(manifest, {1: "full"})


# --------------------------------------------------------------------------- labeler page

def _page() -> str:
    return calibrate.LABELER_SRC.read_text(encoding="utf-8")


def test_labeler_is_offline_and_complete():
    html = _page()
    assert not re.findall(r'(?:src|href)\s*=\s*["\']https?://', html)
    assert "fetch(" not in html and "XMLHttpRequest" not in html and "@import" not in html
    for needle in ("manifest.js", "localStorage", "labels.json", "keydown", "planogram_compliant", "stock_value"):
        assert needle in html
    # localStorage is only touched inside try blocks
    for m in re.finditer(r"localStorage", html):
        assert "try" in html[max(0, m.start() - 160):m.start()]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_labeler_script_parses(tmp_path):
    scripts = re.findall(r"<script>(.*?)</script>", _page(), flags=re.S)
    assert scripts
    js = tmp_path / "labeler.js"
    js.write_text(scripts[0], encoding="utf-8")
    res = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_band_fills_rows_then_columns():
    codes = np.full((2, 16), 0)
    codes[0, :8] = 1            # top half of a 4x4 grid is surface (code 1), bottom is product
    codes[1] = -1               # nothing visible
    bf = calibrate.band_fills(codes, np.array([1.0, 0.0]), 2)
    assert bf.shape == (2, 4)
    assert np.allclose(bf[0], [0.0, 1.0, 0.5, 0.5]) and np.allclose(bf[1], 0.5)


def test_heads_with_band_fills_save_load(data, tmp_path):
    feats, fill, labels, *_ = data
    prod = np.linspace(0, 1, int(feats.patch_codes.max()) + 1)
    heads = fit_heads(feats, fill, labels, CFG, productness=prod)
    assert heads.layout["fill_bands"] == 4
    p = heads.stock_proba(feats, fill)
    heads.save(tmp_path / "heads")
    back = Heads.load(tmp_path / "heads")
    assert np.allclose(back.stock_proba(feats, fill), p, atol=1e-5)
    assert "fill_bands" not in fit_heads(feats, fill, labels, CFG).layout   # no productness: old layout


# --------------------------------------------------------------------------- per-area memory

def make_persistent(seed: int = 1):
    """Areas keep their level all day (area-specific), the crop codes identify the area's look, and the
    generic features carry no level signal: only a per-area memory can learn the level."""
    feats, fill, labels, level, comp, zs_comp = make_data(seed)
    rng = np.random.default_rng(seed)
    n = len(feats)
    areas = np.array(feats.area_ids)
    uniq = sorted(set(areas))
    area_level = {a: int(rng.choice(3, p=[0.3, 0.3, 0.4])) for a in uniq}
    level = np.array([area_level[a] for a in areas])
    look = {a: rng.integers(0, 24, 256) for a in uniq}           # every area has its own crate/product look
    codes = np.array([np.where(rng.random(256) < 0.9, look[a], rng.integers(0, 24, 256)) for a in areas])
    feats.patch_codes = codes.astype(np.int16)
    feats.clip = rng.normal(size=feats.clip.shape).astype(np.float32)
    feats.dino_cls = rng.normal(size=feats.dino_cls.shape).astype(np.float32)
    fill = rng.random(n).astype(np.float32)
    for (cam, img, area), lv in zip(feats.keys, level):
        labels[cam][img][area] = scoring.make_entry(True, (0.0, 0.5, 1.0)[lv])
    return feats, fill, labels, level


def test_memory_features_are_causal_and_per_area(data):
    feats, fill, labels, level, comp, _ = data
    idx, ys, yc = label_arrays(feats, labels)
    mem = calibrate.build_memory(feats, ys, yc, ("codes", "hand"), 24)
    F, has = calibrate.memory_features(mem, feats, [1 / 3] * 3)
    first = feats.timestamps == feats.timestamps.min()
    assert not has[first].any() and has[~first].all()            # the first frame has no earlier crop
    assert F.shape == (len(feats), 6) and np.isfinite(F).all()
    # a crop identical to an earlier labelled crop of its area gets that crop's level (nearest neighbour)
    late = feats.subset([len(feats) - 1])
    cam, img, area = late.keys[0]
    src = next(i for i, k in enumerate(feats.keys) if k[2] == area and feats.timestamps[i] == feats.timestamps.min())
    late.patch_codes, late.hand = feats.patch_codes[[src]], feats.hand[[src]]
    Fl, hl = calibrate.memory_features(mem, late, [1 / 3] * 3, tau=0.001, alpha=0.0)
    mix = np.exp(np.r_[0.0, Fl[0, 0], Fl[0, 0] + Fl[0, 1]])
    assert hl[0] and int(np.argmax(mix)) == level[src] and Fl[0, 2] == pytest.approx(1.0, abs=1e-5)
    # unknown area -> no memory; unknown timestamp (-1) -> every labelled crop of the area counts
    other = feats.subset([0, 1])
    other.keys = [("9999", "x.jpg", "9999_1"), (other.keys[1][0], "y.jpg", other.keys[1][2])]
    other.timestamps = np.array([1751999999, -1], np.int64)
    _, h2 = calibrate.memory_features(mem, other, [1 / 3] * 3)
    assert h2.tolist() == [False, True]
    # skipping the latest earlier frame: the second frame (only one earlier frame) loses its memory
    second = feats.timestamps == sorted(set(feats.timestamps))[1]
    _, hs = calibrate.memory_features(mem, feats, [1 / 3] * 3, skip=1)
    assert not hs[second].any() and hs[feats.timestamps >= sorted(set(feats.timestamps))[2]].all()


def test_memory_head_learns_per_area_levels_and_never_touches_unseen_cameras():
    feats, fill, labels, level = make_persistent()
    on = cross_validate(feats, fill, labels, CFG, schemes=("time", "camera"))
    t, c = on["schemes"]["time"], on["schemes"]["camera"]
    assert t["memory_rows"] == t["areas"] and c["memory_rows"] == 0
    assert t["methods"]["heads"]["stock_acc"] > t["methods"]["heads_nomem"]["stock_acc"] + 0.1
    assert t["methods"]["heads"]["per_area"] > t["methods"]["heads_nomem"]["per_area"]
    # leave-one-camera-out: no earlier labelled crop of a held-out camera -> exactly the plain head
    assert c["methods"]["heads"]["total"] == c["methods"]["heads_nomem"]["total"]
    off = cross_validate(feats, fill, labels, CFG, params=HeadParams(memory=False), schemes=("time",))
    assert "heads_nomem" not in off["schemes"]["time"]["methods"]
    assert off["schemes"]["time"]["methods"]["heads"]["total"] == t["methods"]["heads_nomem"]["total"]


def test_memory_heads_roundtrip_and_fallback(tmp_path):
    feats, fill, labels, level = make_persistent()
    early = np.flatnonzero(feats.timestamps < sorted(set(feats.timestamps))[-1])
    heads = fit_heads(feats.subset(early), fill[early], labels, CFG)
    assert heads.mem_stock is not None and heads.memory["names"] == ["codes", "hand"]
    heads.save(tmp_path / "heads")
    meta = json.loads((tmp_path / "heads" / "heads.json").read_text())
    assert meta["version"] == 2 and meta["params"]["mem_skips"] == [0, 1] and "memory" in meta
    with np.load(tmp_path / "heads" / "heads.npz", allow_pickle=False) as z:
        assert {"mem_ts", "mem_ys", "mem_area", "mem_emb_codes", "mem_emb_hand", "memstock_coef"} <= set(z.files)
    back = Heads.load(tmp_path / "heads")
    assert back.params.mem_embeddings == ("codes", "hand") and back.params.mem_skips == (0, 1)
    p = heads.stock_proba(feats, fill)
    assert np.allclose(back.stock_proba(feats, fill), p, atol=1e-5)
    assert np.allclose(p.sum(axis=1), 1, atol=1e-5)
    # later frame of an unknown area / camera: plain head, no crash
    new = feats.subset([0, 1, 2])
    new.keys = [("8888", "1752000000.jpg", "8888_1")] + list(new.keys[1:])
    new.timestamps = np.full(3, 1752000000, np.int64)
    assert back.memory_mask(new).tolist() == [False, True, True]
    plain = back.stock_proba(new, fill[:3], memory=False)
    mixed = back.stock_proba(new, fill[:3])
    assert np.allclose(mixed[0], plain[0]) and np.allclose(mixed.sum(axis=1), 1, atol=1e-5)
    # input without patch codes: the memory falls back (warning) instead of raising
    nocodes = feats.subset(np.arange(4))
    nocodes.patch_codes = None
    lite_heads = fit_heads(feats.subset(early), fill[early], labels, CFG, HeadParams(code_bands=0, fill_bands=0))
    assert lite_heads.memory_mask(nocodes).sum() == 0
    assert lite_heads.stock_proba(nocodes, fill[:4]).shape == (4, 3)


def test_heads_without_memory_still_load(tmp_path, data):
    """Heads saved before the memory existed (no memory keys, no new params) load and predict the same."""
    feats, fill, labels, *_ = data
    heads = fit_heads(feats, fill, labels, CFG, HeadParams(memory=False))
    assert heads.memory is None and heads.mem_stock is None
    heads.save(tmp_path / "h")
    meta = json.loads((tmp_path / "h" / "heads.json").read_text())
    meta["version"] = 1
    for k in [k for k in meta["params"] if k.startswith("mem")]:
        meta["params"].pop(k)
    (tmp_path / "h" / "heads.json").write_text(json.dumps(meta))
    back = Heads.load(tmp_path / "h")
    assert back.mem_stock is None and not back.memory_mask(feats).any()
    assert np.allclose(back.stock_proba(feats, fill), heads.stock_proba(feats, fill), atol=1e-6)


def test_lite_heads_use_a_hand_only_memory():
    feats, fill, labels, *_ = make_data(deep=False)
    heads = fit_heads(feats, fill, labels, Config(backend="lite"))
    assert heads.memory is not None and heads.memory["names"] == ["hand"]
    assert heads.stock_proba(feats, fill).shape == (len(feats), 3)

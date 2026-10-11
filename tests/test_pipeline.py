"""pipeline.py + the CLI: synth -> fit -> predict -> score, persistence, fallbacks, heads."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

import scoring
from sensei import pipeline
from sensei.__main__ import main as cli
from sensei.config import Config
from sensei.data import discover_images

ROW_FIELDS = ["camera_id", "image_name", "area_id", "product_id", "product_name", "english", "loose",
              "timestamp", "stock_level", "stock_value", "fill", "p_levels", "planogram_compliant",
              "p_compliant", "likely_product_id", "likely_product_name", "likely_english", "visible",
              "forecast_empty_s", "quad", "image_path", "fallback"]


def _read(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def synth(tmp_path_factory) -> dict:
    from sensei.synth import generate_dataset
    return generate_dataset(tmp_path_factory.mktemp("synth") / "d", n_cameras=3, images_per_camera=8,
                            seed=1, val_per_camera=2)


@pytest.fixture(scope="module")
def lite_model(synth, tmp_path_factory) -> tuple[pipeline.SenseiModel, Path]:
    cfg = Config(backend="lite", extra={"cache_dir": None})
    out = tmp_path_factory.mktemp("model") / "m"
    return pipeline.fit(synth["images_dir"], synth["planogram"], out, cfg), out


def _baseline(truth: dict) -> int:
    base = {c: {i: {a: scoring.make_entry(True, 1.0) for a in ar} for i, ar in im.items()} for c, im in truth.items()}
    return scoring.score(truth, base)["total"]


def _check_coverage(preds: dict, areas_by_cam: dict, records) -> None:
    for r in records:
        got = preds[r.camera_id][r.image_name]
        assert sorted(got) == sorted(a.area_id for a in areas_by_cam[r.camera_id])
        for e in got.values():
            assert set(e) == {"planogram_compliant", "stock_level", "stock_value"}
            assert scoring.LEVELS[e["stock_level"]] == e["stock_value"]
            assert isinstance(e["planogram_compliant"], bool)


def test_fit_predict_score_lite(synth, lite_model, tmp_path):
    model, mdir = lite_model
    for f in ("config.json", "model.json", "planogram.json", "stock.json", "stock.npz", "compliance.json",
              "series.json", "fit_feats.npz"):
        assert (mdir / f).is_file(), f
    preds, _doc = pipeline.predict_dir(model, synth["val_dir"], tmp_path / "p.json", tmp_path / "d.json")
    recs = discover_images(synth["val_dir"], model.areas_by_cam)
    _check_coverage(preds, model.areas_by_cam, recs)
    truth = _read(synth["annotations"])
    res = scoring.score(truth, _read(tmp_path / "p.json"))
    assert res["stock"].get("missing", 0) == 0
    assert res["total"] > _baseline(truth)          # beats always compliant + full

    d = _read(tmp_path / "d.json")
    assert set(d) == {"section", "generated_at", "backend", "frame_size", "rows", "timeline", "input"}
    assert d["input"]["areas"] == d["input"]["expected_areas"] == len(d["rows"])
    assert d["backend"] == "lite" and d["section"] == "Frutas e Legumes"
    assert len(d["rows"]) == sum(len(a) for i in preds.values() for a in i.values())
    for r in d["rows"]:
        assert list(r) == ROW_FIELDS
        assert abs(sum(r["p_levels"]) - 1) < 1e-3 and len(r["quad"]) == 4
        if r["stock_level"] == "empty":
            assert r["planogram_compliant"]          # an empty area is compliant
        if r["planogram_compliant"]:
            assert r["likely_product_id"] is None
    some = d["rows"][0]["area_id"]
    tl = d["timeline"][some]
    assert len(tl) >= 8 and [t for t, _, _ in tl] == sorted(t for t, _, _ in tl)


def test_save_load_roundtrip(synth, lite_model):
    model, mdir = lite_model
    again = pipeline.SenseiModel.load(mdir)
    recs = discover_images(synth["val_dir"], model.areas_by_cam)
    p1, r1 = pipeline.predict(model, recs)
    p2, r2 = pipeline.predict(again, recs)
    assert p1 == p2
    assert [r["p_levels"] for r in r1] == [r["p_levels"] for r in r2]


def test_fallbacks_never_crash(synth, lite_model, tmp_path):
    model, _ = lite_model
    root = tmp_path / "imgs"
    src = discover_images(synth["val_dir"], model.areas_by_cam)
    cam = src[0].camera_id
    (root / cam).mkdir(parents=True)
    shutil.copy(src[0].path, root / cam / src[0].image_name)
    (root / cam / "1751099999.jpg").write_bytes(b"not a jpeg")      # corrupt
    (root / "7777").mkdir()
    noise = np.random.default_rng(0).integers(0, 255, (72, 128, 3), dtype=np.uint8)
    cv2.imwrite(str(root / "7777" / "1751050000.jpg"), noise)       # unknown camera, unknown view: ignored
    preds, doc = pipeline.predict_dir(model, root)
    assert set(preds) == {cam} and set(preds[cam]) == {src[0].image_name, "1751099999.jpg"}
    _check_coverage(preds, model.areas_by_cam, discover_images(root, model.areas_by_cam))
    bad = [r for r in doc["rows"] if r["image_name"] == "1751099999.jpg"]
    good = {r["area_id"]: r for r in doc["rows"] if r["image_name"] == src[0].image_name}
    assert all(r["visible"] is None and r["fallback"] for r in bad)
    # an unreadable picture reuses the same area's answer from the readable frame of this batch
    assert all((r["stock_level"], r["planogram_compliant"]) ==
               (good[r["area_id"]]["stock_level"], good[r["area_id"]]["planogram_compliant"]) for r in bad)
    # dashboard: the newest READABLE frame is shown; fallback rows are never counters or tasks
    from sensei.dashboard import build
    build(doc, root, tmp_path / "dash")
    js = (tmp_path / "dash" / "data.js").read_text(encoding="utf-8")
    shelf = json.loads(js[js.index("{"):js.rindex("}") + 1])
    assert [c["image"] for c in shelf["cameras"]] == [src[0].image_name]
    assert sum(shelf["counts"].values()) == len(model.areas_by_cam[cam])
    # empty input -> empty output, no crash
    assert pipeline.predict(model, []) == ({}, [])


def test_heads_used_when_present(synth, lite_model, tmp_path):
    _, mdir = lite_model
    mdir2 = tmp_path / "m2"
    shutil.copytree(mdir, mdir2)
    pipeline.calibrate(mdir2, [synth["annotations_train"]], cv=False)
    assert (mdir2 / "heads" / "heads.json").is_file()
    m2 = pipeline.SenseiModel.load(mdir2)
    assert m2.heads is not None
    recs = discover_images(synth["val_dir"], m2.areas_by_cam)
    preds, rows = pipeline.predict(m2, recs)
    _check_coverage(preds, m2.areas_by_cam, recs)
    m1 = pipeline.SenseiModel.load(mdir)
    _, rows1 = pipeline.predict(m1, recs)
    assert [r["p_levels"] for r in rows] != [r["p_levels"] for r in rows1]


def test_cli_run_and_score(synth, tmp_path, capsys):
    out = tmp_path / "out"
    cli(["-q", "run", "--data", str(synth["images_dir"]), "--planogram", str(synth["planogram"]),
         "--images", str(synth["val_dir"]), "--out", str(out), "--backend", "lite"])
    for f in ("predictions.json", "details.json", "dashboard/index.html", "dashboard/data.js", "model/model.json"):
        assert (out / f).is_file(), f
    cli(["score", str(synth["annotations"]), str(out / "predictions.json")])
    assert "Score:" in capsys.readouterr().out
    cli(["-q", "predict", "--model", str(out / "model"), "--images", str(synth["val_dir"]),
         "--out", str(tmp_path / "p2.json")])
    assert _read(tmp_path / "p2.json") == _read(out / "predictions.json")
    cli(["-q", "label", "--model", str(out / "model"), "--data", str(synth["images_dir"]),
         "--out", str(tmp_path / "lab"), "--n", "6"])
    assert (tmp_path / "lab" / "manifest.json").is_file()


def test_unknown_split_and_empty_dir(synth, tmp_path):
    cfg = Config(backend="lite", extra={"cache_dir": None})
    with pytest.raises(ValueError):
        pipeline.fit(tmp_path, synth["planogram"], None, cfg)   # no images at all


@pytest.mark.slow
def test_deep_smoke(tiny_dataset, tmp_path):
    cfg = Config(backend="deep", device="cpu", batch_size=8, extra={"cache_dir": None})
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        pytest.skip("transformers stack not installed")
    if not all(isinstance(try_to_load_from_cache(m, "config.json"), str) for m in (cfg.clip_model, cfg.dino_model)):
        pytest.skip("model weights not cached")
    images, plano = tiny_dataset
    model = pipeline.fit(images, plano, tmp_path / "m", cfg)
    recs = discover_images(images, model.areas_by_cam)
    preds, rows = pipeline.predict(pipeline.SenseiModel.load(tmp_path / "m"), recs)
    _check_coverage(preds, model.areas_by_cam, recs)
    assert all(np.isfinite(r["p_compliant"]) for r in rows)


def test_predict_dir_refuses_empty_input(synth, lite_model, tmp_path, capsys):
    model, mdir = lite_model
    with pytest.raises(FileNotFoundError):
        pipeline.predict_dir(model, tmp_path / "missing")
    (tmp_path / "none").mkdir()
    with pytest.raises(ValueError):
        pipeline.predict_dir(model, tmp_path / "none")
    with pytest.raises(SystemExit) as exc:
        cli(["predict", "--model", str(mdir), "--images", str(tmp_path / "none"), "--out", str(tmp_path / "p.json"), "-q"])
    assert exc.value.code == 2 and not (tmp_path / "p.json").exists()


def test_canonical_keys_and_flat_layout(synth, lite_model, tmp_path):
    model, _ = lite_model
    src = discover_images(synth["val_dir"], model.areas_by_cam)
    r0 = src[0]
    up = tmp_path / "upper" / r0.camera_id
    up.mkdir(parents=True)
    shutil.copy(r0.path, up / f"{r0.timestamp}.JPG")
    preds, _ = pipeline.predict_dir(model, tmp_path / "upper")
    assert set(preds[r0.camera_id]) == {f"{r0.timestamp}.jpg", f"{r0.timestamp}.JPG"}
    # flat folder of <ts>.jpg: the camera is recognised from the picture
    flat = tmp_path / "flat"
    flat.mkdir()
    for r in src:
        shutil.copy(r.path, flat / r.image_name)
    preds, doc = pipeline.predict_dir(model, flat)
    want = {(r.camera_id, r.image_name) for r in src}
    assert {(c, i) for c, imgs in preds.items() for i in imgs} == want
    assert doc["input"]["areas"] == doc["input"]["expected_areas"]


def test_heads_late_shift_passthrough_and_carry(synth, lite_model, tmp_path):
    from sensei.calibrate import load_labels
    _model, mdir = lite_model
    labels = load_labels(synth["annotations_train"])
    cam = sorted(labels)[0]
    last_img = max(labels[cam], key=lambda n: int(Path(n).stem))
    area = sorted(labels[cam][last_img])[0]
    labels[cam][last_img][area] = scoring.make_entry(False, 1.0)       # latest label: wrong product
    lab_path = tmp_path / "lab.json"
    lab_path.write_text(json.dumps(labels), encoding="utf-8")
    mdir2 = tmp_path / "m2"
    shutil.copytree(mdir, mdir2)
    pipeline.calibrate(mdir2, [lab_path], cv=False)
    m2 = pipeline.SenseiModel.load(mdir2)
    h = m2.heads
    assert h.comp["kind"] == "passthrough"
    assert set(h.stock["last_ts"]) == set(labels) and abs(sum(h.stock["late_prior"]) - 1) < 1e-6
    assert area in h.carry["areas"]
    recs = [r for r in discover_images(synth["val_dir"], m2.areas_by_cam) if r.camera_id == cam]
    assert recs and all(r.timestamp > h.stock["last_ts"][cam] for r in recs)
    preds, rows = pipeline.predict(m2, recs)
    for r in recs:      # lite: no DINO gate, the label is carried to every later frame
        assert preds[cam][r.image_name][area]["planogram_compliant"] is False
    _, rows1 = pipeline.predict(pipeline.SenseiModel.load(mdir), recs)
    assert [r["p_compliant"] for r in rows if r["area_id"] != area] == \
        [r["p_compliant"] for r in rows1 if r["area_id"] != area]          # pass-through elsewhere
    feats_like = type("F", (), {})()
    feats_like.camera_ids, feats_like.timestamps = [cam, cam], [h.stock["last_ts"][cam], h.stock["last_ts"][cam] + 1]
    assert h.late_mask(feats_like).tolist() == [False, True]


def test_precision_settings_are_feature_fields():
    # predict must run the image encoders with the precision the model was fitted with
    assert {"int8_clip", "int8_dino", "bf16", "clip_model", "dino_model"} <= set(pipeline.FEATURE_FIELDS)
    from sensei.features import FEATURE_CFG_FIELDS, PRECISION_CFG_FIELDS
    assert set(pipeline.FEATURE_FIELDS) == set(FEATURE_CFG_FIELDS) | set(PRECISION_CFG_FIELDS)

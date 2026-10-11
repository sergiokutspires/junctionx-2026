"""Tests for sensei.dashboard (static staff dashboard builder) and the ui/ assets it copies."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from sensei import dashboard, freshness

PREFIX = "window.SHELF_DATA = "
UI = Path(__file__).resolve().parents[1] / "ui"
TS_OLD, TS_NEW = 1751001000, 1751004600


def write_jpg(path: Path, w: int = 1600, h: int = 900) -> Path:
    """A synthetic 'camera frame': coloured blocks so crops are not uniform."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.zeros((h, w, 3), np.uint8)
    img[:, : w // 2] = (200, 160, 40)
    img[:, w // 2:] = (30, 120, 90)
    Image.fromarray(img).save(path, quality=90)
    return path


def read_data_js(out: Path) -> dict:
    text = (out / "data.js").read_text(encoding="utf-8")
    assert text.startswith(PREFIX) and text.rstrip().endswith(";")
    return json.loads(text[len(PREFIX):].rstrip().rstrip(";"))


def row(cam, ts, area, pid, name, level="full", ok=True, quad=None, img=None, **kw) -> dict:
    r = {"camera_id": cam, "image_name": f"{ts}.jpg", "area_id": area, "product_id": pid, "product_name": name,
         "timestamp": ts, "stock_level": level, "stock_value": {"empty": 0, "half": 0.5, "full": 1}[level],
         "fill": {"empty": 0.04, "half": 0.5, "full": 0.9}[level], "p_levels": [0.1, 0.3, 0.6],
         "planogram_compliant": ok, "p_compliant": 0.96 if ok else 0.2, "likely_product_id": None,
         "likely_product_name": None, "visible": 1.0, "forecast_empty_s": None, "quad": quad,
         "image_path": str(img) if img else None}
    r.update(kw)
    return r


@pytest.fixture
def fake(tmp_path):
    """Two frames of camera 1001 (1600x900), three areas, one wrong product, one empty, one off-frame."""
    old, new = write_jpg(tmp_path / "raw" / f"{TS_OLD}.jpg"), write_jpg(tmp_path / "raw" / f"{TS_NEW}.jpg")
    q1 = [[100, 100], [500, 110], [490, 300], [110, 290]]
    q2 = [[600, 100], [1000, 100], [1000, 300], [600, 300]]
    q10 = [[1500, 600], [1900, 600], [1900, 800], [1500, 800]]      # mostly outside the frame
    rows = []
    for ts, img, lv1 in ((TS_OLD, old, "full"), (TS_NEW, new, "empty")):
        rows += [
            row("1001", ts, "1001_10", "33", "TOMATE CHERRY EMB. 250 G", "full", quad=q10, img=img),
            row("1001", ts, "1001_1", "11", "BANANA CAT I CNT KG", lv1, quad=q1, img=img),
        ]
    rows += [row("1001", TS_NEW, "1001_2", "22", "MAÇÃ GALA KG", "half", ok=False, quad=q2, img=new,
                 likely_product_id="11", likely_product_name="BANANA CAT I CNT KG", likely_english="banana",
                 forecast_empty_s=3000)]
    return {"section": "Frutas e Legumes", "generated_at": TS_NEW, "backend": "lite", "rows": rows}


def test_build_end_to_end(fake, tmp_path):
    out = tmp_path / "site"
    index = dashboard.build(fake, tmp_path / "raw", out)
    assert index == out / "index.html" and index.is_file()
    for name in dashboard.UI_FILES:
        assert (out / name).read_bytes() == (UI / name).read_bytes()
    d = read_data_js(out)

    assert d["section"] == "Frutas e Legumes" and d["snapshot_ts"] == TS_NEW
    assert d["counts"] == {"wrong": 1, "empty": 1, "low": 0, "ok": 1}
    assert [c["id"] for c in d["cameras"]] == ["1001"] and d["cameras"][0]["ts"] == TS_NEW   # latest frame only

    frame = out / d["cameras"][0]["frame"]
    assert frame.name == f"1001_{TS_NEW}.jpg"
    with Image.open(frame) as im:
        assert im.size == (1280, 720) and im.format == "JPEG"
    assert (d["cameras"][0]["w"], d["cameras"][0]["h"], d["cameras"][0]["ow"]) == (1280, 720, 1600)

    areas = {a["id"]: a for a in d["areas"]}
    assert [a["id"] for a in d["areas"]] == ["1001_1", "1001_2", "1001_10"]          # natural order
    assert areas["1001_1"]["status"] == "empty" and areas["1001_2"]["status"] == "wrong"
    assert areas["1001_10"]["status"] == "ok" and areas["1001_1"]["num"] == "1"
    assert areas["1001_1"]["quad"][0] == [80.0, 80.0]                                  # scaled by 1280/1600
    assert areas["1001_1"]["en"] == "banana" and areas["1001_2"]["pt"] == "Maçã Gala"
    assert areas["1001_2"]["len"] == "banana" and areas["1001_2"]["home"] == ["1001_1"]
    assert areas["1001_2"]["fc"] == 3000
    assert [p[0] for p in areas["1001_1"]["tl"]] == [TS_OLD, TS_NEW]                    # timeline from rows
    assert areas["1001_1"]["pri"] > 0 and areas["1001_10"]["pri"] == 0

    for a in d["areas"]:                                                                # crops exist and are JPEGs
        assert a["crop"] == f"img/areas/1001_{TS_NEW}_{a['id']}.jpg"
        with Image.open(out / a["crop"]) as im:
            assert im.format == "JPEG" and 24 <= min(im.size) and max(im.size) <= 400
    assert d["areas"][0]["crop"] and (out / d["areas"][0]["crop"]).stat().st_size > 0


def test_priority_and_status_rules():
    base = {"p_levels": [0.1, 0.2, 0.7], "p_compliant": 0.9, "stock_level": "full", "fill": 0.9}
    assert dashboard._status({**base, "planogram_compliant": False, "stock_level": "empty"}) == "wrong"
    assert dashboard._status({**base, "stock_level": "empty"}) == "empty"
    assert dashboard._status({**base, "stock_level": "half"}) == "low"
    assert dashboard._status(base) == "ok"
    pri = {s: dashboard._priority({**base, "fill": 0.4}, s, 0.7) for s in ("wrong", "empty", "low", "ok")}
    assert pri["wrong"] > pri["low"] and pri["empty"] > pri["low"] and pri["ok"] == 0
    soon = dashboard._priority({"fill": 0.5, "forecast_empty_s": 900}, "low", 0.5)
    later = dashboard._priority({"fill": 0.5, "forecast_empty_s": 7000}, "low", 0.5)
    assert 100 < later < soon < 200                                                     # low stays below urgent
    assert dashboard._confidence({**base, "p_compliant": 0.1, "planogram_compliant": False}, "wrong") == pytest.approx(0.9)
    assert dashboard._confidence({**base, "stock_level": "half"}, "low") == pytest.approx(0.2)
    assert dashboard._num("6215_12") == "12"


def test_missing_and_corrupt_images_do_not_crash(tmp_path):
    q = [[10, 10], [60, 10], [60, 40], [10, 40]]
    bad = tmp_path / "raw" / "1002" / f"{TS_NEW}.jpg"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"not a jpeg")
    rows = [row("1001", TS_NEW, "1001_1", "11", "BANANA CAT I CNT KG", "empty", quad=q, img=tmp_path / "gone.jpg"),
            row("1002", TS_NEW, "1002_1", "12", "LARANJA KG", "half", quad=q, img=bad)]
    out = tmp_path / "site"
    dashboard.build({"rows": rows}, None, out)
    d = read_data_js(out)
    assert {c["id"]: c["frame"] for c in d["cameras"]} == {"1001": None, "1002": None}
    assert all(a["quad"] is None and a["crop"] is None for a in d["areas"])
    assert {a["status"] for a in d["areas"]} == {"empty", "low"}
    assert not (out / "img" / "frames").exists() or not list((out / "img" / "frames").glob("*.jpg"))


def test_image_found_under_data_root_and_unicode_paths(tiny_dataset, tmp_path):
    root, _ = tiny_dataset                                       # <root>/<camera>/<ts>.jpg, 320x180
    q = [[10, 10], [150, 12], [155, 80], [8, 78]]
    rows = [row("1001", 1751008200, "1001_1", "11908", "MAÇÃ COSMIC CRISP 75/85 KG", "full", quad=q)]
    details = tmp_path / "details.json"
    details.write_text(json.dumps({"section": "Frutas e Legumes", "rows": rows}), encoding="utf-8")
    out = tmp_path / "saída ação" / "dash"                       # unicode output path, details given as a file
    dashboard.build(details, root, out)
    d = read_data_js(out)
    cam = d["cameras"][0]
    assert cam["frame"] and (out / cam["frame"]).is_file() and (cam["w"], cam["h"]) == (320, 180)
    assert d["areas"][0]["crop"] and d["areas"][0]["quad"] == [[10.0, 10.0], [150.0, 12.0], [155.0, 80.0], [8.0, 78.0]]
    raw = (out / "data.js").read_bytes()
    assert raw.decode("ascii") and "Ma\\u00e7\\u00e3" in raw.decode("ascii")      # ASCII-safe, accents escaped
    assert d["areas"][0]["pt"] == "Maçã Cosmic Crisp"


def test_empty_details_still_builds(tmp_path):
    out = tmp_path / "site"
    dashboard.build({"section": "X", "rows": []}, None, out)
    d = read_data_js(out)
    assert d["areas"] == [] and d["cameras"] == [] and d["snapshot_ts"] is None


def test_real_camera_smoke(real_areas, real_images_dir, tmp_path):
    """Real planogram quads (incl. areas partly outside the frame) + a real frame: every area gets a crop."""
    from sensei.data import discover_images

    cam = "6383"                                                  # has areas that extend outside the frame
    rec = discover_images(real_images_dir, [cam])[-1]
    rows = [row(cam, rec.timestamp, a.area_id, a.product_id, a.product_name,
                ("empty", "half", "full")[i % 3], ok=(i % 4 != 0), quad=a.quad.tolist(), img=rec.path)
            for i, a in enumerate(real_areas[cam])]
    out = tmp_path / "site"
    dashboard.build({"section": "Frutas e Legumes", "rows": rows}, real_images_dir, out)
    d = read_data_js(out)
    assert len(d["areas"]) == len(real_areas[cam])
    assert all(a["crop"] and (out / a["crop"]).is_file() for a in d["areas"])
    with Image.open(out / d["cameras"][0]["frame"]) as im:
        assert im.size == (1280, 720)


def test_ui_assets_are_offline():
    """No CDN, font, or other network references anywhere in ui/."""
    for name in dashboard.UI_FILES:
        text = (UI / name).read_text(encoding="utf-8")
        # the SVG namespace in inline data: icons is an identifier, not a network request
        text = re.sub(r"""xmlns=(['"]|%22|%27)http://www\.w3\.org/2000/svg\1""", "xmlns", text)
        assert not re.search(r"https?://|(?<![:\w])//[a-z0-9.-]+\.[a-z]{2,}|@import|fonts\.googleapis", text), name
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'src="data.js"' in html and 'src="app.js"' in html and 'href="style.css"' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_app_js_is_valid_javascript():
    res = subprocess.run(["node", "--check", str(UI / "app.js")], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_cfg_frame_width_cli_and_zip(fake, tmp_path):
    """cfg.extra can shrink frames (never above 1280); the CLI builds from a details file and can zip."""
    import zipfile

    from sensei.config import Config

    out = tmp_path / "small"
    dashboard.build(fake, tmp_path / "raw", out, Config(extra={"dashboard_frame_width": 640}))
    cam = read_data_js(out)["cameras"][0]
    assert (cam["w"], cam["h"]) == (640, 360)

    details = tmp_path / "details.json"
    details.write_text(json.dumps(fake), encoding="utf-8")
    cli_out = tmp_path / "cli"
    dashboard.main(["--details", str(details), "--data", str(tmp_path / "raw"), "--out", str(cli_out), "--zip"])
    assert (cli_out / "index.html").is_file()
    with zipfile.ZipFile(tmp_path / "cli.zip") as z:
        names = set(z.namelist())
    assert {"index.html", "app.js", "style.css", "data.js"} <= names
    assert any(n.startswith("img/frames/") for n in names) and any(n.startswith("img/areas/") for n in names)


# --------------------------------------------------------------------------- optional product boxes (OWLv2)

Q_BANANA = [[100, 100], [500, 110], [490, 300], [110, 290]]      # same quad as area 1001_1 of the ``fake`` fixture


def det(x0, y0, x1, y1, label="bananas", score=0.5):
    return [x0, y0, x1, y1, label, score]


def test_select_detections_rules():
    sel = dashboard.select_detections
    shape = (900, 1600)
    good = det(120, 120, 220, 220, "bananas", 0.60)
    boxes = [
        good,
        det(130, 130, 215, 215, "oranges", 0.40),             # almost the same box: suppressed (overlap), best score wins
        det(300, 150, 400, 250, "bananas", 0.20),             # below the score threshold
        det(900, 600, 1000, 700, "bananas", 0.90),            # centre outside every planogram quad
        det(150, 120, 480, 280, "bananas", 0.70),             # shelf-sized (> 3% of the frame): not a product
        det(250, 120, 300, 170, "a person's hand", 0.90),     # distractor query, never drawn
        det(380, 200, 470, 280, "pears", 0.35),
        [1, 2, 3],                                            # malformed
    ]
    out = sel(boxes, [Q_BANANA], shape)
    assert [(b[4], b[5]) for b in out] == [("bananas", 0.60), ("pears", 0.35)]
    assert 0.20 in [b[5] for b in sel(boxes, [Q_BANANA], shape, min_score=0.1)]          # the threshold is a parameter
    assert sel([], [Q_BANANA], shape) == [] and sel(boxes, [], shape) == []
    many = [det(105 + 12 * i, 105, 115 + 12 * i, 115, "apples", 0.5 + i / 1000) for i in range(30)]
    assert len(sel(many, [Q_BANANA], shape, max_boxes=7)) == 7
    inner = [det(110, 110, 300, 200, "a", 0.9), det(120, 120, 150, 150, "b", 0.5)]    # one inside the other
    assert [b[4] for b in sel(inner, [Q_BANANA], shape)] == ["a"]


def test_load_detections_from_dict_json_and_zip(tmp_path):
    import zipfile

    payload = {"queries": ["bananas"], "detections": {"1001|1.jpg": [det(1, 2, 30, 40)]}}
    assert dashboard.load_detections(None) == {"queries": [], "detections": {}}
    assert dashboard.load_detections(payload)["detections"]["1001|1.jpg"][0][4] == "bananas"
    js = tmp_path / "d.json"
    js.write_text(json.dumps(payload), encoding="utf-8")
    assert dashboard.load_detections(js)["queries"] == ["bananas"]
    zp = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("meta.json", "{}")
        z.writestr("owl_detections.json", json.dumps(payload))
    assert dashboard.load_detections(zp)["detections"].keys() == payload["detections"].keys()
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "x")
    with pytest.raises(FileNotFoundError):
        dashboard.load_detections(empty)


def test_build_with_detections_scales_and_labels(fake, tmp_path):
    src = {"queries": ["bananas", "pears"], "detections": {
        f"1001|{TS_NEW}.jpg": [det(120, 120, 220, 220, "bananas", 0.6), det(380, 200, 470, 280, "pears", 0.35),
                               det(1000, 800, 1100, 880, "bananas", 0.9)],        # centre outside the areas
        f"1001|{TS_OLD}.jpg": [det(120, 120, 220, 220, "limes", 0.9)],            # not the shown frame
    }}
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out, detections=src)
    d = read_data_js(out)
    cam = d["cameras"][0]
    assert d["det_labels"] == ["bananas", "pears"]
    assert cam["det"] == [[96.0, 96.0, 176.0, 176.0, 0, 0.6], [304.0, 160.0, 376.0, 224.0, 1, 0.35]]   # x 0.8 (1280/1600)
    assert all(b[2] <= cam["w"] and b[3] <= cam["h"] for b in cam["det"])


def test_build_without_detections_has_no_toggle_data(fake, tmp_path):
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out)
    d = read_data_js(out)
    assert d["det_labels"] == [] and all("det" not in c for c in d["cameras"])
    # frames the source does not cover stay without boxes too
    dashboard.build(fake, tmp_path / "raw", out, detections={"queries": [], "detections": {"9999|1.jpg": [det(1, 1, 9, 9)]}})
    assert all("det" not in c for c in read_data_js(out)["cameras"])


def test_detect_runs_the_detector_only_where_boxes_are_missing(fake, tmp_path, monkeypatch):
    calls = []

    def fake_detector(rgb):
        calls.append(rgb.shape)
        return [det(120, 120, 220, 220, "pears", 0.8)]

    out = tmp_path / "a"
    dashboard.build(fake, tmp_path / "raw", out, detect=fake_detector)
    assert calls == [(900, 1600, 3)] and read_data_js(out)["cameras"][0]["det"][0][5] == 0.8

    cached = {"queries": [], "detections": {f"1001|{TS_NEW}.jpg": [det(130, 130, 230, 230, "bananas", 0.7)]}}
    out = tmp_path / "b"
    dashboard.build(fake, tmp_path / "raw", out, detections=cached, detect=fake_detector)
    assert len(calls) == 1 and read_data_js(out)["det_labels"] == ["bananas"]         # cache wins, detector idle

    monkeypatch.setattr(dashboard, "_try_owl_detector", lambda queries: fake_detector)   # detect=True builds one lazily
    out = tmp_path / "c"
    dashboard.build(fake, tmp_path / "raw", out, detect=True)
    assert len(calls) == 2 and read_data_js(out)["det_labels"] == ["pears"]

    monkeypatch.setattr(dashboard, "_try_owl_detector", lambda queries: None)            # no torch / weights: still builds
    out = tmp_path / "d"
    dashboard.build(fake, tmp_path / "raw", out, detect=True)
    assert "det" not in read_data_js(out)["cameras"][0]


def test_cli_detections_flag(fake, tmp_path):
    from sensei.__main__ import main as sensei_main

    details = tmp_path / "details.json"
    details.write_text(json.dumps(fake), encoding="utf-8")
    dets = tmp_path / "dets.json"
    dets.write_text(json.dumps({"queries": ["bananas"], "detections": {
        f"1001|{TS_NEW}.jpg": [det(120, 120, 220, 220, "bananas", 0.6)]}}), encoding="utf-8")
    for with_dets in (True, False):
        out = tmp_path / f"cli_{with_dets}"
        extra = ["--detections", str(dets)] if with_dets else []
        sensei_main(["dashboard", "--details", str(details), "--data", str(tmp_path / "raw"), "--out", str(out), *extra])
        assert bool(read_data_js(out)["det_labels"]) == with_dets
    out = tmp_path / "mod"
    dashboard.main(["--details", str(details), "--data", str(tmp_path / "raw"), "--out", str(out),
                    "--detections", str(dets)])
    assert read_data_js(out)["cameras"][0]["det"]


def test_ui_has_detection_toggle_in_both_languages():
    js = (UI / "app.js").read_text(encoding="utf-8")
    assert 'data-act="det"' in js and "Show detections" in js and "Mostrar deteções" in js
    assert "hasDet" in js and "det_labels" in js                      # toggle only exists when the data has boxes
    assert ".dbox" in (UI / "style.css").read_text(encoding="utf-8")


REAL_DETS = Path(__file__).resolve().parents[1] / "cache" / "colab" / "sensei_colab_features.zip"


@pytest.mark.skipif(not REAL_DETS.is_file(), reason="Colab feature bundle not cached")
def test_real_owl_detections_are_selectable():
    d = dashboard.load_detections(REAL_DETS)
    assert len(d["queries"]) > 30 and len(d["detections"]) >= 100
    _key, boxes = next(iter(d["detections"].items()))
    full = [[0, 0], [1280, 0], [1280, 720], [0, 720]]
    sel = dashboard.select_detections(boxes, [full], (720, 1280))
    assert 0 < len(sel) <= dashboard.DET_MAX_BOXES
    assert all(b[5] >= dashboard.DET_MIN_SCORE and b[4] not in dashboard.DET_NON_PRODUCT for b in sel)
    assert [b[5] for b in sel] == sorted((b[5] for b in sel), reverse=True)


# --------------------------------------------------------------------------- item counts (visible units per area)

def test_count_units_rules():
    q2 = [[600, 100], [1000, 100], [1000, 300], [600, 300]]
    quads = {"a": Q_BANANA, "b": q2}
    boxes = [
        det(120, 120, 170, 170, "bananas", 0.60),
        det(125, 125, 172, 172, "bananas", 0.50),             # IoU 0.75 with the first: same item, suppressed
        det(200, 120, 250, 170, "oranges", 0.22),             # faint: below the drawing threshold, still counted
        det(300, 120, 350, 170, "bananas", 0.15),             # below the counting threshold
        det(130, 130, 480, 285, "bananas", 0.90),             # > 40% of the area: a crate or the shelf, not an item
        det(250, 120, 300, 170, "a person's hand", 0.90),     # distractor query
        det(650, 120, 700, 170, "pears", 0.30),               # area b
        det(900, 900, 950, 950, "pears", 0.90),               # outside every area
        det(400, 200, 401, 201, "limes", 0.90),               # a speck
        [1, 2, 3],                                            # malformed
    ]
    assert dashboard.count_units(boxes, quads) == {"a": 2, "b": 1}
    assert dashboard.count_units(boxes, quads, min_scores={"a": 0.35}) == {"a": 1, "b": 1}      # per-area threshold
    assert dashboard.count_units(boxes, quads, min_scores={"a": 0.10})["a"] == 3
    assert dashboard.count_units(boxes, quads, nms_iou=0.9)["a"] == 3                            # parameters are real
    assert dashboard.count_units([], quads) == {"a": 0, "b": 0} and dashboard.count_units(boxes, {}) == {}
    assert dashboard.count_units(boxes, {"a": None}) == {}                                        # no quad, no count
    grid = [det(110 + 20 * (i % 10), 105 + 19 * (i // 10), 126 + 20 * (i % 10), 121 + 19 * (i // 10), "x", 0.5) for i in range(100)]
    assert dashboard.count_units(grid, {"a": [[100, 100], [500, 100], [500, 300], [100, 300]]}) == {"a": 100}   # uncapped (drawing stops at 60)
    both = {"a": [[0, 0], [200, 0], [200, 200], [0, 200]], "b": [[100, 0], [400, 0], [400, 200], [100, 200]]}
    assert dashboard.count_units([det(160, 90, 180, 110)], both) == {"a": 0, "b": 1}              # overlap: deepest quad wins


def test_build_adds_counts_totals_and_packs(fake, tmp_path):
    src = {"queries": [], "detections": {
        f"1001|{TS_NEW}.jpg": [
            det(120, 120, 170, 170, "bananas", 0.30),         # area 1 is empty: faint boxes are crate patterns
            det(200, 120, 250, 170, "bananas", 0.60),
            det(650, 120, 700, 170, "apples", 0.50), det(750, 120, 800, 170, "apples", 0.50),   # area 2 (wrong product)
            det(1550, 650, 1600, 700, "packs of cherry tomatoes", 0.50),                           # area 10
        ]}}
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out, detections=src)
    d = read_data_js(out)
    n = {a["id"]: a.get("n") for a in d["areas"]}
    assert n == {"1001_1": 1, "1001_2": 2, "1001_10": 1}
    areas = {a["id"]: a for a in d["areas"]}
    assert areas["1001_10"]["loose"] is False and areas["1001_1"]["loose"] is True        # "EMB. 250 G" = packs, "KG" = loose
    assert d["insights"]["totals"] == {"11": {"n": 1, "k": 1}, "33": {"n": 1, "k": 1}}    # the wrong-product area adds to nothing
    out2 = tmp_path / "plain"
    dashboard.build(fake, tmp_path / "raw", out2)                                         # no boxes at all: no counts, nothing invented
    d2 = read_data_js(out2)
    assert all("n" not in a for a in d2["areas"]) and d2["insights"]["totals"] == {}


def test_product_totals_adds_areas_per_product():
    areas = [{"pid": "1", "status": "ok", "n": 10}, {"pid": "1", "status": "low", "n": 5}, {"pid": "1", "status": "wrong", "n": 7},
             {"pid": "1", "status": "empty"}, {"pid": "2", "status": "ok", "n": 0}]
    assert dashboard.product_totals(areas) == {"1": {"n": 15, "k": 2}, "2": {"n": 0, "k": 1}}


# --------------------------------------------------------------------------- insights

BASE = int(datetime(2025, 6, 27, 9, 0, tzinfo=timezone.utc).timestamp())      # 10:00 in Lisbon (summer time, UTC+1)


def ins_area(aid, pid, fills, status="ok", start_h=0.0, cam="c1", fc=None):
    """Area record with one picture per hour starting ``start_h`` hours after 10:00 local."""
    tl = [[int(BASE + (start_h + i) * 3600), f, "full" if f > 0.7 else "half" if f > 0.2 else "empty"] for i, f in enumerate(fills)]
    return {"id": aid, "cam": cam, "pid": pid, "status": status, "tl": tl, "fc": fc}


def test_lisbon_clock_without_tz_database():
    ts = lambda *a: datetime(*a, tzinfo=timezone.utc).timestamp()      # noqa: E731
    assert dashboard._lisbon_offset_h(ts(2025, 6, 27, 9)) == 1 and dashboard._lisbon_offset_h(ts(2025, 12, 1, 9)) == 0
    assert dashboard._lisbon_offset_h(ts(2025, 3, 30, 0, 59)) == 0 and dashboard._lisbon_offset_h(ts(2025, 3, 30, 1)) == 1
    assert dashboard._lisbon_offset_h(ts(2025, 10, 26, 0, 59)) == 1 and dashboard._lisbon_offset_h(ts(2025, 10, 26, 1)) == 0
    assert dashboard._local_hour(ts(2025, 6, 27, 9, 30)) == pytest.approx(10.5)


def test_insights_soon_sales_restocks_and_adherence():
    areas = [
        ins_area("p1", "P", [1.0, 0.8, 0.6, 1.0, 0.9], cam="c1"),                  # two falls, a restock, one fall
        ins_area("q1", "Q", [1.0, 0.99, 1.0, 0.985], cam="c1"),                    # picture noise only: no sales
        ins_area("w1", "W", [1.0, 0.4, 0.0, 0.0], status="wrong", cam="c2"),       # wrong product: not this product's fill
        ins_area("s1", "S", [0.5, 0.4], status="low", cam="c2", fc=1800),
        ins_area("s2", "S", [0.5, 0.4], status="low", cam="c2", fc=9000),         # too far away
        ins_area("s3", "S", [1.0, 1.0], status="ok", cam="c2", fc=600),            # model says full: no forecast shown
        ins_area("s4", "S", [0.5, 0.4], status="wrong", cam="c1", fc=600),
        ins_area("s5", "S", [0.0, 0.0], status="empty", cam="c1", fc=0),           # already empty: it is a task, not a forecast
    ]
    out = dashboard.compute_insights(areas, {"c1": BASE, "c2": BASE + 60})
    assert [(x["id"], x["fc"], x["at"]) for x in out["soon"]] == [("s4", 600, BASE + 600), ("s1", 1800, BASE + 60 + 1800)]
    sales = {s["pid"]: s for s in out["sales"]}
    assert "W" not in sales
    p = sales["P"]
    assert p["restocks"] == [[BASE + 3 * 3600, "p1"]]                              # jump > +0.3, time of the later picture
    assert p["hours"] == 3.0 and p["rate"] == pytest.approx(0.5 / 3, abs=1e-3)     # the restock hour is left out
    assert sales["Q"]["rate"] == 0 and sales["Q"]["restocks"] == []
    rates = [s["rate"] for s in out["sales"]]
    assert rates == sorted(rates, reverse=True)                                    # fastest first
    assert out["adherence"] == {"ok": 6, "n": 8, "cams": [{"id": "c1", "ok": 3, "n": 4}, {"id": "c2", "ok": 3, "n": 4}]}
    assert dashboard.compute_insights([], {}) == {"soon": [], "sales": [], "hourly": [], "store_peak": None,
                                                  "adherence": {"ok": 0, "n": 0, "cams": []}}


def test_insights_peak_hint_only_when_data_supports_it():
    # one product in 12 areas: fill is steady, then falls 0.3 per hour between 12:00 and 14:00 (local)
    fills = [1.0] * 3 + [0.7, 0.4] + [0.4] * 5                                      # pictures 10:00 ... 20:00
    many = [ins_area(f"a{i}", "P", fills) for i in range(12)]
    out = dashboard.compute_insights(many, {})
    peak = out["sales"][0]["peak"]
    assert peak[:2] == [12, 14] and peak[2] == pytest.approx(0.3, abs=0.01)
    assert out["store_peak"][:2] == [12, 14]
    assert dict(out["hourly"])[12] == pytest.approx(0.3, abs=0.01) and dict(out["hourly"])[10] == 0
    few = dashboard.compute_insights(many[:1], {})                                  # one area: too little to claim a peak
    assert few["sales"][0]["peak"] is None and few["store_peak"] is None
    flat = dashboard.compute_insights([ins_area(f"b{i}", "F", [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65]) for i in range(12)], {})
    assert flat["sales"][0]["peak"] is None and flat["store_peak"] is None         # even decline: no "fastest" hour


def test_build_has_insights(fake, tmp_path):
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out)
    ins = read_data_js(out)["insights"]
    assert [(x["id"], x["fc"], x["at"]) for x in ins["soon"]] == [("1001_2", 3000, TS_NEW + 3000)]
    assert ins["adherence"] == {"ok": 2, "n": 3, "cams": [{"id": "1001", "ok": 2, "n": 3}]}
    assert {s["pid"] for s in ins["sales"]} == {"11", "33"}                         # the wrong-product area is not a product here
    assert next(s for s in ins["sales"] if s["pid"] == "11")["hours"] == 1.0         # two pictures an hour apart


def test_ui_has_insights_and_counts_in_both_languages():
    js = (UI / "app.js").read_text(encoding="utf-8")
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="insights"' in html and 'id="view-insights"' in html and "tab_insights" in html
    for en, pt in (("Running out soon", "A acabar em breve"), ("Sales speed", "Velocidade de vendas"),
                   ("Planogram adherence", "Cumprimento do planograma"), ("visible units", "unidades visíveis"),
                   ("visible packs", "embalagens visíveis"), ("estimate", "estimativa")):
        assert en in js and pt in js, (en, pt)
    assert "renderInsights" in js and "INS.sales" in js and "INS.adherence" in js and "INS.soon" in js
    assert ".ins-card" in (UI / "style.css").read_text(encoding="utf-8")


REAL_DETAILS = next((p for p in (Path(__file__).resolve().parents[1] / "outputs" / m / "details.json"
                     for m in ("real_v3_cal", "real_v1_cal")) if p.is_file()),
                    Path(__file__).resolve().parents[1] / "outputs" / "real_v3_cal" / "details.json")


@pytest.mark.skipif(not (REAL_DETS.is_file() and REAL_DETAILS.is_file()), reason="real details / Colab bundle not available")
def test_real_counts_are_plausible():
    d = json.loads(REAL_DETAILS.read_text(encoding="utf-8-sig"))
    lk = dashboard._det_lookup(dashboard.load_detections(REAL_DETS))
    rows = [r for r in d["rows"] if r["camera_id"] == "6215"]
    boxes = lk[("6215", Path(rows[0]["image_name"]).stem)]
    counts = dashboard.count_units(boxes, {r["area_id"]: r["quad"] for r in rows},
                                   min_scores={r["area_id"]: dashboard.COUNT_MIN_SCORE_EMPTY for r in rows if r["stock_level"] == "empty"})
    assert set(counts) == {r["area_id"] for r in rows}
    assert max(counts.values()) > 5 and all(0 <= v <= 150 for v in counts.values())
    assert counts["6215_6"] == 0 and counts["6215_8"] == 0                           # the two bare shelves: nothing visible


# --------------------------------------------------------------------------- freshness watch + ethylene neighbours


BIO_HEADER = ("type;product_english;planogram_name_pt;loose_or_packed;areas;shelf_life_class;hours_on_display_before_checking;"
              "ethylene_producer;ethylene_sensitive;visible_spoilage_signs;source;confidence")
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")


def bio_dict(tmp_path, lines):
    p = tmp_path / "bio.csv"
    p.write_text("\n".join([BIO_HEADER, *lines]) + "\n", encoding="utf-8-sig")
    return freshness.load_biology(p, None)


@pytest.fixture
def fake_bio(tmp_path):
    return bio_dict(tmp_path, [
        "banana;banana;BANANA CAT I CNT KG;loose;;medium;24;medium;high;Brown spots;USDA AH-66 Banana pp.224-229: https://x.org;high",
        "tomato;cherry tomato;TOMATE CHERRY EMB. 250 G;packed;;fast;0.5;medium;high;Soft, leaking;USDA AH-66 Tomato;medium",
        "apple;gala apple;MAÇÃ GALA KG;loose;;slow;48;high;medium;Wrinkles;USDA AH-66 Apple;medium",
    ])


def test_build_adds_freshness_on_the_shelf_product(fake, fake_bio, tmp_path):
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out, biology=fake_bio)
    d = read_data_js(out)
    areas = {a["id"]: a for a in d["areas"]}
    tom, ban, wrong = areas["1001_10"], areas["1001_1"], areas["1001_2"]
    assert tom["fresh"] == {"h": 1.0, "lim": 0.5, "since": TS_OLD, "basis": "first", "due": True}   # no restock: first picture
    assert tom["status"] == "ok" and tom["pri"] == 0                     # a freshness check never outranks stock tasks
    assert ban["fresh"]["due"] is False and ban["level"] == "empty"      # empty: nothing left to check
    assert wrong["bk"] == "11" and wrong["fresh"]["lim"] == 24            # wrong spot: biology of the banana seen there
    assert set(d["bio"]) == {"11", "33"}                                  # the Gala is planned but not on any shelf
    assert d["bio"]["11"]["src"] == "USDA AH-66 Banana pp.224-229" and d["bio"]["33"]["cls"] == "fast"
    assert "http" not in json.dumps(d["bio"])
    assert d["insights"]["layout"] == {"pairs": [], "mild": 0}            # the fixture's quads are far apart


def test_build_flags_ethylene_neighbours_with_likely_product(tmp_path):
    bio = bio_dict(tmp_path, [
        "avocado;ready-to-eat avocado;ABACATE HASS PRONTO COMER;loose;;fast;8;high;high;Soft;USDA AH-66 Avocado;medium",
        "lettuce;frisee lettuce;ALFACE FRISADA SACO;packed;;fast;8;low;high;Brown spots;USDA AH-66 Lettuce;medium",
        "potato;potato;BATATA BRANCA KG;loose;;slow;12;low;low;Green skin;Larsen 2022;high",
    ])
    qa = [[0, 0], [100, 0], [100, 100], [0, 100]]
    qb = [[104, 0], [200, 0], [200, 100], [104, 100]]                     # 4 px from the avocado
    qc = [[204, 0], [300, 0], [300, 100], [204, 100]]                     # next to the lettuce
    qd = [[600, 0], [700, 0], [700, 100], [600, 100]]                     # far away
    rows = [row("7", TS_NEW, "7_1", "1", "ABACATE HASS PRONTO COMER", quad=qa),
            row("7", TS_NEW, "7_2", "2", "ALFACE FRISADA SACO", quad=qb),
            row("7", TS_NEW, "7_3", "3", "BATATA BRANCA KG", ok=False, quad=qc, likely_product_id="1",
                likely_product_name="ABACATE HASS PRONTO COMER", likely_english="ready-to-eat avocado"),
            row("7", TS_NEW, "7_4", "1", "ABACATE HASS PRONTO COMER", quad=qd)]
    out = tmp_path / "site"
    dashboard.build({"rows": rows}, None, out, biology=bio)
    lay = read_data_js(out)["insights"]["layout"]
    assert [(p["src"], p["dst"], p["dst_type"]) for p in lay["pairs"]] == [("7_1", "7_2", "lettuce"), ("7_3", "7_2", "lettuce")]
    assert lay["mild"] == 0
    if freshness.PROFILES.is_file():                                      # Ines' score: avocado -> lettuce is 9/9 "avoid"
        assert {(p["score"], p["band"]) for p in lay["pairs"]} == {(9, "avoid")}


def test_build_degrades_without_biology(fake, tmp_path):
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out, biology=False)
    d = read_data_js(out)
    assert d["bio"] == {} and not any("fresh" in a or "bk" in a for a in d["areas"])
    assert d["insights"]["layout"] == {"pairs": [], "mild": 0}
    dashboard.build(fake, tmp_path / "raw", tmp_path / "missing", biology=tmp_path / "no_such.csv")   # missing file: no crash
    assert "bio" in read_data_js(tmp_path / "missing")
    details = tmp_path / "details.json"
    details.write_text(json.dumps(fake), encoding="utf-8")
    dashboard.main(["--details", str(details), "--data", str(tmp_path / "raw"), "--out", str(tmp_path / "cli"), "--no-biology"])
    assert read_data_js(tmp_path / "cli")["bio"] == {}


def test_ui_has_freshness_and_layout_in_both_languages():
    js = (UI / "app.js").read_text(encoding="utf-8")
    html = (UI / "index.html").read_text(encoding="utf-8")
    css = (UI / "style.css").read_text(encoding="utf-8")
    for en, pt in (("Check freshness / rotate stock", "Verificar frescura / rodar stock"),
                   ("Layout & waste", "Disposição e desperdício"), ("Layout suggestion", "Sugestão de disposição"),
                   ("Estimate:", "Estimativa:"), ("not on the picture", "não na imagem"),
                   ("When there is time: freshness checks", "Quando houver tempo: verificar frescura")):
        assert en in js and pt in js, (en, pt)
    assert 'id="i-leaf"' in html and 'id="i-gas"' in html
    assert css.count("--fresh:") == 3 and ".s-fresh" in css                    # light, auto-dark and forced-dark tokens
    assert "INS.layout" in js and "D.bio" in js and "#/insights/layout" in js


def _edge_dom(index: Path, route: str, tmp_path: Path) -> str:
    res = subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", f"--user-data-dir={tmp_path / 'edge'}",
                          "--virtual-time-budget=3000", "--dump-dom", index.resolve().as_uri() + route],
                         capture_output=True, text=True, encoding="utf-8", timeout=90)
    return res.stdout


@pytest.mark.skipif(not EDGE.is_file(), reason="Microsoft Edge not installed")
def test_freshness_tasks_render_below_stock_tasks(fake, fake_bio, tmp_path):
    """Real browser: the freshness task is its own last group, below wrong-product / empty tasks; badge in the panel."""
    out = tmp_path / "site"
    index = dashboard.build(fake, tmp_path / "raw", out, biology=fake_bio)
    dom = _edge_dom(index, "#/tasks", tmp_path)
    first, fresh = dom.find("Primeiro: produto errado e vazio"), dom.find("Quando houver tempo: verificar frescura")
    assert 0 < first < fresh, "freshness group must come after the urgent group"
    assert dom.find('data-key="1001_10|') > fresh and dom.find('data-key="1001_1|') < fresh
    panel = _edge_dom(index, "#/gondola/1001/1001_10", tmp_path)
    assert "Verificar frescura / rodar stock" in panel and "Estimativa" in panel and "USDA AH-66 Tomato" in panel


# --------------------------------------------------------------------------- day replay + closing-time mode

def test_replay_events_cover_every_kind():
    series = {
        "1_1": [(300, "low", 0.5), (100, "ok", 0.9), (200, "ok", 0.9), (400, "empty", 0.02), (500, "ok", 0.95)],
        "1_2": [(100, "ok", 0.9), (200, "wrong", 0.5), (300, "empty", 0.02)],
        "1_3": [(100, "low", 0.45), (200, "ok", 0.6), (300, "low", 0.5), (400, "ok", 0.95)],
        "1_4": [(100, "empty", 0.0)],
    }
    ev = dashboard.replay_events(series)
    assert ev == sorted(ev, key=lambda e: (e[0], dashboard._natural(e[1]), e[2]))          # oldest first
    got = {(e[0], e[1], e[2]) for e in ev}
    assert got == {(300, "1_1", "low"), (400, "1_1", "empty"), (500, "1_1", "restock"),
                   (200, "1_2", "wrong"), (300, "1_2", "fixed"), (300, "1_2", "empty"),
                   (200, "1_3", "ok"), (300, "1_3", "low"), (400, "1_3", "restock")}
    assert not [e for e in ev if e[1] == "1_4"]                                         # first picture: no event


def test_replay_state_and_pulse():
    frames = {"A": [{"ts": 100, "s": "eo"}, {"ts": 300, "s": "oo"}], "B": [{"ts": 200, "s": "lw"}]}
    assert dashboard.replay_state(frames, 50) == {}
    assert {c: f["ts"] for c, f in dashboard.replay_state(frames, 250).items()} == {"A": 100, "B": 200}
    assert dashboard.replay_pulse(frames, 100, 300, step=100) == [[100, 1, 0, 0], [200, 1, 1, 1], [300, 0, 1, 1]]


def test_build_adds_day_replay_with_several_frames(fake, fake_bio, tmp_path):
    out = tmp_path / "site"
    dashboard.build(fake, tmp_path / "raw", out, biology=fake_bio)
    d = read_data_js(out)
    rp = d["replay"]
    assert rp["order"] == {"1001": ["1001_1", "1001_2", "1001_10"]}
    fr = rp["frames"]["1001"]
    assert [f["ts"] for f in fr] == [TS_OLD, TS_NEW] and [f["s"] for f in fr] == ["o-o", "ewo"]
    assert fr[1]["lk"] == {"1001_2": ["banana", "Banana"]} and "lk" not in fr[0]
    for f in fr:                                                                        # downscaled local JPEGs
        assert f["f"].startswith("img/replay/")
        with Image.open(out / f["f"]) as im:
            assert im.size[0] == dashboard.REPLAY_FRAME_W and im.format == "JPEG"
    assert rp["events"] == [[TS_NEW, "1001_1", "empty"]]
    assert rp["t0"] == TS_OLD and rp["t1"] == TS_NEW and rp["day0"] <= TS_OLD
    assert (rp["day0"] - 1750978800) % 86400 == 0                                       # local (Lisbon) midnight
    assert rp["pulse"][-1][1:] == [1, 0, 1]
    areas = {a["id"]: a for a in d["areas"]}
    assert areas["1001_1"]["pcls"] == "medium" and areas["1001_2"]["pcls"] == "slow"     # planned product's class


def test_single_frame_per_camera_has_no_replay(tmp_path):
    img = write_jpg(tmp_path / "raw" / f"{TS_NEW}.jpg")
    q = [[100, 100], [500, 110], [490, 300], [110, 290]]
    out = tmp_path / "site"
    dashboard.build({"rows": [row("1001", TS_NEW, "1001_1", "11", "BANANA CAT I CNT KG", "half", quad=q, img=img)]},
                    None, out, biology=False)
    d = read_data_js(out)
    assert "replay" not in d and not (out / "img" / "replay").exists()


def test_ui_has_day_view_and_closing_mode_in_both_languages():
    js = (UI / "app.js").read_text(encoding="utf-8")
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="day" hidden' in html and 'id="view-day"' in html
    for en, pt in (("The store’s day", "O dia da loja"), ("What happened", "O que aconteceu"),
                   ("went empty", "ficou vazia"), ("restock detected", "reposição detetada"),
                   ("wrong product fixed", "produto errado corrigido"), ("back to OK", "voltou a OK"),
                   ("Store pulse", "Pulso da loja"), ("not accuracy", "não a precisão"),
                   ("Closing time", "Hora de fecho"),
                   ("Leave until tomorrow (close to closing)", "Deixar até amanhã (perto do fecho)")):
        assert en in js and pt in js, (en, pt)
    assert "store.get('sensei.close'" in js and "store.set('sensei.close'" in js        # saved with try/catch (store helper)
    assert ".day-ctrl" in (UI / "style.css").read_text(encoding="utf-8")


@pytest.mark.skipif(not EDGE.is_file(), reason="Microsoft Edge not installed")
def test_closing_time_moves_perishable_top_ups_only(fake_bio, tmp_path):
    """Real browser, picture at 20:00 Lisbon (default closing 21:00): low banana (medium class) waits, low apple (slow)
    and the empty banana stay; without replay data the Day tab stays hidden."""
    ts = 1750978800 + 20 * 3600 + 86400                                                 # 28/06 20:00 local
    img = write_jpg(tmp_path / "raw" / f"{ts}.jpg")
    q = [[[100 + 300 * i, 100], [350 + 300 * i, 100], [350 + 300 * i, 300], [100 + 300 * i, 300]] for i in range(3)]
    rows = [row("1001", ts, "1001_1", "11", "BANANA CAT I CNT KG", "half", quad=q[0], img=img),
            row("1001", ts, "1001_2", "22", "MAÇÃ GALA KG", "half", quad=q[1], img=img),
            row("1001", ts, "1001_3", "11", "BANANA CAT I CNT KG", "empty", quad=q[2], img=img)]
    out = tmp_path / "site"
    index = dashboard.build({"rows": rows}, None, out, biology=fake_bio)
    dom = _edge_dom(index, "#/tasks", tmp_path)
    grp = dom.find("Deixar até amanhã (perto do fecho)")
    assert grp > 0 and "Perto do fecho (21:00)" in dom
    assert dom.find('data-key="1001_1|') > grp                                         # banana top-up waits
    assert 0 < dom.find('data-key="1001_2|') < grp and 0 < dom.find('data-key="1001_3|') < grp
    assert re.search(r'data-tab="day"[^>]*hidden', dom)


@pytest.mark.skipif(not EDGE.is_file(), reason="Microsoft Edge not installed")
def test_day_view_renders_events(fake, tmp_path):
    out = tmp_path / "site"
    index = dashboard.build(fake, tmp_path / "raw", out, biology=False)
    dom = _edge_dom(index, "#/day", tmp_path)
    assert "O dia da loja" in dom and "ficou vazia" in dom and 'id="d-range"' in dom and "Pulso da loja" in dom
    assert not re.search(r'data-tab="day"[^>]*hidden', dom)

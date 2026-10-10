"""Tests for sensei.dashboard (static staff dashboard builder) and the ui/ assets it copies."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from sensei import dashboard

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

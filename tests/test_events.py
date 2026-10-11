"""events.py (area status changes, ``watch``) and serve.py (the local /analyze endpoint)."""
from __future__ import annotations

import json
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

import scoring
from sensei import events, pipeline
from sensei.__main__ import main as cli
from sensei.config import Config


def _row(ts, level="full", compliant=True, area="a1", cam="c1", p_comp=0.9, fallback=False):
    p = {"empty": [0.9, 0.05, 0.05], "half": [0.1, 0.8, 0.1], "full": [0.05, 0.05, 0.9]}[level]
    return {"camera_id": cam, "area_id": area, "image_name": f"{ts}.jpg", "timestamp": ts,
            "product_name": "BANANA", "stock_level": level, "planogram_compliant": compliant,
            "p_levels": p, "p_compliant": p_comp if compliant else 1 - p_comp, "likely_product_name":
            None if compliant else "LARANJA", "fallback": fallback}


def test_status_and_classify():
    assert events.status(_row(1, "half")) == "half"
    assert events.status(_row(1, "half", compliant=False)) == "wrong_product"
    assert events.status(_row(1, "empty", compliant=False)) == "empty"   # empty is never "wrong"
    table = {("full", "half"): "became_low", ("half", "empty"): "became_empty", ("full", "empty"): "became_empty",
             ("empty", "full"): "restocked", ("empty", "half"): "restocked", ("half", "full"): "back_to_ok",
             ("full", "wrong_product"): "wrong_product", ("empty", "wrong_product"): "wrong_product",
             ("wrong_product", "full"): "wrong_product_fixed", ("wrong_product", "empty"): "became_empty",
             ("full", "full"): None}
    for (a, b), want in table.items():
        assert events.classify(a, b) == want, (a, b)
    assert set(table.values()) - {None} == set(events.EVENTS)


def test_events_from_rows_order_baseline_and_fields():
    rows = [_row(300, "empty"), _row(100, "full"), _row(200, "half"), _row(400, "full", compliant=False),
            _row(500, "full"), _row(250, "half", fallback=True),
            _row(100, "full", area="a2"), _row(200, "full", area="a2")]
    ev = events.events_from_rows(rows)
    assert [e["event"] for e in ev] == ["became_low", "became_empty", "wrong_product", "wrong_product_fixed"]
    assert [e["ts"] for e in ev] == [200, 300, 400, 500]
    assert all(e["area_id"] == "a1" for e in ev)
    e = ev[2]
    assert {"time", "camera_id", "area_id", "product", "event", "from", "to", "confidence"} <= set(e)
    assert e["from"] == "empty" and e["to"] == "wrong_product" and e["seen_product"] == "LARANJA"
    assert 0 <= e["confidence"] <= 1
    assert e["time"].endswith("+00:00") or e["time"].endswith("+01:00")


def test_confirm_drops_one_frame_flicker():
    rows = [_row(t, lv) for t, lv in [(1, "full"), (2, "half"), (3, "full"), (4, "empty"), (5, "empty"), (6, "empty")]]
    assert [e["event"] for e in events.events_from_rows(rows, confirm=1)] == ["became_low", "back_to_ok",
                                                                            "became_empty"]
    ev = events.events_from_rows(rows, confirm=2)
    assert [(e["event"], e["ts"]) for e in ev] == [("became_empty", 4)]   # time of the first confirming frame


def test_lisbon_time():
    assert events._lisbon_iso(1751029500).startswith("2025-06-27T14:05:00+01:00")   # summer time
    assert events._lisbon_iso(1735732800).endswith("+00:00")                         # January


@pytest.fixture(scope="module")
def synth_model(tmp_path_factory):
    from sensei.synth import generate_dataset
    d = generate_dataset(tmp_path_factory.mktemp("synth") / "d", n_cameras=2, images_per_camera=6, seed=3,
                         val_per_camera=1)
    out = tmp_path_factory.mktemp("model") / "m"
    pipeline.fit(d["images_dir"], d["planogram"], out, Config(backend="lite", extra={"cache_dir": None}))
    return d, out


def test_cli_watch_writes_jsonl(synth_model, tmp_path, capsys):
    d, mdir = synth_model
    out = tmp_path / "events.jsonl"
    cli(["watch", "--model", str(mdir), "--images", str(d["images_dir"]), "--out", str(out), "-q"])
    text = capsys.readouterr().out
    assert "event(s) over 12 frame(s) of 2 camera(s)" in text
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    for e in lines:
        assert e["event"] in events.EVENTS and e["from"] != e["to"]
    assert [e["ts"] for e in lines] == sorted(e["ts"] for e in lines)


def test_serve_analyze_and_health(synth_model):
    from sensei.serve import Analyzer, make_handler
    d, mdir = synth_model
    analyzer = Analyzer(mdir)
    httpd = HTTPServer(("127.0.0.1", 0), make_handler(analyzer))
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        health = json.loads(urllib.request.urlopen(base + "/health", timeout=30).read())
        assert health["ok"] and health["areas"] > 0
        frame = sorted(Path(d["images_dir"]).rglob("*.jpg"))[0]
        cam, ts = frame.parent.name, int(frame.stem)
        req = urllib.request.Request(base + "/analyze", data=frame.read_bytes(), method="POST",
                                     headers={"X-Camera-Id": cam, "X-Timestamp": str(ts), "Content-Type": "image/jpeg"})
        res = json.loads(urllib.request.urlopen(req, timeout=60).read())
        assert res["camera_id"] == cam and res["timestamp"] == ts
        want = {a.area_id for a in analyzer.model.areas_by_cam[cam]}
        assert {a["area_id"] for a in res["areas"]} == want
        entries = res["submission"][cam][f"{ts}.jpg"]
        assert set(entries) == want
        for a in res["areas"]:
            assert entries[a["area_id"]] == scoring.make_entry(a["planogram_compliant"], a["stock_value"])
            assert a["status"] in ("full", "half", "empty", "wrong_product") and 0 <= a["confidence"] <= 1
        # query parameters work too; a bad camera is a 400, not a crash
        req = urllib.request.Request(base + f"/analyze?camera_id=nope&timestamp={ts}", data=frame.read_bytes(),
                                     method="POST")
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=60)
        assert err.value.code == 400
        assert json.loads(urllib.request.urlopen(base + "/health", timeout=30).read())["requests"] == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
        analyzer.close()

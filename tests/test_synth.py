"""Tests for sensei.synth: schema, determinism, scoring round trip and pixel evidence."""
from __future__ import annotations

import json
import time
from collections import Counter

import cv2
import numpy as np
import pytest
from PIL import Image

from scoring import score
from sensei import synth
from sensei.data import discover_images, load_image, load_planogram, visible_fraction, warp_area
from sensei.products import Catalog

CAMERAS, TRAIN, VAL = 4, 12, 2


@pytest.fixture(scope="module")
def ds(tmp_path_factory):
    """The default dataset, generated once (also times the < 20 s requirement)."""
    out = tmp_path_factory.mktemp("synth") / "ds"
    t0 = time.perf_counter()
    info = synth.generate_dataset(out, n_cameras=CAMERAS, images_per_camera=TRAIN, seed=0,
                                  val_per_camera=VAL)
    info["seconds"] = time.perf_counter() - t0
    info["areas_by_cam"] = load_planogram(info["planogram"])
    return info


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_generation_is_fast(ds):
    assert ds["seconds"] < 20, ds["seconds"]
    assert ds["n_cameras"] == CAMERAS
    assert ds["n_train_images"] == CAMERAS * TRAIN and ds["n_val_images"] == CAMERAS * VAL


def test_planogram_schema(ds):
    doc = _load(ds["planogram"])
    assert list(doc) == ["Frutas e Legumes"]
    cams = doc["Frutas e Legumes"]["cameras"]
    assert len(cams) == CAMERAS
    for cam_id, cam in cams.items():
        assert len(cam["products"]) >= 6
        for k, p in enumerate(cam["products"], 1):
            assert p["area_id"] == f"{cam_id}_{k}"
            assert isinstance(p["product_id"], str) and isinstance(p["product_name"], str)
            assert set(p["image_coordinates"]) == {"top_left", "top_right", "bottom_right", "bottom_left"}
            assert all(len(v) == 2 and all(isinstance(c, int) for c in v)
                       for v in p["image_coordinates"].values())
    areas = ds["areas_by_cam"]
    assert sum(len(a) for a in areas.values()) == ds["n_areas"]
    for cam_areas in areas.values():
        for a in cam_areas:
            assert a.quad.shape == (4, 2)
            # top edge above the bottom edge, left of right: orientation TL, TR, BR, BL kept
            assert a.quad[0, 1] < a.quad[3, 1] and a.quad[0, 0] < a.quad[1, 0]


def test_product_names_are_parsed_by_products_module(ds):
    cat = Catalog.from_planogram(ds["areas_by_cam"])
    assert len(cat.products) >= 10
    for info in cat.products.values():
        assert info["english"] and info["base"]
        assert not info["unknown_tokens"], info["raw"]


def test_images_and_timestamps(ds):
    cams = list(ds["areas_by_cam"])
    train = discover_images(ds["images_dir"], cams)
    val = discover_images(ds["val_dir"], cams)
    assert len(train) == ds["n_train_images"] and len(val) == ds["n_val_images"]
    assert {r.split for r in val} == {"val"}
    for r in train[:3] + val[:3]:
        assert Image.open(r.path).size == (1280, 720)
        assert r.timestamp == int(r.path.stem) > 0
    for cam in cams:
        last_train = max(r.timestamp for r in train if r.camera_id == cam)
        first_val = min(r.timestamp for r in val if r.camera_id == cam)
        assert first_val > last_train
        ts = [r.timestamp for r in train if r.camera_id == cam]
        assert len(set(ts)) == len(ts)


def test_val_annotations_cover_every_area_and_score_max(ds):
    ann = _load(ds["annotations"])
    areas = ds["areas_by_cam"]
    val = discover_images(ds["val_dir"], list(areas))
    assert {(r.camera_id, r.image_name) for r in val} == {(c, n) for c, d in ann.items() for n in d}
    for cam, images in ann.items():
        ids = {a.area_id for a in areas[cam]}
        for entry_set in images.values():
            assert set(entry_set) == ids
            for e in entry_set.values():
                assert isinstance(e["planogram_compliant"], bool)
                assert e["stock_level"] in {"empty", "half", "full"}
                assert e["stock_value"] == {"empty": 0, "half": 0.5, "full": 1}[e["stock_level"]]
    res = score(ann, ann)
    n_entries = sum(len(i) for d in ann.values() for i in d.values())
    assert res["areas"] == n_entries > 0
    assert res["total"] == res["max"] == 2 * n_entries


def test_label_variety(ds):
    train = _load(ds["annotations_train"])
    entries = [e for d in train.values() for img in d.values() for e in img.values()]
    levels = Counter(e["stock_level"] for e in entries)
    assert set(levels) == {"empty", "half", "full"}
    assert min(levels.values()) / len(entries) > 0.1
    noncompliant = sum(not e["planogram_compliant"] for e in entries)
    assert 0 < noncompliant / len(entries) < 0.2
    val = _load(ds["annotations"])
    assert any(not e["planogram_compliant"] for d in val.values() for img in d.values() for e in img.values())


def test_one_area_partly_outside_the_frame(ds):
    fracs = [visible_fraction(a.quad, (720, 1280)) for cam in ds["areas_by_cam"].values() for a in cam]
    partly = [f for f in fracs if f < 0.99]
    assert len(partly) == 1 and 0.4 < partly[0] < 0.85, partly


def test_empty_areas_are_compliant_and_stock_is_visible_in_pixels(ds):
    """Truth must be visible: edge density of the warped crop grows with the stock level."""
    ann = _load(ds["annotations_train"])
    edges: dict[str, list[float]] = {"empty": [], "half": [], "full": []}
    for cam, images in ann.items():
        quads = {a.area_id: a.quad for a in ds["areas_by_cam"][cam]}
        for name, truth in list(images.items())[::2]:
            frame = load_image(ds["images_dir"] / cam / name)
            for area_id, e in truth.items():
                if e["stock_level"] == "empty":
                    assert e["planogram_compliant"]
                crop, vis = warp_area(frame, quads[area_id], 112, 0.06)
                gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                edges[e["stock_level"]].append(float((cv2.Canny(gray, 60, 140) > 0)[vis].mean()))
    m = {k: float(np.mean(v)) for k, v in edges.items()}
    assert m["empty"] + 0.04 < m["half"] < m["full"] - 0.02, m


def test_same_seed_same_data_different_seed_differs(tmp_path):
    a = synth.generate_dataset(tmp_path / "a", 2, 3, seed=5, val_per_camera=1)
    b = synth.generate_dataset(tmp_path / "b", 2, 3, seed=5, val_per_camera=1)
    c = synth.generate_dataset(tmp_path / "c", 2, 3, seed=6, val_per_camera=1)
    for key in ("planogram", "annotations", "annotations_train"):
        assert a[key].read_bytes() == b[key].read_bytes()
    first = sorted(a["images_dir"].rglob("*.jpg"))[0].relative_to(a["images_dir"])
    assert (a["images_dir"] / first).read_bytes() == (b["images_dir"] / first).read_bytes()
    assert a["annotations_train"].read_bytes() != c["annotations_train"].read_bytes()


def test_edge_sizes_and_safety(tmp_path):
    info = synth.generate_dataset(tmp_path / "one", n_cameras=1, images_per_camera=1, seed=1,
                                  val_per_camera=0)
    assert info["n_train_images"] == 1 and info["n_val_images"] == 0
    assert _load(info["annotations"]) == {}
    # a real planogram that this generator did not write must never be overwritten
    real = tmp_path / "real"
    real.mkdir()
    (real / "planogram.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        synth.generate_dataset(real, 1, 1)
    assert (real / "planogram.json").read_text() == "{}"
    # regenerating into its own output folder is fine
    synth.generate_dataset(tmp_path / "one", n_cameras=1, images_per_camera=2, seed=1, val_per_camera=0)

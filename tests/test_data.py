"""Tests for sensei.data: planogram, discovery, image loading and perspective warping."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sensei.config import Config
from sensei.data import (discover_images, inset_quad, load_image, load_planogram, subsample_even,
                         visible_fraction, warp_area)
from tests.conftest import TINY_H, TINY_W, write_image

SQUARE = np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=np.float32)


# --------------------------------------------------------------------------- config

def test_config_roundtrip(tmp_path: Path) -> None:
    cfg = Config(backend="lite", inset=0.1, level_prior=[0.2, 0.3, 0.5])
    cfg.to_json(tmp_path / "cfg.json")
    back = Config.from_json(tmp_path / "cfg.json")
    assert back == cfg and back.level_prior == (0.2, 0.3, 0.5)
    with pytest.raises(ValueError):
        Config(backend="bogus")


# --------------------------------------------------------------------------- planogram

def test_load_tiny_planogram(tiny_planogram: Path) -> None:
    areas = load_planogram(tiny_planogram)
    assert list(areas) == ["1001", "1002"]
    a = areas["1002"][0]
    assert a.area_id == "1002_1" and a.product_name == "FEIJÃO VERDE CNT KG"
    assert a.quad.shape == (4, 2) and a.quad.dtype == np.float32
    assert a.quad[0].tolist() == [-40, -30]
    assert a.section == "Frutas e Legumes"


# --------------------------------------------------------------------------- geometry

def test_inset_quad_shrinks_towards_centre() -> None:
    q = inset_quad(SQUARE, 0.1)
    assert np.allclose(q.mean(0), SQUARE.mean(0))
    assert np.allclose(q[0], [15, 15]) and np.allclose(q[2], [105, 105])
    assert np.allclose(inset_quad(SQUARE, 0.0), SQUARE)


def test_warp_inside_is_fully_visible() -> None:
    img = np.zeros((200, 200, 3), np.uint8)
    img[10:60, 10:111] = (255, 0, 0)   # top half of the square red
    img[60:111, 10:111] = (0, 0, 255)  # bottom half blue
    crop, vis = warp_area(img, SQUARE, size=64)
    assert crop.shape == (64, 64, 3) and crop.dtype == np.uint8 and vis.shape == (64, 64)
    assert vis.all()
    assert crop[5, 32, 0] > 200 and crop[58, 32, 2] > 200  # orientation kept (TL at top)
    assert visible_fraction(SQUARE, img.shape) == pytest.approx(1.0)


def test_warp_negative_coords_partly_visible() -> None:
    img = np.full((100, 100, 3), 200, np.uint8)
    quad = np.array([[-50, -50], [50, -50], [50, 50], [-50, 50]], np.float32)  # 1/4 inside
    crop, vis = warp_area(img, quad, size=40)
    assert visible_fraction(quad, img.shape) == pytest.approx(0.25, abs=1e-6)
    assert 0.2 < vis.mean() < 0.3
    assert vis[30, 30] and not vis[5, 5]
    assert (crop[~vis] == 0).all() and (crop[vis] == 200).all()


def test_warp_fully_outside_and_degenerate() -> None:
    img = np.full((100, 100, 3), 200, np.uint8)
    out = np.array([[300, 300], [400, 300], [400, 400], [300, 400]], np.float32)
    crop, vis = warp_area(img, out, size=32)
    assert not vis.any() and not crop.any()
    assert visible_fraction(out, img.shape) == 0.0
    line = np.array([[0, 0], [10, 10], [20, 20], [30, 30]], np.float32)
    crop, vis = warp_area(img, line, size=32, inset=0.1)
    assert crop.shape == (32, 32, 3) and not vis.any()
    assert visible_fraction(line, img.shape) == 0.0


def test_warp_with_inset_and_grayscale_image() -> None:
    gray = np.full((120, 120), 77, np.uint8)
    crop, vis = warp_area(gray, SQUARE, size=16, inset=0.06)
    assert crop.shape == (16, 16) and vis.all() and (crop == 77).all()


# --------------------------------------------------------------------------- image loading

def test_load_image_formats_and_unicode_path(tmp_path: Path) -> None:
    rgb = np.zeros((20, 30, 3), np.uint8)
    rgb[..., 0] = 250  # pure red
    d = tmp_path / "maçã ção"
    p_png = write_image(d / "img.png", rgb)
    out = load_image(p_png)
    assert out.shape == (20, 30, 3) and out.dtype == np.uint8 and out[0, 0].tolist() == [250, 0, 0]

    p_gray = write_image(d / "gray.jpg", np.full((10, 12), 128, np.uint8))
    g = load_image(p_gray)
    assert g.shape == (10, 12, 3) and abs(int(g[5, 5, 0]) - 128) < 3

    import cv2
    rgba = np.zeros((8, 8, 4), np.uint8)
    rgba[..., 1] = 200
    rgba[..., 3] = 255
    ok, buf = cv2.imencode(".png", rgba)  # BGRA: channel 1 = green
    buf.tofile(str(d / "alpha.png"))
    a = load_image(d / "alpha.png")
    assert a.shape == (8, 8, 3) and a[0, 0].tolist() == [0, 200, 0]

    (d / "broken.jpg").write_bytes(b"not an image")
    with pytest.raises(ValueError):
        load_image(d / "broken.jpg")


# --------------------------------------------------------------------------- discovery

def test_discover_real_layout(tiny_dataset: tuple[Path, Path]) -> None:
    root, plan = tiny_dataset
    cams = list(load_planogram(plan))
    (root / "1001" / "._1751001000.jpg").write_bytes(b"x")  # AppleDouble junk
    (root / "1001" / ".hidden.jpg").write_bytes(b"x")
    (root / "1001" / "notes.txt").write_text("x")
    write_image(root / "9999" / "1751001000.jpg", np.zeros((4, 4, 3), np.uint8))  # unknown camera
    recs = discover_images(root, cams)
    assert len(recs) == 6
    assert {r.split for r in recs} == {"unknown"}
    assert [r.camera_id for r in recs] == ["1001"] * 3 + ["1002"] * 3
    assert recs[0].timestamp == 1751001000 and recs[0].image_name == "1751001000.jpg"
    assert discover_images(root, cams, splits=("train", "test")) == recs  # no split dirs -> all
    img = load_image(recs[0].path)
    assert img.shape == (TINY_H, TINY_W, 3)


def test_discover_flat_and_nested_splits(tmp_path: Path) -> None:
    px = np.zeros((4, 4, 3), np.uint8)
    write_image(tmp_path / "train" / "1001_1751000001.JPG", px)        # flat, prefix, upper ext
    write_image(tmp_path / "train" / "1002-1751000002.jpeg", px)
    write_image(tmp_path / "Validation" / "x" / "1001" / "snap.png", px)  # nested, non-numeric
    write_image(tmp_path / "test" / "1002" / "1751000003.jpg", px)
    write_image(tmp_path / "test" / "7777_1751000004.jpg", px)          # unknown camera
    recs = discover_images(tmp_path, ["1001", "1002"])
    got = {(r.camera_id, r.image_name, r.timestamp, r.split) for r in recs}
    assert got == {("1001", "1001_1751000001.JPG", 1751000001, "train"),
                   ("1002", "1002-1751000002.jpeg", 1751000002, "train"),
                   ("1001", "snap.png", -1, "val"),
                   ("1002", "1751000003.jpg", 1751000003, "test")}
    assert {r.image_name for r in discover_images(tmp_path, ["1001", "1002"], splits=["val"])} \
        == {"snap.png"}
    assert recs == sorted(recs, key=lambda r: (r.camera_id, r.timestamp, r.image_name))
    assert discover_images(tmp_path / "missing", ["1001"]) == []


def test_subsample_even_keeps_ends(tiny_dataset: tuple[Path, Path]) -> None:
    root, plan = tiny_dataset
    recs = discover_images(root, list(load_planogram(plan)))
    sub = subsample_even(recs, 2)
    assert len(sub) == 4
    for cam in ("1001", "1002"):
        ts = [r.timestamp for r in sub if r.camera_id == cam]
        assert ts == [1751001000, 1751008200]
    assert subsample_even(recs, 10) == recs and subsample_even(recs, 0) == []


# --------------------------------------------------------------------------- real data

def test_real_planogram_and_images(real_planogram_path: Path, real_images_dir: Path,
                                   real_areas: dict) -> None:
    assert len(real_areas) == 14
    assert sum(len(v) for v in real_areas.values()) == 152
    recs = discover_images(real_images_dir, list(real_areas))
    assert len(recs) == 181
    assert {r.camera_id for r in recs} == set(real_areas)
    assert all(r.split == "unknown" and r.timestamp > 1_700_000_000 for r in recs)
    img = load_image(recs[0].path)
    assert img.shape == (720, 1280, 3)
    fracs = [visible_fraction(a.quad, img.shape) for v in real_areas.values() for a in v]
    assert sum(f < 0.999 for f in fracs) == 5 and min(fracs) > 0.2
    for a in real_areas[recs[0].camera_id]:
        crop, vis = warp_area(img, a.quad, size=224, inset=0.06)
        assert crop.shape == (224, 224, 3) and vis.mean() > 0.2

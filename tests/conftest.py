"""Shared pytest fixtures: paths to the real dataset (skip if absent) and tiny synthetic data.

Fixtures
- ``project_root``      : Path of the repository.
- ``real_root``         : data/raw (skips the test when the real dataset is not present).
- ``real_planogram_path``, ``real_images_dir``, ``real_areas`` (load_planogram result, cached).
- ``debug_dir``         : outputs/debug/tests/ (created) for optional visual output.
- ``tiny_planogram``    : writes a 2-camera planogram.json (one area partly outside the frame,
                          accented product names) into tmp_path and returns its path.
- ``tiny_dataset``      : (images_root, planogram_path) with 3 small JPEGs per camera in the real
                          ``<root>/<camera>/<ts>.jpg`` layout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # so `pytest` (not only `python -m pytest`) finds sensei/ and scoring.py
    sys.path.insert(0, str(ROOT))

REAL_ROOT = ROOT / "data" / "raw"
HAS_REAL_DATA = (REAL_ROOT / "planogram.json").is_file() and (REAL_ROOT / "images").is_dir()

TINY_W, TINY_H = 320, 180
TINY_PLANOGRAM = {
    "Frutas e Legumes": {"cameras": {
        "1001": {"products": [
            {"area_id": "1001_1", "product_id": "11908", "product_name": "BANANA CAT I CNT KG",
             "image_coordinates": {"top_left": [10, 10], "top_right": [150, 12],
                                   "bottom_right": [155, 80], "bottom_left": [8, 78]}},
            {"area_id": "1001_2", "product_id": "32262", "product_name": "MAÇÃ COSMIC CRISP 75/85 KG",
             "image_coordinates": {"top_left": [160, 10], "top_right": [310, 10],
                                   "bottom_right": [312, 85], "bottom_left": [158, 82]}},
        ]},
        "1002": {"products": [
            {"area_id": "1002_1", "product_id": "21413", "product_name": "FEIJÃO VERDE CNT KG",
             "image_coordinates": {"top_left": [-40, -30], "top_right": [120, -25],
                                   "bottom_right": [118, 90], "bottom_left": [-38, 88]}},
            {"area_id": "1002_2", "product_id": "22304", "product_name": "TOMATE CHERRY BIO EMB. 250 GR",
             "image_coordinates": {"top_left": [130, 95], "top_right": [300, 95],
                                   "bottom_right": [305, 170], "bottom_left": [128, 172]}},
        ]},
    }},
}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: needs model weights / takes long (deep backend)")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def real_root() -> Path:
    if not HAS_REAL_DATA:
        pytest.skip("real dataset not present under data/raw")
    return REAL_ROOT


@pytest.fixture(scope="session")
def real_planogram_path(real_root: Path) -> Path:
    return real_root / "planogram.json"


@pytest.fixture(scope="session")
def real_images_dir(real_root: Path) -> Path:
    return real_root / "images"


@pytest.fixture(scope="session")
def real_areas(real_planogram_path: Path) -> dict:
    from sensei.data import load_planogram
    return load_planogram(real_planogram_path)


@pytest.fixture(scope="session")
def debug_dir() -> Path:
    d = ROOT / "outputs" / "debug" / "tests"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def tiny_planogram(tmp_path: Path) -> Path:
    path = tmp_path / "planogram.json"
    path.write_text(json.dumps(TINY_PLANOGRAM, ensure_ascii=False), encoding="utf-8")
    return path


def write_image(path: Path, rgb: np.ndarray) -> Path:
    """Write an RGB uint8 image with cv2 (unicode-safe); the format follows the extension."""
    import cv2
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = rgb if rgb.ndim == 2 else cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(path.suffix, arr)
    assert ok, path
    buf.tofile(str(path))
    return path


@pytest.fixture
def tiny_dataset(tmp_path: Path, tiny_planogram: Path) -> tuple[Path, Path]:
    root = tmp_path / "images"
    rng = np.random.default_rng(0)
    for cam in ("1001", "1002"):
        for k, ts in enumerate((1751001000, 1751004600, 1751008200)):
            img = rng.integers(0, 255, size=(TINY_H, TINY_W, 3), dtype=np.uint8)
            img[:, :, 0] = 40 * k
            write_image(root / cam / f"{ts}.jpg", img)
    return root, tiny_planogram

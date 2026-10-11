"""Planogram loading, image discovery and perspective warping of planogram areas."""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
SPLIT_NAMES = {"train": "train", "test": "test", "val": "val", "validation": "val", "valid": "val"}
CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")


@dataclass(frozen=True)
class Area:
    """One planogram area. ``quad`` is (4,2) float32 [TL, TR, BR, BL] in image pixels."""

    area_id: str
    camera_id: str
    product_id: str
    product_name: str
    section: str
    quad: np.ndarray = field(compare=False, repr=False)


@dataclass(frozen=True)
class ImageRecord:
    """One camera frame on disk. ``timestamp`` is -1 when the file stem is not a number."""

    path: Path
    camera_id: str
    image_name: str
    timestamp: int
    split: str


# --------------------------------------------------------------------------- planogram

def load_planogram(path: str | Path) -> dict[str, list[Area]]:
    """Read planogram.json (UTF-8, every section) -> camera_id -> areas in file order."""
    with open(path, encoding="utf-8-sig") as f:
        doc = json.load(f)
    areas_by_cam: dict[str, list[Area]] = {}
    seen: set[str] = set()
    for section, sec in doc.items():
        cameras = sec.get("cameras", {}) if isinstance(sec, dict) else {}
        for cam_id, cam in cameras.items():
            cam_id = str(cam_id)
            lst = areas_by_cam.setdefault(cam_id, [])
            for p in cam.get("products", []):
                coords = p["image_coordinates"]
                quad = np.array([coords[c] for c in CORNERS], dtype=np.float32).reshape(4, 2)
                quad.setflags(write=False)
                area_id = str(p["area_id"])
                if area_id in seen:
                    log.warning("planogram: duplicate area_id %s (camera %s) kept twice", area_id, cam_id)
                seen.add(area_id)
                lst.append(Area(area_id=area_id, camera_id=cam_id, product_id=str(p["product_id"]),
                                product_name=str(p["product_name"]).strip(), section=str(section),
                                quad=quad))
    return areas_by_cam


# --------------------------------------------------------------------------- discovery

def _is_hidden(name: str) -> bool:
    return name.startswith(".") or name.startswith("__MACOSX")


def _camera_from_prefix(stem: str, cams_by_len: list[str]) -> str | None:
    for cam in cams_by_len:  # longest ids first, so "62151" is not taken for "6215"
        if stem.startswith(cam) and len(stem) > len(cam) and stem[len(cam)] in "_-":
            return cam
    return None


def _timestamp(stem: str, camera_id: str) -> int:
    if stem.isdigit():
        return int(stem)
    rest = stem[len(camera_id) + 1:] if stem.startswith(camera_id) else ""
    return int(rest) if rest.isdigit() else -1


def discover_images(root: str | Path, camera_ids: Iterable[str],
                    splits: Iterable[str] | None = None) -> list[ImageRecord]:
    """Find camera frames under ``root`` (any depth), sorted by (camera, timestamp, name).

    Camera = nearest folder name equal to a known camera id (``root`` itself counts), else a
    file-name prefix ``<cam>_`` / ``<cam>-``; images of unknown cameras are ignored.
    Split = nearest folder in {train, test, val, validation}, else "unknown".
    ``splits`` filters by split; if the tree has no split folders at all (the real dataset:
    train and test are mixed), the filter cannot apply and every image is returned.
    """
    root = Path(root)
    cams = {str(c) for c in camera_ids}
    cams_by_len = sorted(cams, key=len, reverse=True)
    if not root.is_dir():
        log.warning("discover_images: %s is not a directory", root)
        return []

    records: list[ImageRecord] = []
    unknown_cam = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _is_hidden(d))
        rel_parts = Path(dirpath).relative_to(root).parts
        parts = [p for p in (root.resolve().name, *rel_parts) if p]  # nearest component is last
        dir_cam = next((p for p in reversed(parts) if p in cams), None)
        split = next((SPLIT_NAMES[p.lower()] for p in reversed(parts) if p.lower() in SPLIT_NAMES),
                     "unknown")
        for name in sorted(filenames):
            if _is_hidden(name) or Path(name).suffix.lower() not in IMAGE_EXTS:
                continue
            stem = Path(name).stem
            cam = dir_cam or _camera_from_prefix(stem, cams_by_len)
            if cam is None:
                unknown_cam += 1
                continue
            records.append(ImageRecord(path=Path(dirpath) / name, camera_id=cam, image_name=name,
                                       timestamp=_timestamp(stem, cam), split=split))
    if unknown_cam:
        log.warning("discover_images: ignored %d image(s) of cameras not in the planogram", unknown_cam)

    if splits is not None:
        wanted = {SPLIT_NAMES.get(s.lower(), s.lower()) for s in splits}
        if any(r.split != "unknown" for r in records):
            records = [r for r in records if r.split in wanted]
        else:
            log.info("discover_images: no split folders under %s, using all %d images",
                     root, len(records))

    dup = [k for k, n in Counter((r.camera_id, r.image_name) for r in records).items() if n > 1]
    if dup:
        log.warning("discover_images: %d (camera, image_name) pairs occur more than once, e.g. %s",
                    len(dup), dup[0])
    records.sort(key=lambda r: (r.camera_id, r.timestamp, r.image_name, str(r.path)))
    return records


def subsample_even(records: list[ImageRecord], k: int) -> list[ImageRecord]:
    """Keep at most ``k`` images per camera, evenly spaced over the time-sorted list.

    The first and last image of each camera are always kept (when k >= 2).
    """
    if k <= 0:
        return []
    by_cam: dict[str, list[ImageRecord]] = {}
    for r in records:
        by_cam.setdefault(r.camera_id, []).append(r)
    out: list[ImageRecord] = []
    for cam_recs in by_cam.values():
        cam_recs.sort(key=lambda r: (r.timestamp, r.image_name))
        n = len(cam_recs)
        if n <= k:
            out.extend(cam_recs)
            continue
        idx = np.unique(np.floor(np.linspace(0, n - 1, k) + 0.5).astype(int))
        out.extend(cam_recs[i] for i in idx)
    out.sort(key=lambda r: (r.camera_id, r.timestamp, r.image_name, str(r.path)))
    return out


# --------------------------------------------------------------------------- images

def load_image(path: str | Path) -> np.ndarray:
    """Read an image as RGB uint8 (H, W, 3). Works with unicode paths, grayscale, PNG + alpha.

    Raises FileNotFoundError if missing, ValueError if the file cannot be decoded.
    """
    path = Path(path)
    buf = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED) if buf.size else None
    if img is None:
        img = _load_with_pillow(path)
    if img.dtype != np.uint8:
        img = _to_uint8(img)
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    channels = img.shape[2]
    if channels == 1:
        return cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2RGB)
    if channels == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
    if channels == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    raise ValueError(f"unsupported channel count {channels} in {path}")


def image_size(path: str | Path) -> tuple[int, int] | None:
    """(width, height) from the file header (cheap, no decode); None if unreadable."""
    try:
        from PIL import Image  # noqa: PLC0415
        with Image.open(path) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:  # noqa: BLE001 - corrupt / missing: the caller decides
        return None


def common_frame_size(paths: Iterable[str | Path], limit: int = 50) -> tuple[int, int] | None:
    """Most common (width, height) among (up to ``limit``) images: the frame size the planogram
    quads are drawn in. None if none is readable."""
    sizes = Counter(s for s in (image_size(p) for p in list(paths)[:limit]) if s is not None)
    return sizes.most_common(1)[0][0] if sizes else None


def to_frame_size(image: np.ndarray, frame_size: Iterable[int] | None) -> np.ndarray:
    """``image`` resized to ``frame_size`` (w, h) when it differs (planogram quads are absolute pixels
    of the fit-time frame); unchanged otherwise."""
    if not frame_size:
        return image
    w0, h0 = (int(v) for v in frame_size)
    h, w = image.shape[:2]
    if (w, h) == (w0, h0) or w0 <= 0 or h0 <= 0:
        return image
    interp = cv2.INTER_AREA if w > w0 else cv2.INTER_LINEAR
    return cv2.resize(image, (w0, h0), interpolation=interp)


def _load_with_pillow(path: Path) -> np.ndarray:
    """Fallback decoder (formats OpenCV lacks); returns BGR like cv2 or raises ValueError."""
    try:
        from PIL import Image  # noqa: PLC0415
        with Image.open(path) as im:
            rgb = np.asarray(im.convert("RGB"))
    except Exception as exc:  # noqa: BLE001 - any decoder error means a corrupt file
        raise ValueError(f"cannot decode image {path}: {exc}") from exc
    return np.ascontiguousarray(rgb[:, :, ::-1])


def _to_uint8(img: np.ndarray) -> np.ndarray:
    if img.dtype == np.uint16:
        return (img >> 8).astype(np.uint8)
    if np.issubdtype(img.dtype, np.floating):
        scale = 255.0 if np.nanmax(img) <= 1.0 else 1.0
        return np.clip(np.nan_to_num(img) * scale, 0, 255).astype(np.uint8)
    return np.clip(img, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- geometry

def inset_quad(quad: np.ndarray, frac: float) -> np.ndarray:
    """Shrink a quad towards its centroid: each corner moves ``frac`` of the way to the centre.

    For a rectangle this trims frac/2 of the width (and height) on every side.
    """
    q = np.asarray(quad, dtype=np.float32).reshape(4, 2)
    if frac <= 0:
        return q.copy()
    c = q.mean(axis=0, keepdims=True)
    return (c + (q - c) * (1.0 - float(frac))).astype(np.float32)


def _polygon_area(poly: np.ndarray) -> float:
    if len(poly) < 3:
        return 0.0
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _clip_polygon(poly: np.ndarray, w: float, h: float) -> np.ndarray:
    """Sutherland-Hodgman clip of a polygon against the rectangle [0,w] x [0,h]."""
    pts = [tuple(p) for p in np.asarray(poly, dtype=np.float64)]
    edges = [(0, 0.0, 1), (0, w, -1), (1, 0.0, 1), (1, h, -1)]  # (axis, bound, keep side sign)
    for axis, bound, sign in edges:
        if not pts:
            break
        inside = [sign * (p[axis] - bound) >= 0 for p in pts]
        out = []
        for i, p in enumerate(pts):
            q, q_in = pts[i - 1], inside[i - 1]
            if inside[i] != q_in:  # edge crosses the boundary: add intersection
                t = (bound - q[axis]) / (p[axis] - q[axis])
                out.append((q[0] + t * (p[0] - q[0]), q[1] + t * (p[1] - q[1])))
            if inside[i]:
                out.append(p)
        pts = out
    return np.array(pts, dtype=np.float64).reshape(-1, 2)


def visible_fraction(quad: np.ndarray, image_shape: tuple[int, ...]) -> float:
    """Share of the quad's area (in image space) that lies inside the frame."""
    h, w = image_shape[:2]
    q = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    total = _polygon_area(q)
    if total <= 1e-9:
        return 0.0
    return float(np.clip(_polygon_area(_clip_polygon(q, w, h)) / total, 0.0, 1.0))


def area_transform(quad: np.ndarray, size: int = 224, inset: float = 0.0) -> np.ndarray | None:
    """3x3 homography mapping the (inset) quad [TL,TR,BR,BL] onto a size x size square.

    Returns None for a degenerate quad (collinear corners / zero area).
    """
    src = inset_quad(quad, inset) if inset > 0 else np.asarray(quad, dtype=np.float32).reshape(4, 2)
    if _polygon_area(src.astype(np.float64)) < 1.0:
        return None
    s = float(size - 1)
    dst = np.array([[0, 0], [s, 0], [s, s], [0, s]], dtype=np.float32)
    try:
        m = cv2.getPerspectiveTransform(src.astype(np.float32), dst)
    except cv2.error:
        return None
    return m if np.all(np.isfinite(m)) else None


def warp_area(image: np.ndarray, quad: np.ndarray, size: int = 224,
              inset: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Rectify one planogram area to a square crop.

    Returns (crop uint8 (size, size, C), visible bool (size, size)); crop pixels that fall
    outside the image are 0 and visible False.
    """
    h, w = image.shape[:2]
    shape = (size, size) + image.shape[2:]
    m = area_transform(quad, size, inset)
    if m is None:
        return np.zeros(shape, dtype=np.uint8), np.zeros((size, size), dtype=bool)
    crop = cv2.warpPerspective(image, m, (size, size), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    ones = np.ones((h, w), dtype=np.uint8)
    visible = cv2.warpPerspective(ones, m, (size, size), flags=cv2.INTER_NEAREST,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    crop = crop.reshape(shape).astype(np.uint8, copy=False)
    crop[~visible] = 0
    return crop, visible

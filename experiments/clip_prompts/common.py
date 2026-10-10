"""Shared helpers for the clip_prompts experiment (self-contained; does not import sensei/)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXP = Path(__file__).resolve().parent
PLANOGRAM = ROOT / "data" / "raw" / "planogram.json"
IMAGES = ROOT / "data" / "raw" / "images"
CACHE = EXP / "cache"
SHEETS = EXP / "sheets"

CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")


def load_planogram(path=PLANOGRAM):
    """camera_id -> list of dict(area_id, product_id, product_name, quad (4,2) float32)."""
    with open(path, encoding="utf-8") as f:
        pg = json.load(f)
    out = {}
    for section, sv in pg.items():
        for cam, cv in sv["cameras"].items():
            lst = out.setdefault(str(cam), [])
            for p in cv["products"]:
                q = np.array([p["image_coordinates"][k] for k in CORNERS], np.float32)
                lst.append(dict(area_id=p["area_id"], product_id=str(p["product_id"]),
                                product_name=p["product_name"], quad=q, section=section))
    return out


def list_images(root=IMAGES, cams=None):
    recs = []
    for cam_dir in sorted(Path(root).iterdir()):
        if not cam_dir.is_dir():
            continue
        cam = cam_dir.name
        if cams is not None and cam not in cams:
            continue
        for p in sorted(cam_dir.glob("*.jpg")):
            try:
                ts = int(p.stem)
            except ValueError:
                ts = -1
            recs.append(dict(cam=cam, image_name=p.name, ts=ts, path=p))
    recs.sort(key=lambda r: (r["cam"], r["ts"], r["image_name"]))
    return recs


def load_image(path):
    buf = np.fromfile(str(path), np.uint8)
    im = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if im is None:
        raise IOError(f"cannot decode {path}")
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def inset_quad(quad, frac):
    c = quad.mean(0, keepdims=True)
    return (c + (quad - c) * (1.0 - 2 * frac)).astype(np.float32)


def warp_quad(image, quad, size=224, inset=0.06):
    """Perspective-warp the (inset) quad to size x size. Returns (crop, visible mask)."""
    q = inset_quad(quad, inset) if inset > 0 else quad.astype(np.float32)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    M = cv2.getPerspectiveTransform(q, dst)
    crop = cv2.warpPerspective(image, M, (size, size), flags=cv2.INTER_AREA,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    ones = np.full(image.shape[:2], 255, np.uint8)
    vis = cv2.warpPerspective(ones, M, (size, size), flags=cv2.INTER_NEAREST,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 127
    return crop, vis


def bbox_crop(image, quad, size=224, context=0.12):
    """Axis-aligned bbox of the quad with `context` margin, padded to square, resized.
    Pixels outside the frame are filled with mid-grey (128)."""
    H, W = image.shape[:2]
    x0, y0 = quad.min(0)
    x1, y1 = quad.max(0)
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(w, h) * (1 + 2 * context)
    sx0, sy0 = int(round(cx - side / 2)), int(round(cy - side / 2))
    s = int(round(side))
    canvas = np.full((s, s, 3), 128, np.uint8)
    ix0, iy0 = max(sx0, 0), max(sy0, 0)
    ix1, iy1 = min(sx0 + s, W), min(sy0 + s, H)
    if ix1 > ix0 and iy1 > iy0:
        canvas[iy0 - sy0:iy1 - sy0, ix0 - sx0:ix1 - sx0] = image[iy0:iy1, ix0:ix1]
    return cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA)


def quad_visible_fraction(quad, shape):
    H, W = shape[:2]
    # rasterise at 1/2 res for speed
    xs, ys = quad[:, 0], quad[:, 1]
    x0, y0 = int(np.floor(xs.min())), int(np.floor(ys.min()))
    x1, y1 = int(np.ceil(xs.max())), int(np.ceil(ys.max()))
    m = np.zeros((y1 - y0 + 1, x1 - x0 + 1), np.uint8)
    cv2.fillPoly(m, [np.round(quad - [x0, y0]).astype(np.int32)], 1)
    tot = m.sum()
    if tot == 0:
        return 0.0
    yy, xx = np.nonzero(m)
    xx, yy = xx + x0, yy + y0
    inside = ((xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)).sum()
    return float(inside) / float(tot)


def key_of(cam, image_name, area_id):
    return f"{cam}|{image_name}|{area_id}"

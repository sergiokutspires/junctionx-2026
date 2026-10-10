"""Shared helpers for the compliance_zeroshot experiment (no imports from sensei/)."""
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


def load_planogram(path=PLANOGRAM):
    """camera_id -> list of dict(area_id, product_id, product_name, quad (4,2) float32)."""
    with open(path, encoding="utf-8") as f:
        pg = json.load(f)
    out = {}
    for sec, v in pg.items():
        for cam, c in v["cameras"].items():
            lst = out.setdefault(str(cam), [])
            for p in c["products"]:
                ic = p["image_coordinates"]
                quad = np.array([ic["top_left"], ic["top_right"], ic["bottom_right"], ic["bottom_left"]],
                                dtype=np.float32)
                lst.append(dict(area_id=p["area_id"], product_id=str(p["product_id"]),
                                product_name=p["product_name"], quad=quad, section=sec))
    return out


def list_images(cams):
    recs = []
    for cam in cams:
        d = IMAGES / cam
        if not d.is_dir():
            continue
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                recs.append((cam, fn, str(d / fn)))
    return recs


def load_image(path):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def inset_quad(quad, frac):
    c = quad.mean(0, keepdims=True)
    return (c + (quad - c) * (1.0 - frac)).astype(np.float32)


def warp_area(image, quad, size=224, inset=0.0):
    """Perspective-warp the quad to a size x size square. Returns (crop, visible mask)."""
    q = inset_quad(quad, inset) if inset > 0 else quad.astype(np.float32)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(q, dst)
    crop = cv2.warpPerspective(image, M, (size, size), flags=cv2.INTER_AREA if False else cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    ones = np.full(image.shape[:2], 255, np.uint8)
    vis = cv2.warpPerspective(ones, M, (size, size), flags=cv2.INTER_NEAREST,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 127
    return crop, vis


def bbox_crop(image, quad, pad=0.08, square=True, size=224):
    """Axis-aligned bounding-box crop of the quad (natural perspective, keeps object shapes),
    padded, clipped to the image; returns (crop resized to size x size with letterbox, visible frac)."""
    H, W = image.shape[:2]
    x0, y0 = quad.min(0)
    x1, y1 = quad.max(0)
    w, h = x1 - x0, y1 - y0
    x0 -= pad * w; x1 += pad * w; y0 -= pad * h; y1 += pad * h
    if square:
        cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0)
        x0, x1, y0, y1 = cx - s / 2, cx + s / 2, cy - s / 2, cy + s / 2
    xi0, yi0 = int(max(0, np.floor(x0))), int(max(0, np.floor(y0)))
    xi1, yi1 = int(min(W, np.ceil(x1))), int(min(H, np.ceil(y1)))
    if xi1 <= xi0 + 2 or yi1 <= yi0 + 2:
        return np.zeros((size, size, 3), np.uint8)
    crop = image[yi0:yi1, xi0:xi1]
    ch, cw = crop.shape[:2]
    s = size / max(ch, cw)
    nh, nw = max(1, int(round(ch * s))), max(1, int(round(cw * s)))
    r = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    out = np.zeros((size, size, 3), np.uint8)
    oy, ox = (size - nh) // 2, (size - nw) // 2
    out[oy:oy + nh, ox:ox + nw] = r
    return out


def visible_fraction(quad, shape):
    H, W = shape[:2]
    pts = quad.astype(np.float64)
    full = abs(cv2.contourArea(pts.astype(np.float32)))
    if full <= 0:
        return 0.0
    clip = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
    inter, _ = cv2.intersectConvexConvex(pts.astype(np.float32), clip)
    return float(max(0.0, min(1.0, inter / full)))

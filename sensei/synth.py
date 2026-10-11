"""Synthetic supermarket dataset: fake planogram + ceiling-camera frames + val annotations.

Purpose: tests, demos and end-to-end checks without the real dataset. The scene mimics the
real one: grey floor, crates (mostly teal) seen in perspective, products drawn as
many small coloured ellipses (loose) or labelled rectangles (packaged), stock that varies over
a day with restocks, ~8% of restocked areas holding another product of the same camera,
occasional hands over the shelves, and one area partly outside the frame.

Output layout (all UTF-8 JSON, all images 1280x720 JPEG)::

    out_dir/planogram.json              real schema, section "Frutas e Legumes"
    out_dir/images/<cam>/<ts>.jpg       "train/test" frames of one day
    out_dir/val/<cam>/<ts>.jpg          later frames (hidden validation analogue)
    out_dir/annotations.json            truth for the val frames (challenge format)
    out_dir/annotations_train.json      same format for the images/ frames (dev extra)

Use ``--data <out_dir>/images`` for ``fit`` (a ``val`` folder next to ``images`` would make the
split filter drop the unlabelled-split images) and ``--images <out_dir>/val`` for ``predict``.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

W, H = 1280, 720
SECTION = "Frutas e Legumes"
DAY_START, DAY_END = 1751001155, 1751049846   # 06:12 .. 19:24 Lisbon, like the real day
VAL_START = 1751052241                         # the brief's example timestamp: later than the day
LEVEL_NAMES = {0.0: "empty", 0.5: "half", 1.0: "full"}
CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")
MARKER = "SYNTHETIC.txt"
RIM = 9                       # crate rim width in texture pixels
P_WRONG = 0.08                # share of restocks that put another product into the area
MAX_ITEMS = 420               # cap of drawn items per crate (keeps generation fast)

# (product_id, planogram name, item colour RGB, item half-axes (a, b) px, max tilt degrees)
LOOSE = [
    (11908, "BANANA CAT I CNT KG", (236, 204, 48), (23, 6), 30),
    (12441, "LARANJA CAL. 73/85 KG", (240, 136, 28), (11, 11), 180),
    (13077, "MAÇÃ GALA KG", (192, 40, 46), (11, 11), 180),
    (13590, "MAÇÃ GOLDEN KG", (214, 204, 72), (11, 11), 180),
    (13913, "MAÇÃ GRANNY SMITH KG", (126, 184, 58), (11, 11), 180),
    (14226, "TOMATE RAMO KG", (208, 42, 34), (10, 9), 180),
    (14802, "PERA ROCHA CAL. 60/65 KG", (186, 192, 84), (13, 10), 60),
    (15119, "LIMÃO KG", (246, 228, 62), (13, 9), 60),
    (15633, "KIWI VERDE KG", (140, 114, 64), (12, 9), 60),
    (16058, "CEBOLA AMARELA KG", (204, 148, 84), (11, 10), 180),
    (16372, "PEPINO KG", (54, 118, 56), (24, 6), 30),
    (16795, "PIMENTO VERMELHO KG", (198, 30, 38), (12, 10), 180),
    (17240, "CENOURA KG", (234, 124, 34), (22, 5), 35),
    (17684, "BATATA BRANCA KG", (206, 176, 120), (13, 10), 60),
    (18105, "UVA BRANCA S/ SEMENTES KG", (176, 202, 98), (8, 7), 180),
    (18527, "ANANÁS KG", (204, 160, 52), (17, 23), 25),
    (18963, "FEIJÃO VERDE CNT KG", (70, 160, 62), (21, 3), 40),
    (19310, "ABÓBORA KG", (226, 140, 56), (19, 14), 60),
    (19748, "MELÃO CANTALUPE KG", (222, 190, 122), (22, 18), 60),
    (20164, "PÊSSEGO AMARELO KG", (240, 168, 98), (11, 11), 180),
]
# (product_id, planogram name, dot colour RGB, dot radius px, label colour RGB)
PACKS = [
    (21307, "TOMATE CHERRY EMB. 250 G", (200, 36, 36), 4, (60, 150, 70)),
    (21856, "KIWI EMB. 500 G", (138, 112, 62), 6, (70, 160, 70)),
    (22418, "BATATA EMB. 3 KG", (206, 176, 120), 8, (200, 150, 40)),
    (22973, "MIRTILOS EMB. 125 G", (52, 58, 120), 4, (60, 90, 170)),
    (23509, "CEBOLA EMB. 1 KG", (204, 150, 80), 7, (220, 120, 40)),
    (24012, "MORANGO EMB. 500 G", (214, 44, 56), 5, (200, 50, 60)),
    (24574, "COGUMELOS EMB. 250 G", (226, 214, 190), 6, (130, 100, 70)),
]
CRATES = {  # kind -> (floor RGB, rim RGB)
    "teal": ((38, 150, 135), (22, 100, 92)),
    "grey": ((158, 162, 168), (112, 116, 122)),
    "cardboard": ((178, 142, 100), (140, 108, 74)),
}
COVERAGE = {0.0: (0.0, 0.07), 0.5: (0.38, 0.62), 1.0: (0.9, 1.0)}   # share of the crate covered


@dataclass(frozen=True)
class Art:
    """How one product is drawn."""

    pid: str
    name: str
    packaged: bool
    color: tuple
    size: tuple          # loose: item half-axes; packaged: (dot radius, 0)
    tilt: float = 180.0
    label: tuple = (0, 0, 0)


ARTS: list[Art] = (
    [Art(str(p), n, False, c, s, t) for p, n, c, s, t in LOOSE]
    + [Art(str(p), n, True, c, (r, 0), 0.0, lab) for p, n, c, r, lab in PACKS])


@dataclass
class _Area:
    area_id: str
    art: int                 # index into ARTS of the planogram product
    quad: np.ndarray         # (4, 2) float32 TL, TR, BR, BL (rounded to int pixels)
    crate: str
    tex_size: tuple          # inner (w, h) in texture px
    homog: np.ndarray        # texture -> image
    bbox: tuple              # clipped frame box (x0, y0, x1, y1) touched by the warped texture
    base: np.ndarray         # empty crate texture
    shift_homog: np.ndarray  # texture -> clipped bbox
    mask: np.ndarray         # (bh, bw, 1) bool, pixels of the bbox covered by the crate


@dataclass
class _Camera:
    cam_id: str
    areas: list
    background: np.ndarray
    noise: np.ndarray        # (H+64, W+64) int16 sensor-noise bank
    times: np.ndarray        # train times then val times
    levels: np.ndarray       # (n_areas, T) truth in {0, .5, 1}
    shown: np.ndarray        # (n_areas, T) ARTS index actually drawn
    seed: int


# ----------------------------------------------------------------------------- layout

def _camera_layout(rng: np.random.Generator, partly_outside: bool) -> list[np.ndarray]:
    """Crate quads (n, 4, 2) from a grid seen through a random perspective."""
    ncols, nrows = int(rng.integers(3, 5)), int(rng.integers(2, 4))
    cw, ch, gx, gy = 1.0, 0.62, 0.16, 0.20
    pw, ph = ncols * cw + (ncols - 1) * gx, nrows * ch + (nrows - 1) * gy
    plane = np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]])
    x0, x1 = rng.uniform(90, 140), W - rng.uniform(90, 140)
    ytop, ybot = rng.uniform(110, 170), H - rng.uniform(20, 50)
    squeeze = rng.uniform(0.06, 0.14) * (x1 - x0)
    jit = lambda: rng.uniform(-10, 10, 2)  # noqa: E731
    dst = np.float32([np.array([x0 + squeeze, ytop]) + jit(), np.array([x1 - squeeze, ytop]) + jit(),
                      np.array([x1, ybot]) + jit(), np.array([x0, ybot]) + jit()])
    mat = cv2.getPerspectiveTransform(plane, dst)
    quads = []
    for r in range(nrows):
        for c in range(ncols):
            xs, ys = c * (cw + gx), r * (ch + gy)
            corners = np.float32([[[xs, ys], [xs + cw, ys], [xs + cw, ys + ch], [xs, ys + ch]]])
            quads.append(np.round(cv2.perspectiveTransform(corners, mat)[0]))
    if partly_outside:  # push the top-right crate over the right frame edge (about 60% visible)
        q = quads[ncols - 1]
        width = float(q[:, 0].max() - q[:, 0].min())
        quads[ncols - 1] = q + np.float32([max(0.0, W - 0.6 * width - q[:, 0].min()), 0])
    return [q.astype(np.float32) for q in quads]


def _background(rng: np.random.Generator, ytop: float) -> np.ndarray:
    """Grey floor with tile seams and a dull back band (static for a camera)."""
    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    bg = np.array([150, 152, 156], np.float32) * (0.9 + 0.14 * yy) + rng.normal(0, 3, (H, W, 1))
    bg = np.clip(bg, 0, 255).astype(np.uint8)
    for x in range(int(rng.integers(0, 120)), W, 160):
        cv2.line(bg, (x, 0), (x, H), (134, 136, 141), 2)
    for y in range(int(rng.integers(0, 120)), H, 150):
        cv2.line(bg, (0, y), (W, y), (134, 136, 141), 2)
    band = int(max(40, ytop - 25))
    bg[:band] = (72, 76, 82)
    for _ in range(14):  # neutral clutter in the back band
        x, w = int(rng.integers(0, W - 80)), int(rng.integers(40, 160))
        v = int(rng.integers(95, 140))
        cv2.rectangle(bg, (x, int(rng.integers(0, band - 12))), (x + w, band - 4), (v, v + 3, v + 6), -1)
    return bg


def _crate_texture(rng: np.random.Generator, w: int, h: int, kind: str) -> np.ndarray:
    floor, rim = CRATES[kind]
    tex = np.empty((h + 2 * RIM, w + 2 * RIM, 3), np.float32)
    tex[:] = rim
    tex[RIM:RIM + h, RIM:RIM + w] = floor
    shade = np.ones(tex.shape[:2] + (1,), np.float32)
    step = int(rng.integers(22, 34))
    if kind == "teal":     # plastic ribs
        shade[:, RIM::step] = 0.86
    elif kind == "grey":   # metal tray grid
        shade[RIM::step, :] = 0.9
        shade[:, RIM::step] = 0.9
    else:                  # cardboard flap
        shade[h // 2 + RIM - 1:h // 2 + RIM + 1, :] = 0.8
    tex = tex * shade + rng.normal(0, 4, tex.shape[:2] + (1,))
    return np.clip(tex, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------- products

def _pick_order(rng: np.random.Generator, pts: np.ndarray, n_keep: int, size: tuple) -> np.ndarray:
    """Indices of the n_keep points nearest to one side of the crate (a half-empty pile)."""
    ang = math.radians(float(rng.choice([0, 90, 180, 270])) + rng.normal(0, 15))
    proj = pts @ np.array([math.cos(ang), math.sin(ang)]) + rng.normal(0, 0.05 * max(size), len(pts))
    keep = np.argsort(proj)[:n_keep]
    return keep[np.argsort(pts[keep, 1])]    # back to front


def _draw_loose(tex: np.ndarray, rng: np.random.Generator, art: Art, cov: float, scale: float) -> None:
    a, b = art.size[0] * scale, art.size[1] * scale
    iw, ih = tex.shape[1] - 2 * RIM, tex.shape[0] - 2 * RIM
    cap = int(min(MAX_ITEMS, 3.0 * iw * ih / (math.pi * a * b)))
    n_keep = int(round(cov * cap))
    if n_keep <= 0:
        return
    m = 0.5 * min(a, b)
    pts = rng.uniform([RIM + m, RIM + m], [RIM + iw - m, RIM + ih - m], size=(cap, 2))
    idx = _pick_order(rng, pts, n_keep, (iw, ih))
    cols = np.clip(np.array(art.color) + rng.normal(0, 9, (len(idx), 3)), 0, 255).astype(int).tolist()
    angs = rng.uniform(-art.tilt, art.tilt, len(idx)).tolist()
    ax, ay = max(1, int(a)), max(1, int(b))
    for (x, y), col, ang in zip(pts[idx].tolist(), cols, angs):
        c = (int(x), int(y))
        cv2.ellipse(tex, c, (ax, ay), ang, 0, 360, col, -1, cv2.LINE_AA)
        cv2.ellipse(tex, c, (ax, ay), ang, 0, 360, [int(v * 0.68) for v in col], 1, cv2.LINE_AA)
        if min(ax, ay) >= 6:
            cv2.ellipse(tex, (c[0] - ax // 4, c[1] - ay // 4), (max(1, ax // 3), max(1, ay // 3)),
                        ang, 0, 360, [min(255, int(v * 1.2) + 12) for v in col], -1, cv2.LINE_AA)


def _draw_packs(tex: np.ndarray, rng: np.random.Generator, art: Art, cov: float, scale: float) -> None:
    pw, ph = int(50 * scale), int(32 * scale)
    iw, ih = tex.shape[1] - 2 * RIM, tex.shape[0] - 2 * RIM
    cols_n, rows_n = max(1, iw // (pw + 5)), max(1, ih // (ph + 5))
    n_keep = int(round(cov * cols_n * rows_n))
    if n_keep <= 0:
        return
    gx = (np.arange(cols_n) + 0.5) * iw / cols_n + RIM
    gy = (np.arange(rows_n) + 0.5) * ih / rows_n + RIM
    pts = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2) + rng.normal(0, 2.5, (cols_n * rows_n, 2))
    idx = _pick_order(rng, pts, n_keep, (iw, ih))
    r = max(2, int(art.size[0] * scale))
    for x, y in pts[idx].tolist():
        x0, y0 = int(x - pw / 2), int(y - ph / 2)
        cv2.rectangle(tex, (x0, y0), (x0 + pw, y0 + ph), (232, 238, 242), -1)
        for _ in range(int(rng.integers(6, 10))):
            dx, dy = int(rng.integers(r, pw - r)), int(rng.integers(int(ph * 0.35) + r, ph - r + 1))
            col = np.clip(np.array(art.color) + rng.normal(0, 8, 3), 0, 255).astype(int).tolist()
            cv2.circle(tex, (x0 + dx, y0 + dy), r, col, -1, cv2.LINE_AA)
        cv2.rectangle(tex, (x0, y0), (x0 + pw, y0 + int(ph * 0.3)), art.label, -1)
        cv2.rectangle(tex, (x0, y0), (x0 + pw, y0 + ph), (118, 124, 130), 1)


def _draw_products(tex: np.ndarray, rng: np.random.Generator, art: Art, level: float, scale: float) -> None:
    lo, hi = COVERAGE[level]
    cov = float(rng.uniform(lo, hi))
    (_draw_packs if art.packaged else _draw_loose)(tex, rng, art, cov, scale)


def _draw_hand(img: np.ndarray, rng: np.random.Generator, quad: np.ndarray) -> None:
    """A skin-coloured forearm + hand reaching into the area (occluder)."""
    tip = quad.mean(0) + rng.normal(0, 14, 2)
    ang = rng.uniform(0, 2 * math.pi)
    direction = np.array([math.cos(ang), math.sin(ang)])
    mid, base = tip + 110 * direction, tip + 260 * direction
    skin = tuple(int(v) for v in rng.integers([150, 100, 70], [230, 175, 140]))
    sleeve = tuple(int(v) for v in rng.integers(20, 90, 3))
    p = lambda v: (int(v[0]), int(v[1]))  # noqa: E731
    cv2.line(img, p(base), p(mid), sleeve, 46, cv2.LINE_AA)
    cv2.line(img, p(mid), p(tip), skin, 34, cv2.LINE_AA)
    cv2.ellipse(img, p(tip), (36, 26), math.degrees(ang), 0, 360, skin, -1, cv2.LINE_AA)
    for k in range(-1, 3):  # fingers
        f = tip - 28 * direction + 11 * k * np.array([-direction[1], direction[0]])
        cv2.line(img, p(f), p(f - 30 * direction), skin, 8, cv2.LINE_AA)


# ----------------------------------------------------------------------------- simulation

def _simulate(rng: np.random.Generator, times: np.ndarray, n_areas: int, planned: list[int],
              pool: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Per area: stock level and drawn product over time (depletion + restocks, rare wrong product)."""
    t_n = len(times)
    levels = np.zeros((n_areas, t_n))
    shown = np.zeros((n_areas, t_n), int)
    dt_h = np.diff(times, prepend=times[0]) / 3600.0
    for a in range(n_areas):
        rate = rng.uniform(0.2, 0.55)
        level = float(rng.choice([0.0, 0.5, 1.0], p=[0.35, 0.25, 0.40]))
        art = _maybe_wrong(rng, planned[a], pool)
        for t in range(t_n):
            if t > 0:
                if level > 0 and rng.random() < 1 - math.exp(-rate * dt_h[t]):
                    level -= 0.5 if rng.random() > 0.2 else 1.0
                    level = max(level, 0.0)
                restock = 0.45 if level == 0 else 0.12 if level == 0.5 else 0.0
                if rng.random() < restock:
                    level = 1.0 if rng.random() < 0.85 else 0.5
                    art = _maybe_wrong(rng, planned[a], pool)
            levels[a, t], shown[a, t] = level, art
    return levels, shown


def _maybe_wrong(rng: np.random.Generator, planned: int, pool: list[int]) -> int:
    others = [p for p in pool if p != planned]
    return int(rng.choice(others)) if others and rng.random() < P_WRONG else planned


def _any_wrong(cams: list[_Camera], columns, n_train: list[int]) -> bool:
    return any(not _compliant(c, a, t) for c, n in zip(cams, n_train)
               for a in range(len(c.areas)) for t in columns(c, n))


def _force_wrong(cams: list[_Camera], columns, n_train: list[int]) -> bool:
    """Guarantee one non-compliant stocked entry among the chosen time columns."""
    for cam, n in zip(cams, n_train):
        pool = sorted({a.art for a in cam.areas})
        for ai, area in enumerate(cam.areas):
            others = [p for p in pool if p != area.art]
            for t in columns(cam, n):
                if cam.levels[ai, t] > 0 and others:
                    cam.shown[ai, t] = others[0]
                    return True
    return False


def _compliant(cam: _Camera, ai: int, t: int) -> bool:
    return bool(cam.levels[ai, t] == 0 or cam.shown[ai, t] == cam.areas[ai].art)


# ----------------------------------------------------------------------------- rendering

def _area_geometry(quad: np.ndarray) -> tuple[tuple, np.ndarray, tuple]:
    top, bot = np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3])
    left, right = np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1])
    w = int(np.clip(round((top + bot) / 2), 60, 420))
    h = int(np.clip(round((left + right) / 2), 40, 300))
    src = np.float32([[RIM, RIM], [RIM + w, RIM], [RIM + w, RIM + h], [RIM, RIM + h]])
    homog = cv2.getPerspectiveTransform(src, quad.astype(np.float32))
    full = np.float32([[[0, 0], [w + 2 * RIM, 0], [w + 2 * RIM, h + 2 * RIM], [0, h + 2 * RIM]]])
    mapped = cv2.perspectiveTransform(full, homog)[0]
    lo, hi = np.floor(mapped.min(0)).astype(int), np.ceil(mapped.max(0)).astype(int)
    box = (max(0, int(lo[0])), max(0, int(lo[1])), min(W, int(hi[0])), min(H, int(hi[1])))
    return (w, h), homog, box


def _bake_shadows(bg: np.ndarray, areas: list) -> np.ndarray:
    """Darken the floor under and beside every crate (the camera is static, so do it once)."""
    shadow = np.zeros((H, W), np.uint8)
    for area in areas:
        w, h = area.tex_size
        full = np.float32([[[0, 0], [w + 2 * RIM, 0], [w + 2 * RIM, h + 2 * RIM], [0, h + 2 * RIM]]])
        poly = cv2.perspectiveTransform(full, area.homog)[0] + np.float32([7, 9])
        cv2.fillPoly(shadow, [poly.astype(np.int32)], 255)
    shade = cv2.GaussianBlur(shadow, (21, 21), 0).astype(np.float32)[..., None] / 255.0
    return (bg * (1 - 0.35 * shade)).astype(np.uint8)


def _render_frame(cam: _Camera, t: int, rng: np.random.Generator, frac: float) -> np.ndarray:
    """One RGB uint8 frame of the camera at time index t."""
    img = cam.background.copy()
    for ai, area in enumerate(cam.areas):
        x0, y0, x1, y1 = area.bbox
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        tex = area.base.copy()
        w, _ = area.tex_size
        _draw_products(tex, rng, ARTS[int(cam.shown[ai, t])], float(cam.levels[ai, t]),
                       float(np.clip(w / 200.0, 0.55, 1.5)))
        warped = cv2.warpPerspective(tex, area.shift_homog, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR)
        np.copyto(img[y0:y1, x0:x1], warped, where=area.mask)

    if rng.random() < 0.3:
        _draw_hand(img, rng, cam.areas[int(rng.integers(len(cam.areas)))].quad)
    gain = 0.92 + 0.1 * math.sin(math.pi * min(max(frac, 0.0), 1.0))   # daylight
    img = cv2.convertScaleAbs(cv2.GaussianBlur(img, (3, 3), 0), alpha=gain)
    oy, ox = int(rng.integers(0, 64)), int(rng.integers(0, 64))          # sensor noise
    noise = cam.noise[oy:oy + H, ox:ox + W, None]
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def _write_jpeg(path: Path, rgb: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError(f"could not encode {path}")
    buf.tofile(str(path))


# ----------------------------------------------------------------------------- dataset

def _timestamps(rng: np.random.Generator, n_train: int, n_val: int, cam_idx: int) -> tuple[list, list]:
    if n_train <= 1:
        train = np.array([(DAY_START + DAY_END) // 2][:n_train], float)
    else:
        train = np.linspace(DAY_START, DAY_END, n_train)
        train = train + rng.uniform(-1, 1, n_train) * min(300.0, 0.25 * (DAY_END - DAY_START) / n_train)
    train_ts = sorted({int(t) + cam_idx for t in train})
    val_ts = [VAL_START + 1800 * k + 97 * cam_idx for k in range(n_val)]
    return train_ts, val_ts


def _build_camera(seed: int, idx: int, n_train: int, n_val: int) -> _Camera:
    rng = np.random.default_rng([seed, idx])
    cam_id = str(9001 + idx)
    quads = _camera_layout(rng, partly_outside=(idx == 0))
    n_areas = len(quads)
    planned = [int(i) for i in rng.choice(len(ARTS), size=n_areas, replace=False)]
    for a in range(1, n_areas):          # the same product may stand in several areas
        if rng.random() < 0.2:
            planned[a] = planned[int(rng.integers(a))]
    kinds = rng.choice(list(CRATES), size=n_areas, p=[0.7, 0.15, 0.15])
    areas = []
    for a, q in enumerate(quads):
        size, homog, box = _area_geometry(q)
        shifted = np.array([[1, 0, -box[0]], [0, 1, -box[1]], [0, 0, 1]], np.float64) @ homog
        ones = np.full((size[1] + 2 * RIM, size[0] + 2 * RIM), 255, np.uint8)
        mask = cv2.warpPerspective(ones, shifted, (box[2] - box[0], box[3] - box[1]),
                                   flags=cv2.INTER_NEAREST)[..., None] > 0
        areas.append(_Area(f"{cam_id}_{a + 1}", planned[a], q, str(kinds[a]), size, homog, box,
                           _crate_texture(rng, size[0], size[1], str(kinds[a])), shifted, mask))
    train_ts, val_ts = _timestamps(rng, n_train, n_val, idx)
    times = np.array(train_ts + val_ts, dtype=np.int64)
    pool = sorted(set(planned))
    levels, shown = _simulate(rng, times.astype(float), n_areas, planned, pool)
    bg = _bake_shadows(_background(rng, float(min(q[:, 1].min() for q in quads))), areas)
    noise = np.round(rng.normal(0, 2.5, (H + 64, W + 64))).astype(np.int16)
    return _Camera(cam_id, areas, bg, noise, times, levels, shown, int(rng.integers(1 << 30)))


def _planogram_doc(cams: list[_Camera]) -> dict:
    out = {}
    for cam in cams:
        products = []
        for area in cam.areas:
            art = ARTS[area.art]
            coords = {k: [int(v[0]), int(v[1])] for k, v in zip(CORNERS, area.quad)}
            products.append({"area_id": area.area_id, "product_id": art.pid, "product_name": art.name,
                             "image_coordinates": coords})
        out[cam.cam_id] = {"products": products}
    return {SECTION: {"cameras": out}}


def _entry(compliant: bool, level: float) -> dict:
    return {"planogram_compliant": bool(compliant), "stock_level": LEVEL_NAMES[level],
            "stock_value": level}


def _check_target(out: Path) -> None:
    """Refuse to overwrite a real planogram in a folder that was not made by this generator."""
    if (out / "planogram.json").exists() and not (out / MARKER).exists():
        raise FileExistsError(f"{out} already holds a planogram.json that was not generated by "
                              f"sensei.synth; choose another --out folder")


def generate_dataset(out_dir: str | Path, n_cameras: int = 4, images_per_camera: int = 12,
                     seed: int = 0, val_per_camera: int = 2) -> dict:
    """Write a synthetic dataset (see module docstring) and return its paths and counts."""
    out = Path(out_dir)
    _check_target(out)
    out.mkdir(parents=True, exist_ok=True)
    cams = [_build_camera(seed, i, images_per_camera, val_per_camera) for i in range(n_cameras)]
    n_train = [len(c.times) - val_per_camera for c in cams]
    if val_per_camera > 0 and not _any_wrong(cams, lambda c, n: range(n, len(c.times)), n_train):
        _force_wrong(cams, lambda c, n: range(n, len(c.times)), n_train)
    if not _any_wrong(cams, lambda c, n: range(n), n_train):
        _force_wrong(cams, lambda c, n: range(n), n_train)

    ann_val: dict = {}
    ann_train: dict = {}
    for ci, cam in enumerate(cams):
        for t, ts in enumerate(cam.times.tolist()):
            is_val = t >= n_train[ci]
            name = f"{ts}.jpg"
            frac = (ts - DAY_START) / (DAY_END - DAY_START)
            rng = np.random.default_rng([cam.seed, t])
            _write_jpeg(out / ("val" if is_val else "images") / cam.cam_id / name,
                        _render_frame(cam, t, rng, frac))
            truth = {a.area_id: _entry(_compliant(cam, ai, t), float(cam.levels[ai, t]))
                     for ai, a in enumerate(cam.areas)}
            (ann_val if is_val else ann_train).setdefault(cam.cam_id, {})[name] = truth

    def dump(name: str, obj: dict) -> Path:
        path = out / name
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    (out / MARKER).write_text("Generated by sensei.synth (synthetic data, safe to regenerate).\n")
    paths = {"planogram": dump("planogram.json", _planogram_doc(cams)),
             "annotations": dump("annotations.json", ann_val),
             "annotations_train": dump("annotations_train.json", ann_train),
             "images_dir": out / "images", "val_dir": out / "val", "root": out,
             "n_cameras": n_cameras, "n_areas": sum(len(c.areas) for c in cams),
             "n_train_images": sum(n_train), "n_val_images": sum(len(c.times) for c in cams) - sum(n_train)}
    log.info("synthetic dataset in %s: %d cameras, %d areas, %d train + %d val images", out,
             n_cameras, paths["n_areas"], paths["n_train_images"], paths["n_val_images"])
    return paths


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Write a synthetic dataset (planogram, camera frames, answer key) "
                                             "for tests and demos")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--cameras", type=int, default=4, help="number of cameras (default 4)")
    ap.add_argument("--images", type=int, default=12, help="training images per camera (default 12)")
    ap.add_argument("--val", type=int, default=2, help="later, labelled images per camera (default 2)")
    ap.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    generate_dataset(args.out, args.cameras, args.images, args.seed, args.val)


if __name__ == "__main__":
    main()

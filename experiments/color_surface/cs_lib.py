"""color_surface experiment: shared helpers (data, warping, product bases, pixel features).

Classical CV only (numpy / OpenCV / scikit-learn). No deep nets, no labels.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "raw"

S = 128          # warped crop size (square, perspective rectified)
INSET = 0.05     # shrink quads towards their centroid (neighbour bleed)


# ----------------------------------------------------------------------------- data
def load_planogram(path=DATA / "planogram.json"):
    """camera_id -> list of area dicts (file order); iterates over all sections."""
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for sec_name, sec in plan.items():
        for cam, c in sec["cameras"].items():
            for a in c["products"]:
                ic = a["image_coordinates"]
                q = np.array([ic["top_left"], ic["top_right"], ic["bottom_right"], ic["bottom_left"]],
                             np.float32)
                out.setdefault(str(cam), []).append(dict(
                    area_id=a["area_id"], product_id=str(a["product_id"]),
                    product_name=a["product_name"], quad=q, section=sec_name))
    return out


def list_images(cams, root=DATA / "images"):
    out = {}
    for cam in cams:
        d = Path(root) / cam
        files = sorted(d.glob("*.jpg"), key=lambda p: (int(p.stem) if p.stem.isdigit() else -1, p.name))
        out[cam] = files
    return out


def read_bgr(path):
    buf = np.fromfile(str(path), np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return img


def inset_quad(q, frac):
    c = q.mean(0, keepdims=True)
    return (c + (q - c) * (1.0 - frac)).astype(np.float32)


def warp(img, quad, size=S, inset=INSET):
    """Perspective-rectify a planogram quad -> (crop BGR uint8 (S,S,3), visible bool (S,S))."""
    q = inset_quad(quad, inset)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    M = cv2.getPerspectiveTransform(q, dst)
    h, w = img.shape[:2]
    # light anti-alias blur proportional to the down-scale factor
    scale = max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1])) / size
    src = cv2.GaussianBlur(img, (0, 0), 0.5 * scale) if scale > 1.3 else img
    crop = cv2.warpPerspective(src, M, (size, size), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    ones = np.full((h, w), 255, np.uint8)
    vis = cv2.warpPerspective(ones, M, (size, size), flags=cv2.INTER_NEAREST,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 127
    return crop, vis


# ----------------------------------------------------------------------------- products
def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).upper()


# base product groups: same colour family / same fruit -> variety-level confusions
BASE_RULES = [
    (r"^BANANA PAO", "PLANTAIN"),
    (r"^BANANA", "BANANA"),
    (r"^(CITRINOS|CITR |CLEMENTINA|LARANJA|TANGERINA)", "ORANGE"),
    (r"^LIMAO", "LEMON"),
    (r"^LIMA ", "LIME"),
    (r"^MELANCIA", "WATERMELON"),
    (r"^(MELAO|MELOA)", "MELON"),
    (r"^MACA", "APPLE"),
    (r"^PERA", "PEAR"),
    (r"^KIWI", "KIWI"),
    (r"^ALFACE", "LETTUCE"),
    (r"^ABACATE", "AVOCADO"),
    (r"^PIMENTO", "PEPPER"),
    (r"^COUVE BROCOLO", "BROCCOLI"),
    (r"^COUVE FLOR", "CAULIFLOWER"),
    (r"^COUVE", "CABBAGE"),
    (r"^BERINGELA", "AUBERGINE"),
    (r"^CHUCHU", "CHAYOTE"),
    (r"^FEIJAO", "GREEN BEAN"),
    (r"^PEPINO", "CUCUMBER"),
    (r"^CURGETE", "COURGETTE"),
    (r"TOMATE", "TOMATO"),
    (r"^MORANGO", "STRAWBERRY"),
    (r"^MANGA", "MANGO"),
    (r"^UVA", "GRAPE"),
    (r"^CEREJA", "CHERRY"),
    (r"^ABACAXI|^ANANAS", "PINEAPPLE"),
    (r"^PITAYA", "PITAYA"),
    (r"^GOIABA", "GUAVA"),
    (r"^MARACUJA|^GRANADILHA", "PASSION FRUIT"),
    (r"^(MAMAO|PAPAIA)", "PAPAYA"),
    (r"^ALPERCE", "APRICOT"),
    (r"^(PESSEGO|NECTARINA)", "PEACH"),
    (r"^BATATA DOCE", "SWEET POTATO"),
    (r"^BATATA", "POTATO"),
    (r"^GENGIBRE", "GINGER"),
    (r"^ABOBORA", "PUMPKIN"),
    (r"^CEBOLINHA", "SHALLOT"),
    (r"^CEBOLA", "ONION"),
    (r"^ALHO", "GARLIC"),
]


def base_of(name: str) -> str:
    n = strip_accents(name)
    for pat, base in BASE_RULES:
        if re.search(pat, n):
            return base
    return n.split()[0]


def is_packaged(name: str) -> bool:
    n = strip_accents(name)
    if re.search(r"EMB|SACO", n):
        return True
    if re.search(r"(?<![/\d.])\d+\s*(G|GR)\b", n):
        return True
    return bool(re.search(r"(?<![/\w.])\d+(\.\d+)?\s*KG", n))


# ----------------------------------------------------------------------------- pixel features
def lab_and_texture(crop_bgr):
    """Return (lab float32 (S,S,3) with L in 0..100, a,b in ~-128..127; texture (S,S) float32).

    Texture = local standard deviation of L in a 7x7 window (after a light blur), i.e. how
    "busy" the neighbourhood is: product piles have strong shading edges, crate floors and
    liners are flatter (the crate lattice gives a mid value).
    """
    f = crop_bgr.astype(np.float32) / 255.0
    f = cv2.GaussianBlur(f, (0, 0), 0.8)
    lab = cv2.cvtColor(f, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]
    m = cv2.blur(L, (7, 7))
    m2 = cv2.blur(L * L, (7, 7))
    tex = np.sqrt(np.maximum(m2 - m * m, 0.0))
    return lab, tex


def pixel_features(crop_bgr, w_L=0.5, w_ab=1.0, w_tex=0.8):
    lab, tex = lab_and_texture(crop_bgr)
    feat = np.empty(lab.shape[:2] + (4,), np.float32)
    feat[..., 0] = lab[..., 0] * w_L
    feat[..., 1] = lab[..., 1] * w_ab
    feat[..., 2] = lab[..., 2] * w_ab
    feat[..., 3] = np.log1p(tex) * 10.0 * w_tex
    return feat

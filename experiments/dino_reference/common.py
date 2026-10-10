"""Shared helpers for the dino_reference experiment (standalone: no import from sensei/)."""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "raw"
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)


@dataclass
class Area:
    area_id: str
    camera_id: str
    product_id: str
    product_name: str
    quad: np.ndarray  # (4,2) TL TR BR BL


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


# coarse "base product" used only to measure how widely a patch cluster is spread
BASE_ALIASES = {
    "CITRINOS": "LARANJA", "CITR": "LARANJA", "CLEMENTINA": "LARANJA", "MINI": "TOMATE",
    "MELAO": "MELAO", "MELOA": "MELAO", "MAMAO": "PAPAIA", "PAPAIA": "PAPAIA",
}


def base_of(name: str) -> str:
    w = strip_accents(name).upper().split()[0]
    w = re.sub(r"[^A-Z]", "", w)
    if w == "COUVE":  # couve brocolo / branca / roxa / flor / portuguesa are different vegetables
        parts = strip_accents(name).upper().split()
        return "COUVE_" + parts[1] if len(parts) > 1 else "COUVE"
    return BASE_ALIASES.get(w, w)


def load_planogram():
    plan = json.loads((DATA / "planogram.json").read_text(encoding="utf-8"))
    areas = {}
    for sec in plan.values():
        for cam, c in sec["cameras"].items():
            lst = []
            for p in c["products"]:
                ic = p["image_coordinates"]
                q = np.array([ic["top_left"], ic["top_right"], ic["bottom_right"], ic["bottom_left"]], np.float32)
                lst.append(Area(p["area_id"], cam, str(p["product_id"]), p["product_name"], q))
            areas[cam] = lst
    return areas


def list_frames(areas_by_cam):
    out = []
    for cam in sorted(areas_by_cam):
        d = DATA / "images" / cam
        for f in sorted(d.glob("*.jpg")):
            out.append((cam, f.name, int(f.stem) if f.stem.isdigit() else -1, f))
    return out


def load_image(path) -> np.ndarray:
    buf = np.fromfile(str(path), np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def inset_quad(q, frac):
    c = q.mean(0, keepdims=True)
    return (c + (q - c) * (1 - frac)).astype(np.float32)


def warp_area(img, quad, size=224, inset=0.04):
    q = inset_quad(quad, inset)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    M = cv2.getPerspectiveTransform(q, dst)
    crop = cv2.warpPerspective(img, M, (size, size), flags=cv2.INTER_AREA if False else cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    ones = np.full(img.shape[:2], 255, np.uint8)
    vis = cv2.warpPerspective(ones, M, (size, size), flags=cv2.INTER_NEAREST,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 127
    return crop, vis


class Dino:
    def __init__(self, name="facebook/dinov2-small", threads=4):
        import torch
        from transformers import AutoModel
        torch.set_num_threads(threads)
        self.torch = torch
        self.model = AutoModel.from_pretrained(name).eval()
        self.mean = np.array([0.485, 0.456, 0.406], np.float32)
        self.std = np.array([0.229, 0.224, 0.225], np.float32)

    def __call__(self, crops):
        torch = self.torch
        x = np.stack(crops).astype(np.float32) / 255.0
        x = (x - self.mean) / self.std
        x = torch.from_numpy(x.transpose(0, 3, 1, 2).copy())
        with torch.inference_mode():
            out = self.model(pixel_values=x).last_hidden_state
        cls = out[:, 0].numpy()
        pt = out[:, 1:].numpy()
        return cls, pt


def extract(model_name="facebook/dinov2-small", size=224, inset=0.04, batch=16, tag=None):
    """Warp every (frame, area) and store DINO patch tokens (float16, L2-normalised) to the cache."""
    tag = tag or f"{model_name.split('/')[-1]}_{size}"
    f_npz = CACHE / f"feats_{tag}.npz"
    if f_npz.exists():
        return dict(np.load(f_npz, allow_pickle=False))
    areas = load_planogram()
    frames = list_frames(areas)
    dino = Dino(model_name)
    G = size // 14
    keys, cams, aids, ts, visfrac = [], [], [], [], []
    pvis_all, cls_all, pt_all, thumbs = [], [], [], []
    buf_crops, t0 = [], time.time()

    def flush():
        if not buf_crops:
            return
        cls, pt = dino(buf_crops)
        cls_all.append(cls.astype(np.float32))
        pt = pt / (np.linalg.norm(pt, axis=-1, keepdims=True) + 1e-6)
        pt_all.append(pt.astype(np.float16))
        buf_crops.clear()

    for cam, name, t, path in frames:
        img = load_image(path)
        for a in areas[cam]:
            crop, vis = warp_area(img, a.quad, size, inset)
            pv = vis.reshape(G, 14, G, 14).mean((1, 3)) >= 0.5
            keys.append(f"{cam}|{name}|{a.area_id}")
            cams.append(cam); aids.append(a.area_id); ts.append(t)
            visfrac.append(vis.mean()); pvis_all.append(pv.reshape(-1))
            thumbs.append(cv2.resize(crop, (112, 112), interpolation=cv2.INTER_AREA))
            buf_crops.append(crop)
            if len(buf_crops) >= batch:
                flush()
        print(f"{cam} {name} done, {len(keys)} crops, {time.time() - t0:.0f}s", flush=True)
    flush()
    d = dict(keys=np.array(keys), cams=np.array(cams), aids=np.array(aids), ts=np.array(ts, np.int64),
             visfrac=np.array(visfrac, np.float32), pvis=np.stack(pvis_all), cls=np.concatenate(cls_all),
             patches=np.concatenate(pt_all), thumbs=np.stack(thumbs), G=np.array(G),
             seconds=np.array(time.time() - t0))
    np.savez(f_npz, **d)
    return d


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "facebook/dinov2-small"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 224
    d = extract(name, size)
    print(d["patches"].shape, float(d["seconds"]))

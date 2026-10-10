"""OWLv2 core helpers for the owl_detect experiment (self-contained, no import from sensei/).

The expensive part of OWLv2 is the ViT image encoder. We run it ONCE per (frame, tile) and cache
everything that is needed to answer ANY text query later:
  boxes (P,4) in frame pixels x0,y0,x1,y1, objectness logits (P,), the L2-normalised class
  embeddings (P,512) float16 and the per-patch logit shift / scale (P,).
A text query q (L2-normalised, 512) then gives logits  (emb @ q + shift) * scale  for free.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXP = Path(__file__).resolve().parent
MODEL_ID = "google/owlv2-base-patch16-ensemble"
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)

# Two square 720x720 tiles (overlap 160 px) of the 1280x720 frame, each upscaled to 960x960
# (x1.333) so that single fruits (~25-40 px) span 2-3 OWL patches.
TILES = [(0, 0, 720, 720), (560, 0, 1280, 720)]
IN_SIZE = 960


def load_planogram(path=None):
    path = path or ROOT / "data" / "raw" / "planogram.json"
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    cams = {}
    for _sec, v in p.items():
        for cam, c in v["cameras"].items():
            areas = []
            for a in c["products"]:
                ic = a["image_coordinates"]
                q = np.array([ic["top_left"], ic["top_right"], ic["bottom_right"], ic["bottom_left"]], np.float32)
                areas.append({"area_id": a["area_id"], "product_id": str(a["product_id"]),
                              "product_name": a["product_name"], "quad": q})
            cams.setdefault(cam, []).extend(areas)
    return cams


def list_frames(cams):
    out = []
    for cam in sorted(cams):
        d = ROOT / "data" / "raw" / "images" / cam
        if not d.is_dir():
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                out.append((cam, f, d / f))
    return out


def read_rgb(path):
    buf = np.fromfile(str(path), np.uint8)
    im = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if im is None:
        raise IOError(path)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


class Owl:
    def __init__(self, threads=4):
        import torch
        from transformers import Owlv2ForObjectDetection, AutoTokenizer
        torch.set_num_threads(threads)
        self.torch = torch
        self.model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID).eval()
        self.tok = AutoTokenizer.from_pretrained(MODEL_ID)

    def text(self, texts):
        """L2-normalised projected text embeddings (T,512)."""
        torch = self.torch
        with torch.inference_mode():
            t = self.tok(texts, padding="max_length", max_length=16, truncation=True, return_tensors="pt")
            e = self.model.owlv2.get_text_features(input_ids=t["input_ids"], attention_mask=t["attention_mask"])
            if not isinstance(e, torch.Tensor):  # newer transformers may return a ModelOutput
                e = e.pooler_output if getattr(e, "pooler_output", None) is not None else e[0]
            e = e / e.norm(dim=-1, keepdim=True)
        return e.numpy().astype(np.float32)

    def encode_tile(self, tile_rgb):
        """tile (H,W,3) uint8 square -> dict of per-patch arrays; boxes normalised cxcywh in tile."""
        torch = self.torch
        x = cv2.resize(tile_rgb, (IN_SIZE, IN_SIZE), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        x = (x - MEAN) / STD
        px = torch.from_numpy(x.transpose(2, 0, 1)[None].copy())
        m = self.model
        with torch.inference_mode():
            fmap, _ = m.image_embedder(pixel_values=px)
            b, h, w, d = fmap.shape
            feats = fmap.reshape(b, h * w, d)
            boxes = m.box_predictor(feats, fmap)[0]  # (P,4) cxcywh in [0,1]
            obj = m.objectness_predictor(feats)[0]  # (P,)
            ch = m.class_head
            emb = ch.dense0(feats)[0]
            emb = emb / (emb.norm(dim=-1, keepdim=True) + 1e-6)
            shift = ch.logit_shift(feats)[0, :, 0]
            scale = (ch.elu(ch.logit_scale(feats)) + 1)[0, :, 0]
        return {"boxes": boxes.numpy(), "obj": obj.numpy(), "emb": emb.numpy().astype(np.float16),
                "shift": shift.numpy(), "scale": scale.numpy()}


def encode_frame(owl, rgb):
    """Run all tiles of a frame; returns concatenated per-patch arrays with frame-pixel boxes."""
    H, W = rgb.shape[:2]
    parts = []
    for ti, (x0, y0, x1, y1) in enumerate(TILES):
        # clamp tiles for unusual frame sizes; pad with grey if needed
        tile = np.full((y1 - y0, x1 - x0, 3), 128, np.uint8)
        sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if sx1 > sx0 and sy1 > sy0:
            tile[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = rgb[sy0:sy1, sx0:sx1]
        r = owl.encode_tile(tile)
        tw, th = x1 - x0, y1 - y0
        cx, cy, bw, bh = r["boxes"].T
        fb = np.stack([x0 + (cx - bw / 2) * tw, y0 + (cy - bh / 2) * th,
                       x0 + (cx + bw / 2) * tw, y0 + (cy + bh / 2) * th], 1).astype(np.float32)
        r["boxes"] = fb
        r["tile"] = np.full(len(fb), ti, np.int8)
        parts.append(r)
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}

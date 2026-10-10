"""Extract CLIP image features for every (frame, area) crop and cache them.

For each model (B/16, L/14) and each crop type:
  warp : perspective warp of the 6%-inset quad to 224x224 (visible part only)
  bbox : axis-aligned bbox of the quad + 12% context, square, 224x224
we store the global (pooled, projected, L2) embedding. For the warp crop we also store a dense
text-aligned patch map (ClearCLIP-style: last block = q-q self-attention on the values, no residual,
no FFN, then post-LN + projection), float16, used by the `dense` variant.

Usage: python extract.py [--models b16,l14] [--limit N]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (CACHE, bbox_crop, key_of, list_images, load_image, load_planogram,  # noqa: E402
                    quad_visible_fraction, warp_quad)

MODELS = {"b16": "openai/clip-vit-base-patch16", "l14": "openai/clip-vit-large-patch14"}
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
SIZE = 224
INSET = 0.06


def visible_warp(image, quad):
    """Warp, then keep only the visible rows/cols band and stretch back to SIZE."""
    crop, vis = warp_quad(image, quad, SIZE, INSET)
    if vis.mean() > 0.995:
        return crop, 1.0
    rows = np.nonzero(vis.mean(1) > 0.9)[0]
    cols = np.nonzero(vis.mean(0) > 0.9)[0]
    vf = float(vis.mean())
    if len(rows) < 8 or len(cols) < 8:
        return crop, vf
    import cv2
    sub = crop[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    return cv2.resize(sub, (SIZE, SIZE), interpolation=cv2.INTER_LINEAR), vf


def iter_crops(limit=None):
    pg = load_planogram()
    recs = [r for r in list_images() if r["cam"] in pg]
    if limit:
        recs = recs[:limit]
    for r in recs:
        try:
            im = load_image(r["path"])
        except Exception as e:  # corrupt image -> skipped (run.py fills a fallback)
            print("WARN", e)
            continue
        for a in pg[r["cam"]]:
            w, vf = visible_warp(im, a["quad"])
            b = bbox_crop(im, a["quad"], SIZE, 0.12)
            yield key_of(r["cam"], r["image_name"], a["area_id"]), r["ts"], w, b, vf


def to_tensor(crops):
    import torch
    x = np.stack(crops).astype(np.float32) / 255.0
    x = (x - MEAN) / STD
    return torch.from_numpy(x.transpose(0, 3, 1, 2).copy())


class ClipImage:
    def __init__(self, name):
        import torch
        from transformers import CLIPModel
        self.torch = torch
        self.model = CLIPModel.from_pretrained(MODELS[name], torch_dtype=torch.float32).eval()
        self.vm = self.model.vision_model

    def __call__(self, x, dense=False):
        torch = self.torch
        with torch.inference_mode():
            out = self.vm(pixel_values=x, output_hidden_states=dense, return_dict=True)
            g = self.model.visual_projection(out.pooler_output)
            g = torch.nn.functional.normalize(g, dim=-1)
            if not dense:
                return g.numpy(), None
            h = out.hidden_states[-2]                    # input to the last block
            blk = self.vm.encoder.layers[-1]
            at = blk.self_attn
            y = blk.layer_norm1(h)
            B, T, C = y.shape
            nh, hd = at.num_heads, at.head_dim
            q = at.q_proj(y).view(B, T, nh, hd).transpose(1, 2)
            v = at.v_proj(y).view(B, T, nh, hd).transpose(1, 2)
            attn = torch.softmax((q @ q.transpose(-1, -2)) * at.scale, dim=-1)
            o = (attn @ v).transpose(1, 2).reshape(B, T, C)
            o = at.out_proj(o)
            o = self.vm.post_layernorm(o[:, 1:])
            d = self.model.visual_projection(o)
            d = torch.nn.functional.normalize(d, dim=-1)
            G = int(round((T - 1) ** 0.5))
            return g.numpy(), d.reshape(B, G, G, -1).numpy().astype(np.float16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="b16,l14")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    import torch
    torch.set_num_threads(args.threads)
    CACHE.mkdir(parents=True, exist_ok=True)

    # crops are cheap: build them once into RAM (1962 x 2 x 150 KB ~ 0.6 GB)
    t0 = time.time()
    keys, ts, W, Bb, VF = [], [], [], [], []
    for k, t, w, b, vf in iter_crops(args.limit):
        keys.append(k); ts.append(t); W.append(w); Bb.append(b); VF.append(vf)
    print(f"{len(keys)} crops built in {time.time() - t0:.1f}s", flush=True)
    np.savez(CACHE / "meta.npz", keys=np.array(keys), ts=np.array(ts, np.int64), visible=np.array(VF, np.float32))

    for name in args.models.split(","):
        out = CACHE / f"feats_{name}.npz"
        if out.exists() and not args.limit:
            print("exists", out); continue
        t0 = time.time()
        enc = ClipImage(name)
        print(f"[{name}] loaded in {time.time() - t0:.1f}s", flush=True)
        gw, gb, dw = [], [], []
        t0 = time.time()
        for i in range(0, len(keys), args.batch):
            xw = to_tensor(W[i:i + args.batch]); xb = to_tensor(Bb[i:i + args.batch])
            g1, d1 = enc(xw, dense=True)
            g2, _ = enc(xb, dense=False)
            gw.append(g1); dw.append(d1); gb.append(g2)
            if (i // args.batch) % 10 == 0:
                done = i + len(xw)
                el = time.time() - t0
                print(f"[{name}] {done}/{len(keys)}  {el:.0f}s  eta {el / done * (len(keys) - done):.0f}s", flush=True)
        np.savez(out, keys=np.array(keys), warp=np.concatenate(gw), bbox=np.concatenate(gb))
        np.save(CACHE / f"dense_{name}.npy", np.concatenate(dw))
        print(f"[{name}] done in {time.time() - t0:.0f}s", flush=True)
        del enc


if __name__ == "__main__":
    main()

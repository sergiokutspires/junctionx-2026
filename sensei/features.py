"""Per-crop features: handcrafted descriptors (always) + CLIP / DINOv2 embeddings (deep backend).

torch / transformers are imported lazily inside ``Extractor`` so ``backend="lite"`` works
without them. See SPEC.md section 4 (features) and the contract addendum.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import cv2
import numpy as np

from .config import Config
from .data import Area, ImageRecord, load_image, warp_area

log = logging.getLogger(__name__)

CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DINO_PATCH = 14
HSV_BINS = (8, 4, 4)
HAND_NAMES = ([f"hsv_{i}" for i in range(int(np.prod(HSV_BINS)))]
              + ["sat_mean", "sat_std", "val_mean", "val_std", "low_sat_frac",
                 "edge_density", "colourfulness"])
HAND_DIM = len(HAND_NAMES)
FEATURE_CFG_FIELDS = ("backend", "crop_size", "inset", "clip_model", "dino_model")
CACHE_VERSION = 1


def grid_size(crop_size: int) -> int:
    """DINOv2 patch grid side for a crop size (224 -> 16)."""
    return max(1, crop_size // DINO_PATCH)


def l2n(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """L2-normalise along ``axis`` (safe for zero vectors)."""
    n = np.linalg.norm(x, axis=axis, keepdims=True)
    return (x / np.maximum(n, 1e-12)).astype(np.float32)


# --------------------------------------------------------------------------- container

@dataclass
class CropFeatures:
    """Columnar features, one row per (image, area)."""

    keys: list[tuple[str, str, str]]              # (camera_id, image_name, area_id)
    timestamps: np.ndarray                        # (N,) int64
    visible: np.ndarray                           # (N,) float32 visible fraction of the warped crop
    hand: np.ndarray                              # (N, H) float32
    clip: np.ndarray | None = None                # (N, Dc) float32 L2
    dino_cls: np.ndarray | None = None            # (N, Dd) float32 L2
    patch_codes: np.ndarray | None = None         # (N, G*G) int16, -1 = not visible
    patch_visible: np.ndarray | None = None       # (N, G*G) bool
    image_paths: list[str] = field(default_factory=list)

    _ARRAYS = ("timestamps", "visible", "hand", "clip", "dino_cls", "patch_codes", "patch_visible")

    def __len__(self) -> int:
        return len(self.keys)

    @property
    def camera_ids(self) -> list[str]:
        return [k[0] for k in self.keys]

    @property
    def area_ids(self) -> list[str]:
        return [k[2] for k in self.keys]

    def subset(self, idx: Sequence[int] | np.ndarray) -> "CropFeatures":
        """Rows ``idx`` (int indices or a boolean mask) as a new CropFeatures."""
        idx = np.asarray(idx)
        if idx.dtype == bool:
            idx = np.flatnonzero(idx)
        idx = idx.astype(np.int64)
        arrays = {name: (None if getattr(self, name) is None else getattr(self, name)[idx])
                  for name in self._ARRAYS}
        paths = [self.image_paths[i] for i in idx] if self.image_paths else []
        return CropFeatures(keys=[self.keys[i] for i in idx], image_paths=paths, **arrays)

    @staticmethod
    def concat(parts: list["CropFeatures"]) -> "CropFeatures":
        """Stack several CropFeatures (optional arrays must be present in all or none)."""
        if not parts:
            raise ValueError("nothing to concatenate")
        arrays = {}
        for name in CropFeatures._ARRAYS:
            vals = [getattr(p, name) for p in parts]
            arrays[name] = None if any(v is None for v in vals) else np.concatenate(vals)
        return CropFeatures(keys=[k for p in parts for k in p.keys],
                            image_paths=[s for p in parts for s in p.image_paths], **arrays)

    def save(self, path: str | Path) -> None:
        """Write a compressed npz (no pickle)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        out = {"keys": np.array(self.keys, dtype=str).reshape(-1, 3),
               "image_paths": np.array(self.image_paths, dtype=str)}
        for name in self._ARRAYS:
            v = getattr(self, name)
            if v is not None:
                out[name] = v
        np.savez_compressed(path, **out)

    @classmethod
    def load(cls, path: str | Path) -> "CropFeatures":
        with np.load(Path(path), allow_pickle=False) as z:
            keys = [tuple(str(s) for s in row) for row in z["keys"]]
            paths = [str(s) for s in z["image_paths"]] if "image_paths" in z else []
            arrays = {name: (z[name] if name in z else None) for name in cls._ARRAYS}
        return cls(keys=keys, image_paths=paths, **arrays)


# --------------------------------------------------------------------------- handcrafted

def handcrafted(crop: np.ndarray, visible: np.ndarray | None = None) -> np.ndarray:
    """Colour/texture descriptor over visible pixels: HSV histogram (8x4x4, sums to 1),
    saturation/value mean+std, share of low-saturation pixels, Canny edge density and
    Hasler-Suesstrunk colourfulness. All in ~[0, 1]; zeros when nothing is visible."""
    crop = np.asarray(crop)
    if crop.ndim == 2:
        crop = np.stack([crop] * 3, axis=-1)
    crop = crop[..., :3].astype(np.uint8, copy=False)
    mask = np.ones(crop.shape[:2], bool) if visible is None else np.asarray(visible, bool)
    out = np.zeros(HAND_DIM, dtype=np.float32)
    n = int(mask.sum())
    if n == 0:
        return out
    hsv = cv2.cvtColor(np.ascontiguousarray(crop), cv2.COLOR_RGB2HSV)
    m8 = mask.astype(np.uint8)
    hist = cv2.calcHist([hsv], [0, 1, 2], m8, list(HSV_BINS), [0, 180, 0, 256, 0, 256]).ravel()
    nb = hist.size
    out[:nb] = hist / max(hist.sum(), 1.0)
    s = hsv[..., 1][mask].astype(np.float32) / 255.0
    v = hsv[..., 2][mask].astype(np.float32) / 255.0
    gray = cv2.cvtColor(np.ascontiguousarray(crop), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 150) > 0
    inner = cv2.erode(m8, np.ones((3, 3), np.uint8)).astype(bool)  # ignore the frame border
    edge_density = float(edges[inner].mean()) if inner.any() else 0.0
    rgb = crop[mask].astype(np.float32)
    rg = rgb[:, 0] - rgb[:, 1]
    yb = 0.5 * (rgb[:, 0] + rgb[:, 1]) - rgb[:, 2]
    colourful = (np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean())) / 255.0
    out[nb:] = [s.mean(), s.std(), v.mean(), v.std(), float((s < 0.15).mean()),
                edge_density, colourful]
    return out


def patch_visibility(visible: np.ndarray, grid: int) -> np.ndarray:
    """(grid*grid,) bool: a patch is visible if >= 50% of its pixels are inside the frame."""
    m = np.asarray(visible, dtype=np.float32)
    side = grid * DINO_PATCH
    if m.shape != (side, side):
        m = cv2.resize(m, (side, side), interpolation=cv2.INTER_AREA)
    frac = m.reshape(grid, DINO_PATCH, grid, DINO_PATCH).mean(axis=(1, 3))
    return (frac >= 0.5).ravel()


# --------------------------------------------------------------------------- deep models

class Extractor:
    """CLIP + DINOv2 wrapper. Models load lazily on first use."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.device = cfg.resolve_device()
        self._clip = None
        self._tok = None
        self._dino = None
        self._torch = None
        self.logit_scale: float = 100.0

    # -- loading
    def _torch_mod(self):
        if self._torch is None:
            import torch  # noqa: PLC0415 - optional dependency
            if self.device == "cpu":
                torch.set_num_threads(os.cpu_count() or 1)
            self._torch = torch
        return self._torch

    @staticmethod
    def _from_pretrained(cls, name: str):
        """Prefer the local HF cache (no network); download only if missing."""
        try:
            return cls.from_pretrained(name, local_files_only=True)
        except OSError:
            log.info("downloading %s (not in the local cache)", name)
            return cls.from_pretrained(name)

    def _load_clip(self) -> None:
        if self._clip is not None:
            return
        self._torch_mod()
        from transformers import CLIPModel, CLIPTokenizer  # noqa: PLC0415
        t0 = time.perf_counter()
        self._clip = self._from_pretrained(CLIPModel, self.cfg.clip_model).to(self.device).eval()
        self._tok = self._from_pretrained(CLIPTokenizer, self.cfg.clip_model)
        self.logit_scale = float(self._clip.logit_scale.exp().item())
        log.info("loaded %s on %s in %.1fs", self.cfg.clip_model, self.device, time.perf_counter() - t0)

    def _load_dino(self) -> None:
        if self._dino is not None:
            return
        self._torch_mod()
        from transformers import AutoModel  # noqa: PLC0415
        t0 = time.perf_counter()
        self._dino = self._from_pretrained(AutoModel, self.cfg.dino_model).to(self.device).eval()
        log.info("loaded %s on %s in %.1fs", self.cfg.dino_model, self.device, time.perf_counter() - t0)

    # -- preprocessing
    def _batch_tensor(self, crops: Sequence[np.ndarray], side: int, mean: np.ndarray, std: np.ndarray):
        torch = self._torch_mod()
        arr = []
        for c in crops:
            c = np.asarray(c)[..., :3]
            if c.shape[:2] != (side, side):
                c = cv2.resize(c, (side, side), interpolation=cv2.INTER_AREA
                               if c.shape[0] > side else cv2.INTER_CUBIC)
            arr.append(c)
        x = (np.stack(arr).astype(np.float32) / 255.0 - mean) / std
        return torch.from_numpy(x.transpose(0, 3, 1, 2).copy()).to(self.device)

    @staticmethod
    def _as_tensor(out):
        """get_*_features returns a tensor (transformers 4) or a model output (5)."""
        if hasattr(out, "shape"):
            return out
        for name in ("image_embeds", "text_embeds", "pooler_output"):
            v = getattr(out, name, None)
            if v is not None:
                return v
        return out[0]

    # -- public
    def clip_image(self, crops: Sequence[np.ndarray]) -> np.ndarray:
        """(N, Dc) L2-normalised CLIP image embeddings."""
        self._load_clip()
        torch = self._torch_mod()
        side = int(self._clip.config.vision_config.image_size)
        outs = []
        bs = max(1, self.cfg.batch_size)
        with torch.inference_mode():
            for i in range(0, len(crops), bs):
                x = self._batch_tensor(crops[i:i + bs], side, CLIP_MEAN, CLIP_STD)
                outs.append(self._as_tensor(self._clip.get_image_features(pixel_values=x)).float().cpu().numpy())
        if not outs:
            return np.zeros((0, self.clip_dim), np.float32)
        return l2n(np.concatenate(outs))

    def clip_text(self, texts: Sequence[str]) -> np.ndarray:
        """(T, Dc) L2-normalised CLIP text embeddings."""
        self._load_clip()
        torch = self._torch_mod()
        outs = []
        with torch.inference_mode():
            for i in range(0, len(texts), 256):
                tok = self._tok(list(texts[i:i + 256]), padding=True, truncation=True,
                                return_tensors="pt").to(self.device)
                outs.append(self._as_tensor(self._clip.get_text_features(**tok)).float().cpu().numpy())
        if not outs:
            return np.zeros((0, self.clip_dim), np.float32)
        return l2n(np.concatenate(outs))

    def dino(self, crops: Sequence[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        """(cls (N, Dd) L2, patches (N, G, G, Dd) L2 per patch), G = crop_size // 14."""
        self._load_dino()
        torch = self._torch_mod()
        g = grid_size(self.cfg.crop_size)
        side = g * DINO_PATCH
        cls_out, patch_out = [], []
        bs = max(1, self.cfg.batch_size)
        with torch.inference_mode():
            for i in range(0, len(crops), bs):
                x = self._batch_tensor(crops[i:i + bs], side, IMAGENET_MEAN, IMAGENET_STD)
                h = self._dino(pixel_values=x).last_hidden_state.float()
                cls_out.append(h[:, 0].cpu().numpy())
                # last G*G tokens are the patches (robust to register tokens)
                patch_out.append(h[:, -g * g:].reshape(h.shape[0], g, g, -1).cpu().numpy())
        if not cls_out:
            d = self.dino_dim
            return np.zeros((0, d), np.float32), np.zeros((0, g, g, d), np.float32)
        return l2n(np.concatenate(cls_out)), l2n(np.concatenate(patch_out))

    @property
    def clip_dim(self) -> int:
        self._load_clip()
        return int(self._clip.config.projection_dim)

    @property
    def dino_dim(self) -> int:
        self._load_dino()
        return int(self._dino.config.hidden_size)


# --------------------------------------------------------------------------- crops

def iter_crops(records: Iterable[ImageRecord], areas_by_cam: dict[str, list[Area]],
               cfg: Config) -> Iterator[tuple[tuple[str, str, str], int, np.ndarray, np.ndarray, float, str]]:
    """Yield (key, timestamp, crop uint8, visible mask, visible fraction, image path) per
    (image, area). A corrupt/missing image is logged and yields nothing."""
    for rec in records:
        areas = areas_by_cam.get(rec.camera_id)
        if not areas:
            log.warning("camera %s not in the planogram: skipping %s", rec.camera_id, rec.path)
            continue
        try:
            image = load_image(rec.path)
        except (OSError, ValueError) as exc:
            log.warning("cannot read %s (%s): skipping", rec.path, exc)
            continue
        for a in areas:
            crop, vis = warp_area(image, a.quad, cfg.crop_size, cfg.inset)
            yield ((rec.camera_id, rec.image_name, a.area_id), int(rec.timestamp), crop, vis,
                   float(vis.mean()), str(rec.path))


def _cache_key(records: Sequence[ImageRecord], areas_by_cam: dict[str, list[Area]], cfg: Config) -> str:
    h = hashlib.sha1()
    h.update(json.dumps({"v": CACHE_VERSION, **{f: getattr(cfg, f) for f in FEATURE_CFG_FIELDS}},
                        sort_keys=True).encode())
    for rec in records:
        try:
            st = os.stat(rec.path)
            meta = f"{st.st_size}:{st.st_mtime_ns}"
        except OSError:
            meta = "missing"
        h.update(f"{rec.camera_id}|{rec.image_name}|{rec.timestamp}|{Path(rec.path).resolve()}|{meta}\n".encode())
        for a in areas_by_cam.get(rec.camera_id, []):
            h.update(f"{a.area_id}:{np.round(np.asarray(a.quad, np.float64), 2).tolist()}\n".encode())
    return h.hexdigest()[:16]


def compute_features(records: Sequence[ImageRecord], areas_by_cam: dict[str, list[Area]], cfg: Config,
                     extractor: Extractor | None = None, return_patches: bool = True,
                     cache_dir: str | Path | None = "cache") -> tuple[CropFeatures, np.ndarray | None]:
    """Features for every (image, area). Patches: float16 (N, G, G, Dd) or None (lite /
    return_patches=False). Results are cached under ``cache_dir/<hash>/`` when given."""
    records = list(records)
    deep = cfg.backend == "deep"
    cache_path = None
    if cache_dir is not None:
        cache_path = Path(cache_dir) / f"feats_{_cache_key(records, areas_by_cam, cfg)}"
        fp, pp = cache_path / "feats.npz", cache_path / "patches.npy"
        if fp.is_file() and (not (deep and return_patches) or pp.is_file()):
            log.info("features: cache hit %s", cache_path)
            feats = CropFeatures.load(fp)
            patches = np.load(pp, mmap_mode="r") if deep and return_patches else None
            return feats, patches

    t0 = time.perf_counter()
    g = grid_size(cfg.crop_size)
    if deep and extractor is None:
        extractor = Extractor(cfg)
    keys, ts, vis_frac, hand, paths, pvis = [], [], [], [], [], []
    clip_parts, cls_parts, patch_parts = [], [], []
    buf: list[np.ndarray] = []

    def flush() -> None:
        if not buf:
            return
        clip_parts.append(extractor.clip_image(buf))
        cls, pat = extractor.dino(buf)
        cls_parts.append(cls)
        if return_patches or cache_path is not None:
            patch_parts.append(pat.astype(np.float16))
        buf.clear()
        log.info("features: %d crops (%.0fs)", len(keys), time.perf_counter() - t0)

    for key, t, crop, vis, frac, path in iter_crops(records, areas_by_cam, cfg):
        keys.append(key)
        ts.append(t)
        vis_frac.append(frac)
        paths.append(path)
        hand.append(handcrafted(crop, vis))
        pvis.append(patch_visibility(vis, g))
        if deep:
            buf.append(crop)
            if len(buf) >= max(1, cfg.batch_size) * 4:
                flush()
    if deep:
        flush()

    n = len(keys)
    feats = CropFeatures(
        keys=keys, timestamps=np.array(ts, np.int64), visible=np.array(vis_frac, np.float32),
        hand=np.array(hand, np.float32).reshape(n, HAND_DIM),
        clip=np.concatenate(clip_parts) if deep and clip_parts else None,
        dino_cls=np.concatenate(cls_parts) if deep and cls_parts else None,
        patch_visible=np.array(pvis, bool).reshape(n, g * g), image_paths=paths)
    patches = np.concatenate(patch_parts) if deep and patch_parts else None
    log.info("features: %d crops from %d images in %.1fs (backend=%s)", n, len(records),
             time.perf_counter() - t0, cfg.backend)

    if cache_path is not None and n:
        cache_path.mkdir(parents=True, exist_ok=True)
        feats.save(cache_path / "feats.npz")
        if patches is not None:
            np.save(cache_path / "patches.npy", patches)
    return feats, (patches if return_patches else None)


def export_cache(feats_dir: str | Path, out_dir: str | Path) -> None:
    """Copy (hard-link when possible) a cache entry's feats.npz / patches.npy to ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("feats.npz", "patches.npy"):
        src, dst = Path(feats_dir) / name, out_dir / name
        if not src.is_file():
            continue
        if dst.exists():
            dst.unlink()
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)


# --------------------------------------------------------------------------- text

def prompt_set_embedding(extractor: Extractor, prompts: Sequence[str]) -> np.ndarray:
    """(Dc,) mean of the prompts' CLIP text embeddings, re-normalised."""
    return l2n(extractor.clip_text(list(prompts)).mean(axis=0))


def product_text_embeddings(extractor: Extractor, catalog) -> dict[str, np.ndarray]:
    """product_id -> (Dc,) L2 text embedding (mean over ``products.prompts_for(name)``)."""
    from .products import prompts_for  # noqa: PLC0415
    ids = catalog.ids() if hasattr(catalog, "ids") else list(catalog.products)
    prompt_lists = [prompts_for(catalog[pid]["name"]) for pid in ids]
    flat = [p for ps in prompt_lists for p in ps]
    emb = extractor.clip_text(flat)
    out, i = {}, 0
    for pid, ps in zip(ids, prompt_lists):
        out[pid] = l2n(emb[i:i + len(ps)].mean(axis=0))
        i += len(ps)
    return out

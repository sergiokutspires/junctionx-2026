"""Stock level: unsupervised per-crop fill in [0, 1] and a posterior over (empty, half, full).

Idea (SPEC section 4): the store's surfaces (teal/green crates, grey metal trays, cardboard,
white foam liners, the black banana display) look the same under every product, products do not.

1. ``PatchCoder``: DINOv2 patch tokens -> PCA -> KMeans clusters. Each cluster gets a
   "productness" weight in [0, 1] from
   (a) its spread over product BASE categories (and cameras): surface clusters are everywhere,
       product clusters concentrate on a few bases;
   (b) optional zero-shot CLIP naming: the CLIP embeddings of the crops the cluster dominates are
       compared with surface prompts vs produce prompts.
2. ``fill_raw`` = mean productness over the visible patches (lite backend: colour heuristic).
   Optionally blended with a crop-level CLIP "stocked vs empty" score.
3. Per-area normalisation with the global distribution as floor/ceiling, so an area that is
   always full is never stretched to look empty.
4. Level posterior: soft monotone (ordinal-logistic) thresholds in RANK space of the fit-time
   fills (u = empirical CDF of the fill), mixed with a small level prior so tails stay honest.
   (A 1-D GMM, SPEC step 4, was dropped: the fill distribution is very skewed towards 1 and
   rank thresholds transfer better between cameras on the teacher labels.)

Defaults were chosen with the teacher labels (data/labels/teacher_labels*.json) as a dev set;
fitting itself never needs labels. The pipeline applies ``scoring.best_stock`` to the posterior.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

LEVEL_NAMES = ("empty", "half", "full")

SURFACE_PROMPTS: list[str] = [
    "an empty teal plastic crate",
    "an empty green plastic crate seen from above",
    "an empty grey metal tray",
    "an empty cardboard box",
    "white foam packaging liner",
    "a white egg-crate foam tray",
    "a black plastic display",
    "an empty black curved banana display shelf",
    "an empty supermarket shelf",
    "the empty bottom of a produce crate",
]

# Defaults for the knobs below can be overridden through ``cfg.extra["stock"]``.
DEFAULTS: dict[str, Any] = {
    "n_clusters": None,          # None -> cfg.n_patch_clusters (48 recommended: better than 24)
    "patches_per_crop": 64,      # patch sample per crop for PCA/KMeans
    "spread_threshold": 0.55,    # normalised base-entropy at which spread productness = 0.5
    "spread_temp": 0.08,
    "camera_weight": 0.3,        # share of the camera entropy in the spread measure
    "clip_cluster_weight": 1.0,  # weight of the CLIP naming vs the spread (spread alone is weak)
    "exemplar_power": 4.0,       # cluster exemplar = CLIP crops weighted by cluster share ** power
    "clip_crop_weight": 0.0,     # crop-level CLIP stocked score in fill_raw (did not help on labels)
    "clip_scale": 100.0,         # logit scale for CLIP softmaxes
    "area_weight": 0.25,         # relative (per-area) vs absolute fill
    "lo_q": 10.0, "hi_q": 90.0,  # percentiles for normalisation
    "t1": 0.07, "t2": 0.23,      # rank thresholds empty|half and half|full (share of fit crops below)
    "w1": 0.03, "w2": 0.15,      # their logistic widths (rank units)
    "prior_mix": 0.10,           # posterior = (1-mix) * thresholds + mix * level_prior
    "level_prior": None,         # None -> (0.10, 0.20, 0.70), the real-data mix; see report
    "temp": 1.0,                 # multiplies the widths (>1 = less confident)
    # lite backend (handcrafted only) is much weaker: thresholds that keep it at least at the
    # "always full" baseline on the teacher labels
    "lite": {"t1": 0.04, "t2": 0.08, "w1": 0.03, "w2": 0.10},
}
REAL_LEVEL_MIX = (0.10, 0.20, 0.70)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def _norm_entropy(counts: np.ndarray, prior: np.ndarray) -> np.ndarray:
    """Row-wise entropy of counts / prior (corrects for group size), normalised to [0, 1]."""
    q = counts / np.maximum(prior, 1e-9)[None, :]
    p = q / np.maximum(q.sum(axis=1, keepdims=True), 1e-12)
    k = int((prior > 0).sum())
    if k <= 1:
        return np.zeros(len(counts))
    h = -(p * np.log(np.where(p > 0, p, 1.0))).sum(axis=1)
    return h / np.log(k)


def stock_text_embeddings(extractor, catalog) -> dict[str, np.ndarray]:
    """CLIP text embeddings used by the stock model: {"surface": (S,Dc), "produce": (B,Dc)}.

    "produce" has one row per catalog base (mean of ``products.base_prompts``, L2).
    """
    from .features import l2n  # noqa: PLC0415
    from .products import base_prompts  # noqa: PLC0415
    surface = extractor.clip_text(SURFACE_PROMPTS)
    bases = catalog.bases()
    lists = [base_prompts(b) for b in bases]
    emb = extractor.clip_text([p for ps in lists for p in ps])
    rows, i = [], 0
    for ps in lists:
        rows.append(emb[i:i + len(ps)].mean(axis=0))
        i += len(ps)
    return {"surface": l2n(surface), "produce": l2n(np.stack(rows))}


# --------------------------------------------------------------------------- patch coder

class PatchCoder:
    """PCA + KMeans over DINOv2 patch tokens with a per-cluster productness weight."""

    def __init__(self, n_clusters: int = 24, pca_dims: int = 48, seed: int = 0,
                 spread_threshold: float = DEFAULTS["spread_threshold"],
                 spread_temp: float = DEFAULTS["spread_temp"],
                 camera_weight: float = DEFAULTS["camera_weight"]):
        self.n_clusters, self.pca_dims, self.seed = n_clusters, pca_dims, seed
        self.spread_threshold, self.spread_temp = spread_threshold, spread_temp
        self.camera_weight = camera_weight
        self.mean: np.ndarray | None = None          # (D,)
        self.components: np.ndarray | None = None    # (p, D)
        self.centers: np.ndarray | None = None       # (K, p)
        self.entropy_group: np.ndarray | None = None  # (K,) normalised entropy over bases/products
        self.entropy_camera: np.ndarray | None = None
        self.share: np.ndarray | None = None         # (K,) share of sampled patches
        self.productness: np.ndarray | None = None   # (K,) final weight in [0, 1]

    # -- fitting
    def fit(self, patch_sample: np.ndarray, product_ids: np.ndarray, visible: np.ndarray | None = None,
            camera_ids: np.ndarray | None = None) -> "PatchCoder":
        """Fit on (M, D) patch vectors labelled with the planogram product/base of their area."""
        from sklearn.cluster import KMeans  # noqa: PLC0415
        from sklearn.decomposition import PCA  # noqa: PLC0415
        x = np.asarray(patch_sample, dtype=np.float32)
        groups = np.asarray(product_ids).astype(str)
        cams = None if camera_ids is None else np.asarray(camera_ids).astype(str)
        if visible is not None:
            m = np.asarray(visible, bool)
            x, groups = x[m], groups[m]
            cams = None if cams is None else cams[m]
        if len(x) < self.n_clusters:
            raise ValueError(f"need >= {self.n_clusters} visible patches, got {len(x)}")
        p = int(min(self.pca_dims, x.shape[1], len(x)))
        pca = PCA(n_components=p, random_state=self.seed, svd_solver="randomized").fit(x)
        self.mean = pca.mean_.astype(np.float32)
        self.components = pca.components_.astype(np.float32)
        z = self.project(x)
        km = KMeans(n_clusters=self.n_clusters, n_init=3, random_state=self.seed).fit(z)
        self.centers = km.cluster_centers_.astype(np.float32)
        labels = km.labels_
        self.share = np.bincount(labels, minlength=self.n_clusters) / len(labels)
        self.entropy_group = self._entropy(labels, groups)
        self.entropy_camera = (self._entropy(labels, cams) if cams is not None
                               else np.full(self.n_clusters, np.nan))
        self.productness = self.spread_productness()
        log.info("PatchCoder: %d patches, %d clusters; productness %s", len(x), self.n_clusters,
                 np.round(self.productness, 2).tolist())
        return self

    def _entropy(self, labels: np.ndarray, groups: np.ndarray) -> np.ndarray:
        uniq, gi = np.unique(groups, return_inverse=True)
        counts = np.zeros((self.n_clusters, len(uniq)))
        np.add.at(counts, (labels, gi), 1.0)
        return _norm_entropy(counts, counts.sum(axis=0))

    def spread(self) -> np.ndarray:
        """(K,) spread in [0, 1]: high = present under many bases/cameras = surface."""
        h = self.entropy_group
        if self.entropy_camera is not None and not np.isnan(self.entropy_camera).any():
            h = (1 - self.camera_weight) * h + self.camera_weight * self.entropy_camera
        return h

    def spread_productness(self) -> np.ndarray:
        return _sigmoid((self.spread_threshold - self.spread()) / self.spread_temp)

    # -- encoding
    def project(self, x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, np.float32) - self.mean) @ self.components.T

    def encode(self, patches: np.ndarray, visible: np.ndarray | None = None,
               batch: int = 64) -> np.ndarray:
        """(N,G,G,D) or (N,P,D) patches -> (N, P) int16 cluster ids (-1 where not visible)."""
        if self.centers is None:
            raise RuntimeError("PatchCoder is not fitted")
        n = len(patches)
        out = np.empty((n, int(np.prod(patches.shape[1:-1]))), dtype=np.int16)
        c2 = (self.centers ** 2).sum(axis=1)
        for s in range(0, n, batch):
            x = np.asarray(patches[s:s + batch], dtype=np.float32).reshape(-1, patches.shape[-1])
            z = self.project(x)
            d = c2[None, :] - 2.0 * z @ self.centers.T
            out[s:s + batch] = d.argmin(axis=1).reshape(-1, out.shape[1])
        if visible is not None:
            out[~np.asarray(visible, bool).reshape(out.shape)] = -1
        return out

    # -- state
    def state_dict(self) -> dict[str, Any]:
        return {"n_clusters": self.n_clusters, "pca_dims": self.pca_dims, "seed": self.seed,
                "spread_threshold": self.spread_threshold, "spread_temp": self.spread_temp,
                "camera_weight": self.camera_weight,
                **{k: getattr(self, k) for k in ("mean", "components", "centers", "entropy_group",
                                                 "entropy_camera", "share", "productness")}}

    @classmethod
    def from_state(cls, d: dict[str, Any]) -> "PatchCoder":
        c = cls(int(d["n_clusters"]), int(d["pca_dims"]), int(d["seed"]), float(d["spread_threshold"]),
                float(d["spread_temp"]), float(d["camera_weight"]))
        for k in ("mean", "components", "centers", "entropy_group", "entropy_camera", "share",
                  "productness"):
            v = d.get(k)
            setattr(c, k, None if v is None else np.asarray(v, dtype=np.float32 if k != "share" else float))
        return c


# --------------------------------------------------------------------------- fill helpers

def fill_raw(codes: np.ndarray, visible_patch_mask: np.ndarray | None, productness: np.ndarray) -> np.ndarray:
    """(N,) mean productness over the visible patches (codes -1 = not visible). NaN if none visible."""
    codes = np.asarray(codes)
    valid = codes >= 0
    if visible_patch_mask is not None:
        valid &= np.asarray(visible_patch_mask, bool)
    w = np.asarray(productness, np.float32)[np.where(valid, codes, 0)] * valid
    n = valid.sum(axis=1)
    out = np.full(len(codes), np.nan, dtype=np.float32)
    ok = n > 0
    out[ok] = w.sum(axis=1)[ok] / n[ok]
    return out


def fill_raw_lite(hand: np.ndarray) -> np.ndarray:
    """Lite-backend fill heuristic from the handcrafted descriptor (``features.HAND_NAMES``).

    Piles of produce are textured (many edges, uneven brightness); empty crates, trays and foam
    are smoother. raw = 0.7 * edge_density/0.3 + 0.3 * value_std/0.3, clipped to [0, 1]
    (on the teacher labels edge density alone separates empty crops with AUC ~0.86; colour and
    saturation do not help because teal crates are saturated). Per-area normalisation follows.
    """
    from .features import HAND_NAMES  # noqa: PLC0415
    h = np.asarray(hand, np.float32)
    ix = {n: i for i, n in enumerate(HAND_NAMES)}
    edge = np.clip(h[:, ix["edge_density"]] / 0.3, 0, 1)
    vstd = np.clip(h[:, ix["val_std"]] / 0.3, 0, 1)
    return np.clip(0.7 * edge + 0.3 * vstd, 0, 1).astype(np.float32)


def cluster_shares(codes: np.ndarray, n_clusters: int) -> np.ndarray:
    """(N, K) share of each crop's visible patches in each cluster."""
    codes = np.asarray(codes)
    valid = codes >= 0
    share = np.zeros((len(codes), n_clusters), np.float32)
    rows = np.repeat(np.arange(len(codes)), codes.shape[1])[valid.ravel()]
    np.add.at(share, (rows, codes.ravel()[valid.ravel()].astype(np.int64)), 1.0)
    return share / np.maximum(valid.sum(axis=1, keepdims=True), 1)


def cluster_clip_productness(codes: np.ndarray, clip: np.ndarray, text_emb: dict[str, np.ndarray],
                             n_clusters: int, scale: float = 100.0, power: float = 4.0) -> np.ndarray:
    """(K,) zero-shot "is this cluster produce?" from the CLIP embeddings of the crops it dominates.

    Each cluster's exemplar = mean CLIP crop embedding weighted by (share of the crop's visible
    patches in the cluster) ** power, then softmax over surface + produce prompts -> P(produce).
    """
    share = cluster_shares(codes, n_clusters)
    ex = (share ** power).T @ np.asarray(clip, np.float32)       # (K, Dc)
    ex /= np.maximum(np.linalg.norm(ex, axis=1, keepdims=True), 1e-12)
    out = _clip_produce_prob(ex, text_emb, scale)
    out[share.sum(axis=0) == 0] = 0.5                              # unused cluster: no opinion
    return out


def _clip_produce_prob(img: np.ndarray, text_emb: dict[str, np.ndarray], scale: float) -> np.ndarray:
    """P(produce) for L2 image embeddings: softmax over all surface + produce prompts."""
    s = np.asarray(text_emb["surface"], np.float32)
    p = np.asarray(text_emb["produce"], np.float32)
    logits = scale * np.asarray(img, np.float32) @ np.concatenate([s, p]).T
    return _softmax(logits, axis=1)[:, len(s):].sum(axis=1).astype(np.float32)


# --------------------------------------------------------------------------- level posterior

def soft_levels(u: np.ndarray, t1: float, t2: float, w1: float, w2: float | None = None) -> np.ndarray:
    """(N,3) ordinal-logistic posterior: P(level > empty) = sigma((u-t1)/w1), P(full) = sigma((u-t2)/w2)."""
    w2 = w1 if w2 is None else w2
    u = np.asarray(u, np.float64)
    a = _sigmoid((u - t1) / max(w1, 1e-6))
    b = np.minimum(a, _sigmoid((u - t2) / max(w2, 1e-6)))
    p = np.clip(np.stack([1 - a, a - b, b], axis=1), 1e-4, 1)
    return (p / p.sum(axis=1, keepdims=True)).astype(np.float32)


def rank_of(values: np.ndarray, reference_sorted: np.ndarray) -> np.ndarray:
    """Mid-rank of each value within a sorted reference sample, in (0, 1)."""
    ref = np.asarray(reference_sorted, np.float64)
    v = np.asarray(values, np.float64)
    if len(ref) == 0:
        return np.full(len(v), 0.5)
    lo = np.searchsorted(ref, v, side="left")
    hi = np.searchsorted(ref, v, side="right")
    return (lo + hi + 1.0) / (2.0 * (len(ref) + 1.0))


# --------------------------------------------------------------------------- model

class StockModel:
    """Fill estimate + level posterior. All learning is unsupervised (see module docstring)."""

    def __init__(self) -> None:
        self.params: dict[str, Any] = dict(DEFAULTS)
        self.backend = "deep"
        self.coder: PatchCoder | None = None
        self.text_emb: dict[str, np.ndarray] | None = None
        self.area_lo: dict[str, float] = {}
        self.area_hi: dict[str, float] = {}
        self.g_lo = 0.0
        self.g_hi = 1.0
        self.reference = np.zeros(0, np.float32)   # sorted fit-time fills (<= 2001 quantiles)
        self.level_prior = np.asarray(REAL_LEVEL_MIX, np.float32)

    # -- fitting
    def fit(self, feats, area_product: dict[str, str], cfg, patches: np.ndarray | None = None,
            catalog=None, text_emb: dict[str, np.ndarray] | None = None) -> None:
        """Fit on all fit-time crops (no labels).

        patches: (N,G,G,D) DINOv2 patch tokens aligned with ``feats`` (deep backend); when given the
        PatchCoder is fitted and ``feats.patch_codes`` filled (in place). ``catalog``
        (products.Catalog) maps products to base fruits for the spread statistic (else product ids).
        ``text_emb`` from ``stock_text_embeddings`` enables CLIP naming of the clusters (strongly
        recommended: without it productness comes from the weaker spread statistic only).
        """
        self.params = {**DEFAULTS, **(getattr(cfg, "extra", {}) or {}).get("stock", {})}
        P = self.params
        lp = P["level_prior"] if P["level_prior"] is not None else REAL_LEVEL_MIX
        self.level_prior = np.asarray(lp, np.float32) / float(np.sum(lp))
        self.text_emb = (None if text_emb is None or feats.clip is None
                         else {k: np.asarray(v, np.float32) for k, v in text_emb.items()})
        self.backend = "deep" if (cfg.backend == "deep" and patches is not None) else "lite"
        if self.backend == "deep":
            groups = self._groups(feats, area_product, catalog)
            self.coder = self._fit_coder(feats, patches, groups, cfg)
            feats.patch_codes = self.coder.encode(patches, feats.patch_visible)
            a = float(P["clip_cluster_weight"])
            if self.text_emb is not None and a > 0:
                zs = cluster_clip_productness(feats.patch_codes, feats.clip, self.text_emb,
                                              self.coder.n_clusters, P["clip_scale"], P["exemplar_power"])
                self.coder.productness = ((1 - a) * self.coder.spread_productness() + a * zs).astype(
                    np.float32)
            log.info("cluster productness: %s", np.round(np.sort(self.coder.productness), 2).tolist())
        else:
            self.coder = None
            if cfg.backend == "deep":
                log.warning("StockModel.fit: no patches given, using the lite fill heuristic")
        raw = self.fill_raw(feats)
        self._fit_area_stats(feats.area_ids, raw)
        f = self._normalise(feats.area_ids, raw)
        f = np.sort(f[np.isfinite(f)])
        if len(f) > 2001:
            f = np.quantile(f, np.linspace(0, 1, 2001))
        self.reference = f.astype(np.float32)
        log.info("stock fit: %d crops, backend=%s, fill quantiles 10/50/90 = %s", len(feats),
                 self.backend, np.round(np.quantile(f, [0.1, 0.5, 0.9]), 3).tolist() if len(f) else [])

    @staticmethod
    def _groups(feats, area_product: dict[str, str], catalog) -> np.ndarray:
        out = []
        for a in feats.area_ids:
            pid = area_product.get(a, a)
            out.append(catalog[pid]["base"] if catalog is not None and pid in catalog else pid)
        return np.asarray(out)

    def _fit_coder(self, feats, patches: np.ndarray, groups: np.ndarray, cfg) -> PatchCoder:
        rng = np.random.default_rng(cfg.seed)
        n, gp = len(feats), int(np.prod(patches.shape[1:-1]))
        vis = (np.ones((n, gp), bool) if feats.patch_visible is None
               else np.asarray(feats.patch_visible, bool).reshape(n, gp))
        k = int(self.params["patches_per_crop"])
        rows, cols = [], []
        for i in range(n):
            idx = np.flatnonzero(vis[i])
            if len(idx):
                pick = rng.choice(idx, size=min(k, len(idx)), replace=False)
                rows.append(np.full(len(pick), i))
                cols.append(pick)
        if not rows:
            raise ValueError("no visible patches to fit the PatchCoder")
        r, c = np.concatenate(rows), np.concatenate(cols)
        flat = np.empty((len(r), patches.shape[-1]), np.float32)
        for i in np.unique(r):           # crop by crop so a memory-mapped array is read once each
            sel = r == i
            flat[sel] = np.asarray(patches[i], np.float32).reshape(gp, -1)[c[sel]]
        P = self.params
        n_clusters = int(P["n_clusters"] or cfg.n_patch_clusters)
        n_clusters = max(2, min(n_clusters, len(flat)))
        coder = PatchCoder(n_clusters, cfg.pca_dims, cfg.seed, P["spread_threshold"],
                           P["spread_temp"], P["camera_weight"])
        return coder.fit(flat, groups[r], camera_ids=np.asarray(feats.camera_ids)[r])

    def encode(self, feats, patches: np.ndarray | None) -> None:
        """Fill ``feats.patch_codes`` for new crops (predict time), in place."""
        if self.coder is not None and patches is not None:
            feats.patch_codes = self.coder.encode(patches, feats.patch_visible)

    def _fit_area_stats(self, area_ids: list[str], raw: np.ndarray) -> None:
        P = self.params
        ok = np.isfinite(raw)
        self.g_lo = float(np.percentile(raw[ok], P["lo_q"])) if ok.any() else 0.0
        self.g_hi = float(np.percentile(raw[ok], P["hi_q"])) if ok.any() else 1.0
        if self.g_hi - self.g_lo < 1e-3:
            self.g_lo, self.g_hi = min(self.g_lo, 0.0), max(self.g_hi, 1.0)
        ids = np.asarray(area_ids)
        self.area_lo, self.area_hi = {}, {}
        for a in np.unique(ids):
            v = raw[(ids == a) & ok]
            if len(v) == 0:
                continue
            # global floor/ceiling: an area that never empties is never stretched to look empty
            self.area_lo[str(a)] = float(min(np.percentile(v, P["lo_q"]), self.g_lo))
            self.area_hi[str(a)] = float(max(np.percentile(v, P["hi_q"]), self.g_hi))

    def _normalise(self, area_ids: list[str], raw: np.ndarray) -> np.ndarray:
        a = float(self.params["area_weight"])
        absf = np.clip((raw - self.g_lo) / max(self.g_hi - self.g_lo, 1e-6), 0, 1)
        lo = np.array([self.area_lo.get(x, self.g_lo) for x in area_ids], np.float64)
        hi = np.array([self.area_hi.get(x, self.g_hi) for x in area_ids], np.float64)
        rel = np.clip((raw - lo) / np.maximum(hi - lo, 1e-6), 0, 1)
        return (a * rel + (1 - a) * absf).astype(np.float32)

    # -- inference
    def fill_raw(self, feats) -> np.ndarray:
        """(N,) absolute fill score before per-area normalisation (NaN if nothing visible)."""
        if self.backend == "deep" and self.coder is not None and feats.patch_codes is not None:
            raw = fill_raw(feats.patch_codes, feats.patch_visible, self.coder.productness)
            w = float(self.params["clip_crop_weight"])
            if self.text_emb is not None and feats.clip is not None and w > 0:
                zs = _clip_produce_prob(feats.clip, self.text_emb, self.params["clip_scale"])
                raw = (1 - w) * raw + w * zs
        else:
            if self.backend == "deep":
                log.warning("deep stock model but no patch_codes: call encode() first; using lite fill")
            raw = fill_raw_lite(feats.hand)
            raw = np.where(np.asarray(feats.visible) > 0, raw, np.nan)
        return np.asarray(raw, np.float32)

    def fill(self, feats) -> np.ndarray:
        """(N,) fill in [0, 1] (share of the area covered by product, per-area normalised).

        Crops with nothing visible get the median fit-time fill."""
        f = self._normalise(feats.area_ids, self.fill_raw(feats))
        med = float(np.median(self.reference)) if len(self.reference) else 0.5
        return np.where(np.isfinite(f), f, med).astype(np.float32)

    def rank(self, fill: np.ndarray) -> np.ndarray:
        """Share of fit-time crops with a lower fill (mid-rank), in (0, 1)."""
        return rank_of(fill, self.reference)

    def proba_from_fill(self, fill: np.ndarray) -> np.ndarray:
        """(N,3) P(empty, half, full) for given fills."""
        P = self.params if self.backend == "deep" else {**self.params, **self.params["lite"]}
        t = float(P["temp"])
        p = soft_levels(self.rank(fill), P["t1"], P["t2"], P["w1"] * t, P["w2"] * t)
        mix = float(P["prior_mix"])
        p = (1 - mix) * p + mix * self.level_prior[None, :]
        return (p / p.sum(axis=1, keepdims=True)).astype(np.float32)

    def predict_proba(self, feats) -> np.ndarray:
        """(N,3) P(empty, half, full); rows sum to 1."""
        return self.proba_from_fill(self.fill(feats))

    # -- persistence (json + npz, no pickle)
    def state_dict(self) -> dict[str, Any]:
        """Plain dict: python scalars/dicts plus numpy arrays (see ``save`` for json + npz)."""
        return {"params": dict(self.params), "backend": self.backend,
                "area_lo": dict(self.area_lo), "area_hi": dict(self.area_hi),
                "g_lo": self.g_lo, "g_hi": self.g_hi, "reference": self.reference,
                "level_prior": self.level_prior,
                "coder": None if self.coder is None else self.coder.state_dict(),
                "text_emb": None if self.text_emb is None else dict(self.text_emb)}

    @classmethod
    def from_state(cls, d: dict[str, Any]) -> "StockModel":
        m = cls()
        m.params = {**DEFAULTS, **d.get("params", {})}
        m.backend = d.get("backend", "lite")
        m.area_lo = {k: float(v) for k, v in d.get("area_lo", {}).items()}
        m.area_hi = {k: float(v) for k, v in d.get("area_hi", {}).items()}
        m.g_lo, m.g_hi = float(d["g_lo"]), float(d["g_hi"])
        m.reference = np.asarray(d.get("reference", []), np.float32)
        m.level_prior = np.asarray(d.get("level_prior", REAL_LEVEL_MIX), np.float32)
        m.coder = None if d.get("coder") is None else PatchCoder.from_state(d["coder"])
        te = d.get("text_emb")
        m.text_emb = None if te is None else {k: np.asarray(v, np.float32) for k, v in te.items()}
        return m

    def save(self, directory: str | Path) -> None:
        """Write ``stock.json`` (scalars) + ``stock.npz`` (arrays) into ``directory``."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        d = self.state_dict()
        arrays: dict[str, np.ndarray] = {"reference": d.pop("reference"),
                                         "level_prior": d.pop("level_prior")}
        coder = d.pop("coder")
        if coder is not None:
            meta = {}
            for k, v in coder.items():
                if isinstance(v, np.ndarray):
                    arrays[f"coder.{k}"] = v
                elif v is not None:
                    meta[k] = v
            d["coder"] = meta
        te = d.pop("text_emb")
        if te is not None:
            arrays.update({f"text.{k}": v for k, v in te.items()})
        d["has_text"] = te is not None
        (directory / "stock.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
        np.savez_compressed(directory / "stock.npz", **arrays)

    @classmethod
    def load(cls, directory: str | Path) -> "StockModel":
        directory = Path(directory)
        d = json.loads((directory / "stock.json").read_text(encoding="utf-8"))
        with np.load(directory / "stock.npz", allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        d["reference"] = arrays.get("reference", np.zeros(0, np.float32))
        d["level_prior"] = arrays.get("level_prior", np.asarray(REAL_LEVEL_MIX, np.float32))
        if d.get("coder") is not None:
            d["coder"].update({k[6:]: v for k, v in arrays.items() if k.startswith("coder.")})
        d["text_emb"] = ({k[5:]: v for k, v in arrays.items() if k.startswith("text.")}
                         if d.get("has_text") else None)
        return cls.from_state(d)

"""Planogram compliance: zero-shot product recognition -> p(compliant) and the likely product.

Primary evidence is CLIP zero-shot recognition at the coarse BASE level (banana vs orange vs
apple ...): a softmax over the catalog's base prompt ensembles (temperature = CLIP logit_scale)
with a prior that favours the expected base and, among the alternatives, bases sold on the same
camera. Within the same base (variety / packaging) the model flips only on very strong product-
level text evidence. Crops that are empty, barely visible or occluded keep the prior: an empty
area is compliant because nothing wrong is shown.

Optional supporting evidence (``proto_weight`` > 0): image prototypes per base built at fit
time from crops recognised with high confidence (transductive refinement).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from .features import l2n
from .products import EMPTY_PROMPTS, OCCLUSION_PROMPTS, base_prompts, prompts_for

log = logging.getLogger(__name__)

EMPTY_KEY = "__empty__"
OCCL_KEY = "__occlusion__"
BASE_PREFIX = "base:"

# Tunables (override with cfg.extra["compliance"] = {...}). Values tuned on the teacher labels.
DEFAULTS: dict[str, float] = {
    "temperature": 1.0,      # multiplies CLIP logit_scale (1 = CLIP's own temperature)
    "cam_weight": 4.0,       # prior weight of a same-camera base vs a base sold elsewhere
    "base_margin": 1.0,      # extra logit handicap the alternative base must overcome
    "pairwise": 1.0,         # 1: expected base vs strongest rival; 0: vs all rivals (softmax mass)
    "group_margin": 3.0,     # extra handicap for look-alike bases of the same group (potato / sweet potato)
    "variety_margin": 4.0,   # product-level logit gap needed to doubt the variety (same base)
    "variety_prior": 0.97,   # p(right variety) before evidence
    "fill_lo": 0.15,         # fill gate: below -> prior only
    "fill_hi": 0.40,         # fill gate: above -> full evidence
    "vis_lo": 0.25,          # visible-fraction gate
    "vis_hi": 0.50,
    "empty_gate": 0.6,
    "debias": 0.0,           # subtract this x the per-base median logit over the fit crops (hub correction)       # CLIP p(empty) above this -> prior (no product shown)
    "likely_cam_bonus": 3.0, # logit bonus of same-camera bases when naming the likely product
    "proto_weight": 0.0,     # weight of image-prototype logits (0 = text only)
    "proto_conf": 0.9,       # confidence needed for a crop to build a base prototype
    "proto_min": 3,          # crops needed for a prototype
    "proto_topk": 3,         # expected base must be in the text top-k to feed its prototype
    "proto_temp": 1.0,       # multiplies logit_scale for image-prototype similarities
}


def text_embeddings(extractor, catalog) -> dict[str, np.ndarray]:
    """All text embeddings the model uses: product ids, ``base:<base>``, ``__empty__``, ``__occlusion__``.

    Pass the result as ``text_emb`` to :meth:`ComplianceModel.fit`.
    """
    groups: dict[str, list[str]] = {pid: prompts_for(catalog[pid]["name"]) for pid in catalog.ids()}
    for b in catalog.bases():
        groups[BASE_PREFIX + b] = base_prompts(b)
    groups[EMPTY_KEY] = list(EMPTY_PROMPTS)
    groups[OCCL_KEY] = list(OCCLUSION_PROMPTS)
    flat = [t for ts in groups.values() for t in ts]
    emb = extractor.clip_text(flat)
    out, i = {}, 0
    for k, ts in groups.items():
        out[k] = l2n(emb[i:i + len(ts)].mean(axis=0)).astype(np.float32)
        i += len(ts)
    return out


def _smoothstep(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    t = np.clip((np.asarray(x, dtype=np.float64) - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _logit(p: np.ndarray | float) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p) - np.log1p(-p)


def _softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def _camera_of(area_id: str) -> str:
    return area_id.rsplit("_", 1)[0]


class ComplianceModel:
    """p(compliant) per crop from zero-shot base recognition (see module docstring)."""

    def __init__(self) -> None:
        self.params: dict[str, float] = dict(DEFAULTS)
        self.prior: float = 0.93
        self.logit_scale: float = 100.0
        self.area_product: dict[str, str] = {}
        self.area_camera: dict[str, str] = {}
        self.product_base: dict[str, str] = {}
        self.product_name: dict[str, str] = {}
        self.base_group: dict[str, str] = {}
        self.bases: list[str] = []
        self.product_ids: list[str] = []
        self.base_emb: np.ndarray | None = None      # (B, D)
        self.base_bias: np.ndarray | None = None     # (B,) median logit per base over fit crops
        self.prod_emb: np.ndarray | None = None      # (P, D)
        self.empty_emb: np.ndarray | None = None     # (D,)
        self.occl_emb: np.ndarray | None = None      # (D,)
        self.base_proto: np.ndarray | None = None    # (B, D), zero rows = no prototype

    # ------------------------------------------------------------------ fit

    def fit(self, feats, area_product: dict[str, str], catalog, text_emb: dict[str, np.ndarray] | None,
            fill: np.ndarray, cfg) -> None:
        """Store the catalog, text embeddings and (optionally) image prototypes."""
        self.prior = float(cfg.compliance_prior)
        extra = (cfg.extra or {})
        self.params.update(extra.get("compliance", {}))
        self.logit_scale = float(extra.get("clip_logit_scale", 100.0))
        self.area_product = dict(area_product)
        self.area_camera = {a: _camera_of(a) for a in self.area_product}
        for cam, _, a in feats.keys:
            self.area_camera[a] = cam
        self.product_ids = list(catalog.ids())
        self.product_base = {pid: catalog[pid]["base"] for pid in self.product_ids}
        self.product_name = {pid: catalog[pid]["name"] for pid in self.product_ids}
        self.bases = sorted(set(self.product_base.values()))
        self.base_group = {catalog[p]["base"]: catalog[p].get("group", catalog[p]["base"]) for p in self.product_ids}

        if feats.clip is None or text_emb is None:
            log.info("compliance: no CLIP features/text embeddings (lite) -> constant prior %.2f", self.prior)
            self.base_emb = None
            return
        self.prod_emb = np.stack([text_emb[p] for p in self.product_ids]).astype(np.float32)
        rows = []
        for b in self.bases:
            if BASE_PREFIX + b in text_emb:
                rows.append(text_emb[BASE_PREFIX + b])
            else:  # derive from the products of that base
                idx = [i for i, p in enumerate(self.product_ids) if self.product_base[p] == b]
                rows.append(l2n(self.prod_emb[idx].mean(axis=0)))
        self.base_emb = np.stack(rows).astype(np.float32)
        self.empty_emb = text_emb.get(EMPTY_KEY)
        self.occl_emb = text_emb.get(OCCL_KEY)

        self.base_proto = None
        self.base_bias = np.median(self.logit_scale * self.params["temperature"]
                                   * (feats.clip.astype(np.float32) @ self.base_emb.T), axis=0).astype(np.float32)
        if self.params["proto_weight"] > 0:
            self._fit_prototypes(feats, np.asarray(fill, dtype=np.float32))
        log.info("compliance fit: %d products, %d bases, %d crops, prototypes: %s", len(self.product_ids),
                 len(self.bases), len(feats), "none" if self.base_proto is None
                 else int((np.abs(self.base_proto).sum(1) > 0).sum()))

    def _fit_prototypes(self, feats, fill: np.ndarray) -> None:
        """Mean CLIP image embedding per base over well-stocked crops where text and planogram agree.

        A crop is used for its EXPECTED base only if that base is in the top-k of the raw text
        logits and the text-only model calls it compliant with high confidence, so areas that
        hold another product all day do not pollute the prototype.
        """
        pw = self.params["proto_weight"]
        self.params["proto_weight"] = 0.0          # text-only pass
        ev = self.evidence(feats, fill)
        self.params["proto_weight"] = pw
        k = int(self.params["proto_topk"])
        rank = (ev["z_text"] > ev["z_text"][np.arange(len(feats)), np.maximum(ev["exp_base"], 0)][:, None]).sum(1)
        ok = ((ev["weight"] > 0.9) & (ev["p_base_ok"] >= self.params["proto_conf"]) & (rank < k)
              & (ev["exp_base"] >= 0))
        protos = np.zeros_like(self.base_emb)
        for bi in range(len(self.bases)):
            sel = ok & (ev["exp_base"] == bi)
            if sel.sum() >= self.params["proto_min"]:
                protos[bi] = l2n(feats.clip[sel].mean(axis=0))
        self.base_proto = protos

    # ------------------------------------------------------------------ predict

    def evidence(self, feats, fill: np.ndarray) -> dict[str, np.ndarray]:
        """Per-crop intermediate quantities (for predict, debugging and the UI)."""
        n = len(feats)
        P = self.params
        areas = [k[2] for k in feats.keys]
        cams = [k[0] for k in feats.keys]
        exp_pid = [self.area_product.get(a) for a in areas]
        known = np.array([p is not None and p in self.product_base for p in exp_pid])
        fill = np.asarray(fill, dtype=np.float64).reshape(-1)
        if fill.shape[0] != n:
            raise ValueError(f"fill has {fill.shape[0]} rows, feats {n}")
        vis = np.asarray(feats.visible, dtype=np.float64)
        gate = _smoothstep(fill, P["fill_lo"], P["fill_hi"]) * _smoothstep(vis, P["vis_lo"], P["vis_hi"])
        out = {"gate": gate, "known": known}
        if self.base_emb is None or feats.clip is None:
            out["post_base"] = np.zeros((n, max(len(self.bases), 1)))
            return out

        X = feats.clip.astype(np.float32)
        s = self.logit_scale * P["temperature"]
        z = s * (X @ self.base_emb.T)                                    # (N, B)
        if self.base_bias is not None and P["debias"]:
            z = z - P["debias"] * self.base_bias[None, :]
        z_text = z

        # empty / occlusion as extra classes (text only): they gate (no product visible), never "win" a base
        extra_cols = [e for e in (self.empty_emb, self.occl_emb) if e is not None]
        p_empty = np.zeros(n)
        p_occl = np.zeros(n)
        if extra_cols:
            ze = s * (X @ np.stack(extra_cols).T)
            full = _softmax(np.concatenate([z_text, ze], axis=1))
            p_empty = full[:, len(self.bases)] if self.empty_emb is not None else p_empty
            if self.occl_emb is not None:
                p_occl = full[:, -1]
        clear = 1.0 - _smoothstep(np.maximum(p_empty, p_occl), P["empty_gate"] - 0.2, P["empty_gate"])

        if self.base_proto is not None and P["proto_weight"] > 0:
            has = np.abs(self.base_proto).sum(1) > 0
            zp = self.logit_scale * P["proto_temp"] * (X @ self.base_proto.T)
            # bases without a prototype: neutral score (row mean of the available ones)
            fallback = zp[:, has].mean(axis=1, keepdims=True) if has.any() else np.zeros((n, 1))
            zp = np.where(has[None, :], zp, fallback)
            z = z_text + P["proto_weight"] * (zp - fallback)

        # prior over bases: expected base gets `prior`, the others share the rest (same camera x cam_weight)
        cam_bases: dict[str, set[str]] = {}
        for a, pid in self.area_product.items():
            if pid in self.product_base:
                cam_bases.setdefault(self.area_camera.get(a, _camera_of(a)), set()).add(self.product_base[pid])
        bidx = {b: i for i, b in enumerate(self.bases)}
        logprior = np.zeros((n, len(self.bases)))
        exp_b = np.full(n, -1)
        for i in range(n):
            if not known[i]:
                continue
            eb = self.product_base[exp_pid[i]]
            exp_b[i] = bidx[eb]
            w = np.ones(len(self.bases))
            for b in cam_bases.get(cams[i], ()):
                w[bidx[b]] = P["cam_weight"]
            w[exp_b[i]] = 0.0
            w = w / w.sum() * (1 - self.prior) if w.sum() > 0 else w
            w[exp_b[i]] = self.prior
            logprior[i] = np.log(np.maximum(w, 1e-12))
            g = self.base_group.get(eb, eb)
            for b in self.bases:
                if b != eb and self.base_group.get(b, b) == g:
                    logprior[i, bidx[b]] -= P["group_margin"]
        zz = z + logprior
        zz[np.arange(n), np.maximum(exp_b, 0)] += np.where(known, P["base_margin"], 0.0)
        post = _softmax(zz)
        if P["pairwise"]:  # expected vs its strongest single rival (not vs the sum of all rivals)
            ze = zz[np.arange(n), np.maximum(exp_b, 0)]
            rival = zz.copy()
            rival[np.arange(n), np.maximum(exp_b, 0)] = -np.inf
            p_pair = 1 / (1 + np.exp(-(ze - rival.max(axis=1))))
            p_base_ok = np.where(known, p_pair, 1.0)
        else:
            p_base_ok = np.where(known, post[np.arange(n), np.maximum(exp_b, 0)], 1.0)

        # variety level: same-base products only, strong evidence needed
        zp = s * (X @ self.prod_emb.T)                                    # (N, P)
        pidx = {p: j for j, p in enumerate(self.product_ids)}
        p_var_ok = np.ones(n)
        var_best = [None] * n
        for i in range(n):
            if not known[i]:
                continue
            pe = exp_pid[i]
            same = [pidx[q] for q in self.product_ids if q != pe and self.product_base[q] == self.product_base[pe]]
            if not same:
                continue
            j = same[int(np.argmax(zp[i, same]))]
            d = zp[i, j] - zp[i, pidx[pe]]
            p_wrong = (1 - P["variety_prior"]) / (1 - P["variety_prior"] + P["variety_prior"]
                                                   * np.exp(-(d - P["variety_margin"])))
            p_var_ok[i] = 1 - p_wrong
            var_best[i] = self.product_ids[j]

        p_model = p_base_ok * p_var_ok
        w = gate * clear * known
        logit = w * _logit(p_model) + (1 - w) * _logit(self.prior)
        out.update(z_text=z_text, post_base=post, p_base_ok=p_base_ok, p_var_ok=p_var_ok, p_empty=p_empty, p_occl=p_occl,
                   clear=clear, weight=w, p_compliant=1 / (1 + np.exp(-logit)), exp_base=exp_b,
                   prod_logits=zp, var_best=np.array(var_best, dtype=object), exp_pid=np.array(exp_pid, dtype=object))
        return out

    def predict(self, feats, fill: np.ndarray) -> tuple[np.ndarray, list[str | None]]:
        """(p_compliant (N,), likely product id when p_compliant < 0.5 else None)."""
        n = len(feats)
        if self.base_emb is None or feats.clip is None:
            return np.full(n, self.prior, dtype=np.float32), [None] * n
        ev = self.evidence(feats, fill)
        p = ev["p_compliant"].astype(np.float32)
        likely: list[str | None] = [None] * n
        for i in np.flatnonzero(p < 0.5):
            likely[i] = self._likely_product(feats.keys[i][0], ev, i)
        return p, likely

    def _likely_product(self, cam: str, ev: dict, i: int) -> str | None:
        """Product most likely shown instead of the expected one.

        Bases are ranked by hub-corrected text logits (minus the per-base median over the fit
        crops) plus a bonus for bases sold on the same camera (misplaced stock usually comes from
        a neighbouring crate); then the best product of that base, same-camera products first.
        """
        exp_b = int(ev["exp_base"][i])
        if ev["p_base_ok"][i] >= 0.5 and ev["var_best"][i] is not None:
            return ev["var_best"][i]
        score = ev["z_text"][i].astype(np.float64).copy()
        if self.base_bias is not None:
            score -= (1.0 - self.params["debias"]) * self.base_bias
        cam_pids = self._camera_products(cam)
        cam_b = {self.product_base[p] for p in cam_pids}
        score += np.array([self.params["likely_cam_bonus"] if b in cam_b else 0.0 for b in self.bases])
        if exp_b >= 0:
            score[exp_b] = -np.inf
        base = self.bases[int(score.argmax())]
        cands = [p for p in self.product_ids if self.product_base[p] == base]
        if not cands:
            return None
        pool = [p for p in cands if p in cam_pids] or cands
        pidx = {p: j for j, p in enumerate(self.product_ids)}
        return max(pool, key=lambda p: ev["prod_logits"][i, pidx[p]])

    def _camera_products(self, cam: str) -> set[str]:
        return {p for a, p in self.area_product.items() if self.area_camera.get(a) == cam and p in self.product_base}

    # ------------------------------------------------------------------ persistence

    def state_dict(self) -> dict[str, Any]:
        """JSON-able metadata plus numpy arrays (see :func:`save_state` for the json + npz layout)."""
        arrays = {k: getattr(self, k) for k in ("base_emb", "prod_emb", "empty_emb", "occl_emb", "base_proto",
                                              "base_bias")
                  if getattr(self, k) is not None}
        return {"params": dict(self.params), "prior": self.prior, "logit_scale": self.logit_scale,
                "area_product": self.area_product, "area_camera": self.area_camera,
                "product_base": self.product_base, "product_name": self.product_name,
                "base_group": self.base_group,
                "bases": self.bases, "product_ids": self.product_ids,
                "arrays": {k: np.asarray(v, dtype=np.float32) for k, v in arrays.items()}}

    @classmethod
    def from_state(cls, d: dict[str, Any]) -> "ComplianceModel":
        m = cls()
        m.params.update(d.get("params", {}))
        m.prior = float(d["prior"])
        m.logit_scale = float(d.get("logit_scale", 100.0))
        for k in ("area_product", "area_camera", "product_base", "product_name", "base_group"):
            setattr(m, k, dict(d.get(k, {})))
        m.bases = list(d.get("bases", []))
        m.product_ids = list(d.get("product_ids", []))
        for k, v in d.get("arrays", {}).items():
            setattr(m, k, np.asarray(v, dtype=np.float32))
        return m

    def save(self, directory: str | Path, name: str = "compliance") -> None:
        save_state(self.state_dict(), directory, name)

    @classmethod
    def load(cls, directory: str | Path, name: str = "compliance") -> "ComplianceModel":
        return cls.from_state(load_state(directory, name))


def save_state(state: dict[str, Any], directory: str | Path, name: str) -> None:
    """Write ``<name>.json`` (metadata) and ``<name>.npz`` (the ``arrays`` entry). No pickle."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in state.items() if k != "arrays"}
    (d / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    np.savez(d / f"{name}.npz", **state.get("arrays", {}))


def load_state(directory: str | Path, name: str) -> dict[str, Any]:
    d = Path(directory)
    state = json.loads((d / f"{name}.json").read_text(encoding="utf-8"))
    npz = d / f"{name}.npz"
    if npz.exists():
        with np.load(npz, allow_pickle=False) as z:
            state["arrays"] = {k: z[k] for k in z.files}
    return state

"""Fit everything from unlabelled images, predict any images, save/load the model.

Model directory layout (json + npz, no pickle):
    config.json, model.json (meta), planogram.json (copy), stock.json/.npz, compliance.json/.npz,
    series.json (fit-time fill per area), fit_feats.npz (fit-time CropFeatures, used by
    ``label``/``calibrate``), cam_thumbs.npz (one small grey mean frame per camera, used to find the
    camera of images in a flat folder), heads/ (optional calibration heads, used automatically).
"""
from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

import scoring

from .config import Config
from .data import IMAGE_EXTS, Area, ImageRecord, discover_images, load_image, load_planogram, subsample_even
from .products import Catalog

log = logging.getLogger(__name__)

MODEL_VERSION = 1
LEVELS = ("empty", "half", "full")
FEATURE_FIELDS = ("backend", "crop_size", "inset", "clip_model", "dino_model")
THUMB_SIZE = (128, 72)         # (w, h) of the per-camera high-pass grey thumbnails
MIN_THUMB_CORR = 0.35          # below this an image is not assigned to any camera (real data: own camera
#                                >= 0.53 on all 181 frames, best other camera <= 0.16)


@dataclass
class SenseiModel:
    """Everything learned at fit time."""

    cfg: Config
    planogram: dict                      # the raw planogram.json document
    areas_by_cam: dict[str, list[Area]]
    catalog: Catalog
    stock: Any                           # stock.StockModel
    compliance: Any                      # compliance.ComplianceModel
    series: Any                          # temporal.AreaSeries (fit-time fills)
    heads: Any = None                    # calibrate.Heads or None
    fit_feats: Any = None                # features.CropFeatures of the fit crops (optional)
    meta: dict = field(default_factory=dict)
    cam_thumbs: dict = field(default_factory=dict)   # camera_id -> normalised grey thumbnail (flat)

    @property
    def area_product(self) -> dict[str, str]:
        return self.catalog.area_product()

    @property
    def section(self) -> str:
        for areas in self.areas_by_cam.values():
            if areas:
                return areas[0].section
        return ""

    def save(self, directory: str | Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        self.cfg.to_json(d / "config.json")
        (d / "planogram.json").write_text(json.dumps(self.planogram, ensure_ascii=False), encoding="utf-8")
        self.stock.save(d)
        self.compliance.save(d)
        self.series.save(d / "series.json")
        if self.fit_feats is not None and len(self.fit_feats):
            self.fit_feats.save(d / "fit_feats.npz")
        if self.heads is not None:
            self.heads.save(d / "heads")
        if self.cam_thumbs:
            np.savez_compressed(d / "cam_thumbs.npz", **{f"c{k}": v for k, v in self.cam_thumbs.items()})
        meta = {**self.meta, "version": MODEL_VERSION, "backend": self.cfg.backend}
        (d / "model.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        log.info("model saved to %s", d)
        return d

    @classmethod
    def load(cls, directory: str | Path, load_fit_feats: bool = False) -> "SenseiModel":
        from .compliance import ComplianceModel  # noqa: PLC0415
        from .stock import StockModel  # noqa: PLC0415
        from .temporal import AreaSeries  # noqa: PLC0415
        d = Path(directory)
        if not (d / "model.json").is_file():
            raise FileNotFoundError(f"no model in {d} (model.json missing): run `fit` first")
        cfg = Config.from_json(d / "config.json")
        planogram = json.loads((d / "planogram.json").read_text(encoding="utf-8"))
        areas = load_planogram(d / "planogram.json")
        heads = None
        if (d / "heads" / "heads.json").is_file():
            from .calibrate import Heads  # noqa: PLC0415
            heads = Heads.load(d / "heads")
            log.info("using calibration heads from %s", d / "heads")
        fit_feats = None
        if load_fit_feats and (d / "fit_feats.npz").is_file():
            from .features import CropFeatures  # noqa: PLC0415
            fit_feats = CropFeatures.load(d / "fit_feats.npz")
        thumbs = {}
        if (d / "cam_thumbs.npz").is_file():
            with np.load(d / "cam_thumbs.npz", allow_pickle=False) as z:
                thumbs = {k[1:]: z[k] for k in z.files}
        return cls(cfg=cfg, planogram=planogram, areas_by_cam=areas, catalog=Catalog.from_planogram(areas),
                   stock=StockModel.load(d), compliance=ComplianceModel.load(d),
                   series=AreaSeries.load(d / "series.json"), heads=heads, fit_feats=fit_feats,
                   meta=json.loads((d / "model.json").read_text(encoding="utf-8")), cam_thumbs=thumbs)


# --------------------------------------------------------------------------- helpers

def _cache_dir(cfg: Config) -> str | None:
    return cfg.extra.get("cache_dir", "cache")


def _text_embeddings(cfg: Config, catalog: Catalog, extractor) -> tuple[dict | None, dict | None]:
    """(stock text embeddings, compliance text embeddings); (None, None) for the lite backend."""
    if cfg.backend != "deep" or extractor is None:
        return None, None
    from .compliance import text_embeddings  # noqa: PLC0415
    from .stock import stock_text_embeddings  # noqa: PLC0415
    return stock_text_embeddings(extractor, catalog), text_embeddings(extractor, catalog)


def _compute(records: Sequence[ImageRecord], areas_by_cam: dict[str, list[Area]], cfg: Config, extractor=None):
    from .features import compute_features  # noqa: PLC0415
    return compute_features(records, areas_by_cam, cfg, extractor=extractor,
                            return_patches=cfg.backend == "deep", cache_dir=_cache_dir(cfg))


def _thumb(path: str | Path) -> np.ndarray | None:
    """Small high-pass grey thumbnail (lighting-robust), zero mean / unit norm, for camera
    matching; None if unreadable."""
    import cv2  # noqa: PLC0415
    try:
        rgb = load_image(path)
    except (ValueError, OSError):
        return None
    g = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), THUMB_SIZE, interpolation=cv2.INTER_AREA)
    g = g.astype(np.float32)
    v = (g - cv2.GaussianBlur(g, (0, 0), 3)).ravel()
    v -= v.mean()
    return v / max(float(np.linalg.norm(v)), 1e-6)


def camera_thumbs(records: Sequence[ImageRecord]) -> dict[str, np.ndarray]:
    """camera_id -> normalised mean thumbnail over (up to 6, evenly spaced) of its frames."""
    out: dict[str, np.ndarray] = {}
    for cam in sorted({r.camera_id for r in records}):
        recs = [r for r in records if r.camera_id == cam]
        recs = [recs[int(i)] for i in np.unique(np.linspace(0, len(recs) - 1, min(6, len(recs))).round())]
        ts = [t for t in (_thumb(r.path) for r in recs) if t is not None]
        if ts:
            v = np.mean(ts, axis=0)
            out[cam] = (v / max(float(np.linalg.norm(v)), 1e-6)).astype(np.float32)
    return out


def infer_camera(model: SenseiModel, path: str | Path) -> tuple[str | None, float]:
    """(camera_id, correlation) of the fit-time camera whose view matches this image best (static
    ceiling cameras); camera None when no thumbnails exist or the best match is below MIN_THUMB_CORR."""
    if not model.cam_thumbs:
        return None, 0.0
    t = _thumb(path)
    if t is None:
        return None, 0.0
    cams = sorted(c for c, v in model.cam_thumbs.items() if v.shape == t.shape)
    if not cams:
        log.warning("camera thumbnails of this model have another format: refit to match flat folders")
        return None, 0.0
    corr = np.array([float(model.cam_thumbs[c] @ t) for c in cams])
    best = int(np.argmax(corr))
    return (cams[best] if corr[best] >= MIN_THUMB_CORR else None), float(corr[best])


def submission_key(rec: ImageRecord) -> str:
    """Annotation key of an image: ``<unix_ts>.jpg`` when the stem holds a timestamp (as in the
    brief's annotations), else the file name as on disk."""
    return f"{rec.timestamp}.jpg" if rec.timestamp >= 0 else rec.image_name


def zero_shot(model: SenseiModel, feats) -> tuple[np.ndarray, np.ndarray, np.ndarray, list]:
    """Unsupervised outputs for crops whose ``patch_codes`` are set: (fill, p_levels, p_compliant, likely)."""
    fill = model.stock.fill(feats)
    p_lv = model.stock.proba_from_fill(fill)
    p_comp, likely = model.compliance.predict(feats, fill)
    return fill, p_lv, np.asarray(p_comp, np.float32), list(likely)


# --------------------------------------------------------------------------- fit

def fit(data_root: str | Path, planogram_path: str | Path, out_dir: str | Path | None, cfg: Config,
        splits: Sequence[str] | None = ("train", "test")) -> SenseiModel:
    """Learn the stock and compliance models from the (unlabelled) images under ``data_root``."""
    from .compliance import ComplianceModel  # noqa: PLC0415
    from .stock import StockModel  # noqa: PLC0415
    from .temporal import AreaSeries  # noqa: PLC0415
    t0 = time.perf_counter()
    planogram_path = Path(planogram_path)
    planogram = json.loads(planogram_path.read_text(encoding="utf-8"))
    areas_by_cam = load_planogram(planogram_path)
    catalog = Catalog.from_planogram(areas_by_cam)
    area_product = catalog.area_product()
    records = discover_images(data_root, areas_by_cam, splits)
    records = subsample_even(records, cfg.max_images_per_camera)
    if not records:
        raise ValueError(f"no images of planogram cameras found under {data_root}")
    log.info("fit: %d images of %d cameras (backend=%s)", len(records),
             len({r.camera_id for r in records}), cfg.backend)

    extractor = None
    if cfg.backend == "deep":
        from .features import Extractor  # noqa: PLC0415
        extractor = Extractor(cfg)
    feats, patches = _compute(records, areas_by_cam, cfg, extractor)
    if not len(feats):
        raise ValueError("no readable images to fit on")
    stock_text, comp_text = _text_embeddings(cfg, catalog, extractor)

    stock = StockModel()
    stock.fit(feats, area_product, cfg, patches=patches, catalog=catalog, text_emb=stock_text)
    del patches
    fill = stock.fill(feats)
    p_lv = stock.proba_from_fill(fill)
    comp = ComplianceModel()
    comp.fit(feats, area_product, catalog, comp_text, fill, cfg)
    series = AreaSeries()
    series.add_many(feats.area_ids, feats.timestamps, fill, p_lv)

    meta = {"n_images": len(records), "n_crops": len(feats), "data_root": str(data_root),
            "fit_seconds": round(time.perf_counter() - t0, 1),
            "first_ts": int(feats.timestamps.min()), "last_ts": int(feats.timestamps.max())}
    model = SenseiModel(cfg=cfg, planogram=planogram, areas_by_cam=areas_by_cam, catalog=catalog,
                        stock=stock, compliance=comp, series=series, fit_feats=feats, meta=meta,
                        cam_thumbs=camera_thumbs(records))
    if out_dir is not None:
        model.save(out_dir)
    log.info("fit done in %.1fs", time.perf_counter() - t0)
    return model


# --------------------------------------------------------------------------- predict

def _fallback_proba(model: SenseiModel, area_id: str) -> tuple[float | None, np.ndarray]:
    """(fill, p_levels) for an area we could not look at: its fit-time median, else the prior."""
    med = model.series.median_fill(area_id)
    if med is not None:
        return med, model.stock.proba_from_fill(np.array([med], np.float32))[0]
    return None, np.asarray(model.cfg.level_prior, np.float64) / float(sum(model.cfg.level_prior))


def _apply_heads(model: SenseiModel, feats, fill, p_lv, p_comp) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(stock posterior, p_compliant, carried) from the calibration heads. Stock: the head with the
    late-day prior shift for frames after the last labelled one. Compliance: the unsupervised
    p_compliant (pass-through heads), lowered where a non-compliant label is carried forward."""
    h = model.heads
    try:
        zs_s = p_lv if h.layout.get("zs_stock") else None
        zs_c = p_comp if h.layout.get("zs_comp") else None
        carried = h.carried(feats) if hasattr(h, "carried") else np.zeros(len(feats), bool)
        if carried.any():
            log.info("predict: %d area(s) flagged from an earlier non-compliant label", int(carried.sum()))
        return (h.stock_proba(feats, fill, zs_stock=zs_s), h.compliance_proba(feats, fill, zs_comp=zs_c),
                carried)
    except (ValueError, KeyError) as exc:   # heads incompatible with these features: stay unsupervised
        log.warning("calibration heads not usable (%s): using the unsupervised outputs", exc)
        return p_lv, p_comp, np.zeros(len(feats), bool)


def _likely_for(model: SenseiModel, feats, fill, rows: np.ndarray, likely: list) -> list:
    """Name a likely product for rows flagged only by the heads (the zero-shot model gave none)."""
    need = [int(i) for i in rows if likely[int(i)] is None]
    comp = model.compliance
    if not need or getattr(comp, "base_emb", None) is None or feats.clip is None:
        return likely
    try:
        sub = feats.subset(need)
        ev = comp.evidence(sub, np.asarray(fill)[need])
        for j, i in enumerate(need):
            likely[i] = comp._likely_product(sub.keys[j][0], ev, j)  # noqa: SLF001 - same package
    except Exception as exc:  # noqa: BLE001 - naming is cosmetic, never fail predict for it
        log.warning("could not name likely products: %s", exc)
    return likely


def predict(model: SenseiModel, image_records: Sequence[ImageRecord], cfg: Config | None = None
            ) -> tuple[dict, list[dict]]:
    """(predictions in the submission format, details rows for the UI).

    Every planogram area of each image's camera appears exactly once. Images of unknown cameras are
    skipped (warning); unreadable images get a fallback answer (compliant, area median stock).
    """
    from .temporal import AreaSeries, forecast_empty, smooth  # noqa: PLC0415
    cfg = cfg or model.cfg
    for f in FEATURE_FIELDS:   # features must match the fitted model
        if getattr(cfg, f) != getattr(model.cfg, f):
            log.warning("predict: cfg.%s=%r differs from the model's %r: using the model's", f,
                        getattr(cfg, f), getattr(model.cfg, f))
            cfg = cfg.replace(**{f: getattr(model.cfg, f)})
    t0 = time.perf_counter()
    records = []
    for r in image_records:
        if r.camera_id in model.areas_by_cam:
            records.append(r)
        else:
            log.warning("camera %s not in the planogram: skipping %s", r.camera_id, r.path)
    seen, uniq = set(), []
    for r in records:              # one answer per (camera, image_name)
        if (r.camera_id, r.image_name) in seen:
            log.warning("duplicate image %s/%s: keeping the first (%s)", r.camera_id, r.image_name, r.path)
            continue
        seen.add((r.camera_id, r.image_name))
        uniq.append(r)
    records = uniq

    # ---- features + models (one batch over all images)
    by_key: dict[tuple[str, str, str], int] = {}
    feats = None
    fill = p_lv = p_comp = np.zeros(0)
    carried = np.zeros(0, bool)
    likely: list = []
    if records:
        try:
            extractor = None
            if cfg.backend == "deep":
                from .features import Extractor  # noqa: PLC0415
                extractor = Extractor(cfg)
            feats, patches = _compute(records, model.areas_by_cam, cfg, extractor)
            if len(feats):
                model.stock.encode(feats, patches)
                del patches
                fill, p_lv, p_comp, likely = zero_shot(model, feats)
                if model.heads is not None:
                    p_lv, p_comp, carried = _apply_heads(model, feats, fill, p_lv, p_comp)
                    likely = _likely_for(model, feats, fill, np.flatnonzero(p_comp < 0.5), likely)
                by_key = {k: i for i, k in enumerate(feats.keys)}
        except Exception:  # noqa: BLE001 - never crash: every area gets the fallback answer
            log.exception("predict: feature/model failure, using fallback answers for all images")
            by_key = {}

    # ---- assemble rows
    series = AreaSeries.from_state(model.series.state_dict())
    rows: list[dict] = []
    n_fallback = 0
    for r in records:
        for a in model.areas_by_cam[r.camera_id]:
            i = by_key.get((r.camera_id, r.image_name, a.area_id))
            if i is None:
                n_fallback += 1
                f, p = _fallback_proba(model, a.area_id)
                pc, lk, vis, kept = 1.0, None, None, False
            else:
                f, p = float(fill[i]), np.asarray(p_lv[i], np.float64)
                pc, lk, vis = float(p_comp[i]), likely[i], float(feats.visible[i])
                kept = bool(carried[i]) if len(carried) else False   # carried flag: no empty override
                if cfg.smoothing_weight > 0:
                    f, p = smooth(f, p, series.neighbours(a.area_id, r.timestamp, cfg.smoothing_window_s),
                                  cfg, now_ts=r.timestamp)
            p = np.clip(np.asarray(p, np.float64), 0, None)
            p = p / p.sum() if p.sum() > 0 else np.full(3, 1 / 3)
            value, level = scoring.best_stock(*[float(x) for x in p])
            compliant = bool(scoring.best_compliance(pc)) or (value == 0.0 and not kept)  # empty -> nothing wrong shown
            if compliant:
                lk = None
            rows.append(_row(model, r, a, level, value, f, p, compliant, pc, lk, vis, i is None))
            if f is not None and i is not None:
                series.add(a.area_id, r.timestamp, f, p)
    if n_fallback:
        log.warning("predict: %d area answers are fallbacks (unreadable images)", n_fallback)

    # ---- forecast (uses fit-time + predicted fills up to each frame)
    for row in rows:
        if not row["fallback"]:
            eta = forecast_empty(series.before(row["area_id"], row["timestamp"]), row["timestamp"])
            row["forecast_empty_s"] = None if eta is None else int(round(eta))

    preds: dict = {}
    keys = {(r.camera_id, r.image_name): submission_key(r) for r in records}
    for row in rows:
        entry = scoring.make_entry(row["planogram_compliant"], row["stock_value"])
        imgs = preds.setdefault(row["camera_id"], {})
        canon = keys[(row["camera_id"], row["image_name"])]
        names = [canon] if canon == row["image_name"] else [canon, row["image_name"]]  # + on-disk alias
        for name in names:
            if name == row["image_name"] or (name not in imgs or row["area_id"] not in imgs[name]):
                imgs.setdefault(name, {})[row["area_id"]] = entry
    log.info("predict: %d images, %d areas in %.1fs", len(records), len(rows), time.perf_counter() - t0)
    return preds, rows


def _row(model: SenseiModel, rec: ImageRecord, a: Area, level: str, value: float, fill: float | None,
         p: np.ndarray, compliant: bool, pc: float, likely: str | None, vis: float | None,
         fallback: bool) -> dict:
    prod = model.catalog[a.product_id] if a.product_id in model.catalog else {}
    lp = model.catalog[likely] if likely is not None and likely in model.catalog else None
    return {"camera_id": a.camera_id, "image_name": rec.image_name, "area_id": a.area_id,
            "product_id": a.product_id, "product_name": a.product_name,
            "english": prod.get("english", a.product_name.lower()), "loose": bool(prod.get("loose", True)),
            "timestamp": int(rec.timestamp), "stock_level": level, "stock_value": value,
            "fill": None if fill is None else round(float(fill), 4),
            "p_levels": [round(float(x), 4) for x in p], "planogram_compliant": compliant,
            "p_compliant": round(float(pc), 4), "likely_product_id": likely,
            "likely_product_name": None if lp is None else lp["name"],
            "likely_english": None if lp is None else lp.get("english"),
            "visible": None if vis is None else round(vis, 4), "forecast_empty_s": None,
            "quad": [[round(float(x), 1), round(float(y), 1)] for x, y in np.asarray(a.quad)],
            "image_path": str(rec.path), "fallback": bool(fallback)}


def details_doc(model: SenseiModel, rows: list[dict]) -> dict:
    """The details.json document (rows + per-area timeline over fit-time and predicted frames)."""
    tl: dict[str, dict[int, list]] = {}
    for a in model.series.areas():
        for t, f, p in model.series.rows(a):
            tl.setdefault(a, {})[int(t)] = [int(t), round(float(f), 3), scoring.best_stock(*p)[1]]
    for r in rows:
        if r["fill"] is not None and r["visible"] is not None:   # not a fallback answer
            tl.setdefault(r["area_id"], {})[r["timestamp"]] = [r["timestamp"], round(r["fill"], 3), r["stock_level"]]
    wanted = {r["area_id"] for r in rows}
    ts = [r["timestamp"] for r in rows if r["timestamp"] >= 0]
    return {"section": model.section, "generated_at": max(ts) if ts else int(time.time()),
            "backend": model.cfg.backend, "rows": rows,
            "timeline": {a: [tl[a][t] for t in sorted(tl[a])] for a in sorted(tl) if a in wanted}}


def _flat_records(model: SenseiModel, root: Path, known: set[Path]) -> tuple[list[ImageRecord], int]:
    """Images under ``root`` with no camera in their path or name (flat layouts): camera found by
    matching the view against the fit-time cameras. Paths with an all-digit component other than a
    planogram camera (an unknown camera) are left out. Returns (records, n_unmatched)."""
    out, missed = [], 0
    for path in sorted(root.rglob("*")):
        if path in known or not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        parts = [*path.relative_to(root).parent.parts, path.stem.split("_")[0].split("-")[0]]
        if any(p.isdigit() and p not in model.areas_by_cam and len(p) < 9 for p in parts):
            continue            # explicit unknown camera id (a long digit run is a timestamp)
        cam, corr = infer_camera(model, path)
        if cam is None:
            missed += 1
            continue
        stem = path.stem
        ts = int(stem) if stem.isdigit() else -1
        log.info("camera of %s inferred from the picture: %s (corr %.2f)", path.name, cam, corr)
        out.append(ImageRecord(path=path, camera_id=cam, image_name=path.name, timestamp=ts, split="unknown"))
    return out, missed


def predict_dir(model: SenseiModel, images: str | Path, out: str | Path | None = None,
                details: str | Path | None = None, cfg: Config | None = None,
                strict: bool = True) -> tuple[dict, dict]:
    """Discover every image under ``images``, predict, and write the json files.

    ``strict``: raise FileNotFoundError when the folder is missing and ValueError when no image
    matches a planogram camera (an empty submission would score -5 per area). Images without a
    camera in their path or name get one from their content (``infer_camera``).
    """
    root = Path(images)
    if not root.is_dir():
        if strict:
            raise FileNotFoundError(f"image folder not found: {root}")
        log.warning("image folder not found: %s", root)
    records = discover_images(root, model.areas_by_cam)
    missed = 0
    if root.is_dir():
        extra, missed = _flat_records(model, root, {r.path for r in records})
        records = sorted(records + extra, key=lambda r: (r.camera_id, r.timestamp, r.image_name, str(r.path)))
    n_files = sum(1 for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS) if root.is_dir() else 0
    if not records:
        msg = (f"no images of planogram cameras under {root} ({n_files} image file(s) found; expected "
               "<camera_id>/<ts>.jpg, <camera_id>_<ts>.jpg or frames of known camera views)")
        if strict:
            raise ValueError(msg)
        log.warning(msg)
    preds, rows = predict(model, records, cfg)
    doc = details_doc(model, rows)
    doc["input"] = {"folder": str(root), "image_files": n_files, "images_used": len({(r["camera_id"], r["image_name"]) for r in rows}),
                    "unmatched": missed, "cameras": sorted({r["camera_id"] for r in rows}),
                    "expected_areas": sum(len(model.areas_by_cam[r.camera_id]) for r in
                                          {(r.camera_id, r.image_name): r for r in records}.values()),
                    "areas": len(rows)}
    for path, obj in ((out, preds), (details, doc)):
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
            log.info("wrote %s", path)
    return preds, doc


# --------------------------------------------------------------------------- calibration glue

def calibrate(model_dir: str | Path, label_paths: Sequence[str | Path], cv: bool = True) -> dict:
    """Fit calibration heads on labelled fit-time crops and store them in ``<model_dir>/heads``."""
    from .calibrate import cross_validate, fit_heads, format_report, load_labels  # noqa: PLC0415
    model = SenseiModel.load(model_dir, load_fit_feats=True)
    feats = model.fit_feats
    if feats is None:
        raise FileNotFoundError(f"{model_dir}/fit_feats.npz missing: refit the model")
    labels = load_labels(*label_paths)
    fill, p_lv, p_comp, _ = zero_shot(model, feats)
    coder = getattr(model.stock, "coder", None)
    prod = None if coder is None else getattr(coder, "productness", None)   # per-band fills of the stock head
    report: dict = {}
    if cv:
        report = cross_validate(feats, fill, labels, model.cfg, zs_stock=p_lv, zs_comp=p_comp, productness=prod)
        log.info("cross-validation:\n%s", format_report(report))
        (Path(model_dir) / "calibration_cv.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    heads = fit_heads(feats, fill, labels, model.cfg, zs_stock=p_lv, zs_comp=p_comp, productness=prod)
    heads.save(Path(model_dir) / "heads")
    log.info("heads saved to %s", Path(model_dir) / "heads")
    return report


def remove_heads(model_dir: str | Path) -> None:
    shutil.rmtree(Path(model_dir) / "heads", ignore_errors=True)

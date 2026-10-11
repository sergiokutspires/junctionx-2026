"""Rebuild the submission model from the public repo + the dataset and check it gives the same answers.

Fits a fresh model with the exact config of models/real_v3_cal (config.json), calibrates it on the public
labels (data/labels/teacher_labels_v2.json) as README "Run it" documents, predicts a folder (default
data/val_sim) and compares:

  * every model file with the SHA-256 fingerprint in results/model_manifest.json (model.json is compared
    without its wall-clock ``fit_seconds``);
  * the predictions with a reference predictions.json (default outputs/rehearsal_0850/predictions.json):
    byte-identical, or the list of areas whose answer changed.

The frozen models (models/real_v3_cal, models/real_v1) are only read, never written.

  .venv/Scripts/python tools/reproduce_check.py                   # reuse the on-disk feature cache (fast)
  .venv/Scripts/python tools/reproduce_check.py --fresh-features  # recompute every CLIP/DINOv2 feature

Exit code 0 = predictions identical, 1 = they differ, 2 = setup error.

Model files can differ in the last float32 bits from run to run: the stock model's k-means runs multithreaded.
Set OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 for bit-identical rebuilds (results/reproduce.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FROZEN = ("real_v3_cal", "real_v1")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def compare_model(out: Path, manifest: dict) -> dict:
    """{file: 'same' | 'differs' | 'missing' | 'extra'} against the manifest entry of real_v3_cal."""
    saved = manifest["models"]["real_v3_cal"]
    res = {}
    for name in sorted(set(saved) | {str(p.relative_to(out)).replace("\\", "/")
                                     for p in out.rglob("*") if p.is_file()}):
        p = out / name
        if name not in saved:
            res[name] = "extra"
        elif not p.is_file():
            res[name] = "missing"
        elif sha256(p) == saved[name]["sha256"]:
            res[name] = "same"
        elif name == "model.json":   # differs by the wall-clock fit_seconds only?
            ref = json.loads((ROOT / "models" / "real_v3_cal" / "model.json").read_text(encoding="utf-8"))
            new = json.loads(p.read_text(encoding="utf-8"))
            ref.pop("fit_seconds", None), new.pop("fit_seconds", None)
            ref.pop("data_root", None), new.pop("data_root", None)
            res[name] = "same (except fit_seconds)" if ref == new else "differs"
        else:
            res[name] = "differs"
    return res


def diff_predictions(ref: dict, new: dict) -> list[str]:
    out = []
    for cam in sorted(set(ref) | set(new)):
        imgs_r, imgs_n = ref.get(cam, {}), new.get(cam, {})
        for img in sorted(set(imgs_r) | set(imgs_n)):
            ar, an = imgs_r.get(img, {}), imgs_n.get(img, {})
            for area in sorted(set(ar) | set(an)):
                if ar.get(area) != an.get(area):
                    out.append(f"{cam}/{img}/{area}: {ar.get(area)} -> {an.get(area)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/raw/images", help="training images (default data/raw/images)")
    ap.add_argument("--planogram", default="data/raw/planogram.json")
    ap.add_argument("--labels", nargs="+", default=["data/labels/teacher_labels_v2.json"])
    ap.add_argument("--config", default="models/real_v3_cal/config.json", help="config of the model to rebuild")
    ap.add_argument("--out", default="models/repro_check", help="where the rebuilt model goes")
    ap.add_argument("--images", default="data/val_sim", help="images to predict with the rebuilt model")
    ap.add_argument("--ref", default="outputs/rehearsal_0850/predictions.json", help="reference predictions.json")
    ap.add_argument("--fresh-features", action="store_true",
                    help="ignore the on-disk feature cache: recompute every CLIP/DINOv2 feature (slow on CPU)")
    ap.add_argument("--no-cv", action="store_true", help="skip the calibration cross-validation (faster)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import os
    os.chdir(ROOT)   # the feature cache (cache/) and the default paths are relative to the project root
    from sensei import pipeline
    from sensei.config import Config

    out = (ROOT / args.out).resolve()
    if out.name in FROZEN or any(out == (ROOT / "models" / f).resolve() for f in FROZEN):
        print(f"refusing to write into a frozen model folder: {out}")
        return 2
    if not (ROOT / args.ref).is_file():
        print(f"reference predictions missing: {args.ref}")
        return 2
    tmp = None
    if args.fresh_features:   # an empty, throw-away feature cache: every feature is recomputed
        tmp = tempfile.mkdtemp(prefix="repro_feats_")
        pipeline._cache_dir = lambda cfg: tmp   # noqa: SLF001
    cfg = Config.from_json(ROOT / args.config)
    times = {}
    t0 = time.perf_counter()
    pipeline.fit(args.data, args.planogram, out, cfg)   # relative, as README runs it (paths are stored)
    times["fit_s"] = round(time.perf_counter() - t0, 1)
    t1 = time.perf_counter()
    pipeline.calibrate(out, args.labels, cv=not args.no_cv)
    times["calibrate_s"] = round(time.perf_counter() - t1, 1)
    t2 = time.perf_counter()
    model = pipeline.SenseiModel.load(out)
    pred_path = out / "repro_predictions.json"
    pipeline.predict_dir(model, args.images, pred_path, None)
    times["predict_s"] = round(time.perf_counter() - t2, 1)
    times["total_s"] = round(time.perf_counter() - t0, 1)
    pred_path_bytes = pred_path.read_bytes()
    ref_bytes = (ROOT / args.ref).read_bytes()

    manifest = json.loads((ROOT / "results" / "model_manifest.json").read_text(encoding="utf-8"))
    files = compare_model(out, manifest)
    if args.no_cv:
        files.pop("calibration_cv.json", None)
    files.pop("repro_predictions.json", None)
    changed = diff_predictions(json.loads(ref_bytes), json.loads(pred_path_bytes))
    n_areas = sum(len(a) for imgs in json.loads(ref_bytes).values() for a in imgs.values())
    identical = pred_path_bytes == ref_bytes
    report = {"identical_predictions": identical, "areas_compared": n_areas, "areas_changed": len(changed),
              "changed": changed[:50], "model_files": files, "fresh_features": args.fresh_features,
              "times": times, "versions": _versions()}
    print(json.dumps(report, indent=1))
    print(("REPRODUCED: predictions byte-identical to " if identical else
           f"NOT IDENTICAL: {len(changed)} of {n_areas} areas differ from ") + args.ref)
    if tmp:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if identical else 1


def _versions() -> dict:
    import platform
    v = {"python": platform.python_version()}
    for mod in ("numpy", "torch", "transformers", "sklearn", "PIL"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001
            v[mod] = None
    return v


if __name__ == "__main__":
    sys.exit(main())

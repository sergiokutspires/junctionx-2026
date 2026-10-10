"""Command line: ``python -m sensei <command> ...`` (see README.md / SPEC.md section 4)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:   # scoring.py lives in the project root
    sys.path.insert(0, str(ROOT))

from .config import Config  # noqa: E402

log = logging.getLogger("sensei")


def _cfg(args: argparse.Namespace) -> Config:
    cfg = Config.from_json(args.config) if getattr(args, "config", None) else Config()
    changes = {}
    if getattr(args, "backend", None):
        changes["backend"] = args.backend
    if getattr(args, "max_images_per_camera", None):
        changes["max_images_per_camera"] = args.max_images_per_camera
    if getattr(args, "device", None):
        changes["device"] = args.device
    return cfg.replace(**changes) if changes else cfg


def cmd_synth(args) -> None:
    from .synth import generate_dataset
    info = generate_dataset(args.out, args.cameras, args.images, args.seed, args.val)
    print(json.dumps({k: str(v) for k, v in info.items() if k in ("root", "images_dir", "val_dir", "planogram",
                                                                    "annotations", "n_areas")}, indent=1))


def cmd_fit(args) -> None:
    from . import pipeline
    t0 = time.perf_counter()
    pipeline.fit(args.data, args.planogram, args.model, _cfg(args))
    if args.labels:
        pipeline.calibrate(args.model, args.labels, cv=not args.no_cv)
    print(f"model: {args.model}  ({time.perf_counter() - t0:.1f}s)")


def _predict(model_dir: str, images: str, out: str, details: str | None, device: str | None) -> None:
    from . import pipeline
    t0 = time.perf_counter()
    try:
        model = pipeline.SenseiModel.load(model_dir)
        cfg = model.cfg.replace(device=device) if device else None
        preds, doc = pipeline.predict_dir(model, images, out, details, cfg)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}\nNothing was written: an empty submission would score -5 per area.",
              file=sys.stderr)
        sys.exit(2)
    info = doc.get("input", {})
    skipped = info.get("image_files", 0) - info.get("images_used", 0)
    print(f"predictions: {out}  ({info.get('images_used', 0)} images of {len(info.get('cameras', []))} cameras, "
          f"{info.get('areas', 0)} areas (expected {info.get('expected_areas', 0)}), "
          f"{skipped} image file(s) skipped, heads: {'yes' if model.heads is not None else 'no'}, "
          f"{time.perf_counter() - t0:.1f}s)")


def cmd_predict(args) -> None:
    _predict(args.model, args.images, args.out, args.details, args.device)


def cmd_score(args) -> None:
    import scoring
    truth = json.loads(Path(args.annotations).read_text(encoding="utf-8"))
    preds = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    res = scoring.score(truth, preds)
    base = {c: {i: {a: scoring.make_entry(True, 1.0) for a in areas} for i, areas in imgs.items()}
            for c, imgs in truth.items()}
    print(json.dumps(res, indent=1))
    print(f"Score: {res['total']} / {res['max']}   (always compliant + full: "
          f"{scoring.score(truth, base)['total']})")


def cmd_dashboard(args) -> None:
    from .dashboard import build, make_zip
    print(build(args.details, args.data, args.out, detections=args.detections, detect=args.detect))
    if args.zip:
        print(make_zip(args.out))


def cmd_label(args) -> None:
    from .calibrate import export_sheets
    from .pipeline import SenseiModel
    model = SenseiModel.load(args.model, load_fit_feats=True)
    if model.fit_feats is None:
        sys.exit(f"{args.model}/fit_feats.npz missing: refit the model")
    fill = model.stock.fill(model.fit_feats)
    manifest = export_sheets(model.fit_feats, args.data, model.areas_by_cam, args.out, model.cfg,
                             n=args.n, fill=fill)
    print(f"{len(manifest.get('tiles', manifest))} tiles -> {args.out} (open labeler.html)")


def cmd_calibrate(args) -> None:
    from .calibrate import format_report
    from .pipeline import calibrate
    report = calibrate(args.model, args.labels, cv=not args.no_cv)
    if report:
        print(format_report(report))
    print(f"heads: {Path(args.model) / 'heads'}")


def cmd_run(args) -> None:
    from . import pipeline
    out = Path(args.out)
    model_dir = out / "model"
    t0 = time.perf_counter()
    pipeline.fit(args.data, args.planogram, model_dir, _cfg(args))
    if args.labels:
        pipeline.calibrate(model_dir, args.labels, cv=not args.no_cv)
    t1 = time.perf_counter()
    _predict(str(model_dir), args.images or args.data, str(out / "predictions.json"),
             str(out / "details.json"), None)
    from .dashboard import build
    index = build(out / "details.json", args.images or args.data, out / "dashboard")
    print(f"fit {t1 - t0:.1f}s, predict+dashboard {time.perf_counter() - t1:.1f}s")
    print(f"dashboard: {index}")


def cmd_submit(args) -> None:
    from .submit import run
    code = run(args.images, args.model, args.out, detect=not args.no_detect, detections=args.detections,
               device=args.device)
    if code:
        sys.exit(code)


def _fit_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data", required=True, help="image root (any layout)")
    p.add_argument("--planogram", required=True)
    p.add_argument("--backend", choices=("deep", "lite"))
    p.add_argument("--max-images-per-camera", type=int)
    p.add_argument("--device", help="auto | cpu | cuda")
    p.add_argument("--config", help="Config JSON (fields override the defaults)")
    p.add_argument("--labels", nargs="+", help="optional annotation files: also fit calibration heads")
    p.add_argument("--no-cv", action="store_true", help="skip cross-validation when calibrating")


class _SubParsers(argparse._SubParsersAction):   # noqa: SLF001
    """Every sub-command also accepts -q/--quiet (before or after its other options)."""

    def add_parser(self, name, **kwargs):
        p = super().add_parser(name, **kwargs)
        p.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS, help="warnings only")
        return p


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m sensei", description="Sensei shelf monitor")
    ap.add_argument("-q", "--quiet", action="store_true", help="warnings only")
    ap.register("action", "parsers", _SubParsers)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("synth", help="write a synthetic dataset")
    p.add_argument("--out", required=True)
    p.add_argument("--cameras", type=int, default=4)
    p.add_argument("--images", type=int, default=12, help="train images per camera")
    p.add_argument("--val", type=int, default=2, help="val images per camera")
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_synth)

    p = sub.add_parser("fit", help="learn from unlabelled images")
    _fit_args(p)
    p.add_argument("--model", required=True, help="output model directory")
    p.set_defaults(func=cmd_fit)

    p = sub.add_parser("predict", help="answer every area of every image")
    p.add_argument("--model", required=True)
    p.add_argument("--images", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--details")
    p.add_argument("--device")
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("score", help="local challenge score")
    p.add_argument("annotations")
    p.add_argument("predictions")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("dashboard", help="build the static staff dashboard")
    p.add_argument("--details", required=True)
    p.add_argument("--data", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--zip", action="store_true")
    p.add_argument("--detections", default=None,
                   help="OWLv2 product boxes: .zip holding owl_detections.json, or that .json (optional)")
    p.add_argument("--detect", action="store_true",
                   help="run OWLv2 locally on the shown frames lacking boxes (free; slow on CPU)")
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("label", help="export contact sheets + labelling page")
    p.add_argument("--model", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--out", default="labeling")
    p.add_argument("--n", type=int, default=150)
    p.set_defaults(func=cmd_label)

    p = sub.add_parser("calibrate", help="fit calibration heads from labels")
    p.add_argument("--model", required=True)
    p.add_argument("--labels", required=True, nargs="+")
    p.add_argument("--no-cv", action="store_true")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("submit", help="validation day: images (folder/zip) -> checked predictions.json + staff app")
    p.add_argument("--images", required=True, nargs="+", help="folder, .zip, or image files (flags go after the paths)")
    p.add_argument("--model", default="models/real_v1_cal")
    p.add_argument("--out", default="submission")
    p.add_argument("--no-detect", action="store_true", help="skip the local OWLv2 product boxes in the staff app")
    p.add_argument("--detections", default=None, help="cached OWLv2 boxes (.zip/.json) to reuse (optional)")
    p.add_argument("--device", help="auto | cpu | cuda")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("run", help="fit + predict + dashboard")
    _fit_args(p)
    p.add_argument("--images", help="images to predict (default: --data)")
    p.add_argument("--out", default="outputs")
    p.set_defaults(func=cmd_run)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    args.func(args)


if __name__ == "__main__":
    main()

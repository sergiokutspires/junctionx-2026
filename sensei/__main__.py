"""Command line: ``python -m sensei <command> ...``.

Each sub-command is a thin wrapper around one module: ``fit`` and ``predict`` call ``sensei.pipeline``,
``calibrate`` and ``label`` call ``sensei.calibrate``, ``dashboard`` calls ``sensei.dashboard`` and
``submit`` (the validation-day command) calls ``sensei.submit``. Run ``python -m sensei <command> --help``
for the options of one command; README.md has worked examples.
"""
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

DEFAULT_MODEL = "models/real_v3_cal"


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
        _, doc = pipeline.predict_dir(model, images, out, details, cfg)
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
    biology = False if getattr(args, "no_biology", False) else getattr(args, "biology", None)
    print(build(args.details, args.data, args.out, detections=args.detections, detect=args.detect, biology=biology))
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
               device=args.device, password=args.password)
    if code:
        sys.exit(code)


def cmd_watch(args) -> None:
    from .events import summary, watch
    t0 = time.perf_counter()
    try:
        events, rows = watch(args.model, args.images, args.out, confirm=args.confirm, device=args.device)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"ERROR: {exc}")
    print(summary(events, rows))
    print(f"events: {args.out or '(not written: use --out)'}  ({time.perf_counter() - t0:.1f}s)")


def cmd_serve(args) -> None:
    from .serve import serve
    serve(args.model, port=args.port, device=args.device)


# --------------------------------------------------------------------------- argument parser

DEVICE_HELP = "auto (default: CUDA if available, else CPU) | cpu | cuda"
LABELS_HELP = "answer-key file(s) in the challenge format (e.g. data/labels/teacher_labels_v2.json); later files win"


def _fit_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data", required=True,
                   help="folder of training images (any layout: <cam>/<ts>.jpg, <cam>_<ts>.jpg, train/test folders)")
    p.add_argument("--planogram", required=True, help="planogram.json of the store")
    p.add_argument("--backend", choices=("deep", "lite"),
                   help="deep = CLIP + DINOv2 (default); lite = handcrafted colour features only (no torch, weaker)")
    p.add_argument("--max-images-per-camera", type=int, metavar="N",
                   help="fit on at most N images per camera, evenly spread over time (default 150)")
    p.add_argument("--device", help=DEVICE_HELP)
    p.add_argument("--config", metavar="JSON", help="Config JSON file; its fields override the defaults")
    p.add_argument("--labels", nargs="+", metavar="FILE",
                   help="optional: " + LABELS_HELP + "; also fits the calibration heads")
    p.add_argument("--no-cv", action="store_true", help="skip the held-out cross-validation report when calibrating")


class _SubParsers(argparse._SubParsersAction):   # noqa: SLF001
    """Every sub-command also accepts -q/--quiet (before or after its other options)."""

    def add_parser(self, name, **kwargs):
        p = super().add_parser(name, **kwargs)
        p.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS,
                       help="log warnings only (no progress messages)")
        return p


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m sensei",
        description="Fresh Eyes shelf monitor: stock level (empty / half / full) and planogram compliance "
                    "for every planogram area of ceiling-camera images.",
        epilog="Validation day: python -m sensei submit --images <folder|.zip>  (or double-click SUBMIT.bat). "
               "Run python -m sensei <command> --help for the options of one command.")
    ap.add_argument("-q", "--quiet", action="store_true", help="log warnings only (no progress messages)")
    ap.register("action", "parsers", _SubParsers)
    sub = ap.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name: str, summary: str, description: str | None = None) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=summary, description=description or summary)

    p = add("submit", "validation day: images (folder / .zip / files) -> checked predictions.json + staff app",
            "Predict every planogram area of the given images with a fitted model, check the written "
            "predictions.json independently (format, every area of every image), then build the staff app. "
            "Exit code: 0 check passed, 1 check failed (file written but flagged), 2 input error (nothing written).")
    p.add_argument("--images", required=True, nargs="+", metavar="PATH",
                   help="a folder, a .zip, or image files (put any other options after the paths)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"fitted model directory (default: {DEFAULT_MODEL}; models/real_v1 = the label-free fallback)")
    p.add_argument("--out", default="submission",
                   help="output folder for predictions.json, details.json and dashboard/ (default: submission)")
    p.add_argument("--no-detect", action="store_true",
                   help="skip the optional OWLv2 product boxes and unit counts in the staff app (faster)")
    p.add_argument("--detections", default=None, metavar="FILE",
                   help="reuse cached OWLv2 boxes (.zip holding owl_detections.json, or that .json)")
    p.add_argument("--device", help=DEVICE_HELP)
    p.add_argument("--password", default=None,
                   help="password of an encrypted .zip (ZipCrypto only; unzip AES zips by hand)")
    p.set_defaults(func=cmd_submit)

    p = add("fit", "learn the label-free models from unlabelled images (optionally calibrate on labels)",
            "Fit the unsupervised stock and compliance models on the images under --data and save them to "
            "--model. With --labels, also fit the calibration heads (same as running `calibrate` afterwards).")
    _fit_args(p)
    p.add_argument("--model", required=True, help="output model directory")
    p.set_defaults(func=cmd_fit)

    p = add("calibrate", "fit the calibration heads of a fitted model on labelled frames",
            "Fit the stock head and the per-area memory on the labelled fit-time crops of --model and save them "
            "in <model>/heads (used automatically by predict and submit). Also writes calibration_cv.json, "
            "the held-out scores, unless --no-cv.")
    p.add_argument("--model", required=True, help="fitted model directory (from `fit`)")
    p.add_argument("--labels", required=True, nargs="+", metavar="FILE", help=LABELS_HELP)
    p.add_argument("--no-cv", action="store_true", help="skip the held-out cross-validation report")
    p.set_defaults(func=cmd_calibrate)

    p = add("predict", "answer every planogram area of every image (no format check, no staff app)",
            "Write predictions.json (challenge format) and optionally details.json (per-area details for the "
            "staff app). Use `submit` on validation day: it adds the independent format check.")
    p.add_argument("--model", required=True, help="fitted model directory")
    p.add_argument("--images", required=True, help="image folder (any layout)")
    p.add_argument("--out", required=True, help="predictions.json to write")
    p.add_argument("--details", help="details.json to write (input of `dashboard`)")
    p.add_argument("--device", help=DEVICE_HELP)
    p.set_defaults(func=cmd_predict)

    p = add("score", "local challenge score of a predictions file against an answer key",
            "Score predictions with the brief's rules (scoring.py) and compare with the always-compliant + "
            "full baseline.")
    p.add_argument("annotations", help="answer key in the challenge format")
    p.add_argument("predictions", help="predictions.json to score")
    p.set_defaults(func=cmd_score)

    p = add("dashboard", "build the static staff app from details.json",
            "Build the staff app (a folder that opens from file://, no server, no network) from the details.json "
            "written by predict or submit.")
    p.add_argument("--details", required=True, help="details.json from predict / submit")
    p.add_argument("--data", default=None, help="image folder, used when a row's image_path is missing")
    p.add_argument("--out", required=True, help="output folder (index.html is written there)")
    p.add_argument("--zip", action="store_true", help="also write <out>.zip")
    p.add_argument("--detections", default=None, metavar="FILE",
                   help="OWLv2 product boxes: .zip holding owl_detections.json, or that .json (optional)")
    p.add_argument("--detect", action="store_true",
                   help="run OWLv2 locally on the shown frames lacking boxes (free; slow on CPU)")
    p.add_argument("--biology", default=None, metavar="CSV",
                   help="produce biology reference CSV (default docs/produce_biology_reference.csv; values typed "
                        "into docs/produce_biology_template.csv override it)")
    p.add_argument("--no-biology", action="store_true", help="no freshness badges or ethylene pairs")
    p.set_defaults(func=cmd_dashboard)

    p = add("label", "export contact sheets and a labelling page for labelling crops by eye",
            "Optional human labelling route: write contact sheets, crops and labeler.html for a sample of the "
            "fit-time crops of --model; the labels it exports can be passed to `calibrate`.")
    p.add_argument("--model", required=True, help="fitted model directory (needs fit_feats.npz)")
    p.add_argument("--data", required=True, help="image folder the model was fitted on")
    p.add_argument("--out", default="labeling", help="output folder (default: labeling)")
    p.add_argument("--n", type=int, default=150, help="crops to sample, stratified by fill (default 150)")
    p.set_defaults(func=cmd_label)

    p = add("run", "fit + predict + dashboard in one go (development shortcut)",
            "Fit a model into <out>/model, predict --images (default: --data) and build <out>/dashboard.")
    _fit_args(p)
    p.add_argument("--images", help="images to predict (default: --data)")
    p.add_argument("--out", default="outputs", help="output folder (default: outputs)")
    p.set_defaults(func=cmd_run)

    p = add("watch", "area events: compare each area with its previous frame (became_empty, restocked, ...)",
            "Predict every frame under --images, order each camera's frames by time and emit one JSON line per "
            "area status change: became_empty, became_low, restocked, back_to_ok, wrong_product, "
            "wrong_product_fixed. The first frame of an area only sets its baseline.")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"fitted model directory (default: {DEFAULT_MODEL})")
    p.add_argument("--images", required=True, help="image folder (any layout)")
    p.add_argument("--out", default=None, help="events.jsonl to write (one JSON event per line)")
    p.add_argument("--confirm", type=int, default=1, metavar="K",
                   help="report a new status only after K consecutive frames show it (default 1)")
    p.add_argument("--device", help=DEVICE_HELP)
    p.set_defaults(func=cmd_watch)

    p = add("serve", "local HTTP endpoint: POST a JPEG to /analyze, get every area's status (127.0.0.1 only)",
            "Load the model once and answer POST /analyze (JPEG body; headers X-Camera-Id and X-Timestamp or "
            "query parameters camera_id and timestamp) and GET /health. Standard library only.")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"fitted model directory (default: {DEFAULT_MODEL})")
    p.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1 (default 8765)")
    p.add_argument("--device", help=DEVICE_HELP)
    p.set_defaults(func=cmd_serve)

    p = add("synth", "write a small synthetic dataset (for tests and demos)",
            "Write a synthetic planogram, camera frames and an answer key for the later frames.")
    p.add_argument("--out", required=True, help="output folder")
    p.add_argument("--cameras", type=int, default=4, help="number of cameras (default 4)")
    p.add_argument("--images", type=int, default=12, help="training images per camera (default 12)")
    p.add_argument("--val", type=int, default=2, help="later, labelled images per camera (default 2)")
    p.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    p.set_defaults(func=cmd_synth)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    args.func(args)


if __name__ == "__main__":
    main()

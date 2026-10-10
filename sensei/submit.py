"""One-command validation-day run: ``python -m sensei submit --images <folder|.zip|files...>``.

Steps: unpack (zip) -> predict (strict) -> validate the written JSON independently of the pipeline
-> write ``<out>/predictions.json`` (the file to hand in) + ``details.json`` -> staff dashboard in
``<out>/dashboard/`` (OWLv2 boxes unless ``--no-detect``; the dashboard can never fail the submission)
-> unmissable summary. Exit code: 0 validation passed, 1 validation failed (file still written, flagged),
2 input error (nothing written).
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import shutil
import sys
import time
import zipfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import IO, Any, Iterator, Sequence

from .data import IMAGE_EXTS

log = logging.getLogger("sensei.submit")

ROOT = Path(__file__).resolve().parents[1]
BRIEF_IMAGES, BRIEF_AREAS = 26, 289          # what the brief says the hidden set holds (tripwire only)
LEVEL_VALUE = {"empty": 0.0, "half": 0.5, "full": 1.0}
SENTINEL = ".sensei_extracted"               # marks a val_images folder this tool created (safe to wipe)
MAX_UNZIPPED = 4 << 30                       # refuse zip bombs
MAX_FALLBACK_SHARE = 0.5                     # more unreadable/failed answers than this: validation fails
MAX_SHOWN = 12                               # problems listed on screen


# --------------------------------------------------------------------------- input: folder / zip / files

def _hidden(parts: Sequence[str]) -> bool:
    return any(p.startswith(".") or p.startswith("__MACOSX") for p in parts)


def _clean_path(raw: str | Path) -> Path:
    """Tolerate quotes and a stray trailing quote left by ``"C:\\folder\\"`` on a Windows command line."""
    return Path(str(raw).strip().strip('"').strip("'").strip())


def list_images(root: Path) -> list[Path]:
    """Image files under ``root`` (any depth), without macOS/hidden junk (``__MACOSX``, ``._x.jpg``)."""
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not _hidden(p.relative_to(root).parts))


def extract_zip(src: Path | IO[bytes], dest: Path, depth: int = 0) -> int:
    """Unpack the image files of a zip into ``dest`` (structure kept). Skips ``__MACOSX``, ``._*``,
    ``.DS_Store`` and everything that is not an image; refuses paths that escape ``dest``; unpacks
    zips inside the zip (two levels). Returns the number of images written."""
    n = total = 0
    with zipfile.ZipFile(src) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = [p for p in PurePosixPath(info.filename.replace("\\", "/")).parts if p not in ("", ".", "/")]
            if not parts or _hidden(parts):
                continue
            if any(p == ".." or ":" in p for p in parts):
                log.warning("zip: skipping unsafe path %r", info.filename)
                continue
            suffix = Path(parts[-1]).suffix.lower()
            total += info.file_size
            if total > MAX_UNZIPPED:
                raise ValueError("zip is unreasonably large when unpacked")
            if suffix == ".zip" and depth < 2:
                n += extract_zip(io.BytesIO(zf.read(info)), dest.joinpath(*parts[:-1], Path(parts[-1]).stem), depth + 1)
            elif suffix in IMAGE_EXTS:
                target = dest.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as fin, open(target, "wb") as fout:
                    shutil.copyfileobj(fin, fout)
                n += 1
    return n


def _fresh_images_dir(out: Path) -> Path:
    d = out / "val_images"
    if d.exists():
        if (d / SENTINEL).exists() or not any(d.iterdir()):
            shutil.rmtree(d)
        else:
            raise ValueError(f"{d} exists and was not created by this tool: choose another --out")
    d.mkdir(parents=True)
    (d / SENTINEL).write_text("created by `python -m sensei submit`; safe to delete\n", encoding="utf-8")
    return d


def prepare_images(sources: Sequence[str | Path], out: Path) -> tuple[Path, list[str]]:
    """Folder that holds the validation images, plus notes to show. A single folder with images is
    used in place; a zip, a folder of zips, or several files/folders are gathered in ``<out>/val_images``."""
    srcs = [_clean_path(s) for s in sources]
    notes: list[str] = []
    for s in srcs:
        if not s.exists():
            raise FileNotFoundError(f"not found: {s}")
    if len(srcs) == 1 and srcs[0].is_dir():
        d = srcs[0]
        if list_images(d):
            return d, notes
        zips = sorted(p for p in d.rglob("*.zip") if not _hidden(p.relative_to(d).parts))
        if not zips:
            raise ValueError(f"no image files (and no .zip) found in {d}")
        notes.append(f"no images directly in {d}: unpacking the {len(zips)} zip file(s) inside it")
        srcs = zips
    dest = _fresh_images_dir(out)
    n = 0
    for s in srcs:
        if s.is_dir():
            for p in list_images(s):
                target = dest / s.name / p.relative_to(s)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
                n += 1
        elif s.suffix.lower() == ".zip":
            try:
                n += extract_zip(s, dest)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"{s.name} is not a valid zip file ({exc})") from exc
        elif s.suffix.lower() in IMAGE_EXTS:
            shutil.copyfile(s, dest / s.name)
            n += 1
        else:
            raise ValueError(f"cannot use {s.name}: give a folder, a .zip or image files (unpack .7z/.rar first)")
    if n == 0:
        raise ValueError("no image files found in the input")
    notes.append(f"{n} image file(s) gathered in {dest}")
    return dest, notes


# --------------------------------------------------------------------------- independent validation

def _canon(key: str) -> str:
    """Identity of an image under its aliases: ``<ts>.jpg`` for ``<ts>.JPG`` / ``<cam>_<ts>.jpg``."""
    m = re.search(r"(?:^|[_-])(\d{6,})$", Path(key).stem)
    return f"{int(m.group(1))}.jpg" if m else key


def _read_strict(path: Path) -> tuple[Any, list[str]]:
    dupes: list[str] = []

    def hook(pairs):
        d: dict = {}
        for k, v in pairs:
            if k in d:
                dupes.append(k)
            d[k] = v
        return d
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook), dupes


def validate_predictions(pred_path: str | Path, planogram: dict[str, Sequence[str]],
                         image_files: Sequence[Path] = (), rows: Sequence[dict] | None = None) -> dict:
    """Check the file that will be handed in, as the scorer would read it.

    ``planogram``: camera id -> area ids (read from the planogram, not from the pipeline).
    ``image_files``: every image on disk; each must be answered. ``rows``: details rows (fallback check).
    Returns {ok, errors, warnings, images, cameras, areas, expected_areas, levels, wrong, fallback}.
    """
    errors: list[str] = []
    warnings: list[str] = []
    try:
        doc, dupes = _read_strict(Path(pred_path))
    except (OSError, ValueError) as exc:
        return {"ok": False, "errors": [f"predictions.json unreadable: {exc}"], "warnings": [], "images": 0,
                "cameras": 0, "areas": 0, "expected_areas": 0, "levels": Counter(), "wrong": 0, "fallback": 0}
    errors += [f"duplicate key {k!r} in the JSON" for k in dupes]
    if not isinstance(doc, dict) or not doc:
        return {"ok": False, "errors": errors + ["predictions.json is empty or not an object"], "warnings": [],
                "images": 0, "cameras": 0, "areas": 0, "expected_areas": 0, "levels": Counter(), "wrong": 0,
                "fallback": 0}

    levels: Counter = Counter()
    wrong = areas = expected = 0
    images: set[tuple[str, str]] = set()
    all_keys: set[str] = set()
    for cam, imgs in doc.items():
        if cam not in planogram:
            errors.append(f"camera {cam!r} is not in the planogram")
            continue
        want = set(planogram[cam])
        if not isinstance(imgs, dict) or not imgs:
            errors.append(f"camera {cam}: no images")
            continue
        counted: set[str] = set()
        for name, entries in imgs.items():
            all_keys.add(name)
            if Path(name).suffix.lower() not in IMAGE_EXTS:
                errors.append(f"{cam}/{name}: key is not an image file name")
            if not isinstance(entries, dict):
                errors.append(f"{cam}/{name}: not an object of areas")
                continue
            miss, extra = want - set(entries), set(entries) - want
            if miss:
                errors.append(f"{cam}/{name}: {len(miss)} area(s) missing, e.g. {sorted(miss)[0]}")
            if extra:
                errors.append(f"{cam}/{name}: {len(extra)} unknown area(s), e.g. {sorted(extra)[0]}")
            bad = 0
            for area_id, e in entries.items():
                lvl = e.get("stock_level") if isinstance(e, dict) else None
                val = e.get("stock_value") if isinstance(e, dict) else None
                ok = (isinstance(e, dict) and type(e.get("planogram_compliant")) is bool and lvl in LEVEL_VALUE
                      and isinstance(val, (int, float)) and not isinstance(val, bool)
                      and abs(float(val) - LEVEL_VALUE[lvl]) < 1e-9)
                if not ok:
                    bad += 1
                    if bad == 1:
                        errors.append(f"{cam}/{name}/{area_id}: invalid entry {e!r}")
            if bad > 1:
                errors.append(f"{cam}/{name}: {bad} invalid entries in total")
            c = _canon(name)
            if c not in counted:          # aliases of one image are counted once
                counted.add(c)
                images.add((cam, c))
                expected += len(want)
                areas += len(want & set(entries))
                for area_id in want & set(entries):
                    e = entries[area_id]
                    if isinstance(e, dict) and e.get("stock_level") in LEVEL_VALUE:
                        levels[e["stock_level"]] += 1
                        wrong += e.get("planogram_compliant") is False

    unanswered = [p for p in image_files if p.name not in all_keys and _canon(p.name) not in all_keys]
    if unanswered:
        errors.append(f"{len(unanswered)} image file(s) got no answer (camera not recognised?): "
                      + ", ".join(p.name for p in unanswered[:5]) + (" ..." if len(unanswered) > 5 else ""))
    fallback = sum(1 for r in rows or [] if r.get("fallback"))
    if rows and fallback:
        share = fallback / len(rows)
        (errors if share >= MAX_FALLBACK_SHARE else warnings).append(
            f"{fallback} of {len(rows)} area answers are fallbacks (unreadable pictures or a model failure)")
    if areas >= 20 and sum(1 for v in levels.values() if v) == 1:
        warnings.append(f"every area has the same stock level ({next(iter(levels))}): check the model")
    if len(images) != BRIEF_IMAGES or areas != BRIEF_AREAS:
        warnings.append(f"the brief announces {BRIEF_IMAGES} images / {BRIEF_AREAS} areas; this run has "
                        f"{len(images)} / {areas}: check that all images were handed over")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "images": len(images),
            "cameras": len({c for c, _ in images}), "areas": areas, "expected_areas": expected,
            "levels": levels, "wrong": wrong, "fallback": fallback}


# --------------------------------------------------------------------------- weights / dashboard

def _hf_cached(repo_id: str) -> bool:
    try:
        from huggingface_hub import constants  # noqa: PLC0415
        hub = Path(constants.HF_HUB_CACHE)
    except Exception:  # noqa: BLE001
        hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    snaps = hub / ("models--" + repo_id.replace("/", "--")) / "snapshots"
    return snaps.is_dir() and any(any(s.glob("*.safetensors")) or any(s.glob("*.bin")) for s in snaps.iterdir())


@contextmanager
def _offline_if_cached(repos: Sequence[str]) -> Iterator[bool]:
    """Hugging Face offline mode when every needed weight is cached: no stalls on flaky venue wifi."""
    missing = [r for r in repos if not _hf_cached(r)]
    if missing:
        log.warning("weights not in the local cache (internet needed): %s", ", ".join(missing))
        yield False
        return
    names = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
    old = {n: os.environ.get(n) for n in names}
    for n in names:
        os.environ[n] = "1"
    hub = sys.modules.get("huggingface_hub.constants")
    old_flag = getattr(hub, "HF_HUB_OFFLINE", None)
    if hub is not None:
        hub.HF_HUB_OFFLINE = True
    try:
        yield True
    finally:
        for n, v in old.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v
        if hub is not None:
            hub.HF_HUB_OFFLINE = old_flag


def _build_dashboard(details: Path, data_root: Path, out_dir: Path, detect: bool, detections: str | None) -> Path | None:
    """Staff app; never raises. Boxes are best effort: on any failure the app is rebuilt without them."""
    from .dashboard import build  # noqa: PLC0415
    if (out_dir / "data.js").exists() and (out_dir / "index.html").exists():
        shutil.rmtree(out_dir, ignore_errors=True)       # a previous build of ours: no stale crops
    for use_detect in ((True, False) if detect else (False,)):
        try:
            return build(details, data_root, out_dir, detections=detections, detect=use_detect)
        except Exception as exc:  # noqa: BLE001
            log.warning("dashboard build %s failed (%s: %s)", "with detection" if use_detect else "", type(exc).__name__, exc)
            if use_detect:
                print("WARNING: product detection failed, building the staff app without boxes.", flush=True)
    return None


# --------------------------------------------------------------------------- the run

def _banner(lines: Sequence[str]) -> None:
    bar = "=" * 70
    print("\n".join([bar, *lines, bar]), flush=True)


def run(images: Sequence[str | Path], model: str | Path = "models/real_v1_cal", out: str | Path = "submission",
        detect: bool = True, detections: str | None = None, device: str | None = None) -> int:
    """Whole validation-day flow; returns the exit code (0 passed, 1 failed validation, 2 input error)."""
    from . import pipeline  # noqa: PLC0415
    from .data import load_planogram  # noqa: PLC0415
    t0 = time.perf_counter()
    out_dir = Path(out).resolve()
    fresh = not out_dir.exists()
    out_dir.mkdir(parents=True, exist_ok=True)
    if fresh:   # the repo is public: a new output folder (store pictures, answers) ignores itself in git
        (out_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    pred_path, details_path = out_dir / "predictions.json", out_dir / "details.json"
    for stale in (pred_path, details_path):          # an old file must never pass for this run's result
        stale.unlink(missing_ok=True)
    model_dir = _clean_path(model)
    if not model_dir.is_absolute() and not (Path.cwd() / model_dir / "model.json").is_file() \
            and (ROOT / model_dir / "model.json").is_file():
        model_dir = ROOT / model_dir
    try:
        folder, notes = prepare_images(images, out_dir)
        files = list_images(folder)
        for n in notes:
            print(n, flush=True)
        print(f"{len(files)} image file(s) in {folder}", flush=True)
        sensei = pipeline.SenseiModel.load(model_dir)
        repos = [sensei.cfg.clip_model, sensei.cfg.dino_model] if sensei.cfg.backend == "deep" else []
        if detect:
            from .dashboard import OWL_MODEL  # noqa: PLC0415
            repos.append(OWL_MODEL)
        cfg = sensei.cfg.replace(device=device) if device else None
        with _offline_if_cached(repos) as offline:
            if offline:
                log.info("all weights are cached: Hugging Face offline mode")
            t1 = time.perf_counter()
            _, doc = pipeline.predict_dir(sensei, folder, pred_path, details_path, cfg)
            t2 = time.perf_counter()
            planogram = {c: [a.area_id for a in areas]
                         for c, areas in load_planogram(model_dir / "planogram.json").items()}
            rep = validate_predictions(pred_path, planogram, files, doc.get("rows"))
            _banner(["SENSEI SUBMISSION CHECK: " + ("PASSED" if rep["ok"] else "FAILED - DO NOT HAND IN YET"),
                     f" images : {rep['images']}  (brief: {BRIEF_IMAGES}; image files found: {len(files)})",
                     f" cameras: {rep['cameras']} of {len(planogram)} planogram cameras",
                     f" areas  : {rep['areas']} of {rep['expected_areas']} expected"
                     f"  (brief: {BRIEF_AREAS})",
                     " stock  : " + " | ".join(f"{k} {rep['levels'].get(k, 0)}" for k in LEVEL_VALUE),
                     f" wrong product: {rep['wrong']}",
                     f" predicted in {t2 - t1:.0f}s (heads: {'yes' if sensei.heads is not None else 'no'})"])
            for e in rep["errors"][:MAX_SHOWN]:
                print(f"ERROR:   {e}")
            if len(rep["errors"]) > MAX_SHOWN:
                print(f"ERROR:   ... and {len(rep['errors']) - MAX_SHOWN} more")
            for w in rep["warnings"]:
                print(f"WARNING: {w}")
            if rep["ok"]:
                print(f"HAND IN THIS FILE: {pred_path}", flush=True)
            else:
                print(f"predictions.json was written but is NOT valid/complete: {pred_path}", flush=True)
            print("Building the staff app" + (" (with OWLv2 product boxes, about 10 s per camera)..." if detect else "..."),
                  flush=True)
            index = _build_dashboard(details_path, folder, out_dir / "dashboard", detect, detections)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}\nNothing was written: an empty submission would score -5 per area.\n"
              "Expected: a folder or zip with <camera_id>/<unix_ts>.jpg, or flat <unix_ts>.jpg files.",
              file=sys.stderr)
        return 2
    lines = []
    if rep["ok"]:
        lines.append(f"HAND IN THIS FILE: {pred_path}")
    else:
        lines.append(f"NOT VALID - fix the errors above first: {pred_path}")
    lines.append(f"Open the staff app: {index}" if index else "Staff app: NOT built (see the warning above)")
    lines.append(f"Total time: {time.perf_counter() - t0:.0f}s")
    _banner(lines)
    return 0 if rep["ok"] else 1

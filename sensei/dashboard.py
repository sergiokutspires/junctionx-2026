"""Static staff dashboard: turns ``details.json`` into a folder that opens from ``file://``.

``build(details, data_root, out_dir, cfg)`` copies ``ui/`` (index.html, app.js, style.css), writes
``data.js`` (``window.SHELF_DATA = {...};``), downscaled camera frames (<= 1280 px wide, JPEG q80)
to ``img/frames/<cam>_<ts>.jpg`` and a perspective-corrected crop of every area to
``img/areas/<cam>_<ts>_<area>.jpg``. Only the latest frame of each camera is shown (the history of
earlier frames feeds the per-area sparkline through ``timeline``). No network, no build step.

Usage: ``python -m sensei.dashboard --details details.json --data data/raw --out dashboard/ [--zip]``
Google Colab (free, CPU is enough): ``!python -m sensei.dashboard --details details.json --data data/raw/images
--out dashboard --zip`` then ``from google.colab import files; files.download("dashboard.zip")``.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from . import data as sdata
from .config import Config

log = logging.getLogger(__name__)

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
UI_FILES = ("index.html", "app.js", "style.css")
MAX_FRAME_W = 1280          # downscaled frame width limit (px)
JPEG_QUALITY = 80
CROP_LONG_SIDE = (200, 360)  # min / max long side of an area crop (px)
LEVELS = ("empty", "half", "full")
STATUS_ORDER = ("wrong", "empty", "low", "ok")


# --------------------------------------------------------------------------- row helpers

def _status(row: dict) -> str:
    """Primary status of an area: wrong product > empty > low (half) > ok."""
    if row.get("planogram_compliant") is False:
        return "wrong"
    level = row.get("stock_level")
    if level == "empty":
        return "empty"
    if level == "half":
        return "low"
    return "ok"


def _confidence(row: dict, status: str) -> float:
    """Confidence in [0, 1] of the verdict that put the area in ``status``."""
    p_levels = row.get("p_levels")
    level = row.get("stock_level")
    p_stock = None
    if isinstance(p_levels, (list, tuple)) and len(p_levels) == 3 and level in LEVELS:
        p_stock = float(p_levels[LEVELS.index(level)])
    p_comp = row.get("p_compliant")
    if status == "wrong":
        return float(np.clip(1.0 - float(p_comp), 0.0, 1.0)) if p_comp is not None else 0.6
    if p_stock is not None:
        return float(np.clip(p_stock, 0.0, 1.0))
    if status == "ok" and p_comp is not None:
        return float(np.clip(p_comp, 0.0, 1.0))
    return 0.6


def _priority(row: dict, status: str, conf: float) -> float:
    """Sort key (higher = do sooner): wrong/empty tier 200+, low tier 100+, 0 for ok."""
    if status in ("wrong", "empty"):
        return round(200.0 + 40.0 * conf, 2)
    if status == "low":
        fill = float(row.get("fill") if row.get("fill") is not None else 0.5)
        forecast = row.get("forecast_empty_s")
        urgency = 10.0 * (1.0 - float(np.clip(fill, 0.0, 1.0)))
        if forecast is not None:
            urgency += 30.0 * (1.0 - float(np.clip(forecast / 7200.0, 0.0, 1.0)))
        return round(100.0 + urgency, 2)
    return 0.0


def _num(area_id: str) -> str:
    """Short area label: '6215_2' -> '2'."""
    return str(area_id).rsplit("_", 1)[-1]


def _names(row: dict) -> dict:
    """English / Portuguese display names of the planned product and of the likely seen product."""
    from . import products  # noqa: PLC0415 - keeps import light when only formatting

    raw = str(row.get("product_name") or "")
    parsed = products.parse_name(raw) if raw else {}
    en = row.get("english") or parsed.get("english") or raw.title() or "Product"
    pt = parsed.get("pt") or raw.title() or en
    out = {"raw": raw, "en": en, "pt": pt, "loose": row.get("loose", parsed.get("loose", True))}
    lraw = row.get("likely_product_name")
    if lraw:
        lp = products.parse_name(str(lraw))
        out["lraw"] = str(lraw)
        out["len"] = row.get("likely_english") or lp.get("english") or str(lraw).title()
        out["lpt"] = lp.get("pt") or str(lraw).title()
    return out


# --------------------------------------------------------------------------- images

def _index_images(data_root: str | Path | None, camera_ids: set[str]) -> dict[tuple[str, str], Path]:
    """(camera, image_name) -> path for every image found under ``data_root`` (any layout)."""
    if not data_root or not Path(data_root).is_dir():
        return {}
    recs = sdata.discover_images(data_root, camera_ids)
    return {(r.camera_id, r.image_name): r.path for r in recs}


def _find_image(row: dict, index: dict[tuple[str, str], Path]) -> Path | None:
    p = row.get("image_path")
    if p and Path(p).is_file():
        return Path(p)
    return index.get((str(row["camera_id"]), str(row["image_name"])))


def _save_jpeg(rgb: np.ndarray, path: Path, quality: int = JPEG_QUALITY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(path, format="JPEG", quality=quality, optimize=True)


def _save_frame(rgb: np.ndarray, path: Path, max_w: int = MAX_FRAME_W,
                quality: int = JPEG_QUALITY) -> tuple[int, int]:
    """Write the frame downscaled to <= max_w wide; returns the written (width, height)."""
    h, w = rgb.shape[:2]
    if w > max_w:
        nh = max(1, round(h * max_w / w))
        rgb = np.asarray(Image.fromarray(rgb).resize((max_w, nh), Image.LANCZOS))
        h, w = rgb.shape[:2]
    _save_jpeg(rgb, path, quality)
    return w, h


def _crop_area(rgb: np.ndarray, quad: np.ndarray, path: Path, quality: int = JPEG_QUALITY) -> bool:
    """Perspective-correct crop of one area keeping its aspect ratio. False if nothing is visible."""
    import cv2  # noqa: PLC0415 - only needed here

    q = np.asarray(quad, dtype=np.float32).reshape(4, 2)
    if sdata.visible_fraction(q, rgb.shape) < 0.05:
        return False
    top, bottom = np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3])
    left, right = np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1])
    w, h = (top + bottom) / 2.0, (left + right) / 2.0
    long_side = max(w, h)
    if long_side < 4:
        return False
    target = float(np.clip(long_side * 1.6, *CROP_LONG_SIDE))
    ow, oh = max(24, round(w * target / long_side)), max(24, round(h * target / long_side))
    dst = np.array([[0, 0], [ow - 1, 0], [ow - 1, oh - 1], [0, oh - 1]], dtype=np.float32)
    try:
        m = cv2.getPerspectiveTransform(q, dst)
        crop = cv2.warpPerspective(rgb, m, (ow, oh), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=(48, 48, 48))
    except cv2.error:
        log.warning("dashboard: could not crop quad %s", q.tolist())
        return False
    _save_jpeg(crop, path, quality)
    return True


# --------------------------------------------------------------------------- build

def _load_details(details: str | Path | dict) -> dict:
    if isinstance(details, dict):
        return details
    return json.loads(Path(details).read_text(encoding="utf-8-sig"))


def _timelines(details: dict, rows: list[dict]) -> dict[str, list[list]]:
    """area_id -> sorted [[ts, fill, level], ...]: from details['timeline'], else from the rows."""
    out: dict[str, dict[int, list]] = {}
    for area_id, pts in (details.get("timeline") or {}).items():
        for p in pts:
            if len(p) >= 3:
                out.setdefault(str(area_id), {})[int(p[0])] = [int(p[0]), round(float(p[1]), 3), str(p[2])]
    for r in rows:  # rows always contribute, so the latest frame is on the sparkline
        ts = int(r.get("timestamp", -1))
        if ts < 0 or r.get("fill") is None:
            continue
        out.setdefault(str(r["area_id"]), {}).setdefault(
            ts, [ts, round(float(r["fill"]), 3), str(r.get("stock_level", "full"))])
    return {a: [pts[t] for t in sorted(pts)] for a, pts in out.items()}


def _frame_stem(cam: str, ts: int, image_name: str) -> str:
    return f"{cam}_{ts if ts >= 0 else Path(image_name).stem}"


def build(details: str | Path | dict, data_root: str | Path | None, out_dir: str | Path,
          cfg: Config | None = None) -> Path:
    """Write the static dashboard into ``out_dir`` and return the path of its ``index.html``."""
    cfg = cfg or Config()
    max_w = min(MAX_FRAME_W, int(cfg.extra.get("dashboard_frame_width", MAX_FRAME_W)))   # spec: <= 1280 px
    quality = int(cfg.extra.get("dashboard_jpeg_quality", JPEG_QUALITY))
    d = _load_details(details)
    rows: list[dict] = list(d.get("rows") or [])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in UI_FILES:
        src = UI_DIR / name
        if not src.is_file():
            raise FileNotFoundError(f"ui asset missing: {src}")
        shutil.copyfile(src, out / name)

    cam_ids = {str(r["camera_id"]) for r in rows}
    index = _index_images(data_root, cam_ids)
    timelines = _timelines(d, rows)

    # latest READABLE image of every camera (fallback rows = unreadable picture: guessed answers
    # that no camera saw, so they never become counters or tasks)
    latest: dict[str, tuple[int, str]] = {}
    for r in rows:
        if r.get("fallback"):
            continue
        key = (int(r.get("timestamp", -1)), str(r["image_name"]))
        c = str(r["camera_id"])
        if c not in latest or key > latest[c]:
            latest[c] = key
    cur = [r for r in rows if not r.get("fallback")
           and (int(r.get("timestamp", -1)), str(r["image_name"])) == latest[str(r["camera_id"])]]
    unreadable = {}
    for r in rows:
        c = str(r["camera_id"])
        if r.get("fallback") and c not in latest:
            unreadable[c] = max(unreadable.get(c, -1), int(r.get("timestamp", -1)))
    for c, ts in unreadable.items():
        log.warning("dashboard: camera %s has no readable picture: shown as not checked", c)
    product_areas: dict[str, list[str]] = {}
    for r in cur:
        product_areas.setdefault(str(r["product_id"]), []).append(str(r["area_id"]))

    cameras: list[dict] = []
    areas: list[dict] = []
    for cam in sorted(latest, key=lambda c: (len(c), c)):
        ts, image_name = latest[cam]
        cam_rows = [r for r in cur if str(r["camera_id"]) == cam]
        stem = _frame_stem(cam, ts, image_name)
        entry: dict[str, Any] = {"id": cam, "image": image_name, "ts": ts, "frame": None,
                                 "w": 0, "h": 0, "ow": 0, "oh": 0}
        rgb = None
        src_path = _find_image(cam_rows[0], index)
        if src_path is not None:
            try:
                rgb = sdata.load_image(src_path)
            except (ValueError, OSError) as exc:
                log.warning("dashboard: cannot read %s (%s); camera %s shown without picture",
                            src_path, exc, cam)
        else:
            log.warning("dashboard: image %s of camera %s not found under %s", image_name, cam, data_root)
        scale = 1.0
        if rgb is not None:
            entry["oh"], entry["ow"] = rgb.shape[:2]
            entry["w"], entry["h"] = _save_frame(rgb, out / "img" / "frames" / f"{stem}.jpg", max_w, quality)
            entry["frame"] = f"img/frames/{stem}.jpg"
            scale = entry["w"] / entry["ow"]
        cameras.append(entry)

        for r in sorted(cam_rows, key=lambda r: _natural(str(r["area_id"]))):
            status = _status(r)
            conf = _confidence(r, status)
            area_id = str(r["area_id"])
            quad = r.get("quad")
            crop = None
            if quad is not None and rgb is not None:
                rel = f"img/areas/{stem}_{area_id}.jpg"
                if _crop_area(rgb, np.asarray(quad, dtype=np.float32), out / rel, quality):
                    crop = rel
            a = {"id": area_id, "cam": cam, "num": _num(area_id), "pid": str(r["product_id"]),
                 **_names(r), "status": status, "level": r.get("stock_level", "full"),
                 "fill": _round(r.get("fill")), "pl": [round(float(x), 3) for x in r.get("p_levels") or []],
                 "pc": _round(r.get("p_compliant")), "conf": round(conf, 3),
                 "pri": _priority(r, status, conf), "vis": _round(r.get("visible", 1.0)),
                 "fc": (int(r["forecast_empty_s"]) if r.get("forecast_empty_s") is not None else None),
                 "quad": ([[round(float(x) * scale, 1), round(float(y) * scale, 1)] for x, y in quad]
                          if quad is not None and rgb is not None else None),
                 "crop": crop, "tl": timelines.get(area_id, [])}
            if r.get("likely_product_id") is not None:
                a["lpid"] = str(r["likely_product_id"])
                a["home"] = [x for x in product_areas.get(a["lpid"], []) if x != area_id][:3]
            areas.append(a)

    for cam in sorted(unreadable, key=lambda c: (len(c), c)):
        cameras.append({"id": cam, "image": None, "ts": unreadable[cam], "frame": None, "w": 0, "h": 0,
                        "ow": 0, "oh": 0, "unreadable": True})
    counts = {s: sum(1 for a in areas if a["status"] == s) for s in STATUS_ORDER}
    payload = {
        "version": 1,
        "section": d.get("section", ""),
        "generated_at": d.get("generated_at"),
        "backend": d.get("backend", ""),
        "timezone": "Europe/Lisbon",
        "snapshot_ts": max((c["ts"] for c in cameras if not c.get("unreadable")), default=None),
        "oldest_ts": min((c["ts"] for c in cameras if not c.get("unreadable")), default=None),
        "counts": counts,
        "cameras": cameras,
        "areas": areas,
    }
    text = "window.SHELF_DATA = " + json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + ";\n"
    (out / "data.js").write_text(text, encoding="utf-8")
    log.info("dashboard: %d cameras, %d areas %s -> %s", len(cameras), len(areas), counts, out / "index.html")
    return out / "index.html"


def make_zip(out_dir: str | Path) -> Path:
    """Zip a built dashboard folder next to itself (``<out_dir>.zip``), e.g. to download from Colab."""
    out = Path(out_dir)
    return Path(shutil.make_archive(str(out), "zip", root_dir=out))


def _round(x: Any, nd: int = 3) -> float | None:
    return None if x is None else round(float(x), nd)


def _natural(area_id: str) -> tuple:
    """Sort key keeping '6215_2' before '6215_10'."""
    cam, _, num = area_id.rpartition("_")
    return (cam, int(num) if num.isdigit() else 0, area_id)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build the static staff dashboard from details.json")
    ap.add_argument("--details", required=True)
    ap.add_argument("--data", default=None, help="image root (any layout) used when image_path is missing")
    ap.add_argument("--out", required=True)
    ap.add_argument("--zip", action="store_true", help="also write <out>.zip (handy on Colab)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    index = build(args.details, args.data, args.out)
    print(index)
    if args.zip:
        print(make_zip(args.out))


if __name__ == "__main__":
    main()

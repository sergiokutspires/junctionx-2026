"""Optional calibration with a few self-labelled crops (SPEC sections 2c and 6).

Three parts, all usable without the rest of the pipeline:

* ``export_sheets``  : contact sheets + ``manifest.json/.js`` + crops + ``labeler.html`` for
  labelling by eye. ``labels_from_tiles`` turns tile labels back into annotations format.
* ``fit_heads``      : cost-sensitive heads on [fill, fill^2, visible, PCA(CLIP), PCA(DINO cls),
  handcrafted, patch-cluster band histograms, per-band fills (stock only)] (multinomial
  logistic regression for the stock level, logistic regression for compliance).
  ``Heads.save`` / ``Heads.load`` use json + npz (no pickle).
  With ``HeadParams.memory`` (default) a second stock head also sees a per-area memory: the labelled crops
  of the same area from earlier frames (``memory_features``), stored with the heads as npz.
* ``cross_validate`` : leave-one-camera-out and time-blocked scores computed with ``scoring.score``.

Labels are always in annotations format: ``{camera: {image_name: {area_id: {...}}}}``.
Optional ``zs_stock`` / ``zs_comp`` arguments let the heads stack on top of the unsupervised
outputs (stock level posterior (N,3), p_compliant (N,)); pass the same arrays at predict time.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import scoring
from .config import Config
from .data import Area, discover_images, inset_quad, load_image
from .features import CropFeatures
from .products import parse_name

log = logging.getLogger(__name__)

LEVEL_NAMES = ("empty", "half", "full")
LEVEL_INDEX = {n: i for i, n in enumerate(LEVEL_NAMES)}
LEVEL_VALUES = (0.0, 0.5, 1.0)
EPS = 1e-4
LABELER_SRC = Path(__file__).resolve().parents[1] / "labeler" / "labeler.html"


# =========================================================================== labels

def level_index(entry: dict) -> int:
    """0/1/2 for an annotation entry (stock_value wins over stock_level)."""
    v = entry.get("stock_value")
    if v is not None:
        return int(round(float(v) * 2))
    return LEVEL_INDEX[entry["stock_level"]]


def load_labels(*paths: str | Path) -> dict:
    """Merge annotation files (later files win per area)."""
    out: dict = {}
    for p in paths:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        for cam, images in doc.items():
            for image, areas in images.items():
                out.setdefault(cam, {}).setdefault(image, {}).update(areas)
    return out


def label_arrays(feats: CropFeatures, labels: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rows of ``feats`` that have a label -> (row indices, stock class 0/1/2, compliant bool)."""
    idx, ys, yc = [], [], []
    for i, (cam, image, area) in enumerate(feats.keys):
        e = labels.get(cam, {}).get(image, {}).get(area)
        if e is None:
            continue
        idx.append(i)
        ys.append(level_index(e))
        yc.append(bool(e["planogram_compliant"]))
    return np.array(idx, dtype=np.int64), np.array(ys, dtype=np.int64), np.array(yc, dtype=bool)


def predictions_from_probs(keys: Sequence[tuple[str, str, str]], p_stock: np.ndarray,
                           p_comp: np.ndarray) -> dict:
    """Submission-format predictions: ``best_stock`` on the posterior, 0.5 threshold on compliance."""
    out: dict = {}
    for (cam, image, area), p, pc in zip(keys, p_stock, p_comp):
        value, _ = scoring.best_stock(*[float(x) for x in p])
        out.setdefault(cam, {}).setdefault(image, {})[area] = scoring.make_entry(
            scoring.best_compliance(float(pc)), value)
    return out


# =========================================================================== sheets

_FONTS: dict[tuple[int, bool], ImageFont.ImageFont] = {}


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """A TrueType font that exists on Windows, Linux and Colab (falls back to Pillow's default)."""
    key = (size, bold)
    if key not in _FONTS:
        names = (("arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf") if bold
                 else ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"))
        font = None
        for name in names:
            try:
                font = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size)
            except TypeError:  # Pillow < 10.1
                font = ImageFont.load_default()
        _FONTS[key] = font
    return _FONTS[key]


def _fit_text(text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    """Shorten ``text`` with an ellipsis so it fits ``max_w`` pixels."""
    if font.getlength(text) <= max_w:
        return text
    while len(text) > 1 and font.getlength(text + "...") > max_w:
        text = text[:-1]
    return text + "..."


def _rect_crop(image: np.ndarray, quad: np.ndarray, inset: float, long_side: int) -> np.ndarray:
    """Warp the quad to an upright rectangle with the quad's own aspect ratio (outside = black)."""
    q = inset_quad(np.asarray(quad, np.float32), inset) if inset > 0 else np.asarray(quad, np.float32)
    w = 0.5 * (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3]))
    h = 0.5 * (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1]))
    if w < 2 or h < 2:
        return np.zeros((long_side // 2, long_side, 3), np.uint8)
    s = long_side / max(w, h)
    ow, oh = max(2, int(round(w * s))), max(2, int(round(h * s)))
    dst = np.array([[0, 0], [ow - 1, 0], [ow - 1, oh - 1], [0, oh - 1]], np.float32)
    m = cv2.getPerspectiveTransform(q, dst)
    return cv2.warpPerspective(image, m, (ow, oh), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _context_view(image: np.ndarray, quad: np.ndarray, width: int, margin: float = 0.6) -> np.ndarray:
    """Part of the frame around the quad (bbox + margin) with the quad outline drawn on top."""
    h, w = image.shape[:2]
    q = np.asarray(quad, np.float32)
    x0, y0 = q.min(axis=0)
    x1, y1 = q.max(axis=0)
    mx, my = max(30.0, margin * (x1 - x0)), max(30.0, margin * (y1 - y0))
    rx0, ry0 = int(max(0, np.floor(x0 - mx))), int(max(0, np.floor(y0 - my)))
    rx1, ry1 = int(min(w, np.ceil(x1 + mx))), int(min(h, np.ceil(y1 + my)))
    if rx1 - rx0 < 4 or ry1 - ry0 < 4:  # quad entirely outside the frame: show the whole frame
        rx0, ry0, rx1, ry1 = 0, 0, w, h
    region = image[ry0:ry1, rx0:rx1]
    s = width / region.shape[1]
    view = cv2.resize(region, (width, max(2, int(round(region.shape[0] * s)))),
                      interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)
    pts = ((q - [rx0, ry0]) * s).round().astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(view, [pts], True, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.polylines(view, [pts], True, (255, 235, 0), 2, cv2.LINE_AA)
    return view


def _paste_fit(canvas: Image.Image, arr: np.ndarray, box: tuple[int, int, int, int]) -> None:
    """Paste ``arr`` into ``box`` (x, y, w, h), keeping the aspect ratio, centred."""
    x, y, bw, bh = box
    im = Image.fromarray(arr)
    s = min(bw / im.width, bh / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    canvas.paste(im, (x + (bw - im.width) // 2, y + (bh - im.height) // 2))


def _hhmm(ts: int) -> str:
    """Store-local time (Europe/Lisbon; UTC if tz data is missing) as HH:MM, '' for unknown."""
    if ts < 0:
        return ""
    when = datetime.fromtimestamp(ts, timezone.utc)
    try:
        from zoneinfo import ZoneInfo  # noqa: PLC0415
        when = when.astimezone(ZoneInfo("Europe/Lisbon"))
    except Exception:  # noqa: BLE001 - tzdata can be missing on Windows
        pass
    return when.strftime("%H:%M")


def _draw_tile(tile: dict, crop: np.ndarray, ctx: np.ndarray, w: int, h: int) -> Image.Image:
    """One 'w x h' tile: header (big id, area, product EN + PT) and crop + context side by side."""
    img = Image.new("RGB", (w, h), (28, 29, 34))
    d = ImageDraw.Draw(img)
    head_h = 66
    d.rectangle([0, 0, w, head_h], fill=(12, 12, 16))
    d.text((10, 8), f"{tile['tile']:03d}", font=_font(48, True), fill=(255, 214, 10))
    x = 128
    top = f"{tile['area_id']}  {_hhmm(tile['timestamp'])}"
    d.text((x, 5), _fit_text(top, _font(20, True), w - x - 8), font=_font(20, True), fill=(255, 255, 255))
    kind = "loose" if tile.get("loose") else "packaged" if tile.get("packaged") else ""
    en = f"{tile['english']}" + (f" ({kind})" if kind else "")
    d.text((x, 28), _fit_text(en, _font(20, True), w - x - 8), font=_font(20, True), fill=(120, 230, 150))
    d.text((x, 50), _fit_text(tile["product_name"], _font(13), w - x - 8), font=_font(13), fill=(170, 175, 185))
    pad, body_h = 6, h - head_h - 12
    half = (w - 3 * pad) // 2
    _paste_fit(img, crop, (pad, head_h + 6, half, body_h))
    _paste_fit(img, ctx, (2 * pad + half, head_h + 6, half, body_h))
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 72, 82), width=2)
    return img


def _select(keys: list, n: int | None, fill: np.ndarray | None, seed: int) -> list[int]:
    """Row indices to label: all, or n rows stratified by fill (random inside each stratum)."""
    total = len(keys)
    if n is None or n >= total:
        return list(range(total))
    rng = np.random.default_rng(seed)
    if fill is not None and len(fill) == total:
        order = np.argsort(np.asarray(fill, np.float64), kind="stable")
        chunks = np.array_split(order, n)
        return [int(rng.choice(c)) for c in chunks if len(c)]
    return sorted(int(i) for i in rng.choice(total, size=n, replace=False))


def export_sheets(feats_or_keys: CropFeatures | Sequence[tuple[str, str, str]], data_root: str | Path,
                  areas_by_cam: dict[str, list[Area]], out_dir: str | Path, cfg: Config,
                  n: int | None = None, fill: np.ndarray | None = None, seed: int | None = None,
                  per_sheet: int = 12, cols: int = 3, tile_w: int = 533, tile_h: int = 270,
                  crop_long_side: int = 360, context_w: int = 560) -> dict:
    """Write the labelling kit into ``out_dir`` and return the manifest dict.

    ``feats_or_keys`` is a CropFeatures (its ``image_paths`` locate the images) or a list of
    ``(camera_id, image_name, area_id)``. ``n`` rows are sampled, stratified by ``fill`` when
    given (rows must align with the keys), else at random. Files written:
    ``sheets/sheet_###.jpg`` (``per_sheet`` tiles, ``cols`` columns, <= 1600 px wide),
    ``crops/t####.jpg`` + ``crops/t####_ctx.jpg``, ``manifest.json``, ``manifest.js`` and a copy of
    ``labeler/labeler.html``.
    """
    out = Path(out_dir)
    (out / "sheets").mkdir(parents=True, exist_ok=True)
    (out / "crops").mkdir(parents=True, exist_ok=True)
    seed = cfg.seed if seed is None else seed
    if isinstance(feats_or_keys, CropFeatures):
        keys = list(feats_or_keys.keys)
        paths = list(feats_or_keys.image_paths) or [None] * len(keys)
    else:
        keys = [tuple(k) for k in feats_or_keys]
        paths = [None] * len(keys)
    fill_arr = None if fill is None else np.asarray(fill, np.float64)
    chosen = _select(keys, n, fill_arr, seed)

    area_by_id = {a.area_id: a for areas in areas_by_cam.values() for a in areas}
    located: dict[tuple[str, str], str] = {}
    for i in chosen:
        if paths[i] and Path(paths[i]).is_file():
            located[keys[i][:2]] = str(paths[i])
    missing = {keys[i][:2] for i in chosen} - set(located)
    if missing:
        cams = sorted({c for c, _ in missing})
        for rec in discover_images(data_root, cams):
            if (rec.camera_id, rec.image_name) in missing:
                located[(rec.camera_id, rec.image_name)] = str(rec.path)

    # natural reading order: camera, time, area number (tiles of one frame stay together)
    def sort_key(i: int):
        cam, image, area = keys[i]
        stem = Path(image).stem
        return (cam, int(stem) if stem.isdigit() else 0, image, area)

    chosen.sort(key=sort_key)
    tiles: list[dict] = []
    imgs_cache: tuple[tuple[str, str], np.ndarray] | None = None
    for i in chosen:
        cam, image, area_id = keys[i]
        area = area_by_id.get(area_id)
        path = located.get((cam, image))
        if area is None or path is None:
            log.warning("sheet: skipping %s/%s/%s (area or image not found)", cam, image, area_id)
            continue
        if imgs_cache is None or imgs_cache[0] != (cam, image):
            try:
                imgs_cache = ((cam, image), load_image(path))
            except (OSError, ValueError) as exc:
                log.warning("sheet: cannot read %s (%s)", path, exc)
                imgs_cache = ((cam, image), None)
        frame = imgs_cache[1]
        if frame is None:
            continue
        tid = len(tiles) + 1
        info = parse_name(area.product_name)
        stem = Path(image).stem
        ts = int(stem) if stem.isdigit() else -1
        crop = _rect_crop(frame, area.quad, cfg.inset, crop_long_side)
        ctx = _context_view(frame, area.quad, context_w)
        crop_rel, ctx_rel = f"crops/t{tid:04d}.jpg", f"crops/t{tid:04d}_ctx.jpg"
        Image.fromarray(crop).save(out / crop_rel, quality=90)
        Image.fromarray(ctx).save(out / ctx_rel, quality=88)
        h, w = frame.shape[:2]
        vis = float(feats_or_keys.visible[i]) if isinstance(feats_or_keys, CropFeatures) else None
        tiles.append({
            "tile": tid, "sheet": (tid - 1) // per_sheet + 1, "camera": cam, "image_name": image,
            "area_id": area_id, "timestamp": ts, "product_id": area.product_id,
            "product_name": area.product_name, "english": info["english"], "pt": info.get("pt", area.product_name),
            "loose": bool(info["loose"]), "packaged": bool(info["packaged"]),
            "crop": crop_rel, "context": ctx_rel, "visible": None if vis is None else round(vis, 3),
            "fill": None if fill_arr is None else round(float(fill_arr[i]), 3),
            "_crop": crop, "_ctx": ctx, "_frame": (w, h)})

    rows = -(-per_sheet // cols)
    sheets = []
    for s in range(0, len(tiles), per_sheet):
        chunk = tiles[s:s + per_sheet]
        sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), (10, 10, 12))
        for j, t in enumerate(chunk):
            sheet.paste(_draw_tile(t, t["_crop"], t["_ctx"], tile_w, tile_h),
                        ((j % cols) * tile_w, (j // cols) * tile_h))
        name = f"sheets/sheet_{s // per_sheet + 1:03d}.jpg"
        sheet.save(out / name, quality=88)
        sheets.append(name)
    for t in tiles:
        t.pop("_crop"), t.pop("_ctx"), t.pop("_frame")

    ident = hashlib.sha1("|".join(f"{t['camera']}/{t['image_name']}/{t['area_id']}" for t in tiles).encode())
    manifest = {"version": 1, "id": ident.hexdigest()[:10], "created": int(time.time()),
                "n_tiles": len(tiles), "per_sheet": per_sheet, "cols": cols, "sheets": sheets,
                "levels": list(LEVEL_NAMES), "tiles": tiles}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "manifest.js").write_text("window.MANIFEST = " + json.dumps(manifest, ensure_ascii=True) + ";\n",
                                     encoding="utf-8")
    if LABELER_SRC.is_file():
        shutil.copyfile(LABELER_SRC, out / "labeler.html")
    else:
        log.warning("labeler page not found at %s", LABELER_SRC)
    log.info("labeling kit: %d tiles, %d sheets -> %s", len(tiles), len(sheets), out)
    return manifest


def _tile_entry(value) -> tuple[int | None, bool]:
    """(level index or None, wrong-product flag) from the accepted tile-label spellings."""
    wrong = False
    if isinstance(value, dict):
        if "wrong" in value:
            wrong = bool(value["wrong"])
        elif "planogram_compliant" in value:
            wrong = not bool(value["planogram_compliant"])
        elif "compliant" in value:
            wrong = not bool(value["compliant"])
        for k in ("level", "stock_level", "stock", "stock_value"):
            if value.get(k) is not None:
                value = value[k]
                break
        else:
            return None, wrong
    if isinstance(value, str):
        return LEVEL_INDEX.get(value.strip().lower()), wrong
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if v in (0.0, 0.5, 1.0):
            return int(round(v * 2)), wrong
    return None, wrong


def labels_from_tiles(manifest: dict | str | Path, tile_labels: dict) -> dict:
    """Tile labels -> annotations format.

    ``tile_labels`` maps tile id (int or str) to ``"empty"|"half"|"full"`` or to a dict like
    ``{"level": "half", "wrong": true}``. Tiles without a stock level are skipped (warning).
    """
    if not isinstance(manifest, dict):
        manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
    by_id = {int(t["tile"]): t for t in manifest["tiles"]}
    out: dict = {}
    skipped = 0
    for tid, value in tile_labels.items():
        tile = by_id.get(int(tid))
        level, wrong = _tile_entry(value)
        if tile is None or level is None:
            skipped += 1
            continue
        out.setdefault(tile["camera"], {}).setdefault(tile["image_name"], {})[tile["area_id"]] = {
            "planogram_compliant": not wrong, "stock_level": LEVEL_NAMES[level],
            "stock_value": LEVEL_VALUES[level]}
    if skipped:
        log.warning("labels_from_tiles: %d tile labels skipped (unknown tile or no stock level)", skipped)
    return out


# =========================================================================== heads

@dataclass
class HeadParams:
    """Knobs of the heads (stored with them). Defaults were chosen by cross-validation on the
    teacher labels (see ``cross_validate``): big-ish PCA blocks, strong L2, no handcrafted block
    when CLIP/DINO exist (it lets the head memorise crate colours of other cameras)."""

    n_clip: int = 128           # PCA dims of the CLIP embedding (0 = unused; capped at n_labelled / 4)
    n_dino: int = 128           # PCA dims of the DINOv2 cls embedding (same cap)
    use_hand: bool = False      # the 135 handcrafted features (always on when no CLIP/DINO is present)
    code_bands: int = 2         # horizontal bands of the patch-cluster histogram (0 = unused; needs patch_codes)
    w_small: float = 1.0        # penalty weight of [fill, fill^2, visible] (> 1 = lighter L2 on them)
    w_zs: float = 4.0           # same for the unsupervised inputs (zs_stock / zs_comp)
    w_codes: float = 1.0        # same for the patch-cluster histogram
    fill_bands: int = 4         # stock head: fill (mean patch productness) of this many row bands and
    #                             as many column bands (depletion starts at one side of the crate;
    #                             0 = unused; needs patch_codes and the coder's productness)
    w_fill_bands: float = 4.0   # penalty weight of those band fills
    c_stock: float = 0.03       # inverse L2 strength of the stock model
    c_comp: float = 10.0        # same for compliance (few features, so nearly unregularised)
    stock_class_weight: str | None = None   # None keeps probabilities calibrated for best_stock
    comp_class_weight: str | None = None    # "balanced" over-flags: errors cost the same both ways
    comp_features: str = "zs"   # "zs": [fill, visible, unsupervised p_compliant]; "all": every block
    min_class: int = 5          # compliance falls back to a constant prior below this many examples
    prior_strength: float = 10.0  # pseudo-counts of cfg.compliance_prior in that constant prior
    comp_head: bool = False     # False: compliance = the unsupervised p_compliant unchanged when given
    #                             (the fitted head scored slightly lower in camera and time CV)
    late_shift: bool = True     # frames after a camera's last labelled frame: prior shift of the stock
    #                             posterior towards the label mix of the last labelled frames (stock
    #                             drops late in the day; the hidden val frames are later than all labels)
    carry_tau: float = 0.6      # carry a non-compliant label forward when DINO cos(crop, labelled crop) >= this
    carry_p: float = 0.05       # p_compliant given to a carried non-compliant area
    # per-area memory (the cameras are fixed, so later frames show the same areas): the labelled crops are
    # kept with their labels; a second stock head adds, for every crop, the similarity-weighted label mix of
    # the most similar labelled crops of the SAME area from EARLIER frames (one block per embedding) and the
    # best similarity. Rows whose area has no earlier labelled crop (unknown area, new camera, first frame)
    # use the plain stock head. Labels v2, last-2-frames / last-frame folds: 1.322 -> 1.411 / 1.401 -> 1.480.
    memory: bool = True
    mem_embeddings: tuple = ("codes", "hand")   # "codes" = centred patch-cluster histogram, "hand" = centred
    #                                             handcrafted colour features (each L2-normalised)
    mem_tau: float = 0.01       # softmax temperature over cosine similarities (0.01 ~ nearest neighbour)
    mem_alpha: float = 0.3      # pseudo-count weight of the label prior in the neighbour label mix
    mem_w: float = 1.0          # penalty weight of the memory columns (> 1 = lighter L2)
    mem_min_rows: int = 30      # fewer labelled rows with an earlier labelled frame: no memory head
    mem_skips: tuple = (0, 1)   # training copies whose memory drops the latest k earlier frames, so the head
    #                             also learns gaps of 2 frames (memory alone, (0,), over-trusted 3-4 h old labels)
    mem_last: bool = False      # add the area's last labelled level (one-hot) and the hours since it (tested:
    #                             +0.003 / +0.000 on the last-2 / last-frame folds, below the +0.01 bar)


def _pca_fit(x: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    mean = x.mean(axis=0)
    k = max(1, min(k, x.shape[0] - 1, x.shape[1]))
    _, _, vt = np.linalg.svd(x - mean, full_matrices=False)
    return mean.astype(np.float32), vt[:k].astype(np.float32)


def code_histograms(codes: np.ndarray, n_codes: int, bands: int) -> np.ndarray:
    """Bag-of-clusters per horizontal band: (N, bands * n_codes), each band sums to 1 over its visible patches."""
    n, cells = codes.shape
    g = int(round(cells ** 0.5))
    grid = codes.reshape(n, g, g).astype(np.int64)
    out = np.zeros((n, bands, n_codes), np.float32)
    edges = np.linspace(0, g, bands + 1).round().astype(int)
    for b in range(bands):
        part = grid[:, edges[b]:edges[b + 1]].reshape(n, -1)
        for k in range(n_codes):
            out[:, b, k] = (part == k).sum(axis=1)
        out[:, b] /= np.maximum((part >= 0).sum(axis=1, keepdims=True), 1)
    return out.reshape(n, -1)


def band_fills(codes: np.ndarray, productness: np.ndarray, bands: int) -> np.ndarray:
    """(N, 2 * bands): mean productness of the visible patches (code >= 0) in each horizontal band
    (top to bottom) then each vertical band (left to right). A band with nothing visible gets the
    mean of the crop's other bands (0.5 when nothing is visible at all)."""
    codes = np.asarray(codes)
    prod = np.asarray(productness, np.float64)
    n, cells = codes.shape
    g = int(round(cells ** 0.5))
    grid = codes.reshape(n, g, g)
    edges = np.linspace(0, g, bands + 1).round().astype(int)
    out = np.zeros((n, 2 * bands))
    for ax, gr in enumerate((grid, grid.transpose(0, 2, 1))):
        for b in range(bands):
            part = gr[:, edges[b]:edges[b + 1]].reshape(n, -1)
            vis = part >= 0
            cnt = vis.sum(axis=1)
            tot = (prod[np.where(vis, part, 0)] * vis).sum(axis=1)
            out[:, ax * bands + b] = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
    with warnings.catch_warnings():   # nanmean warns on all-NaN rows
        warnings.simplefilter("ignore", RuntimeWarning)
        fallback = np.nanmean(out, axis=1, keepdims=True)
    fallback = np.where(np.isfinite(fallback), fallback, 0.5)
    return np.where(np.isfinite(out), out, fallback)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, np.float64), 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def _zs_stock_cols(zs: np.ndarray) -> np.ndarray:
    lp = np.log(np.clip(np.asarray(zs, np.float64), 1e-3, 1.0))
    return np.stack([lp[:, 1] - lp[:, 0], lp[:, 2] - lp[:, 1]], axis=1)


def _fit_lr(x: np.ndarray, w: np.ndarray, y: np.ndarray, c: float, class_weight: str | None, seed: int) -> dict:
    """Standardise (columns scaled up by ``w`` = lighter penalty) + L2 logistic regression;
    returns plain arrays (no sklearn object)."""
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    scale = scale / w
    lr = LogisticRegression(C=c, class_weight=class_weight, max_iter=3000, random_state=seed)
    lr.fit((x - mean) / scale, y)
    return {"mean": mean.astype(np.float32), "scale": scale.astype(np.float32),
            "coef": lr.coef_.astype(np.float32), "intercept": lr.intercept_.astype(np.float32),
            "classes": [int(v) for v in lr.classes_]}


def _apply_lr(m: dict, x: np.ndarray) -> np.ndarray:
    z = ((x - m["mean"]) / m["scale"]) @ m["coef"].T + m["intercept"]
    if z.shape[1] == 1:  # binary: probability of classes[1]
        p1 = 1.0 / (1.0 + np.exp(-z[:, 0]))
        return np.stack([1 - p1, p1], axis=1)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def _lr_proba3(m: dict, x: np.ndarray) -> np.ndarray:
    """(N,3) posterior of a stock LR whose ``classes`` may miss a level (missing level = EPS)."""
    q = _apply_lr(m, x)
    p = np.full((len(x), 3), EPS)
    for col, c in enumerate(m["classes"]):
        p[:, c] = q[:, col]
    return p


# =========================================================================== per-area memory

MEM_CODE_BANDS = 2


def _l2(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float32)
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _raw_memory_embedding(feats: CropFeatures, name: str, n_codes: int) -> np.ndarray | None:
    """Uncentred embedding ``name`` of every row, or None when the features lack it."""
    if name == "codes":
        if feats.patch_codes is None or n_codes <= 0:
            return None
        return code_histograms(feats.patch_codes, n_codes, MEM_CODE_BANDS)
    if name == "hand":
        return None if feats.hand is None or not np.size(feats.hand) else np.asarray(feats.hand, np.float32)
    if name == "dino":
        return None if feats.dino_cls is None else np.asarray(feats.dino_cls, np.float32)
    if name == "clip":
        return None if feats.clip is None else np.asarray(feats.clip, np.float32)
    raise ValueError(f"unknown memory embedding {name!r}")


def build_memory(feats: CropFeatures, ys: np.ndarray, yc: np.ndarray, names: Sequence[str],
                 n_codes: int) -> dict | None:
    """Memory table of labelled crops: per row area, time, level, compliance and one centred, L2-normalised
    embedding per name (the centre is stored to embed new crops the same way). None if no embedding exists."""
    emb, center = {}, {}
    for name in names:
        raw = _raw_memory_embedding(feats, name, n_codes)
        if raw is None:
            continue
        center[name] = raw.mean(axis=0).astype(np.float32)
        emb[name] = _l2(raw - center[name])
    if not emb or not len(feats):
        return None
    return {"names": list(emb), "n_codes": int(n_codes), "areas": list(feats.area_ids),
            "ts": np.asarray(feats.timestamps, np.int64), "ys": np.asarray(ys, np.int64),
            "yc": np.asarray(yc, bool), "emb": emb, "center": center}


def memory_features(memory: dict, feats: CropFeatures, prior: Sequence[float], tau: float = 0.01,
                    alpha: float = 0.3, skip: int = 0, last: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """(F, has): per row of ``feats``, features from the labelled crops of the same area taken strictly
    EARLIER (any time when the row's timestamp is unknown, < 0). Per embedding: the two log-ratios of the
    similarity-weighted level mix (softmax of cosine / ``tau``, smoothed with ``alpha`` x ``prior``) and the
    best cosine; with ``last`` also the level of the latest labelled frame (one-hot) and the hours since. ``has`` is
    False (and the row all zeros) where no such crop exists or the input lacks an embedding. ``skip`` > 0
    also drops the area's ``skip`` latest earlier labelled frames (training rows that mimic a longer gap)."""
    names = list(memory["names"])
    width = 3 * len(names) + (4 if last else 0)
    n = len(feats)
    F = np.zeros((n, width), np.float64)
    has = np.zeros(n, bool)
    if not n:
        return F, has
    q_emb = {}
    for name in names:
        raw = _raw_memory_embedding(feats, name, int(memory["n_codes"]))
        if raw is None or raw.shape[1] != memory["emb"][name].shape[1]:
            log.warning("memory: the input has no %r embedding: plain stock head for these crops", name)
            return F, has
        q_emb[name] = _l2(raw - memory["center"][name])
    prior = np.asarray(prior, np.float64)
    m_ts, m_ys = np.asarray(memory["ts"], np.int64), np.asarray(memory["ys"], np.int64)
    rows_by_area: dict[str, list[int]] = {}
    for j, a in enumerate(memory["areas"]):
        rows_by_area.setdefault(a, []).append(j)
    q_ts = np.asarray(feats.timestamps, np.int64)
    onehot = np.eye(3)
    for i, a in enumerate(feats.area_ids):
        mem = rows_by_area.get(a)
        if not mem:
            continue
        mem = np.asarray(mem)
        if q_ts[i] >= 0:
            mem = mem[m_ts[mem] < q_ts[i]]
        if skip > 0 and len(mem):
            frames = np.unique(m_ts[mem])                       # ascending
            mem = mem[m_ts[mem] < frames[-skip]] if len(frames) > skip else mem[:0]
        if not len(mem):
            continue
        has[i] = True
        oh = onehot[m_ys[mem]]
        for k, name in enumerate(names):
            s = memory["emb"][name][mem] @ q_emb[name][i]
            w = np.exp((s - s.max()) / tau)
            mix = np.clip((w @ oh / w.sum() + alpha * prior) / (1.0 + alpha), 1e-6, None)
            F[i, 3 * k:3 * k + 3] = np.log(mix[1] / mix[0]), np.log(mix[2] / mix[1]), float(s.max())
        if last:
            j = mem[np.argmax(m_ts[mem])]
            F[i, 3 * len(names):3 * len(names) + 3] = onehot[m_ys[j]]
            F[i, -1] = (q_ts[i] - m_ts[j]) / 3600.0 if q_ts[i] >= 0 else 1.0
    return F, has


class Heads:
    """Fitted stock and compliance heads (see module docstring). Build with ``fit_heads``."""

    VERSION = 2   # 2: optional per-area memory (memory table + mem_stock head); version-1 heads load unchanged

    def __init__(self, params: HeadParams, layout: dict, pca: dict, stock: dict, comp: dict,
                 carry: dict | None = None, memory: dict | None = None, mem_stock: dict | None = None):
        self.params, self.layout, self.pca, self.stock, self.comp = params, layout, pca, stock, comp
        # areas whose latest labelled frame is non-compliant: {"areas", "ts", "dino" (n,D) or None}
        self.carry = carry or {"areas": [], "ts": [], "dino": None}
        self.memory = memory          # build_memory() table of the labelled crops, or None
        self.mem_stock = mem_stock    # stock LR on [design, memory_features], or None

    # ---- features
    def _design(self, feats, fill, zs_stock, zs_comp, which: str) -> tuple[np.ndarray, np.ndarray]:
        """Design matrix and per-column penalty weights (a weight > 1 shrinks that column's L2 penalty)."""
        P = self.params
        fill = np.asarray(fill, np.float64)
        blocks = [(np.stack([fill, fill ** 2, np.asarray(feats.visible, np.float64)], axis=1), P.w_small)]
        if not (which == "comp" and self.layout["comp_small"]):
            for name, arr in (("clip", feats.clip), ("dino", feats.dino_cls)):
                if name in self.pca:
                    if arr is None:
                        raise ValueError(f"heads were fitted with {name} features but the input has none")
                    mean, comps = self.pca[name]
                    blocks.append(((np.asarray(arr, np.float32) - mean) @ comps.T, 1.0))
            if self.layout["hand"]:
                blocks.append((np.asarray(feats.hand, np.float64), 1.0))
            if self.layout["code_bands"]:
                if feats.patch_codes is None:
                    raise ValueError("heads were fitted with patch_codes but the input has none")
                blocks.append((code_histograms(feats.patch_codes, self.layout["n_codes"],
                                               self.layout["code_bands"]), P.w_codes))
        if which == "stock" and self.layout["zs_stock"]:
            if zs_stock is None:
                raise ValueError("these heads were fitted with zs_stock: pass the same unsupervised posterior")
            blocks.append((_zs_stock_cols(zs_stock), P.w_zs))
        if which == "comp" and self.layout["zs_comp"]:
            if zs_comp is None:
                raise ValueError("these heads were fitted with zs_comp: pass the same p_compliant")
            blocks.append((_logit(zs_comp)[:, None], P.w_zs))
        if which == "stock" and self.layout.get("fill_bands"):
            if feats.patch_codes is None:
                raise ValueError("heads were fitted with band fills but the input has no patch_codes")
            blocks.append((band_fills(feats.patch_codes, np.asarray(self.layout["productness"]),
                                      int(self.layout["fill_bands"])), P.w_fill_bands))
        x = np.concatenate([b for b, _ in blocks], axis=1)
        w = np.concatenate([np.full(b.shape[1], wt) for b, wt in blocks])
        return x, w

    # ---- predictions
    def late_mask(self, feats: CropFeatures) -> np.ndarray:
        """(N,) True for rows later than their camera's last labelled frame (unknown camera: the
        latest labelled frame overall). A row without a timestamp (< 0, a file name that is not a Unix
        time) counts as late: the hidden set is known to be later in the day than every labelled frame."""
        last = self.stock.get("last_ts") or {}
        if not last:
            return np.zeros(len(feats), bool)
        default = max(last.values())
        return np.array([int(t) < 0 or int(t) > int(last.get(c, default))
                         for c, t in zip(feats.camera_ids, feats.timestamps)], dtype=bool)

    def memory_block(self, feats: CropFeatures) -> tuple[np.ndarray, np.ndarray]:
        """(F, has) per-area memory features of ``feats`` (see ``memory_features``); has is all False
        without a memory table."""
        if self.memory is None or not len(feats):
            return np.zeros((len(feats), 0)), np.zeros(len(feats), bool)
        P = self.params
        return memory_features(self.memory, feats, self.stock.get("prior", [1 / 3] * 3), P.mem_tau, P.mem_alpha,
                               last=P.mem_last)

    def memory_mask(self, feats: CropFeatures) -> np.ndarray:
        """(N,) True for rows the memory stock head answers (their area has an earlier labelled crop)."""
        if self.mem_stock is None:
            return np.zeros(len(feats), bool)
        return self.memory_block(feats)[1]

    def stock_proba(self, feats: CropFeatures, fill: np.ndarray, zs_stock: np.ndarray | None = None,
                    late_shift: bool | None = None, memory: bool = True) -> np.ndarray:
        """(N,3) posterior over (empty, half, full); rows sum to 1. Rows whose area has an earlier labelled
        crop use the memory head (``memory=False`` forces the plain head). Rows after the last labelled
        frame get the prior shift p * late_prior / train_prior (``params.late_shift``)."""
        m = self.stock
        fill = np.asarray(fill, np.float64)
        if m["kind"] == "constant":
            p = np.tile(np.asarray(m["prior"], np.float64), (len(feats), 1))
        else:
            p = _lr_proba3(m, self._design(feats, fill, zs_stock, None, "stock")[0])
            if memory and self.mem_stock is not None and len(feats):
                try:
                    F, has = self.memory_block(feats)
                    if has.any():
                        rows = np.flatnonzero(has)
                        x = self._design(feats.subset(rows), fill[rows],
                                         None if zs_stock is None else np.asarray(zs_stock)[rows], None, "stock")[0]
                        p[rows] = _lr_proba3(self.mem_stock, np.concatenate([x, F[rows]], axis=1))
                except (ValueError, KeyError, IndexError) as exc:   # never lose the plain head over the memory
                    log.warning("memory stock head not usable (%s): plain stock head", exc)
        p = np.clip(p, EPS, None)
        p = p / p.sum(axis=1, keepdims=True)
        shift = self.params.late_shift if late_shift is None else late_shift
        if shift and m.get("late_prior") is not None and len(feats):
            late = self.late_mask(feats)
            if late.any():
                p[late] *= np.asarray(m["late_prior"], np.float64) / np.asarray(m["prior"], np.float64)
                p[late] /= p[late].sum(axis=1, keepdims=True)
        return p.astype(np.float32)

    def carried(self, feats: CropFeatures) -> np.ndarray:
        """(N,) True where the area's latest labelled frame (before this row) was non-compliant and
        the crop still looks like that labelled crop (DINO cosine >= ``params.carry_tau``)."""
        out = np.zeros(len(feats), bool)
        c = self.carry
        if not c["areas"] or not len(feats):
            return out
        pos = {a: j for j, a in enumerate(c["areas"])}
        dino = None
        if c.get("dino") is not None and feats.dino_cls is not None:
            dino = np.asarray(feats.dino_cls, np.float32)
            dino = dino / np.maximum(np.linalg.norm(dino, axis=1, keepdims=True), 1e-8)
        for i, (a, t) in enumerate(zip(feats.area_ids, feats.timestamps)):
            j = pos.get(a)
            if j is None or 0 <= int(t) <= int(c["ts"][j]):     # no timestamp (< 0): later than the label
                continue
            out[i] = dino is None or float(dino[i] @ c["dino"][j]) >= self.params.carry_tau
        return out

    def compliance_proba(self, feats: CropFeatures, fill: np.ndarray, zs_comp: np.ndarray | None = None,
                         carry: bool = True) -> np.ndarray:
        """(N,) probability that the area shows its planogram product (carried non-compliant
        labels lower it to ``params.carry_p``)."""
        m = self.comp
        if m["kind"] == "constant":
            p = np.full(len(feats), float(m["prior"]), dtype=np.float32)
        elif m["kind"] == "passthrough":
            if zs_comp is None:
                raise ValueError("these heads pass the unsupervised p_compliant through: pass zs_comp")
            p = np.asarray(zs_comp, np.float32).copy()
        else:
            q = _apply_lr(m, self._design(feats, fill, None, zs_comp, "comp")[0])
            p = np.clip(q[:, 1], EPS, 1 - EPS).astype(np.float32)
        if carry:
            p = np.where(self.carried(feats), np.minimum(p, self.params.carry_p), p).astype(np.float32)
        return p

    # ---- persistence
    def save(self, directory: str | Path) -> None:
        """Write ``heads.json`` + ``heads.npz`` into ``directory``."""
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        arrays: dict[str, np.ndarray] = {}
        meta = {"version": self.VERSION, "params": asdict(self.params), "layout": self.layout,
                "carry": {"areas": list(self.carry["areas"]), "ts": [int(t) for t in self.carry["ts"]]}}
        if self.carry.get("dino") is not None:
            arrays["carry_dino"] = np.asarray(self.carry["dino"], np.float32)
        for name, (mean, comps) in self.pca.items():
            arrays[f"pca_{name}_mean"], arrays[f"pca_{name}_comps"] = mean, comps
        models = [("stock", self.stock), ("comp", self.comp)]
        if self.mem_stock is not None and self.memory is not None:
            models.append(("memstock", self.mem_stock))
            mem = self.memory
            areas = sorted(set(mem["areas"]))
            pos = {a: k for k, a in enumerate(areas)}
            meta["memory"] = {"names": list(mem["names"]), "n_codes": int(mem["n_codes"]), "areas": areas}
            arrays["mem_area"] = np.array([pos[a] for a in mem["areas"]], np.int32)
            arrays["mem_ts"] = np.asarray(mem["ts"], np.int64)
            arrays["mem_ys"] = np.asarray(mem["ys"], np.int8)
            arrays["mem_yc"] = np.asarray(mem["yc"], bool)
            for name in mem["names"]:
                arrays[f"mem_emb_{name}"] = np.asarray(mem["emb"][name], np.float32)
                arrays[f"mem_center_{name}"] = np.asarray(mem["center"][name], np.float32)
        for tag, m in models:
            meta[tag] = {k: v for k, v in m.items() if not isinstance(v, np.ndarray)}
            for k, v in m.items():
                if isinstance(v, np.ndarray):
                    arrays[f"{tag}_{k}"] = v
        (d / "heads.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        np.savez_compressed(d / "heads.npz", **arrays)

    @classmethod
    def load(cls, directory: str | Path) -> "Heads":
        d = Path(directory)
        meta = json.loads((d / "heads.json").read_text(encoding="utf-8"))
        fields = {f for f in HeadParams.__dataclass_fields__}
        params = HeadParams(**{k: v for k, v in meta["params"].items() if k in fields})
        params.mem_embeddings, params.mem_skips = tuple(params.mem_embeddings), tuple(params.mem_skips)
        with np.load(d / "heads.npz", allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        pca = {n: (arrays[f"pca_{n}_mean"], arrays[f"pca_{n}_comps"]) for n in ("clip", "dino")
               if f"pca_{n}_mean" in arrays}
        models = {}
        for tag in ("stock", "comp", "memstock"):
            if tag not in meta:
                continue
            m = dict(meta[tag])
            for k in ("mean", "scale", "coef", "intercept"):
                if f"{tag}_{k}" in arrays:
                    m[k] = arrays[f"{tag}_{k}"]
            models[tag] = m
        carry = dict(meta.get("carry") or {"areas": [], "ts": []})
        carry["dino"] = arrays.get("carry_dino")
        memory = None
        if "memory" in meta and "memstock" in models:   # version-1 heads have neither
            mm = meta["memory"]
            names = list(mm["names"])
            memory = {"names": names, "n_codes": int(mm["n_codes"]),
                      "areas": [mm["areas"][int(k)] for k in arrays["mem_area"]],
                      "ts": arrays["mem_ts"].astype(np.int64), "ys": arrays["mem_ys"].astype(np.int64),
                      "yc": arrays["mem_yc"].astype(bool),
                      "emb": {n: arrays[f"mem_emb_{n}"] for n in names},
                      "center": {n: arrays[f"mem_center_{n}"] for n in names}}
        return cls(params, meta["layout"], pca, models["stock"], models["comp"], carry, memory,
                   models.get("memstock") if memory is not None else None)


def fit_heads(feats: CropFeatures, fill: np.ndarray, labels: dict, cfg: Config,
              params: HeadParams | None = None, zs_stock: np.ndarray | None = None,
              zs_comp: np.ndarray | None = None, productness: np.ndarray | None = None) -> Heads:
    """Fit both heads on the rows of ``feats`` that have an entry in ``labels``.

    Stock: multinomial logistic regression (decide with ``scoring.best_stock``). Compliance:
    logistic regression with class weights; a constant prior when one class has fewer than
    ``params.min_class`` examples. ``zs_*`` (optional) add the unsupervised outputs as features;
    ``productness`` (the patch coder's per-cluster weights, optional) adds per-band fills to the
    stock head (``params.fill_bands``).
    """
    params = params or HeadParams()
    idx, ys, yc = label_arrays(feats, labels)
    if len(idx) == 0:
        raise ValueError("none of the labelled areas is in the features")
    fill = np.asarray(fill, np.float64)
    pca = {}
    cap = max(2, len(idx) // 4)
    if params.n_clip > 0 and feats.clip is not None:
        pca["clip"] = _pca_fit(np.asarray(feats.clip[idx], np.float32), min(params.n_clip, cap))
    if params.n_dino > 0 and feats.dino_cls is not None:
        pca["dino"] = _pca_fit(np.asarray(feats.dino_cls[idx], np.float32), min(params.n_dino, cap))
    use_codes = params.code_bands > 0 and feats.patch_codes is not None
    layout = {"hand": bool(params.use_hand or (feats.clip is None and feats.dino_cls is None)), "zs_stock": zs_stock is not None, "zs_comp": zs_comp is not None,
              "comp_small": params.comp_features == "zs" and zs_comp is not None,
              "code_bands": int(params.code_bands) if use_codes else 0,
              "n_codes": int(feats.patch_codes.max()) + 1 if use_codes else 0}
    if params.fill_bands > 0 and feats.patch_codes is not None and productness is not None:
        layout["fill_bands"] = int(params.fill_bands)
        layout["productness"] = [float(v) for v in np.asarray(productness).ravel()]
    heads = Heads(params, layout, pca, {"kind": "constant", "prior": [1 / 3] * 3}, {"kind": "constant", "prior": 0.5})
    sub = feats.subset(idx)
    zs_s = None if zs_stock is None else np.asarray(zs_stock)[idx]
    zs_c = None if zs_comp is None else np.asarray(zs_comp)[idx]

    counts = np.bincount(ys, minlength=3)
    prior = (counts + 1.0) / (counts.sum() + 3.0)
    if (counts > 0).sum() >= 2:
        m = _fit_lr(*heads._design(sub, fill[idx], zs_s, None, "stock"), ys, params.c_stock,
                    params.stock_class_weight, cfg.seed)
        m["kind"], m["prior"] = "lr", [float(v) for v in prior]
    else:
        m = {"kind": "constant", "prior": [float(v) for v in prior]}
    # label mix of the last labelled frame of every camera (target prior for later frames)
    cams, ts = np.array(sub.camera_ids), np.asarray(sub.timestamps, np.int64)
    last_ts = {str(c): int(ts[cams == c].max()) for c in sorted(set(cams))}
    is_last = np.array([t == last_ts[c] for c, t in zip(cams, ts)], dtype=bool)
    m["last_ts"] = last_ts
    m["late_prior"] = [float(v) for v in (np.bincount(ys[is_last], minlength=3) + 1.0) / (is_last.sum() + 3.0)]
    heads.stock = m
    heads.carry = _carry_table(sub, yc)
    if params.memory and m["kind"] == "lr":
        _fit_memory_head(heads, sub, fill[idx], zs_s, ys, yc, cfg)

    n_pos, n_neg = int(yc.sum()), int((~yc).sum())
    if zs_comp is not None and not params.comp_head:
        c = {"kind": "passthrough"}
    elif min(n_pos, n_neg) < params.min_class:
        k = params.prior_strength
        p = (n_pos + k * cfg.compliance_prior) / (len(yc) + k)
        c = {"kind": "constant", "prior": float(p)}
        log.info("compliance head: %d compliant / %d not -> constant prior %.3f", n_pos, n_neg, p)
    else:
        c = _fit_lr(*heads._design(sub, fill[idx], None, zs_c, "comp"), yc.astype(np.int64), params.c_comp,
                    params.comp_class_weight, cfg.seed)
        c["kind"] = "lr"
    c["n_pos"], c["n_neg"] = n_pos, n_neg
    heads.comp = c
    return heads


def _fit_memory_head(heads: Heads, sub: CropFeatures, fill: np.ndarray, zs_stock: np.ndarray | None,
                     ys: np.ndarray, yc: np.ndarray, cfg: Config) -> None:
    """Store the labelled rows as the memory table and fit the memory stock head on the rows that have an
    earlier labelled crop of their area (causal, like later frames at predict time). Leaves
    ``heads.memory`` / ``heads.mem_stock`` None when there is too little to learn from."""
    P = heads.params
    n_codes = int(heads.layout.get("n_codes") or 0)
    if not n_codes and sub.patch_codes is not None and np.size(sub.patch_codes):
        n_codes = int(np.asarray(sub.patch_codes).max()) + 1
    memory = build_memory(sub, ys, yc, P.mem_embeddings, n_codes)
    if memory is None:
        return
    heads.memory = memory
    F, has = heads.memory_block(sub)
    if has.sum() < P.mem_min_rows or len(set(ys[has].tolist())) < 2:
        log.info("memory head: %d rows with an earlier labelled crop: not fitted", int(has.sum()))
        heads.memory = None
        return
    xs, yy = [], []
    for skip in sorted(set(int(k) for k in P.mem_skips) | {0}):
        if skip:
            F, has = memory_features(heads.memory, sub, heads.stock.get("prior", [1 / 3] * 3), P.mem_tau,
                                     P.mem_alpha, skip, P.mem_last)
        rows = np.flatnonzero(has)
        if not len(rows):
            continue
        x, w = heads._design(sub.subset(rows), fill[rows], None if zs_stock is None else zs_stock[rows], None, "stock")
        xs.append(np.concatenate([x, F[rows]], axis=1))
        yy.append(ys[rows])
    mm = _fit_lr(np.concatenate(xs), np.concatenate([w, np.full(F.shape[1], P.mem_w)]),
                 np.concatenate(yy), P.c_stock, P.stock_class_weight, cfg.seed)
    mm["kind"], mm["n_rows"] = "lr", int(sum(len(v) for v in yy))
    heads.mem_stock = mm


def _carry_table(sub: CropFeatures, yc: np.ndarray) -> dict:
    """Areas whose latest labelled frame is non-compliant, with that frame's time and DINO cls."""
    latest: dict[str, int] = {}
    for j, (a, t) in enumerate(zip(sub.area_ids, sub.timestamps)):
        if a not in latest or int(t) > int(sub.timestamps[latest[a]]):
            latest[a] = j
    rows = [j for a, j in sorted(latest.items()) if not yc[j]]
    dino = None
    if sub.dino_cls is not None and rows:
        dino = np.asarray(sub.dino_cls[rows], np.float32)
        dino = dino / np.maximum(np.linalg.norm(dino, axis=1, keepdims=True), 1e-8)
    return {"areas": [sub.area_ids[j] for j in rows], "ts": [int(sub.timestamps[j]) for j in rows], "dino": dino}


# =========================================================================== cross-validation

def _folds(feats: CropFeatures, idx: np.ndarray, scheme: str, holdout_frames: int):
    """Yield (name, train_rows, test_rows) over the labelled rows ``idx``."""
    cams = np.array(feats.camera_ids)[idx]
    if scheme == "camera":
        for cam in sorted(set(cams)):
            yield cam, idx[cams != cam], idx[cams == cam]
        return
    test_mask = np.zeros(len(idx), bool)
    for cam in set(cams):
        sel = np.flatnonzero(cams == cam)
        frames = sorted(set(int(t) for t in feats.timestamps[idx[sel]]))
        k = min(holdout_frames, len(frames) - 1)
        if k <= 0:
            continue
        last = set(frames[-k:])
        test_mask[sel] = [int(t) in last for t in feats.timestamps[idx[sel]]]
    yield "last_frames", idx[~test_mask], idx[test_mask]


def _summ(res: dict) -> dict:
    n = max(res["areas"], 1)
    return {"total": res["total"], "max": res["max"], "areas": res["areas"],
            "per_area": round(res["total"] / n, 4),
            "ident_acc": round(res["identification"].get("right", 0) / n, 4),
            "stock_acc": round(res["stock"].get("correct", 0) / n, 4),
            "stock_cases": res["stock"]}


def cross_validate(feats: CropFeatures, fill: np.ndarray, labels: dict, cfg: Config,
                   baseline: dict | None = None, zs_stock: np.ndarray | None = None,
                   zs_comp: np.ndarray | None = None, params: HeadParams | None = None,
                   schemes: Iterable[str] = ("camera", "time"), holdout_frames: int = 2,
                   productness: np.ndarray | None = None) -> dict:
    """Held-out challenge scores (``scoring.score``) for the heads and simple references.

    Schemes: ``"camera"`` = leave one camera out; ``"time"`` = the last ``holdout_frames`` labelled
    frames of every camera are the test set (mimics the later-in-the-day hidden validation set);
    ``"time1"``, ``"time3"``... the same with that many frames. With a per-area memory, ``heads`` uses it
    where the held-out area has earlier labelled frames in the training part (never in camera folds) and
    ``heads_nomem`` is the same heads without it; ``memory_rows`` counts the held-out rows it answered.
    ``baseline`` = ``{"p_stock": (N,3), "p_comp": (N,)}`` (either key optional) are the supplied
    unsupervised outputs; if omitted and ``zs_*`` are given they serve as the baseline. The
    constants are: all full/half/empty + compliant, and ``train_prior`` (best_stock of the training
    label frequencies). Returns a json-friendly dict ``{scheme: {"areas", "methods", "per_camera"}}``.
    """
    idx, ys, yc = label_arrays(feats, labels)
    if len(idx) == 0:
        raise ValueError("none of the labelled areas is in the features")
    base = dict(baseline or {})
    if zs_stock is not None:
        base.setdefault("p_stock", zs_stock)
    if zs_comp is not None:
        base.setdefault("p_comp", zs_comp)
    pos = {int(r): j for j, r in enumerate(idx)}
    fill = np.asarray(fill, np.float64)
    report: dict = {"n_labelled": int(len(idx)), "schemes": {}}
    for scheme in schemes:
        truth: dict = {}
        methods: dict[str, dict] = {}
        rows_by_cam: dict[str, list[int]] = {}
        n_mem = 0
        ho = int(scheme[4:]) if scheme.startswith("time") and scheme[4:].isdigit() else holdout_frames
        for name, train, test in _folds(feats, idx, "camera" if scheme == "camera" else "time", ho):
            if len(train) == 0 or len(test) == 0:
                continue
            tr_feats, te_feats = feats.subset(train), feats.subset(test)
            heads = fit_heads(tr_feats, fill[train], labels, cfg, params,
                              None if zs_stock is None else np.asarray(zs_stock)[train],
                              None if zs_comp is None else np.asarray(zs_comp)[train], productness)
            zs_te = None if zs_stock is None else np.asarray(zs_stock)[test]
            p_comp_te = heads.compliance_proba(te_feats, fill[test], None if zs_comp is None else np.asarray(zs_comp)[test])
            preds = {"heads": (heads.stock_proba(te_feats, fill[test], zs_te), p_comp_te)}
            if heads.mem_stock is not None:   # the same heads without the per-area memory
                preds["heads_nomem"] = (heads.stock_proba(te_feats, fill[test], zs_te, memory=False), p_comp_te)
                n_mem += int(heads.memory_mask(te_feats).sum())
            if "p_stock" in base or "p_comp" in base:
                preds["baseline"] = (
                    np.asarray(base["p_stock"])[test] if "p_stock" in base else np.tile([0.15, 0.35, 0.5], (len(test), 1)),
                    np.asarray(base["p_comp"])[test] if "p_comp" in base else np.full(len(test), cfg.compliance_prior))
            n = len(test)
            for lvl, label in enumerate(LEVEL_NAMES):
                one = np.zeros((n, 3))
                one[:, lvl] = 1.0
                preds[f"all_{label}"] = (one, np.ones(n))
            tr_counts = np.bincount(ys[[pos[int(r)] for r in train]], minlength=3) + 1.0
            preds["train_prior"] = (np.tile(tr_counts / tr_counts.sum(), (n, 1)), np.ones(n))
            keys = [feats.keys[r] for r in test]
            for method, (ps, pc) in preds.items():
                p = predictions_from_probs(keys, ps, pc)
                methods.setdefault(method, {})
                for cam, imgs in p.items():
                    for img, areas in imgs.items():
                        methods[method].setdefault(cam, {}).setdefault(img, {}).update(areas)
            for r in test:
                cam, img, area = feats.keys[r]
                truth.setdefault(cam, {}).setdefault(img, {})[area] = labels[cam][img][area]
                rows_by_cam.setdefault(cam, []).append(int(r))
        if not truth:
            report["schemes"][scheme] = {"areas": 0, "methods": {}, "per_camera": {}}
            continue
        out = {"areas": sum(len(a) for i in truth.values() for a in i.values()), "memory_rows": n_mem,
               "methods": {}, "per_camera": {}}
        for method, p in methods.items():
            out["methods"][method] = _summ(scoring.score(truth, p))
        for cam in sorted(truth):
            cam_truth = {cam: truth[cam]}
            row = {"areas": sum(len(a) for a in truth[cam].values())}
            for method in ("heads", "heads_nomem", "baseline", "all_full", "train_prior"):
                if method in methods:
                    row[method] = _summ(scoring.score(cam_truth, {cam: methods[method].get(cam, {})}))["per_area"]
            out["per_camera"][cam] = row
        report["schemes"][scheme] = out
    return report


def format_report(report: dict) -> str:
    """Plain-text table of a ``cross_validate`` report (points per area; max is 2.0)."""
    lines = [f"labelled rows: {report['n_labelled']}"]
    for scheme, res in report["schemes"].items():
        lines.append(f"[{scheme}] held-out areas: {res['areas']}")
        lines.append(f"  {'method':<12}{'per_area':>9}{'ident_acc':>10}{'stock_acc':>10}")
        for method, r in sorted(res["methods"].items(), key=lambda kv: -kv[1]["per_area"]):
            lines.append(f"  {method:<12}{r['per_area']:>9.3f}{r['ident_acc']:>10.3f}{r['stock_acc']:>10.3f}")
    return "\n".join(lines)

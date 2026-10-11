"""Freshness watch and ethylene neighbours for the staff dashboard (pure functions, no images, no network).

Biology per product comes from ``docs/produce_biology_reference.csv`` (researched classes, sources and caveats in
``docs/produce_biology_notes.md``), overridden cell by cell by any NON-EMPTY value a teammate typed into
``docs/produce_biology_template.csv`` (rows matched on ``planogram_name_pt``). Missing files or values only mean
"no badge" for that product.

* **Freshness watch** (``freshness_status``): hours an area has been on display = time of the current picture minus
  the last restock seen in the day's timeline (fill jumping up by more than ``RESTOCK_JUMP`` between consecutive
  pictures, the rule the Insights tab uses), or minus the first picture of the day when no restock was seen. Past
  the product's ``hours_on_display_before_checking`` (and not empty) the area is due a freshness check. It is an
  estimate from time and the shelf-life class, never a judgement of the picture.
* **Ethylene neighbours** (``ethylene_pairs``): areas of the same camera whose quads touch or nearly touch
  (gap <= ``GAP_FRAC`` x sqrt(area of the smaller quad), the rule of ``tools/ethylene_neighbours.py``) where one
  product is a high ethylene producer and the other is highly ethylene sensitive. A layout suggestion only.
"""
from __future__ import annotations

import csv
import io
import logging
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "docs" / "produce_biology_reference.csv"
TEMPLATE = ROOT / "docs" / "produce_biology_template.csv"

RESTOCK_JUMP = 0.30      # same rule as sensei.dashboard.RESTOCK_JUMP (Insights restocks)
GAP_FRAC = 0.25          # neighbours: gap <= 0.25 x sqrt(smaller quad area), checked by eye on the store photos
CLASSES = ("fast", "medium", "slow")
LEVELS = ("high", "medium", "low")

# CSV header (text before " (") -> short key
_COLS = {
    "type": "type", "product_english": "en", "planogram_name_pt": "name", "loose_or_packed": "packing",
    "areas": "areas", "shelf_life_class": "cls", "hours_on_display_before_checking": "lim",
    "ethylene_producer": "prod", "ethylene_sensitive": "sens", "visible_spoilage_signs": "signs",
    "source": "source", "confidence": "conf",
}


def name_key(name: Any) -> str:
    """Matching key of a planogram product name: NFC, upper case, single spaces."""
    return " ".join(unicodedata.normalize("NFC", str(name or "")).upper().split())


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):             # Excel on a Portuguese Windows may save as cp1252
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_biology_csv(path: str | Path) -> list[dict[str, str]]:
    """Rows of a biology CSV with short keys (see ``_COLS``); ``;`` or ``,`` separated. Missing file -> []."""
    p = Path(path)
    if not p.is_file():
        return []
    text = _read_text(p)
    first = text.splitlines()[0] if text else ""
    delim = ";" if first.count(";") >= first.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not rows:
        return []
    keys = [_COLS.get(h.split(" (")[0].strip().lower()) for h in rows[0]]
    out = []
    for r in rows[1:]:
        rec = {k: (r[i].strip() if i < len(r) else "") for i, k in enumerate(keys) if k}
        if rec.get("name"):
            out.append(rec)
    return out


def _clean(rec: dict[str, str], where: str) -> dict[str, Any]:
    """Validated values of one row: bad values are dropped (with a warning), empty ones are left out."""
    out: dict[str, Any] = {}
    for k, v in rec.items():
        v = (v or "").strip()
        if not v:
            continue
        if k == "cls":
            v = v.lower()
            if v not in CLASSES:
                log.warning("freshness: %s: shelf_life_class %r is not fast/medium/slow; ignored", where, v)
                continue
        elif k in ("prod", "sens"):
            v = v.lower()
            if v not in LEVELS:
                log.warning("freshness: %s: ethylene class %r is not high/medium/low; ignored", where, v)
                continue
        elif k == "lim":
            m = re.match(r"^\s*(\d+(?:[.,]\d+)?)", v)
            h = float(m.group(1).replace(",", ".")) if m else 0.0
            if not 0 < h <= 24 * 30:
                log.warning("freshness: %s: hours_on_display_before_checking %r is not a number of hours; ignored", where, v)
                continue
            v = int(h) if h == int(h) else h
        out[k] = v
    return out


def load_biology(reference: str | Path | None = REFERENCE, overrides: str | Path | None = TEMPLATE) -> dict[str, dict]:
    """``{name_key(planogram_name_pt): record}`` from the reference CSV, overridden cell by cell by every non-empty
    value of the teammate's template (``overrides``). A record keeps ``edited`` = the fields taken from the template.
    Either file may be missing; both missing gives ``{}`` (the dashboard then shows no freshness or ethylene hints)."""
    bio: dict[str, dict] = {}
    if reference:
        for rec in read_biology_csv(reference):
            bio[name_key(rec["name"])] = {**_clean(rec, f"{Path(reference).name} {rec['name']}"), "edited": []}
    if overrides:
        for rec in read_biology_csv(overrides):
            vals = _clean(rec, f"{Path(overrides).name} {rec['name']}")
            key = name_key(rec["name"])
            base = bio.setdefault(key, {"name": rec["name"], "edited": []})
            for k, v in vals.items():
                if k in ("name", "type", "en", "packing", "areas") and k in base:
                    continue                     # identity columns are pre-filled copies, not opinions
                if base.get(k) != v:
                    base[k] = v
                    if k not in ("name", "type", "en", "packing", "areas"):
                        base["edited"].append(k)
            if base["edited"] and "conf" in base and "conf" not in vals:
                base.pop("conf")                 # the researcher's confidence no longer describes edited values
    return bio


def short_source(text: str, max_parts: int = 3) -> str:
    """Readable citation from a ``source`` cell: URLs and long parentheticals dropped, ``|`` parts joined by ``; ``."""
    parts = []
    for seg in str(text or "").split("|"):
        s = re.sub(r"https?://\S+", "", seg)
        s = re.sub(r"\s*\([^()]{26,}\)", "", s)
        s = re.sub(r"\s+", " ", s).strip(" :;,.")
        if s and s not in parts:
            parts.append(s)
    return "; ".join(parts[:max_parts])


# --------------------------------------------------------------------------- freshness watch

def restock_times(timeline: Iterable[Iterable], now_ts: float | None = None, jump: float = RESTOCK_JUMP) -> list[int]:
    """Times (of the later picture) where the fill rose by more than ``jump`` between consecutive pictures,
    only pictures up to ``now_ts``. ``timeline`` = ``[[ts, fill, ...], ...]``."""
    pts = sorted((int(p[0]), float(p[1])) for p in timeline if p is not None and len(p) >= 2 and p[1] is not None)
    if now_ts is not None:
        pts = [p for p in pts if p[0] <= now_ts]
    return [t1 for (_, f0), (t1, f1) in zip(pts, pts[1:]) if f1 - f0 > jump]


def on_display_since(timeline: Iterable[Iterable], now_ts: float, jump: float = RESTOCK_JUMP) -> tuple[int, str] | None:
    """``(ts, basis)``: the last restock seen (``"restock"``), else the first picture of the day (``"first"``).
    None without any picture up to ``now_ts``."""
    tl = [p for p in timeline if p is not None and len(p) >= 2 and int(p[0]) <= now_ts]
    if not tl:
        return None
    rs = restock_times(tl, now_ts, jump)
    if rs:
        return rs[-1], "restock"
    return min(int(p[0]) for p in tl), "first"


def freshness_status(timeline: Iterable[Iterable], now_ts: float, level: str | None, limit_h: float | None,
                     jump: float = RESTOCK_JUMP) -> dict | None:
    """``{"h", "lim", "since", "basis", "due"}`` for one area, or None without a check interval or a picture.

    ``h`` = hours on display (now - since, 1 decimal), ``due`` = ``h > lim`` and the area is not empty. With no
    restock seen, the stock may be older than the first picture, so ``h`` is then a lower bound."""
    if not limit_h or limit_h <= 0:
        return None
    timeline = list(timeline or [])
    s = on_display_since(timeline, now_ts, jump)
    if s is None:
        return None
    since, basis = s
    h = max(0.0, (float(now_ts) - since) / 3600.0)
    return {"h": round(h, 1), "lim": limit_h, "since": int(since), "basis": basis,
            "due": bool(h > float(limit_h) and level != "empty")}


# --------------------------------------------------------------------------- ethylene neighbours

def _quad(q: Any) -> list[tuple[float, float]] | None:
    try:
        pts = [(float(p[0]), float(p[1])) for p in q]
    except (TypeError, ValueError, IndexError):
        return None
    return pts if len(pts) >= 3 else None


def polygon_area(p: list[tuple[float, float]]) -> float:
    n = len(p)
    return abs(sum(p[i][0] * p[(i + 1) % n][1] - p[(i + 1) % n][0] * p[i][1] for i in range(n))) / 2.0


def _seg_dist(pt, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / l2))
    return math.hypot(pt[0] - a[0] - t * dx, pt[1] - a[1] - t * dy)


def _inside(pt, poly) -> bool:
    x, y = pt
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _cross(a, b, c, d) -> bool:
    """Segments ab and cd properly intersect."""
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (o(a, b, c) > 0) != (o(a, b, d) > 0) and (o(c, d, a) > 0) != (o(c, d, b) > 0)


def polygon_gap(p: list, q: list) -> float:
    """Smallest distance in pixels between two polygons (0 when they overlap or touch)."""
    if any(_inside(v, q) for v in p) or any(_inside(v, p) for v in q):
        return 0.0
    ep = [(p[i], p[(i + 1) % len(p)]) for i in range(len(p))]
    eq = [(q[i], q[(i + 1) % len(q)]) for i in range(len(q))]
    if any(_cross(a, b, c, d) for a, b in ep for c, d in eq):
        return 0.0
    return min(min(_seg_dist(v, a, b) for v in q for a, b in ep), min(_seg_dist(v, a, b) for v in p for a, b in eq))


def are_neighbours(p: Any, q: Any, gap_frac: float = GAP_FRAC) -> tuple[bool, float]:
    """``(neighbours, gap_px)``: quads closer than ``gap_frac`` x sqrt(area of the smaller one) (a dilation that
    scales with the shelf's size in the picture). Missing quads are never neighbours."""
    a, b = _quad(p), _quad(q)
    if a is None or b is None:
        return False, math.inf
    gap = polygon_gap(a, b)
    return gap <= gap_frac * math.sqrt(max(min(polygon_area(a), polygon_area(b)), 0.0)), gap


def ethylene_pairs(items: list[dict], gap_frac: float = GAP_FRAC) -> tuple[list[dict], int]:
    """Producer -> sensitive neighbour pairs. ``items``: ``{"id", "cam", "quad", "type", "prod", "sens"}`` (the
    product actually on the shelf). Returns ``(pairs, n_mild)``: ``pairs`` = high producer next to high
    sensitivity, ``{"cam", "src", "dst", "src_type", "dst_type", "gap"}`` sorted by camera and areas; ``n_mild`` =
    directional pairs one step milder (high next to medium, medium next to high), counted, not listed. Two areas of
    the same product type are skipped (they ripen together anyway)."""
    by_cam: dict[str, list[dict]] = {}
    for it in items:
        if it.get("quad") is not None and it.get("type"):
            by_cam.setdefault(str(it["cam"]), []).append(it)
    pairs: list[dict] = []
    mild = 0
    for cam, its in by_cam.items():
        for i, a in enumerate(its):
            for b in its[i + 1:]:
                if a["type"] == b["type"]:
                    continue
                near, gap = are_neighbours(a["quad"], b["quad"], gap_frac)
                if not near:
                    continue
                for src, dst in ((a, b), (b, a)):
                    ps, sd = src.get("prod"), dst.get("sens")
                    if ps == "high" and sd == "high":
                        pairs.append({"cam": cam, "src": str(src["id"]), "dst": str(dst["id"]),
                                      "src_type": src["type"], "dst_type": dst["type"], "gap": round(gap, 1)})
                    elif (ps, sd) in (("high", "medium"), ("medium", "high")):
                        mild += 1
    pairs.sort(key=lambda p: (len(p["cam"]), p["cam"], _nat(p["src"]), _nat(p["dst"])))
    return pairs, mild


def _nat(area_id: str) -> tuple:
    cam, _, num = str(area_id).rpartition("_")
    return (cam, int(num) if num.isdigit() else 0, str(area_id))

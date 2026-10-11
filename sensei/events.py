"""Area events: turn per-frame area answers into the changes staff need to hear about.

``watch`` runs the normal predict path (no model changes) over a folder of frames, orders each camera's
frames by time and compares every area with its previous frame. A change of status becomes one JSON line::

    {"time": "2025-06-27T14:05:00+01:00", "ts": 1751029500, "camera_id": "6215", "area_id": "...",
     "product": "Banana", "event": "became_empty", "from": "half", "to": "empty", "confidence": 0.91, ...}

Area status is one of ``full``, ``half``, ``empty`` or ``wrong_product`` (another product is in the area; an
empty area is never "wrong", as in the submission). Events:

=====================  ====================================================
became_empty           any status -> empty
became_low             full -> half
restocked              empty -> half / full
back_to_ok             half -> full (topped up)
wrong_product          full / half / empty -> wrong_product
wrong_product_fixed    wrong_product -> full / half
=====================  ====================================================

The first frame of an area only sets its baseline (no event). With ``confirm=k`` a new status must be seen
in k consecutive frames before it is reported (one-frame flickers are dropped); the event carries the time
of the first of those frames. This is the interface for the alerts staff already get: a store platform can
tail the JSON lines file or call ``events_from_rows`` on its own frames.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

EVENTS = ("became_empty", "became_low", "restocked", "back_to_ok", "wrong_product", "wrong_product_fixed")
LEVEL_INDEX = {"empty": 0, "half": 1, "full": 2}


def status(row: dict) -> str:
    """The area status of one details row: wrong_product, or its stock level."""
    if not row.get("planogram_compliant", True) and row.get("stock_level") != "empty":
        return "wrong_product"
    return str(row.get("stock_level", "full"))


def status_confidence(row: dict) -> float:
    """Model probability of the row's status (level probability; for wrong_product, 1 - p_compliant)."""
    st = status(row)
    if st == "wrong_product":
        return round(1.0 - float(row.get("p_compliant", 0.0)), 3)
    p = row.get("p_levels")
    p_level = float(p[LEVEL_INDEX[st]]) if p and len(p) == 3 else 1.0
    if row.get("planogram_compliant", True) and st != "empty" and row.get("p_compliant") is not None:
        p_level *= float(row["p_compliant"])   # right product AND this level
    return round(p_level, 3)


def classify(old: str, new: str) -> str | None:
    """The event name of a status change, None for no event."""
    if old == new:
        return None
    if new == "empty":
        return "became_empty"
    if new == "wrong_product":
        return "wrong_product"
    if old == "wrong_product":
        return "wrong_product_fixed"
    if old == "empty":
        return "restocked"
    if old == "full" and new == "half":
        return "became_low"
    if old == "half" and new == "full":
        return "back_to_ok"
    return None


def _lisbon_iso(ts: int) -> str:
    """ISO time in store-local Europe/Lisbon time (EU summer-time rule written out: no tz database on Windows)."""
    if ts < 0:
        return ""
    utc = datetime.fromtimestamp(ts, timezone.utc)

    def last_sunday(month: int) -> float:
        d = datetime(utc.year, month, 31, 1, tzinfo=timezone.utc)
        return (d - timedelta(days=(d.weekday() + 1) % 7)).timestamp()

    off = 1 if last_sunday(3) <= ts < last_sunday(10) else 0
    return utc.astimezone(timezone(timedelta(hours=off))).isoformat()


def events_from_rows(rows: Iterable[dict], confirm: int = 1) -> list[dict]:
    """Status-change events of details rows (any order), sorted by time then camera and area."""
    confirm = max(1, int(confirm))
    by_area: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        if r.get("fallback"):        # unreadable frame: no evidence of a change
            continue
        by_area.setdefault((str(r["camera_id"]), str(r["area_id"])), []).append(r)
    out: list[dict] = []
    for seq in by_area.values():
        seq.sort(key=lambda r: (int(r.get("timestamp", -1)), str(r.get("image_name", ""))))
        current = status(seq[0])
        pending: list[dict] = []
        for r in seq[1:]:
            st = status(r)
            if st == current:
                pending = []
                continue
            if pending and status(pending[0]) != st:
                pending = []
            pending.append(r)
            if len(pending) < confirm:
                continue
            first = pending[0]
            name = classify(current, st)
            if name is not None:
                out.append(_event(first, name, current, st, min(status_confidence(x) for x in pending)))
            current, pending = st, []
    out.sort(key=lambda e: (e["ts"], e["camera_id"], e["area_id"]))
    return out


def _event(row: dict, name: str, old: str, new: str, conf: float) -> dict:
    ts = int(row.get("timestamp", -1))
    ev = {"time": _lisbon_iso(ts), "ts": ts, "camera_id": str(row["camera_id"]), "area_id": str(row["area_id"]),
          "product": row.get("product_name"), "event": name, "from": old, "to": new, "confidence": conf,
          "image": row.get("image_name")}
    if new == "wrong_product":
        ev["seen_product"] = row.get("likely_product_name")
    return ev


def summary(events: list[dict], rows: list[dict]) -> str:
    """Readable summary: counts per event, the event log, and the areas still needing action at the end."""
    lines = []
    cams = sorted({str(r["camera_id"]) for r in rows})
    frames = len({(r["camera_id"], r["image_name"]) for r in rows})
    lines.append(f"{len(events)} event(s) over {frames} frame(s) of {len(cams)} camera(s), "
                 f"{len({r['area_id'] for r in rows})} areas")
    counts = Counter(e["event"] for e in events)
    if counts:
        lines.append("  " + ", ".join(f"{k}: {counts[k]}" for k in EVENTS if counts[k]))
    for e in events:
        hhmm = e["time"][11:16] if e["time"] else "--:--"
        extra = f" (seen: {e['seen_product']})" if e.get("seen_product") else ""
        lines.append(f"  {hhmm}  {e['area_id']:<9} {e['event']:<20} {e['product']}  "
                     f"{e['from']} -> {e['to']}  p={e['confidence']:.2f}{extra}")
    last: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: int(r.get("timestamp", -1))):
        if not r.get("fallback"):
            last[str(r["area_id"])] = r
    open_ = [r for r in last.values() if status(r) in ("empty", "wrong_product")]
    if open_:
        open_.sort(key=lambda r: (r["camera_id"], r["area_id"]))
        shown = ", ".join(f"{r['product_name']} [{status(r)}]" for r in open_[:12])
        more = f", ... (+{len(open_) - 12})" if len(open_) > 12 else ""
        lines.append(f"open at the last frame ({len(open_)}): {shown}{more}")
    return "\n".join(lines)


def watch(model_dir: str | Path, images: str | Path, out: str | Path | None = None, confirm: int = 1,
          device: str | None = None) -> tuple[list[dict], list[dict]]:
    """Predict every frame under ``images`` with the model and return (events, details rows).
    Writes the events as JSON lines to ``out`` when given."""
    from .pipeline import SenseiModel, predict_dir  # noqa: PLC0415
    model = SenseiModel.load(model_dir)
    cfg = model.cfg.replace(device=device) if device else None
    _, doc = predict_dir(model, images, None, None, cfg)
    rows = doc["rows"]
    events = events_from_rows(rows, confirm=confirm)
    if out is not None:
        write_jsonl(events, out)
    return events, rows


def write_jsonl(events: list[dict], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    log.info("wrote %d event(s) to %s", len(events), p)
    return p

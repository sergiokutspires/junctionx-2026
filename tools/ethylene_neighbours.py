"""List ethylene producer -> sensitive neighbour pairs in the planogram (inputs are only read).

  .venv/Scripts/python tools/ethylene_neighbours.py [--gap 0.25] [--json out.json]

Inputs: data/raw/planogram.json and docs/produce_biology_reference.csv (ethylene_producer and
ethylene_sensitive columns). Two areas are neighbours when they are on the same camera and their image
polygons are within GAP * sqrt(area of the smaller polygon) pixels. This is image-space adjacency, a
proxy for physical adjacency on the gondola. RED = high producer next to high sensitivity. AMBER =
high next to medium, or medium next to high. Pairs of the same product type are skipped.
See docs/produce_biology_notes.md section 4.
"""
import argparse
import csv
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RISK = {("high", "high"): "RED", ("high", "medium"): "AMBER", ("medium", "high"): "AMBER"}


def load_reference():
    text = (ROOT / "docs" / "produce_biology_reference.csv").read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))[1:]
    by_area = {}
    for r in rows:
        for a in r[4].split():
            by_area[a] = {"type": r[0], "name": r[1], "producer": r[7], "sensitive": r[8]}
    return by_area


def corners(ic):
    return [tuple(ic[k]) for k in ("top_left", "top_right", "bottom_right", "bottom_left")]


def poly_area(p):
    return abs(sum(p[i][0] * p[(i + 1) % 4][1] - p[(i + 1) % 4][0] * p[i][1] for i in range(4))) / 2


def seg_dist(pt, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / length2))
    return math.hypot(pt[0] - a[0] - t * dx, pt[1] - a[1] - t * dy)


def inside(pt, poly):
    x, y = pt
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def poly_gap(p, q):
    if any(inside(v, q) for v in p) or any(inside(v, p) for v in q):
        return 0.0
    return min(min(seg_dist(v, a[i], a[(i + 1) % 4]) for i in range(4) for v in b) for a, b in ((p, q), (q, p)))


def find_pairs(gap_frac=0.25):
    by_area = load_reference()
    cams = json.loads((ROOT / "data" / "raw" / "planogram.json").read_text(encoding="utf-8"))["Frutas e Legumes"]["cameras"]
    pairs = []
    for cam, c in cams.items():
        polys = {p["area_id"]: corners(p["image_coordinates"]) for p in c["products"]}
        ids = list(polys)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                pa, pb = by_area.get(a), by_area.get(b)
                if not pa or not pb or pa["type"] == pb["type"]:
                    continue
                gap = poly_gap(polys[a], polys[b])
                if gap > gap_frac * math.sqrt(min(poly_area(polys[a]), poly_area(polys[b]))):
                    continue
                for src, dst, sa, sb in ((pa, pb, a, b), (pb, pa, b, a)):
                    level = RISK.get((src["producer"], dst["sensitive"]))
                    if level:
                        pairs.append({"level": level, "camera": cam, "producer_area": sa, "producer": src["name"],
                                      "sensitive_area": sb, "sensitive": dst["name"], "gap_px": round(gap)})
    pairs.sort(key=lambda p: (p["level"] != "RED", p["camera"], p["producer_area"], p["sensitive_area"]))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description="List ethylene producer -> sensitive neighbour pairs of the planogram.")
    ap.add_argument("--gap", type=float, default=0.25,
                    help="neighbour gap as a share of sqrt(area of the smaller polygon) (default: %(default)s)")
    ap.add_argument("--json", help="also write the pairs to this JSON file")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    pairs = find_pairs(args.gap)
    for p in pairs:
        print(f"{p['level']:5} cam {p['camera']}  {p['producer_area']:8} {p['producer']:<28} -> "
              f"{p['sensitive_area']:8} {p['sensitive']:<28} gap {p['gap_px']} px")
    print(f"{len(pairs)} pairs, {sum(p['level'] == 'RED' for p in pairs)} RED")
    if args.json:
        Path(args.json).write_text(json.dumps(pairs, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

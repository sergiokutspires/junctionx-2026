"""Build the pitch visuals from the raw camera frames (no model output involved).

Every panel is a real frame or a real perspective-warped planogram area. Status colours on
these images are marked BY EYE for the story slides; model results come from the dashboard.

Usage (from the project root):
    .venv/Scripts/python pitch/assets/make_assets.py
Writes pitch/assets/a1_... .. a5_... .jpg
"""
import datetime
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent
CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")
TZ = datetime.timezone(datetime.timedelta(hours=1))  # Lisbon summer time (WEST)

INK = (20, 20, 24)
PAPER = (250, 250, 247)
MUTED = (110, 110, 118)
WRONG = (190, 40, 160)    # magenta: wrong product
EMPTY = (215, 45, 45)     # red: empty
OKC = (35, 150, 80)       # green: ok
WHITE = (255, 255, 255)


def font(size, bold=True):
    name = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def load_quads():
    plan = json.loads((RAW / "planogram.json").read_text(encoding="utf-8"))
    quads, names = {}, {}
    for section in plan.values():
        for cam, data in section["cameras"].items():
            for a in data["products"]:
                quads[a["area_id"]] = np.array([a["image_coordinates"][c] for c in CORNERS], np.float32)
                names[a["area_id"]] = a["product_name"]
    return quads, names


def frame(cam, ts):
    p = RAW / "images" / cam / f"{ts}.jpg"
    img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def hhmm(ts):
    return datetime.datetime.fromtimestamp(int(ts), TZ).strftime("%H:%M")


def warp(img, quad, size=240, inset=0.04):
    c = quad.mean(0, keepdims=True)
    q = (c + (quad - c) * (1 - inset)).astype(np.float32)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    m = cv2.getPerspectiveTransform(q, dst)
    return cv2.warpPerspective(img, m, (size, size), flags=cv2.INTER_AREA, borderValue=(0, 0, 0))


def tag(draw, xy, text, fill, f, anchor="mm", pad=8):
    box = draw.textbbox(xy, text, font=f, anchor=anchor)
    draw.rounded_rectangle([box[0] - pad, box[1] - pad // 2 - 2, box[2] + pad, box[3] + pad // 2 + 2],
                           radius=6, fill=fill)
    draw.text(xy, text, font=f, fill=WHITE, anchor=anchor)


def annotated_frame(cam, ts, quads, marks, scale=0.75):
    """marks: {area_id: (colour, label or None)}; other areas of the camera get a thin outline."""
    img = Image.fromarray(frame(cam, ts))
    draw = ImageDraw.Draw(img)
    f = font(22)
    for area_id, quad in quads.items():
        if not area_id.startswith(cam + "_"):
            continue
        pts = [tuple(p) for p in quad]
        if area_id in marks:
            colour, _ = marks[area_id]
            draw.polygon(pts, outline=colour, width=7)
        else:
            draw.polygon(pts, outline=(255, 255, 255), width=2)
    for area_id, (colour, label) in marks.items():
        if label:
            cx, cy = quads[area_id].mean(0)
            cx = float(np.clip(cx, 120, img.width - 120))
            cy = float(np.clip(cy, 30, img.height - 30))
            tag(draw, (cx, cy), label, colour, f)
    w, h = img.size
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def titled(panels, captions, title, subtitle, footer):
    gap, margin = 24, 32
    w = sum(p.width for p in panels) + gap * (len(panels) - 1) + 2 * margin
    head, cap_h, foot = 120, 60, 44
    h = head + max(p.height for p in panels) + cap_h + foot
    canvas = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((margin, 26), title, font=font(40), fill=INK)
    d.text((margin, 78), subtitle, font=font(24, bold=False), fill=MUTED)
    x = margin
    for p, cap in zip(panels, captions):
        canvas.paste(p, (x, head))
        d.text((x, head + p.height + 14), cap, font=font(24), fill=INK)
        x += p.width + gap
    d.text((margin, h - foot + 8), footer, font=font(18, bold=False), fill=MUTED)
    return canvas


def save(img, name):
    path = OUT / name
    img.save(path, quality=88)
    print("wrote", path.relative_to(ROOT), img.size)


def a1_planogram_broken(quads):
    p1 = annotated_frame("6215", 1751001268, quads, {
        "6215_3": (WRONG, "expected banana · seen orange"),
        "6215_5": (WRONG, None),
    })
    p2 = annotated_frame("6215", 1751009590, quads, {
        "6215_7": (WRONG, "expected orange · seen banana"),
        "6215_9": (WRONG, None),
    })
    img = titled([p1, p2],
                 [f"{hhmm(1751001268)}  areas 3 & 5 (banana) hold oranges",
                  f"{hhmm(1751009590)}  areas 7 & 9 (orange) hold bananas, all day"],
                 "The planogram is broken before the first customer walks in",
                 "Camera 6215, one island, same day. The plan says BANANA CAT I in 3 and 5, "
                 "CITRINOS DO ALGARVE (orange) in 7 and 9.",
                 "Raw frames from data/raw/images/6215. Magenta = mismatch marked by eye for this slide; "
                 "white = other planogram areas.")
    save(img, "a1_planogram_broken_6215.jpg")


def a2_opening(quads):
    empties = ["6462_1", "6462_4", "6462_5", "6462_6", "6462_7", "6462_8", "6462_9"]
    p1 = annotated_frame("6462", 1751001155, quads, {a: (EMPTY, None) for a in empties})
    p2 = annotated_frame("6462", 1751028563, quads, {"6462_1": (EMPTY, "low")})
    img = titled([p1, p2],
                 [f"{hhmm(1751001155)}  7 of 9 areas empty (bare trays and crates)",
                  f"{hhmm(1751028563)}  stocked; strawberries (area 1) down to one punnet"],
                 "Opening time: what do I restock first?",
                 "Camera 6462: mango, grapes, cherries, strawberries. Containers even change "
                 "(metal trays at 06:12, teal crates later).",
                 "Raw frames from data/raw/images/6462. Red = empty/low marked by eye for this slide.")
    save(img, "a2_opening_vs_midday_6462.jpg")


EMPTY_TILES = [  # (area_id, ts, short english label) - empty surfaces, checked by eye
    ("6462_7", 1751001155, "red grapes"),
    ("6462_5", 1751001155, "grapes 500 g"),
    ("6215_2", 1751001268, "bananas"),
    ("6594_7", 1751001189, "garlic 250 g"),
    ("6781_10", 1751013921, "red potatoes"),
    ("6383_4", 1751029430, "Portuguese cabbage"),
    ("6491_7", 1751048611, "nectarines"),
]
FULL_TILES = [  # same idea, stocked
    ("6462_2", 1751028563, "mangoes"),
    ("6215_10", 1751009590, "Madeira bananas"),
    ("6376_6", 1751029801, "limes"),
    ("6443_1", 1751028789, "round tomatoes"),
    ("6594_10", 1751029354, "red onions"),
    ("6781_3", 1751029808, "potatoes 3 kg"),
    ("6491_1", 1751029202, "apricots"),
]


def tile_grid(rows, quads, size=210):
    label_h, gap = 34, 10
    out_rows = []
    for tiles in rows:
        row = Image.new("RGB", (len(tiles) * (size + gap) - gap, size + label_h), PAPER)
        d = ImageDraw.Draw(row)
        for i, (area_id, ts, label) in enumerate(tiles):
            cam = area_id.split("_")[0]
            crop = Image.fromarray(warp(frame(cam, ts), quads[area_id], size))
            x = i * (size + gap)
            row.paste(crop, (x, 0))
            d.text((x + size // 2, size + 6), label, font=font(19), fill=INK, anchor="ma")
        out_rows.append(row)
    return out_rows


def a3_surfaces(quads):
    empty_row, full_row = tile_grid([EMPTY_TILES, FULL_TILES], quads)
    margin, head, band = 32, 120, 52
    w = empty_row.width + 2 * margin
    h = head + band + empty_row.height + band + full_row.height + 56
    canvas = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((margin, 26), "Empty looks the same everywhere. Products don't.", font=font(40), fill=INK)
    d.text((margin, 78), "Planogram areas from 7 different cameras, warped to squares. "
                         "The label is the product the planogram expects.",
           font=font(24, bold=False), fill=MUTED)
    y = head
    d.text((margin, y + 12), "EMPTY: crates, metal trays, banana displays, wicker, foam liners repeat "
                             "under every product", font=font(24), fill=EMPTY)
    y += band
    canvas.paste(empty_row, (margin, y))
    y += empty_row.height
    d.text((margin, y + 12), "STOCKED: every product looks different", font=font(24), fill=OKC)
    y += band
    canvas.paste(full_row, (margin, y))
    d.text((margin, h - 44), "So 'surface vs product' can be learnt from the whole store without one label. "
                             "Raw crops, no model output.", font=font(18, bold=False), fill=MUTED)
    save(canvas, "a3_surfaces_repeat.jpg")


def a4_depletion(quads):
    frames = sorted(int(p.stem) for p in (RAW / "images" / "6491").glob("*.jpg"))
    frames = [t for t in frames if t >= 1751005570]  # from the first restock (07:26)
    size, gap, label_h, margin, head = 150, 6, 30, 32, 120
    rows = []
    for area_id, name in (("6491_5", "Nectarines, area 5"), ("6491_7", "Nectarines, area 7")):
        row = Image.new("RGB", (len(frames) * (size + gap) - gap, size + label_h), PAPER)
        d = ImageDraw.Draw(row)
        for i, ts in enumerate(frames):
            crop = Image.fromarray(warp(frame("6491", ts), quads[area_id], size))
            row.paste(crop, (i * (size + gap), 0))
            d.text((i * (size + gap) + size // 2, size + 5), hhmm(ts), font=font(18), fill=INK, anchor="ma")
        rows.append((name, row))
    band = 46
    w = rows[0][1].width + 2 * margin
    h = head + sum(band + r.height for _, r in rows) + 56
    canvas = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((margin, 26), "One camera, one day: the shelf tells you when it will run out",
           font=font(40), fill=INK)
    d.text((margin, 78), "Camera 6491, nectarine areas, roughly hourly from the first restock to closing.",
           font=font(24, bold=False), fill=MUTED)
    y = head
    for name, row in rows:
        d.text((margin, y + 10), name, font=font(24), fill=INK)
        y += band
        canvas.paste(row, (margin, y))
        y += row.height
    d.text((margin, h - 44), "Raw crops. The fill curve over these frames drives the "
                             "'empty in ~N min' hint and restock forecasting.",
           font=font(18, bold=False), fill=MUTED)
    save(canvas, "a4_depletion_6491_nectarines.jpg")


def a5_occluders(quads):
    shots = [("6383", 1751001156, "chiller night blind"),
             ("6491", 1751005570, "restocking trolley"),
             ("6215", 1751009590, "pallet of pineapples"),
             ("6383", 1751048924, "shopper's trolley")]
    panels, caps = [], []
    for cam, ts, cap in shots:
        panels.append(annotated_frame(cam, ts, quads, {}, scale=0.36))
        caps.append(f"{cam}  {hhmm(ts)}  {cap}")
    img = titled(panels, caps,
                 "What actually blocks the view in this dataset",
                 "Hourly snapshots: shoppers are rare; covers, trolleys and restocking are the real occluders.",
                 "Raw frames; white = planogram areas.")
    save(img, "a5_occluders.jpg")


def main():
    quads, _ = load_quads()
    a1_planogram_broken(quads)
    a2_opening(quads)
    a3_surfaces(quads)
    a4_depletion(quads)
    a5_occluders(quads)


if __name__ == "__main__":
    main()

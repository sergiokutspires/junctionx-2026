"""Build the 'moments of the day' strips for the pitch from raw camera frames.

Every panel is a real crop of a real frame (data/raw/images/<cam>/<unix ts>.jpg, Lisbon time = UTC+1)
with the planogram quadrilateral of the area drawn on it. The status chips (FULL / HALF / EMPTY / WRONG)
come from the AI answer key (data/labels/teacher_labels_v2.json, three labellers per area, see
votes_v2.json / votes_round1.json); nothing here is model output and nothing touches the submission.
Every quoted time/status is checked against the key before a picture is drawn; the script stops if the key
disagrees, and the "N labellers agree" note on each picture is computed from the votes, not typed.

Usage (project root):   .venv/Scripts/python pitch/assets/make_stories.py [--check]
Writes (1600 px wide, all in pitch/assets):
  story_emptying.jpg            bananas, camera 6215 area 6: full 12:59, bare 15:14, bare at the last picture 18:35
  story_wrong_product.jpg       camera 6215 areas 3+5: oranges in banana crates 06:14 and 07:23, fixed by 08:33
  story_restock.jpg             bananas, camera 6215 area 4: empty 14:08, refilled by 15:14, one bunch left 17:24
  story_emptying_tomato.jpg     alternative: plum tomatoes, camera 6443 area 11: full 10:33, half 11:38, nearly bare 12:39
  story_restock_morning.jpg     whole gondola, camera 6491: bare 06:14, restock trolley in view 07:26, stocked 08:40
  story_wrong_product_6468.jpg  alternative: camera 6468 area 12, passion fruit in the banana slot, fixed by 09:38
--check only verifies the key (no pictures are written).
"""
import datetime
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent
CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")
TZ = datetime.timezone(datetime.timedelta(hours=1))  # Lisbon summer time (WEST)
CHECK_ONLY = "--check" in sys.argv

# colours: same tokens as pitch/slides.html
PAPER = (251, 250, 246)
INK = (20, 23, 28)
MUTED = (68, 75, 85)
LINE = (207, 211, 217)
OK = (10, 107, 69)
EMPTY = (179, 71, 0)
WRONG = (143, 42, 107)
HALF = (138, 97, 0)
WHITE = (255, 255, 255)
STATUS = {"full": (OK, "FULL"), "half": (HALF, "HALF"), "empty": (EMPTY, "EMPTY"), "wrong": (WRONG, "WRONG"),
          "ok": (OK, "OK")}

W = 1600
MARGIN = 40


def font(size, bold=True):
    for name in (("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


# ----------------------------------------------------------------------------- data
def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


KEY = _json("data/labels/teacher_labels_v2.json")
VOTES = {**_json("data/labels/votes_round1.json"), **_json("data/labels/votes_v2.json")}
PLAN = _json("data/raw/planogram.json")
QUADS, NAMES = {}, {}
for _sec in PLAN.values():
    for _cam, _d in _sec["cameras"].items():
        for _a in _d["products"]:
            QUADS[_a["area_id"]] = [tuple(_a["image_coordinates"][c]) for c in CORNERS]
            NAMES[_a["area_id"]] = _a["product_name"]


def hhmm(ts):
    return datetime.datetime.fromtimestamp(int(ts), TZ).strftime("%H:%M")


# unix timestamps of every frame in the key: cam -> {"hh:mm": ts}
T = {cam: {hhmm(int(k.split(".")[0])): int(k.split(".")[0]) for k in KEY[cam]} for cam in KEY}


def frame(cam, ts):
    return Image.open(RAW / "images" / cam / f"{ts}.jpg").convert("RGB")


def verify(cam, t, area, stock=None, compliant=None):
    """Check the key says what the picture will claim. Returns the number of labellers that all agree
    (3) or 0 when they do not agree on the checked field."""
    ts = T[cam][t]
    lab = KEY[cam][f"{ts}.jpg"][area]
    if stock is not None and lab["stock_level"] != stock:
        raise SystemExit(f"key disagrees: {cam} {t} {area} stock is {lab['stock_level']}, story says {stock}")
    if compliant is not None and lab["planogram_compliant"] != compliant:
        raise SystemExit(f"key disagrees: {cam} {t} {area} compliant is {lab['planogram_compliant']}")
    votes = VOTES.get(f"{cam}|{ts}.jpg|{area}", [])
    field, want = ("stock_level", stock) if stock is not None else ("compliant", compliant)
    agree = votes and all(v[field] == want for v in votes)
    return len(votes) if agree else 0


def agree_note(results):
    """results: list of verify() outputs, one per panel."""
    n, full = len(results), sum(1 for r in results if r == 3)
    if full == n:
        return f"3 labellers agree on all {n} panels"
    return f"3 labellers agree on {full} of {n} panels, 2 of 3 on the rest"


# ----------------------------------------------------------------------------- drawing
def union_box(areas):
    pts = [p for a in areas for p in QUADS[a]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def crop_panel(cam, ts, focus, outlines, pw, ph, wfac, dx=0.0, dy=0.0, win_w=None, lw=1.0, tags=()):
    """Crop a pw x ph panel around the areas in `focus`; draw the quad of every (area, colour) in outlines.
    win_w overrides the window width (pixels of the original frame); the window never leaves the frame."""
    x0, y0, x1, y1 = union_box(focus)
    w = win_w or (x1 - x0) * wfac
    h = w * ph / pw
    if h > 720:                       # keep the aspect ratio but stay inside the 1280 x 720 frame
        w, h = w * 720 / h, 720
    if w > 1280:
        w, h = 1280, 1280 * ph / pw
    cx, cy = (x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy
    bx0 = min(max(cx - w / 2, 0), 1280 - w)
    by0 = min(max(cy - h / 2, 0), 720 - h)
    box = (bx0, by0, bx0 + w, by0 + h)
    im = frame(cam, ts).crop(tuple(int(round(v)) for v in box)).resize((pw, ph), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))
    sc = pw / w
    d = ImageDraw.Draw(im)
    for area, colour in outlines:
        q = [((x - box[0]) * sc, (y - box[1]) * sc) for x, y in QUADS[area]]
        d.polygon(q, outline=WHITE, width=max(3, round(11 * lw)))
        d.polygon(q, outline=colour, width=max(2, round(6 * lw)))
    for x, y, text in tags:           # small dark labels pinned to a point of the original frame
        tx, ty = (x - box[0]) * sc, (y - box[1]) * sc
        f = font(26)
        half = d.textlength(text, font=f) / 2 + 14
        tx = min(max(tx, half + 4), pw - half - 4)
        d.rounded_rectangle([tx - half, ty - 21, tx + half, ty + 21], radius=10, fill=INK)
        d.text((tx, ty), text, font=f, fill=WHITE, anchor="mm")
    return im


def chip(draw, xy, text, colour, f, padx=22, pady=8):
    box = draw.textbbox(xy, text, font=f, anchor="mm")
    draw.rounded_rectangle([box[0] - padx, box[1] - pady, box[2] + padx, box[3] + pady], radius=14, fill=colour)
    draw.text(xy, text, font=f, fill=WHITE, anchor="mm")


def fit_text(draw, text, max_w, start, bold=True, min_size=14):
    size = start
    while size > min_size and draw.textlength(text, font=font(size, bold)) > max_w:
        size -= 1
    return font(size, bold)


def chevron(draw, cx, cy, r=14, colour=MUTED):
    draw.polygon([(cx - r // 2, cy - r), (cx + r // 2 + 2, cy), (cx - r // 2, cy + r)], fill=colour)


def strip(name, kicker, kicker_colour, headline, sub, panels, caption, source, ph, gap, wfac, focus,
          chip_size=38, dx=0.0, dy=0.0, win_w=None, lw=1.0):
    """panels: list of dicts(cam, t 'hh:mm', outlines [(area, status)], chip (status key), chip_text)."""
    if CHECK_ONLY:
        print("checked", name)
        return None
    n = len(panels)
    inner = W - 2 * MARGIN
    pw = (inner - gap * (n - 1)) // n
    left = (W - (n * pw + (n - 1) * gap)) // 2
    head_h = 226
    time_h, chip_h, cap_h, src_h = 100, 76, 66, 40
    H = head_h + ph + 12 + time_h + chip_h + cap_h + src_h + 20
    canvas = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(canvas)

    # header
    d.rectangle([0, 0, W, 10], fill=kicker_colour)
    d.text((MARGIN, 30), kicker, font=fit_text(d, kicker, inner, 30), fill=kicker_colour)
    d.text((MARGIN, 66), headline, font=fit_text(d, headline, inner, 68), fill=INK)
    d.text((MARGIN, 156), sub, font=fit_text(d, sub, inner, 30, bold=False), fill=MUTED)

    # panels
    y0 = head_h
    for i, p in enumerate(panels):
        x = left + i * (pw + gap)
        ts = T[p["cam"]][p["t"]]
        colour = STATUS[p["chip"]][0]
        outlines = [(a, STATUS[s][0]) for a, s in p["outlines"]]
        im = crop_panel(p["cam"], ts, focus, outlines, pw, ph, wfac, p.get("dx", dx), p.get("dy", dy),
                        p.get("win_w", win_w), lw, p.get("tags", ()))
        d.rounded_rectangle([x - 7, y0 - 7, x + pw + 7, y0 + ph + 7], radius=14, fill=colour)
        canvas.paste(im, (x, y0))
        ring = Image.new("L", (pw, ph), 255)             # round the photo corners inside the coloured frame
        ImageDraw.Draw(ring).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=8, fill=0)
        canvas.paste(Image.new("RGB", (pw, ph), colour), (x, y0), ring)
        tx = x + pw // 2
        d.text((tx, y0 + ph + 12 + time_h // 2), hhmm(ts), font=font(92), fill=INK, anchor="mm")
        text = p.get("chip_text") or STATUS[p["chip"]][1]
        chip(d, (tx, y0 + ph + 12 + time_h + chip_h // 2 - 4), text, colour, font(chip_size))
        if i < n - 1:
            chevron(d, x + pw + gap // 2, y0 + ph // 2)

    # caption + source
    cy = y0 + ph + 12 + time_h + chip_h + 14
    d.line([(MARGIN, cy), (W - MARGIN, cy)], fill=LINE, width=2)
    d.text((MARGIN, cy + 14), caption, font=fit_text(d, caption, inner, 34), fill=INK)
    d.text((MARGIN, H - 38), source, font=fit_text(d, source, inner, 20, bold=False), fill=MUTED)
    path = OUT / name
    canvas.save(path, quality=92, optimize=True)
    print("wrote", path.relative_to(ROOT), canvas.size, f"{path.stat().st_size // 1024} KB")
    return canvas


def source_line(cam, note):
    return f"Real frames from camera {cam}, Lisbon time. Status from the AI answer key: {note}. Not model output."


# ----------------------------------------------------------------------------- stories
def stock_panels(cam, area, times, stocks):
    res = [verify(cam, t, area, stock=s, compliant=None) for t, s in zip(times, stocks)]
    panels = [dict(cam=cam, t=t, outlines=[(area, s)], chip=s) for t, s in zip(times, stocks)]
    return panels, res


def story_emptying():
    cam, area = "6215", "6215_6"
    times, stocks = ["08:33", "12:59", "15:14", "18:35"], ["full", "full", "empty", "empty"]
    panels, res = stock_panels(cam, area, times, stocks)
    verify(cam, "14:08", area, stock="full")          # the caption quotes this picture
    strip("story_emptying.jpg",
          "EMPTYING   camera 6215, area 6, bananas (BANANA CAT I)", EMPTY,
          "Full at 12:59, bare by 15:14",
          "One banana area, four pictures of the same day. Not refilled before the last picture of the day.",
          panels,
          "Bananas, area 6: stocked at 14:08, bare at 15:14, and still bare at the last picture (18:35).",
          source_line(cam, agree_note(res)),
          350, 44, 1.6, [area])


def story_wrong_product():
    cam, areas = "6215", ["6215_3", "6215_5"]
    times, comp = ["06:14", "07:23", "08:33"], [False, False, True]
    res = [verify(cam, t, a, compliant=c) for t, c in zip(times, comp) for a in areas]
    panels = [
        dict(cam=cam, t="06:14", outlines=[(a, "wrong") for a in areas], chip="wrong", chip_text="ORANGES, NOT BANANAS"),
        dict(cam=cam, t="07:23", outlines=[(a, "wrong") for a in areas], chip="wrong", chip_text="STILL ORANGES"),
        dict(cam=cam, t="08:33", outlines=[(a, "ok") for a in areas], chip="ok", chip_text="BANANAS: FIXED"),
    ]
    strip("story_wrong_product.jpg",
          "WRONG PRODUCT   camera 6215, areas 3 and 5", WRONG,
          "06:14: oranges in the banana crates",
          "The planogram says BANANA CAT I in both areas. The camera sees loose oranges in teal crates.",
          panels,
          "Wrong at 06:14 and still at 07:23, corrected by 08:33: the camera sees the mismatch and the fix.",
          source_line(cam, agree_note(res)),
          340, 56, 1.3, areas, chip_size=35, dx=-42)


def story_restock():
    cam, area = "6215", "6215_4"
    times, stocks = ["12:59", "14:08", "15:14", "17:24"], ["half", "empty", "full", "empty"]
    panels, res = stock_panels(cam, area, times, stocks)
    strip("story_restock.jpg",
          "RESTOCK   camera 6215, area 4, bananas (BANANA CAT I)", OK,
          "Empty at 14:08, refilled by 15:14",
          "Four pictures of one banana area: the gap opens, the gap is closed, and the shelf drains again.",
          panels,
          "Area 4 was bare at 14:08, refilled within 66 minutes, and down to one bunch by 17:24.",
          source_line(cam, agree_note(res)),
          350, 44, 1.6, [area])


def story_emptying_tomato():
    cam, area = "6443", "6443_11"
    times, stocks = ["10:33", "11:38", "12:39", "18:07"], ["full", "half", "empty", "empty"]
    panels, res = stock_panels(cam, area, times, stocks)
    strip("story_emptying_tomato.jpg",
          "RUNNING OUT   camera 6443, area 11, plum tomatoes (TOMATE CHUCHA)", EMPTY,
          "Full at 10:33, nearly bare by 12:39",
          "Half full at 11:38 is the early warning. After 12:39 only a handful is left for the rest of the day.",
          panels,
          "Tomatoes, area 11: full at 10:33, half at 11:38, almost nothing at 12:39, and no refill by 18:07.",
          source_line(cam, agree_note(res)),
          350, 44, 1.6, [area])


def story_restock_morning():
    cam = "6491"
    areas = [f"6491_{i}" for i in range(1, 11)]
    times = ["06:14", "07:26", "08:40"]
    panels = []
    for t, key in zip(times, ("empty", "half", "full")):
        ts = T[cam][t]
        levels = [KEY[cam][f"{ts}.jpg"][a]["stock_level"] for a in areas]
        stocked = sum(1 for lv in levels if lv == "full")
        text = {"empty": f"{levels.count('empty')} OF 10 EMPTY", "half": f"{stocked} OF 10 FULL",
                "full": f"{stocked} OF 10 FULL"}[key]
        panels.append(dict(cam=cam, t=t, outlines=list(zip(areas, levels)), chip=key, chip_text=text))
    panels[1]["tags"] = [(1130, 350, "TROLLEY")]
    still = sum(1 for a in areas if KEY[cam][f"{T[cam]['07:26']}.jpg"][a]["stock_level"] != "full")
    strip("story_restock_morning.jpg",
          "RESTOCK   camera 6491, the whole gondola (nectarines, peaches, apricots)", OK,
          "Bare at 06:14, stocked by 08:40",
          f"A trolley loaded with a crate of fruit is in the picture at 07:26; {still} of 10 areas still wait.",
          panels,
          "A whole gondola from bare crates to full: the camera catches the restock under way, not just the result.",
          "Real frames from camera 6491, Lisbon time. Outline colour = stock level from the AI answer key. Not model output.",
          300, 44, 1.0, areas, win_w=1180, dx=250, lw=0.45)


def story_wrong_product_6468():
    cam, area = "6468", "6468_12"
    times, comp = ["06:12", "07:29", "08:37", "09:38"], [False, False, False, True]
    res = [verify(cam, t, area, compliant=c) for t, c in zip(times, comp)]
    panels = [dict(cam=cam, t=t, outlines=[(area, "wrong")], chip="wrong", chip_text="PASSION FRUIT") for t in times[:3]]
    panels[1]["chip_text"] = "STILL WRONG"
    panels[2]["chip_text"] = "STILL WRONG"
    panels.append(dict(cam=cam, t="09:38", outlines=[(area, "ok")], chip="ok", chip_text="BANANAS: FIXED"))
    strip("story_wrong_product_6468.jpg",
          "WRONG PRODUCT   camera 6468, area 12", WRONG,
          "06:12: passion fruit in the banana slot",
          "The planogram says BANANA PAO (cooking banana). The camera sees dark purple passion fruit until 08:37.",
          panels,
          "A second camera, the same pattern: wrong at opening, corrected by 09:38.",
          source_line(cam, agree_note(res)),
          340, 44, 2.4, [area], chip_size=30)


def main():
    story_emptying()
    story_wrong_product()
    story_restock()
    story_emptying_tomato()
    story_restock_morning()
    story_wrong_product_6468()


if __name__ == "__main__":
    main()

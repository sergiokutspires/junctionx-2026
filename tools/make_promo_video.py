"""fresh. product film (40-48 s, silent, Apple-style: motion + focus, few words).

  .venv/Scripts/python tools/make_promo_video.py [--version public|local|both] [--no-shots]

public -> outputs/pop/fresh_film_public.mp4 (PIXELATED builds only: site_final/app, site_final/day, site_final)
local  -> outputs/pop/fresh_film_local.mp4  (sharp builds rehearsal_final/dashboard, day_replay/dashboard; never post)
After a successful verify each film is copied over outputs/pop/fresh_demo_<version>.mp4 (old one kept as *_prev.mp4).
Screenshots: headless Edge at 1920x1080, device scale 2 (3840x2160) through outputs/shot_harness.html
served at http://127.0.0.1:8765/. Frames are composed with numpy/cv2 (camera moves, spotlight, captions).
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
POP = OUT / "pop"
SHOTS = POP / "film_shots"
HARNESS = "http://127.0.0.1:8765/shot_harness.html"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W, H, FPS = 1920, 1080, 30
SW, SH = 1920, 1080  # css window of the screenshots (x2 pixels)

SOURCES = {
    "public": {"site": "site_final", "app": "site_final/app", "day": "site_final/day"},
    "local": {"site": "site_final", "app": "rehearsal_final/dashboard", "day": "day_replay/dashboard"},
}
SHOTS_SPEC = {
    "tasks": ("app", "#/tasks", None),
    "tap": ("app", "#/tasks", "#counters .s-empty"),
    "gondola": ("app", "#/gondola/6215/6215_7", None),
    "day2": ("day", "#/day/0615/6215/6215_3", None, 450),  # scrolled so the whole camera picture fits
    "insights": ("app", "#/insights", None),
    "hero": ("site", "", None),
}


def shot(url, png):
    png.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="fresh_film_") as prof:
        cmd = [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
               "--no-first-run", "--virtual-time-budget=6000", f"--window-size={SW},{SH}",
               "--force-device-scale-factor=2", f"--screenshot={png}", url]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        except subprocess.TimeoutExpired:
            return False
    return png.exists() and png.stat().st_size > 0


def shot_ok(png, colours=True):
    """A page that lost its stylesheet renders unstyled (blue links, no tiles): retry those."""
    im = cv2.imread(str(png))
    if im is None:
        return False
    small = cv2.resize(im, (192, 108))
    beige = np.all(np.abs(small.astype(int) - np.array([0xE6, 0xF0, 0xF5])) < 8, axis=2).mean()
    sat = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[..., 1]
    green = np.all(np.abs(small.astype(int) - np.array([0x49, 0x84, 0x1E])) < 30, axis=2).mean()
    orange = np.all(np.abs(small.astype(int) - np.array([0x0E, 0x44, 0xC9])) < 40, axis=2).mean()
    blue_unstyled = np.all(np.abs(small.astype(int) - np.array([238, 0, 0])) < 40, axis=2).mean()
    return (beige > 0.25 and (sat > 90).mean() > 0.01 and blue_unstyled < 0.002
            and (not colours or (green + orange) > 0.003))


def take_shots(versions):
    SHOTS.mkdir(parents=True, exist_ok=True)
    jobs = []
    for v in versions:
        for name, spec in SHOTS_SPEC.items():
            src, route, click = spec[:3]
            q = {"app": SOURCES[v][src], "w": SW, "h": SH}
            if len(spec) > 3:
                q["y"] = spec[3]
            if route:
                q["route"] = route
            if click:
                q["click"] = click
            jobs.append((HARNESS + "?" + urllib.parse.urlencode(q), SHOTS / f"{v}_{name}.png"))

    def run(job):
        url, png = job
        col = not any(k in png.name for k in ("insights", "hero"))
        for _ in range(5):
            shot(url, png)
            if shot_ok(png, col):
                return True
        return False

    with ThreadPoolExecutor(4) as ex:
        ok = list(ex.map(run, jobs))
    return all(ok)


# ------------------------------------------------------------------ composition
BEIGE = (0xF5, 0xF0, 0xE6)
INK = (0x1D, 0x1D, 0x1F)
MUTED = (0x6E, 0x6A, 0x63)
MAGENTA = (0xC3, 0x21, 0x72)
FONT_BLACK = "C:/Windows/Fonts/seguibl.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
LOGO = ROOT / "brand" / "fresh_logo_1024.png"
URL = "sergiokutspires.github.io/junctionx-2026"
XFADE = 0.35


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_out_back(t):
    t = min(max(t, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def load(v, name):
    return cv2.imread(str(SHOTS / f"{v}_{name}.png"))


def view(src, cx, cy, w):
    """Crop a 16:9 window of width w (source px) centred on (cx, cy), resized to the output size."""
    sh, sw = src.shape[:2]
    w = min(w, sw)
    h = w * 9 / 16
    x0 = min(max(cx - w / 2, 0), sw - w)
    y0 = min(max(cy - h / 2, 0), sh - h)
    M = np.float32([[W / w, 0, -x0 * W / w], [0, H / h, -y0 * H / h]])
    interp = cv2.INTER_AREA if w > W else cv2.INTER_CUBIC
    return cv2.warpAffine(src, M, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE), (x0, y0, w / W)


def to_out(rect, geo):
    x0, y0, s = geo
    return ((rect[0] - x0) / s, (rect[1] - y0) / s, (rect[2] - x0) / s, (rect[3] - y0) / s)


def spotlight(frame, rect, amount):
    """Dim everything outside a soft rounded rectangle (rect in output px) by up to 55 %."""
    if amount <= 0:
        return frame
    q = 4
    m = np.zeros((H // q, W // q), np.float32)
    x0, y0, x1, y1 = [int(round(c / q)) for c in rect]
    r = 6
    cv2.rectangle(m, (x0 + r, y0), (x1 - r, y1), 1.0, -1)
    cv2.rectangle(m, (x0, y0 + r), (x1, y1 - r), 1.0, -1)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
        cv2.circle(m, (cx, cy), r, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), 3)
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    k = 1 - 0.55 * amount * (1 - m)
    return (frame.astype(np.float32) * k).astype(np.uint8)


_cap_cache = {}


def caption_img(text):
    if text not in _cap_cache:
        f = ImageFont.truetype(FONT_BLACK, 58)
        tw = f.getbbox(text)[2]
        pw, ph = tw + 130, 112
        im = Image.new("RGBA", (pw + 40, ph + 44), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((20, 26, 20 + pw, 26 + ph), radius=ph // 2, fill=(0, 0, 0, 45))  # soft shadow
        d.rounded_rectangle((20, 20, 20 + pw, 20 + ph), radius=ph // 2, fill=(255, 255, 255, 255))
        d.ellipse((58, 20 + ph // 2 - 10, 78, 20 + ph // 2 + 10), fill=MAGENTA + (255,))
        tx = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(tx).text((98, 20 + ph // 2), text, font=f, fill=INK + (255,), anchor="lm")
        a = np.array(im).astype(np.float32)
        b = np.array(tx).astype(np.float32)
        _cap_cache[text] = (a[..., [2, 1, 0]], a[..., 3:] / 255.0, b[..., [2, 1, 0]], b[..., 3:] / 255.0, 20, 20 + ph)
    return _cap_cache[text]


def put_caption(frame, text, t, dur, pos="bl"):
    """Opaque pill pops in within 0.12 s, then the text slides up inside the (clipped) pill;
    everything fades out over the last 0.25 s. pos: bl / br / tl / tr."""
    rgb, al, trgb, tal, py0, py1 = caption_img(text)
    out_a = 1 - ease((t - (dur - 0.25)) / 0.25)
    pa = ease(t / 0.12) * out_a
    if pa <= 0:
        return frame
    ta = ease((t - 0.05) / 0.35) * out_a
    dy = int(46 * (1 - ease((t - 0.05) / 0.4)))
    h, w = rgb.shape[:2]
    x = 80 if pos[1] == "l" else W - 80 - w
    y = H - 70 - h if pos[0] == "b" else 50
    # text layer shifted down by dy, clipped to the pill rows
    sh_rgb = np.zeros_like(trgb)
    sh_al = np.zeros_like(tal)
    if dy < h:
        sh_rgb[dy:] = trgb[:h - dy]
        sh_al[dy:] = tal[:h - dy]
    sh_al[:py0] = 0
    sh_al[py1:] = 0
    out = frame.astype(np.float32)
    reg = out[y:y + h, x:x + w]
    aa = al * pa
    reg = reg * (1 - aa) + rgb * aa
    ta_ = sh_al * ta
    reg = reg * (1 - ta_) + sh_rgb * ta_
    out[y:y + h, x:x + w] = reg
    return out.astype(np.uint8)


def pil_bgr(im):
    return cv2.cvtColor(np.array(im.convert("RGB")), cv2.COLOR_RGB2BGR)


_logo = None


def logo_card(t, dur, tagline=True, url=False):
    global _logo
    if _logo is None:
        _logo = Image.open(LOGO).convert("RGBA")
    im = Image.new("RGB", (W, H), BEIGE)
    s = 0.35 + 0.65 * ease_out_back(t / 0.7)
    size = max(8, int(340 * s))
    cy = 400
    lg = _logo.resize((size, size), Image.LANCZOS)
    im.paste(lg, (W // 2 - size // 2, cy - size // 2), lg)
    d = ImageDraw.Draw(im, "RGBA")
    if tagline:
        a = int(255 * ease((t - 0.6) / 0.6))
        dy = int(30 * (1 - ease((t - 0.6) / 0.6)))
        f = ImageFont.truetype(FONT_BLACK, 76)
        d.text((W // 2, 700 + dy), "See every shelf.", font=f, fill=INK + (a,), anchor="mm")
        d.text((W // 2, 800 + dy), "Fix what matters first.", font=f, fill=INK + (a,), anchor="mm")
    if url:
        a = int(255 * ease((t - 0.5) / 0.6))
        f = ImageFont.truetype(FONT_BLACK, 70)
        d.text((W // 2, 690), "Try it.", font=f, fill=INK + (a,), anchor="mm")
        f2 = ImageFont.truetype(FONT_BOLD, 54)
        d.text((W // 2, 790), URL, font=f2, fill=MAGENTA + (a,), anchor="mm")
        a2 = int(255 * ease((t - 1.1) / 0.6))
        f3 = ImageFont.truetype(FONT_BOLD, 38)
        d.text((W // 2, 930), "NovaLotus", font=f3, fill=MUTED + (a2,), anchor="mm")
    return pil_bgr(im)


def cost_card(t, dur):
    im = Image.new("RGB", (W, H), BEIGE)
    d = ImageDraw.Draw(im, "RGBA")
    a = int(255 * ease(t / 0.3))
    sc = 0.6 + 0.4 * ease_out_back(t / 0.55)
    f = ImageFont.truetype(FONT_BLACK, max(10, int(220 * sc)))
    d.text((W // 2, 400), "$0.00005", font=f, fill=INK + (a,), anchor="mm")
    a1 = int(255 * ease((t - 0.35) / 0.4))
    f2 = ImageFont.truetype(FONT_BLACK, 66)
    d.text((W // 2, 580), "per image", font=f2, fill=MAGENTA + (a1,), anchor="mm")
    a2 = int(255 * ease((t - 0.9) / 0.4))
    dy2 = int(30 * (1 - ease((t - 0.9) / 0.4)))
    f3 = ImageFont.truetype(FONT_BOLD, 52)
    d.text((W // 2, 760 + dy2), "One CPU core.  No GPU.", font=f3, fill=INK + (a2,), anchor="mm")
    a3 = int(255 * ease((t - 1.6) / 0.4))
    dy3 = int(30 * (1 - ease((t - 1.6) / 0.4)))
    d.text((W // 2, 860 + dy3), "~$3/month per 14-camera section", font=f3, fill=MUTED + (a3,), anchor="mm")
    return pil_bgr(im)


def tile_boxes(img):
    """The four solid status tiles, found by their colours in the top 60 % (source px)."""
    top = img[: int(img.shape[0] * 0.6)]
    cols = {"empty": (0x0E, 0x44, 0xC9), "low": (0x00, 0xA0, 0xF2), "wrong": (0xB5, 0x36, 0x9C), "ok": (0x49, 0x84, 0x1E)}
    boxes = {}
    for k, c in cols.items():
        m = np.all(np.abs(top.astype(int) - np.array(c)) < 28, axis=2).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        x, y, w, h = (int(z) for z in st[i, :4])
        boxes[k] = (x, y, x + w, y + h)
    return boxes


def union(*rs, pad=0):
    return (min(r[0] for r in rs) - pad, min(r[1] for r in rs) - pad,
            max(r[2] for r in rs) + pad, max(r[3] for r in rs) + pad)


def build_scenes(v):
    tasks, tap, gond, day, ins, hero = (load(v, n) for n in ("tasks", "tap", "gondola", "day2", "insights", "hero"))
    tb = tile_boxes(tasks)
    row = union(*tb.values())
    dy = row[1] - 252  # the public build sits lower (privacy banner)
    gdy = tile_boxes(gond)["empty"][1] - 252
    pic_g = (766, 1058 + gdy, 2232, 1990 + gdy)
    det_g = (2268, 1150 + gdy, 3076, 2160)
    card1 = (768, 1236 + dy, 1534, 2160)
    card2 = (1560, 1236 + dy, 2262, 2160)
    dt = tile_boxes(day)["empty"]
    pic_d = (dt[0] + 42, dt[1] + 408, dt[0] + 1338, dt[1] + 1230)  # camera 6215 picture (scrolled shot)
    crate = (dt[0] + 380, dt[1] + 1060)  # middle of the empty (red-orange) + wrong-product (purple) rows
    ib = (770, 1010 + dy, 1910, 1780 + dy)
    rcx, rcy = (row[0] + row[2]) / 2, (row[1] + row[3]) / 2
    TW = 2500  # tight framing on the tile row (the four tiles fill ~92 % of the width)

    S = []

    # 1. logo alone + tagline
    S.append((3.0, lambda t, d: logo_card(t, d), None))

    # 2. 06:14 in the day replay: from the whole page into the crate rows of camera 6215
    def s_day(t, d):
        u = ease((t - 0.2) / (d - 1.4))
        c0 = (1900, 1080, 3840)
        c1 = (crate[0] + 30, crate[1] - 60, 1920)
        cx, cy, w = lerp(c0, c1, u)
        f, geo = view(day, cx, cy, w)
        return spotlight(f, to_out(union(pic_d, pad=10), geo), ease((t - 1.6) / 0.8))
    S.append((5.5, s_day, [(0.3, 2.6, "06:14. Before opening.", "br"), (2.8, 5.5, "The camera sees it.", "br")]))

    # 3. the four solid tiles land one by one (tight on the tile row)
    blank = tasks.copy()
    rr = union(row, pad=8)
    blank[rr[1]:rr[3], rr[0]:rr[2]] = np.array(BEIGE[::-1], np.uint8)
    order = ["empty", "low", "wrong", "ok"]

    def s_tiles(t, d):
        img = blank.copy()
        for i, k in enumerate(order):
            p = ease((t - 0.5 - 0.3 * i) / 0.45)
            if p <= 0:
                continue
            x0, y0, x1, y1 = tb[k]
            x0, y0, x1, y1 = x0 - 6, y0 - 6, x1 + 6, y1 + 6
            tile = tasks[y0:y1, x0:x1].astype(np.float32)
            off = int(80 * (1 - p))
            reg = img[y0 + off:y1 + off, x0:x1].astype(np.float32)
            hh = reg.shape[0]
            img[y0 + off:y0 + off + hh, x0:x1] = (reg * (1 - p) + tile[:hh] * p).astype(np.uint8)
        u = ease(t / d)
        f, _ = view(img, rcx, rcy + 330 - 330 * u, 2900 - (2900 - TW) * u)
        return f
    S.append((6.0, s_tiles, [(2.2, 6.0, "Every shelf, colour-coded.")]))

    # 4. tap Vazio: ripple, then the other three fade to tints; then pull back to the shorter list
    vz = tb["empty"]

    def s_tap(t, d):
        u = ease((t - 3.4) / (d - 3.4))
        cx, cy, w = rcx, rcy + 700 * u, TW + 1000 * u
        f, geo = view(tasks if t < 1.0 else tap, cx, cy, w)
        if 1.0 <= t < 1.6:
            g, _ = view(tasks, cx, cy, w)
            a = ease((t - 1.0) / 0.6)
            f = cv2.addWeighted(g, 1 - a, f, a, 0)
        if 0.5 <= t < 1.4:
            ox, oy, _, _ = to_out(((vz[0] + vz[2]) / 2, (vz[1] + vz[3]) / 2, 0, 0), geo)
            p = (t - 0.5) / 0.9
            ov = f.copy()
            cv2.circle(ov, (int(ox), int(oy)), int(30 + 90 * p), (255, 255, 255), -1, cv2.LINE_AA)
            f = cv2.addWeighted(ov, 0.55 * (1 - p), f, 1 - 0.55 * (1 - p), 0)
        return f
    S.append((5.5, s_tap, [(1.7, 5.5, "Tap a colour. See only that.")]))

    # 5. the first task cards: Trocar, then Repor (caption in the dimmed area, top-right)
    def s_cards(t, d):
        u = ease(t / d)
        k = ease((t - 2.8) / 0.7)
        cx = (card1[0] + card2[2]) / 2 + 250 * (1 - k)
        f, geo = view(tasks, cx, (card1[1] + 2160) / 2 - 60, 2600 - 250 * u)
        r = lerp(to_out(union(card1, pad=8), geo), to_out(union(card2, pad=8), geo), k)
        return spotlight(f, r, ease((t - 0.2) / 0.5))
    S.append((6.0, s_cards, [(0.5, 2.9, "Trocar: swap it back.", "tr"), (3.3, 6.0, "Repor: restock.", "tr")]))

    # 6. Gondolas: pins on the camera picture, slow push-in; picture ends above the caption
    def s_gond(t, d):
        u = ease(t / d)
        c0 = ((pic_g[0] + det_g[2]) / 2, (pic_g[1] + pic_g[3]) / 2 - 150, 3300)
        c1 = ((pic_g[0] + pic_g[2]) / 2, (pic_g[1] + pic_g[3]) / 2 + 80, 2400)
        cx, cy, w = lerp(c0, c1, u)
        f, geo = view(gond, cx, cy, w)
        return spotlight(f, to_out(union(pic_g, pad=8), geo), ease((t - 0.8) / 0.8) * (1 - 0.4 * u))
    S.append((6.0, s_gond, [(0.8, 6.0, "Every area, every camera.", "tl")]))

    # 7. Analysis: running out soon (card on the left, caption top-right in the dimmed area)
    def s_ins(t, d):
        u = ease(t / d)
        f, geo = view(ins, (ib[0] + ib[2]) / 2 + 650, (ib[1] + ib[3]) / 2 - 60, 2900 - 500 * u)
        return spotlight(f, to_out(union(ib, pad=10), geo), ease((t - 0.5) / 0.6))
    S.append((5.0, s_ins, [(0.6, 5.0, "Warns before it runs empty.", "tr")]))

    # 8. cost
    S.append((3.5, lambda t, d: cost_card(t, d), None))

    # 9. landing hero: slow push-in from the full page
    def s_hero(t, d):
        u = ease(t / d)
        f, _ = view(hero, 1920, 1080 - 300 * u, 3840 - 1300 * u)
        return f
    S.append((3.0, s_hero, None))

    # 10. end card: logo alone, URL, team
    S.append((3.0, lambda t, d: logo_card(t, d, tagline=False, url=True), None))
    return S


def render(v, path):
    scenes = build_scenes(v)
    total = sum(s[0] for s in scenes) - XFADE * (len(scenes) - 1)
    n = int(round(total * FPS))
    wr = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    starts, acc = [], 0.0
    for d, _, _ in scenes:
        starts.append(acc)
        acc += d - XFADE

    def scene_frame(i, t):
        d, fn, caps = scenes[i]
        f = fn(t, d)
        for cap in caps or []:
            a, b, text = cap[:3]
            pos = cap[3] if len(cap) > 3 else "bl"
            # never overlap a crossfade: start after the incoming one, end before the outgoing one
            if i > 0:
                a = max(a, XFADE + 0.05)
            if i < len(scenes) - 1:
                b = min(b, d - XFADE - 0.1)
            if a <= t < b:
                f = put_caption(f, text, t - a, b - a, pos)
        return f

    for k in range(n):
        T = k / FPS
        act = [i for i, s in enumerate(starts) if s <= T < s + scenes[i][0]] or [len(scenes) - 1]
        if len(act) == 1:
            f = scene_frame(act[0], T - starts[act[0]])
        else:
            i, j = act[0], act[-1]
            a = ease((T - starts[j]) / XFADE)
            f = cv2.addWeighted(scene_frame(i, T - starts[i]), 1 - a, scene_frame(j, T - starts[j]), a, 0)
        wr.write(f)
    wr.release()
    print(f"{v}: rendered {n} frames ({total:.1f} s), scene starts {[round(s, 2) for s in starts]}", flush=True)
    return total


CHECK_T = (2, 6, 12, 18, 24, 30, 36, 40, 44)


def verify(v, path):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    dur = n / fps if fps else 0
    ok = 40 <= dur <= 48
    for t in CHECK_T:
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(t * fps), n - 1))
        r, f = cap.read()
        if not r or f.std() < 3:
            ok = False
            continue
        cv2.imwrite(str(POP / f"film_check_{v}_{t}.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 88])
    cap.release()
    print(f"{v}: {n} frames, {dur:.1f} s, ok={ok}", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["public", "local", "both"], default="both")
    ap.add_argument("--no-shots", action="store_true", help="reuse outputs/pop/film_shots")
    ap.add_argument("--no-copy", action="store_true", help="do not copy over fresh_demo_<version>.mp4")
    a = ap.parse_args()
    versions = ["public", "local"] if a.version == "both" else [a.version]
    if not a.no_shots and not take_shots(versions):
        sys.exit("screenshots failed (is http://127.0.0.1:8765/ serving outputs?)")
    for v in versions:
        out = POP / f"fresh_film_{v}.mp4"
        render(v, out)
        if not verify(v, out):
            print(f"{v}: verify failed, {out.name} NOT copied over the demo video")
        elif not a.no_copy:
            demo = POP / f"fresh_demo_{v}.mp4"
            prev = POP / f"fresh_demo_{v}_prev.mp4"
            if demo.exists() and not prev.exists():
                shutil.copy(demo, prev)
            shutil.copy(out, demo)
            print(f"copied over {demo.name} (previous kept as {demo.stem}_prev.mp4)")


if __name__ == "__main__":
    main()

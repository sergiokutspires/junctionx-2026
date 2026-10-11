"""Rebuild both silent, captioned fresh. demo videos end-to-end from the CURRENT builds (one command).

  .venv/Scripts/python tools/make_demo_video.py                     # both versions, rebuilds outputs/site first
  .venv/Scripts/python tools/make_demo_video.py --version public    # public | local | both
  .venv/Scripts/python tools/make_demo_video.py --no-rebuild        # use outputs/site as it is

  public: outputs/pop/fresh_demo_public.mp4 (+ .webm)  frames from outputs/site (pixelated camera pictures only)
  local:  outputs/pop/fresh_demo_local.mp4             app scenes from the SHARP build (local use only, never post)

Steps: (1) tools/build_site.py rebuilds outputs/site, so the public video shows exactly what is online;
(2) headless Edge screenshots (1920x1080) through outputs/shot_harness.html served at http://127.0.0.1:8765/
(a temporary "python -m http.server 8765 -d outputs" is started if nothing answers there);
(3) captions + title/cost/end cards + crossfades, written with OpenCV (avc1, else mp4v);
(4) check: reopen each file, report frames/duration, save check frames outputs/pop/check_<version>_<t>s.jpg.
Edit SCENES / CAPTIONS below when the website changes; nothing else needs touching.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
POP = OUTPUTS / "pop"
SHOTS = POP / "video_shots"
PORT = 8765
HARNESS = f"http://127.0.0.1:{PORT}/shot_harness.html"
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
W, H, FPS = 1920, 1080, 30
FADE = 0.5            # seconds of crossfade between scenes
WEBM_SIZE, WEBM_FPS = (960, 540), 10   # OpenCV's VP9 encoder is slow: the .webm is a lighter copy

BEIGE = (0xF5, 0xF0, 0xE6)
INK = (0x1D, 0x1D, 0x1F)
MUTED = (0x6E, 0x6A, 0x63)
MAGENTA = (0xC3, 0x21, 0x72)
FONTS = "C:/Windows/Fonts/"

# Which build each version films. The landing hero is always the public site.
SOURCES = {
    "public": {"site": "site", "app": "site/app", "day": "site/day"},
    "local": {"site": "site", "app": "rehearsal_final/dashboard", "day": "day_replay/dashboard"},
}
# name: (source key, route, scroll y, click selector)
SHOTS_SPEC = {
    "hero": ("site", "", None, None),
    "tasks_top": ("app", "#/tasks", None, None),
    "tasks_cards": ("app", "#/tasks", 620, None),
    "gondola": ("app", "#/gondola/6215/6215_7", None, None),
    "products": ("app", "#/products", None, None),
    "insights": ("app", "#/insights", None, None),
    "en": ("app", "#/tasks", None, '[data-act="lang"][data-v="en"]'),
    "day": ("day", "#/day", None, None),
}
# (seconds, shot name or card, caption, push-in zoom). Captions: no invented numbers.
COST_CAPTION = "3.8 CPU-seconds per image · one core · no GPU · about $0.00005 per image"
SCENES = [
    (4.5, "@title", None, 1.0),
    (4.5, "hero", "fresh. — landing page, staff app and day replay, all online", 1.02),
    (4.5, "tasks_top", "Fazer agora: every area of every camera, worst first", 1.03),
    (4.5, "tasks_cards", "Trocar = put the right product back · Repor = restock", 1.03),
    (5.0, "gondola", "Gôndolas: each pin is a planogram area on the camera picture", 1.03),
    (4.5, "products", "Produtos: every product and the areas it sits in", 1.03),
    (4.5, "insights", "Análise: warns before a shelf runs empty", 1.03),
    (5.0, ("tasks_top", "en"), "Portuguese by default, one tap for English", 1.0),
    (5.0, "day", "Day replay: scrub through the store's day, camera by camera", 1.02),
    (5.0, "@cost", COST_CAPTION, 1.0),
    (5.5, "@end", None, 1.0),
]
CHECK_TIMES = (2, 8, 20, 40)


# ------------------------------------------------------------------ helpers
def log(msg):
    print(msg, flush=True)


def font(name, size):
    return ImageFont.truetype(FONTS + name, size)


def server_up():
    try:
        with urllib.request.urlopen(HARNESS, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def find_edge():
    for p in EDGE:
        if Path(p).exists():
            return p
    return shutil.which("msedge")


def harness_url(app, route, y, click):
    q = {"app": app, "w": W, "h": H}
    if route:
        q["route"] = route
    if y:
        q["y"] = y
    if click:
        q["click"] = click
    return HARNESS + "?" + urllib.parse.urlencode(q)


def edge_shot(edge, url, png):
    png.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="fresh_vid_") as prof:  # fresh profile: default language, no memory
        cmd = [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
               "--no-first-run", "--no-default-browser-check", "--virtual-time-budget=6000",
               f"--window-size={W},{H}", f"--screenshot={png}", url]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except subprocess.TimeoutExpired:
            return False
    return png.exists() and png.stat().st_size > 0


def take_shots(versions, edge):
    SHOTS.mkdir(parents=True, exist_ok=True)
    jobs = []
    for v in versions:
        for name, (src, route, y, click) in SHOTS_SPEC.items():
            jobs.append((harness_url(SOURCES[v][src], route, y, click), SHOTS / f"{v}_{name}.png"))
    with ThreadPoolExecutor(3) as ex:
        ok = list(ex.map(lambda j: edge_shot(edge, *j), jobs))
    # The public build has a dark privacy banner on top (styled by tour.css). Right after a rebuild the stylesheet
    # sometimes misses Edge's virtual-time budget and the shot comes out unstyled: retake those, one at a time.
    for _attempt in range(3):
        redo = [i for i, (u, p) in enumerate(jobs) if ok[i] and ("site%2Fapp" in u or "site%2Fday" in u)
                and sum(Image.open(p).convert("RGB").getpixel((W // 2, 10))) > 200]
        if not redo:
            break
        log(f"    retaking {len(redo)} unstyled public shot(s)")
        time.sleep(1)
        for i in redo:
            ok[i] = edge_shot(edge, *jobs[i])
    bad = [p.name for (_, p), k in zip(jobs, ok) if not k]
    if bad:
        raise SystemExit(f"screenshot(s) failed: {', '.join(bad)}")
    log(f"  {len(jobs)} screenshots -> {SHOTS}")


# ------------------------------------------------------------------ cards
def logo(size):
    return Image.open(ROOT / "brand" / "fresh_logo_512.png").convert("RGBA").resize((size, size), Image.LANCZOS)


def centered(d, y, text, f, fill):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)


def title_card():
    im = Image.new("RGBA", (W, H), BEIGE + (255,))
    im.alpha_composite(logo(400), ((W - 400) // 2, 200))
    centered(ImageDraw.Draw(im), 680, "See every shelf. Fix what matters first.", font("seguibl.ttf", 66), INK)
    return im


def cost_card():
    im = Image.new("RGBA", (W, H), BEIGE + (255,))
    box = (300, 170, 1620, 760)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((box[0], box[1] + 10, box[2], box[3] + 10), 36, fill=(60, 40, 20, 40))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(box, 36, fill=(255, 255, 255, 255))
    d.text((380, 240), "WHAT IT COSTS TO RUN", font=font("seguisb.ttf", 32), fill=MAGENTA)
    d.text((372, 295), "3.8 CPU-seconds", font=font("seguibl.ttf", 124), fill=INK)
    d.text((380, 455), "per image  ·  one core  ·  no GPU", font=font("seguisb.ttf", 50), fill=INK)
    d.line((380, 560, 1540, 560), fill=(230, 224, 212), width=3)
    d.text((380, 600), "about $0.00005 per image", font=font("segoeuib.ttf", 54), fill=INK)
    return im


def end_card():
    im = Image.new("RGBA", (W, H), BEIGE + (255,))
    im.alpha_composite(logo(300), ((W - 300) // 2, 170))
    d = ImageDraw.Draw(im)
    centered(d, 540, "Try it: sergiokutspires.github.io/junctionx-2026", font("seguibl.ttf", 64), INK)
    centered(d, 650, "NovaLotus · github.com/sergiokutspires/junctionx-2026", font("seguisb.ttf", 44), MUTED)
    return im


CARDS = {"@title": title_card, "@cost": cost_card, "@end": end_card}


def caption_layer(text):
    """White rounded caption bar near the bottom, near-black text (RGBA layer the size of the frame)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = font("seguisb.ttf", 42)
    d = ImageDraw.Draw(im)
    bw, bh = int(d.textlength(text, font=f) + 96), 92
    x0, y0 = (W - bw) // 2, H - 56 - bh
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 8, x0 + bw, y0 + bh + 8), 46, fill=(30, 20, 10, 70))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 46, fill=(255, 255, 255, 250), outline=(225, 218, 205), width=2)
    d.text((x0 + 48, y0 + bh / 2), text, font=f, fill=INK, anchor="lm")
    return im


# ------------------------------------------------------------------ composing
def to_bgr(im):
    return cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)


def base_image(v, key):
    if key in CARDS:
        return CARDS[key]()
    return Image.open(SHOTS / f"{v}_{key}.png").convert("RGBA").resize((W, H), Image.LANCZOS)


def make_scene(v, sec, key, cap, zoom):
    """Return (frame count, frame(i)) so frames are produced lazily."""
    n = int(round(sec * FPS))
    if cap:  # blend only the band that holds the caption (fast)
        layer = np.asarray(caption_layer(cap))
        rows = np.where(layer[..., 3].max(axis=1) > 0)[0]
        r0, r1 = int(rows.min()), int(rows.max()) + 1
        al = layer[r0:r1, :, 3:4].astype(np.float32) / 255.0
        rgb = cv2.cvtColor(np.ascontiguousarray(layer[r0:r1, :, :3]), cv2.COLOR_RGB2BGR).astype(np.float32) * al

    def put_caption(g):
        if cap:
            g = g.copy()
            g[r0:r1] = (g[r0:r1].astype(np.float32) * (1 - al) + rgb).astype(np.uint8)
        return g

    if isinstance(key, tuple):  # in-scene crossfade, e.g. Portuguese -> English
        a, b = (put_caption(to_bgr(base_image(v, k))) for k in key)

        def fab(i):
            t = min(1.0, max(0.0, (i / FPS - sec * 0.4) / 0.6))
            return cv2.addWeighted(a, 1 - t, b, t, 0)
        return n, fab
    frame = to_bgr(base_image(v, key))

    def f(i):
        g = frame
        if zoom > 1.0:  # slow push-in, anchored at the top so headers stay visible
            z = 1.0 + (zoom - 1.0) * i / max(1, n - 1)
            x0 = (W - W / z) / 2
            g = cv2.warpAffine(frame, np.float32([[z, 0, -x0 * z], [0, z, 0]]), (W, H),
                               flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return put_caption(g)
    return n, f


def open_writer(path):
    for fc in ("avc1", "mp4v"):
        w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fc), FPS, (W, H))
        if w.isOpened():
            return w, fc
    raise SystemExit("no usable video codec (avc1 / mp4v)")


def build_video(v, path):
    w, fc = open_writer(path)
    nf = int(FADE * FPS)
    total, prev_tail = 0, None
    for idx, sp in enumerate(SCENES):
        n, fr = make_scene(v, *sp)
        last = idx == len(SCENES) - 1
        stop = n if last else n - nf
        for i in range(stop):
            g = fr(i)
            if prev_tail is not None and i < nf:  # crossfade from the previous scene's tail
                t = (i + 1) / (nf + 1)
                g = cv2.addWeighted(prev_tail[i], 1 - t, g, t, 0)
            w.write(g)
        total += stop
        prev_tail = None if last else [fr(i) for i in range(n - nf, n)]
    w.release()
    return fc, total


def make_webm(src, dst):
    """Lighter VP9 copy of an mp4 (1280x720, 10 fps). Runs as its own process, in parallel with the rest."""
    c = cv2.VideoCapture(str(src))
    step = max(1, round((c.get(cv2.CAP_PROP_FPS) or FPS) / WEBM_FPS))
    w = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"VP90"), WEBM_FPS, WEBM_SIZE)
    if not w.isOpened():
        raise SystemExit("VP90 writer not available")
    i = 0
    while True:
        ok, f = c.read()
        if not ok:
            break
        if i % step == 0:
            w.write(cv2.resize(f, WEBM_SIZE, interpolation=cv2.INTER_AREA))
        i += 1
    w.release()


def verify(v, path):
    c = cv2.VideoCapture(str(path))
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = c.get(cv2.CAP_PROP_FPS) or FPS
    dur = n / fps
    saved = []
    for t in CHECK_TIMES:
        c.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, f = c.read()
        if ok:
            out = POP / f"check_{v}_{t}s.jpg"
            cv2.imwrite(str(out), f, [cv2.IMWRITE_JPEG_QUALITY, 85])
            saved.append(out.name)
    c.release()
    ok = 45 <= dur <= 60 and len(saved) == len(CHECK_TIMES)
    return n, dur, ok, saved


# ------------------------------------------------------------------ main
def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--_webm":   # internal: child process for the .webm copy
        make_webm(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", choices=("public", "local", "both"), default="both")
    ap.add_argument("--no-rebuild", action="store_true", help="do not rebuild outputs/site first")
    ap.add_argument("--no-webm", action="store_true", help="skip the .webm copy of the public video")
    args = ap.parse_args()
    versions = ["public", "local"] if args.version == "both" else [args.version]
    t0 = time.time()
    py = sys.executable

    if not args.no_rebuild:
        log("1/4 rebuilding the public site (tools/build_site.py) ...")
        for _attempt in range(3):  # a file held open by another process (preview, server) makes rmtree fail
            r = subprocess.run([py, str(ROOT / "tools" / "build_site.py")], cwd=ROOT)
            if r.returncode == 0:
                break
            log("    build_site.py failed, retrying in 3 s")
            time.sleep(3)
        else:
            raise SystemExit("build_site.py failed 3 times")
        log(f"    site rebuilt in {time.time() - t0:.0f} s")

    edge = find_edge()
    if not edge:
        raise SystemExit("Microsoft Edge not found")
    srv = None
    if not server_up():
        log(f"    starting a temporary static server on port {PORT}")
        srv = subprocess.Popen([py, "-m", "http.server", str(PORT), "-d", str(OUTPUTS), "--bind", "127.0.0.1"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if server_up():
                break
            time.sleep(0.2)
        else:
            srv.terminate()
            raise SystemExit("static server did not start")
    try:
        t1 = time.time()
        log("2/4 screenshots (headless Edge, 1920x1080) ...")
        take_shots(versions, edge)
        log(f"    shots in {time.time() - t1:.0f} s")
    finally:
        if srv:
            srv.terminate()

    log("3/4 composing ...")
    webm_proc, results = None, []
    for v in versions:
        t2 = time.time()
        path = POP / f"fresh_demo_{v}.mp4"
        fc, total = build_video(v, path)
        results.append((v, path, fc))
        log(f"    {path.name}: {total} frames written in {time.time() - t2:.0f} s ({fc})")
        if v == "public" and not args.no_webm:
            webm_proc = subprocess.Popen([py, str(Path(__file__).resolve()), "--_webm", str(path),
                                          str(path.with_suffix(".webm"))])

    log("4/4 checking ...")
    for v, path, fc in results:
        n, dur, ok, saved = verify(v, path)
        log(f"{'OK  ' if ok else 'FAIL'} {path.name}: codec={fc} {W}x{H} {FPS}fps frames={n} duration={dur:.1f}s "
            f"size={path.stat().st_size / 1e6:.1f}MB checks={','.join(saved)}")
    if webm_proc:
        webm_proc.wait()
        wp = POP / "fresh_demo_public.webm"
        c = cv2.VideoCapture(str(wp))
        n, fps = int(c.get(cv2.CAP_PROP_FRAME_COUNT)), c.get(cv2.CAP_PROP_FPS) or WEBM_FPS
        ok, _ = c.read()
        c.release()
        log(f"{'OK  ' if ok else 'FAIL'} {wp.name}: codec=VP90 {WEBM_SIZE[0]}x{WEBM_SIZE[1]} {WEBM_FPS}fps "
            f"frames={n} duration={n / fps:.1f}s size={wp.stat().st_size / 1e6:.1f}MB")
    log(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()

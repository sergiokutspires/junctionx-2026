"""Build the public demo site (GitHub Pages) into outputs/site.

  .venv/Scripts/python tools/build_site.py
  .venv/Scripts/python tools/build_site.py --out outputs/site --app outputs/rehearsal_final/dashboard --day outputs/day_replay/dashboard

Layout (see the site contract):
  index.html, site.css      copied from site/ (the landing page; placeholder if missing)
  assets/                   logo, favicon, og.png social card, shot_*.png screenshots of the PIXELATED app
  app/   late-day snapshot of the staff app        } every camera picture pixelated (privacy: Sensei's data,
  day/   whole-day replay of the staff app          } frames can show shoppers), tour + home pill injected
  .nojekyll

--sharp skips the pixelation. Only with Sensei's written OK: never publish sharp store pictures otherwise.
The output folder is deleted and rebuilt on every run (idempotent).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from make_public_demo import pixelate  # noqa: E402

SITE_URL = "https://sergiokutspires.github.io/junctionx-2026/"
# One-line public-demo banner with the way home built in (replaces the floating home pill on phones).
SITE_BANNER = (
    '<div class="public-note" role="note"><a class="pn-home" href="../" aria-label="fresh. home page">'
    '<span aria-hidden="true">&larr;</span><span>fresh<span class="pn-dot">.</span></span></a>'
    '<span class="pn-long">Public demo: camera pictures are pixelated for privacy · '
    'Demonstração pública: imagens desfocadas</span>'
    '<span class="pn-short">Demo: pictures pixelated for privacy</span></div>'
)
TAGLINE = "See every shelf. Fix what matters first."
BLOCK = 24
PICS = (".jpg", ".jpeg", ".png", ".webp")
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

PLACEHOLDER = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>fresh.</title><link rel="icon" href="assets/favicon.png">
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#F5F0E6;color:#1D1D1F;
font-family:-apple-system,"SF Pro Display","Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;text-align:center}}
a{{color:#C32172;font-weight:700}}</style></head>
<body><main><img src="assets/logo.png" alt="fresh." width="160" height="160"><h1>{TAGLINE}</h1>
<p><a href="app/">Open the staff app</a> · <a href="app/?tour=1">Take the 60-second tour</a> · <a href="day/">Replay the store's day</a></p>
</main></body></html>
"""

OG_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;width:1200px;height:630px;overflow:hidden;background:#F5F0E6}
body{display:flex;align-items:center;gap:64px;padding:0 88px;box-sizing:border-box;color:#1D1D1F;
font-family:-apple-system,"SF Pro Display","Segoe UI Variable Display","Segoe UI",system-ui,sans-serif}
img{width:300px;height:300px;flex:none;filter:drop-shadow(0 18px 40px rgba(195,33,114,.25))}
h1{margin:0 0 22px;font-size:66px;line-height:1.04;font-weight:800;letter-spacing:-.02em}
p{margin:0;font-size:28px;line-height:1.35;color:#636366;font-weight:500}
.k{margin-top:28px;display:inline-block;padding:10px 20px;border-radius:999px;background:#fff;color:#1D1D1F;font-size:22px;font-weight:700;
box-shadow:0 1px 2px rgba(60,45,20,.05),0 4px 12px rgba(60,45,20,.05),0 12px 32px rgba(60,45,20,.05)}
.k b{color:#C32172}
</style></head><body><img src="LOGO" alt="">
<div><h1>See every shelf.<br>Fix what matters first.</h1>
<p>Ceiling-camera pictures of the produce section, turned into one to-do list for store staff.</p>
<span class="k">Live demo · by <b>NovaLotus</b></span></div></body></html>
"""


def head_meta(sub: str, title: str) -> str:
    desc = f"{TAGLINE} Public demo of the fresh. staff app: camera pictures pixelated for privacy."
    return "\n".join([
        f'<meta name="description" content="{desc}">',
        '<link rel="icon" type="image/png" href="../assets/favicon.png">',
        '<link rel="apple-touch-icon" href="../assets/logo_180.png">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="fresh.">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{SITE_URL}{sub}/">',
        f'<meta property="og:image" content="{SITE_URL}assets/og.png">',
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:description" content="{desc}">',
        f'<meta name="twitter:image" content="{SITE_URL}assets/og.png">',
    ])


def find_edge() -> str | None:
    for p in EDGE_CANDIDATES:
        if Path(p).exists():
            return p
    return shutil.which("msedge")


PHONE_HARNESS = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;overflow:hidden;background:#F5F0E6}
iframe{display:block;border:0;width:WPX;height:HPX}</style></head><body><iframe src="SRC"></iframe></body></html>"""


def edge_shot(edge: str, url: str, png: Path, w: int, h: int, scale: float = 1.0, budget: int = 4000) -> bool:
    """Screenshot url at w x h CSS px. Headless Edge will not lay out narrower than ~500 px, so phone widths are
    rendered inside an iframe of exactly w x h (a true phone-width viewport)."""
    with tempfile.TemporaryDirectory(prefix="fresh_edge_") as prof:
        if w < 600:
            harness = Path(prof) / "phone.html"
            harness.write_text(PHONE_HARNESS.replace("WPX", f"{w}px").replace("HPX", f"{h}px")
                               .replace("SRC", url.replace('"', "%22")), encoding="utf-8")
            url = harness.as_uri()
        cmd = [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
               "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
               f"--virtual-time-budget={budget}", f"--window-size={w},{h}", f"--force-device-scale-factor={scale}",
               f"--screenshot={png}", url]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except subprocess.TimeoutExpired:
            return False
    return png.exists() and png.stat().st_size > 0


def copy_app(src: Path, dst: Path, name: str, title: str, sharp: bool) -> int:
    if not (src / "index.html").exists():
        raise SystemExit(f"No staff app in {src}")
    shutil.copytree(src, dst)
    pics = [p for p in dst.rglob("*") if p.suffix.lower() in PICS]
    if not sharp:
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            list(ex.map(lambda p: pixelate(p, BLOCK), pics))
    for f in ("tour.js", "tour.css"):
        shutil.copy2(ROOT / "site" / f, dst / f)
    index = dst / "index.html"
    html = index.read_text(encoding="utf-8")
    html = html.replace("</head>", head_meta(name, title) + "\n</head>", 1)
    if not sharp and "public-note" not in html:
        html = html.replace("<body>", "<body>\n" + SITE_BANNER, 1)
    html = html.replace("</body>", '<link rel="stylesheet" href="tour.css">\n<script src="tour.js" charset="utf-8"></script>\n</body>', 1)
    index.write_text(html, encoding="utf-8")
    return 0 if sharp else len(pics)


def main() -> None:
    t0 = time.time()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="outputs/site")
    ap.add_argument("--app", default="outputs/rehearsal_final/dashboard", help="late-day snapshot build")
    ap.add_argument("--day", default="outputs/day_replay/dashboard", help="whole-day replay build")
    ap.add_argument("--sharp", action="store_true", help="do NOT pixelate (needs Sensei's written OK)")
    ap.add_argument("--no-shots", action="store_true", help="skip the headless-Edge og card and screenshots")
    args = ap.parse_args()
    out = (ROOT / args.out).resolve()
    if args.sharp:
        print("!" * 78 + "\n!! --sharp: camera pictures are NOT pixelated. Store frames can show shoppers and are Sensei's data.\n"
              "!! Publish this ONLY with Sensei's written OK.\n" + "!" * 78)
    if out == ROOT or ROOT not in out.parents:
        raise SystemExit(f"Refusing to rebuild {out} (must be inside the project)")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # landing page (written by the landing agent; placeholder only if missing)
    site_src = ROOT / "site"
    copied = []
    if site_src.exists():
        for p in site_src.iterdir():
            if p.name in ("tour.js", "tour.css"):
                continue
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, out / p.name)
            copied.append(p.name)
    if not (out / "index.html").exists():
        (out / "index.html").write_text(PLACEHOLDER, encoding="utf-8")
        print("NOTE: site/index.html missing -> wrote a placeholder landing page into the output")

    assets = out / "assets"
    assets.mkdir(exist_ok=True)
    brand = ROOT / "brand"
    shutil.copy2(brand / "fresh_logo_512.png", assets / "logo.png")
    shutil.copy2(brand / "fresh_logo_180.png", assets / "logo_180.png")
    shutil.copy2(brand / "fresh_logo_64.png", assets / "favicon.png")

    n_pics = copy_app(ROOT / args.app, out / "app", "app", "fresh. staff app (live demo)", args.sharp)
    n_pics += copy_app(ROOT / args.day, out / "day", "day", "fresh. a store's day, replayed", args.sharp)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    t_copy = time.time() - t0

    shots_ok = []
    edge = find_edge()
    if args.no_shots:
        pass
    elif not edge:
        print("WARNING: Microsoft Edge not found: og.png and screenshots skipped")
    else:
        with tempfile.TemporaryDirectory(prefix="fresh_og_") as tmp:
            card = Path(tmp) / "og.html"
            shutil.copy2(brand / "fresh_logo_512.png", Path(tmp) / "logo.png")
            card.write_text(OG_HTML.replace("LOGO", "logo.png"), encoding="utf-8")
            app_url = (out / "app" / "index.html").as_uri() + "?shot=1"
            day_url = (out / "day" / "index.html").as_uri() + "?shot=1"
            jobs = [
                (card.as_uri(), assets / "og.png", 1200, 630, 1.0),
                # desktop shots at a 1200 px viewport, 2x, so the landing page shows them crisp and never upscaled
                (app_url + "#/tasks", assets / "shot_desktop.png", 1200, 760, 2.0),
                (app_url + "#/tasks", assets / "shot_phone.png", 390, 844, 2.0),
                # taller renders, cropped below (CROPS) to the camera picture with its outlined areas
                (app_url + "#/gondola/6215/6215_7", assets / "shot_gondola.png", 1200, 1240, 2.0),
                # the morning story of the landing page's hook: camera 6215 at 06:14
                (day_url + "#/day/0615/6215/6215_3", assets / "shot_day.png", 1200, 1400, 2.0),
            ]
            # CSS-px band (top, height) kept from a tall render: the camera tabs and picture, not the page chrome
            CROPS = {"shot_gondola.png": (0, 440, 1200, 760), "shot_day.png": (16, 592, 712, 580)}   # left, top, width, height
            with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
                res = list(ex.map(lambda j: edge_shot(edge, *j), jobs))
            for (_, png, w, _h, _s), ok in zip(jobs, res):
                if ok and png.name in CROPS:
                    left, top, ww, hh = CROPS[png.name]
                    with Image.open(png) as im:
                        im.load()
                        k = im.size[0] / w
                        band = im.crop((int(left * k), int(top * k), int((left + ww) * k), int((top + hh) * k)))
                    band.save(png, optimize=True)
                if ok:
                    with Image.open(png) as im:
                        size = im.size
                    if png.name == "og.png" and size != (1200, 630):
                        Image.open(png).convert("RGB").resize((1200, 630)).save(png)
                    shots_ok.append(f"{png.name} {size[0]}x{size[1]}")
                else:
                    print(f"WARNING: screenshot failed: {png.name}")

    files = [p for p in out.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"Built {out}")
    print(f"  pictures pixelated (block {BLOCK}): {n_pics}" + ("  [SHARP BUILD: NOT PIXELATED]" if args.sharp else ""))
    print(f"  files: {len(files)}, total size: {total / 1e6:.1f} MB")
    print(f"  landing files copied from site/: {', '.join(sorted(copied)) or '(none)'}")
    print(f"  rendered: {', '.join(shots_ok) or '(none)'}")
    print("  top level: " + ", ".join(sorted(p.name + ("/" if p.is_dir() else "") for p in out.iterdir())))
    print(f"  done in {time.time() - t0:.0f} s (copy + pixelate {t_copy:.0f} s)")


if __name__ == "__main__":
    main()

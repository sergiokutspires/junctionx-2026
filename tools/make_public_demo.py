"""Make a privacy-safe copy of a staff-app build that may be hosted publicly (e.g. GitHub Pages).

The store's camera pictures are Sensei's data and can show shoppers, so every picture in the copy is pixelated
beyond recognition; the app itself (counts, to-do list, Repor / Trocar / Deixar, gondola pins, Análise) is
unchanged. A banner says so. The source build is not modified.

  .venv/Scripts/python tools/make_public_demo.py                      # outputs/rehearsal_0850/dashboard
  .venv/Scripts/python tools/make_public_demo.py --src outputs/day_replay/dashboard --out outputs/public_demo
"""
import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BANNER = (
    '<div class="public-note" role="note" style="position:sticky;top:0;z-index:50;margin:0;padding:8px 16px;'
    'background:#1C1A17;color:#F5F0E6;font:600 14px/1.4 -apple-system,BlinkMacSystemFont,\'Segoe UI\',system-ui,'
    'sans-serif;text-align:center">Public demo: the store\'s camera pictures are pixelated for privacy. '
    'The real app shows them sharp. · Demonstração pública: imagens das câmaras desfocadas.</div>'
)


def pixelate(path: Path, block: int) -> None:
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        small = im.resize((max(1, w // block), max(1, h // block)), Image.BILINEAR)
        out = small.resize((w, h), Image.NEAREST).filter(ImageFilter.GaussianBlur(block / 4))
    out.save(path, quality=70)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="outputs/rehearsal_0850/dashboard", help="staff-app build to copy")
    ap.add_argument("--out", default="outputs/public_demo", help="where the privacy-safe copy goes (replaced)")
    ap.add_argument("--block", type=int, default=24, help="pixel block size (bigger = less recognisable)")
    args = ap.parse_args()
    src, out = (ROOT / args.src).resolve(), (ROOT / args.out).resolve()
    if not (src / "index.html").exists():
        raise SystemExit(f"No staff app in {src}")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    pictures = [p for p in out.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    for p in pictures:
        pixelate(p, args.block)
    index = out / "index.html"
    html = index.read_text(encoding="utf-8")
    if "public-note" not in html:
        html = html.replace("<body>", "<body>\n" + BANNER, 1)
        html = html.replace("<title>fresh.</title>", "<title>fresh. (public demo)</title>", 1)
    index.write_text(html, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages: serve files as they are
    print(f"{len(pictures)} picture(s) pixelated -> {index}")


if __name__ == "__main__":
    main()

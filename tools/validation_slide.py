"""Put the validation run's results on the pitch slide "Your validation pictures." (#sval).

Usage (project root):
  .venv/Scripts/python tools/validation_slide.py [--submission submission] [--slides pitch/slides.html] [--no-pdf]
  .venv/Scripts/python tools/validation_slide.py --placeholder      # reset the slide to the calm placeholder

Reads <submission>/predictions.json (+ details.json, + a run log if one is there), counts the four app
statuses exactly like sensei/dashboard.py (_status: wrong product > empty > low (half) > ok), screenshots the
staff app <submission>/dashboard to <slides dir>/assets/val_app.jpg, rewrites ONLY the block between
<!-- VALIDATION:BEGIN --> and <!-- VALIDATION:END -->, then builds the standalone deck and the backup PDF.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BEGIN, END = "<!-- VALIDATION:BEGIN -->", "<!-- VALIDATION:END -->"
TILES = [("empty", "Vazio"), ("low", "Baixo"), ("wrong", "Produto errado"), ("ok", "OK")]

CSS = """<style>
  #sval { flex-direction: row; align-items: center; gap: 72px; padding: 100px 120px; }
  #sval .vl { flex: 1 1 auto; min-width: 0; }
  #sval h2 { font-size: 92px; }
  #sval .vbig { font-size: 50px; font-weight: 800; letter-spacing: -.02em; margin-top: 34px; font-variant-numeric: tabular-nums; }
  #sval .vbig span { color: #A9A39A; font-weight: 700; }
  #sval .vtiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin-top: 40px; }
  #sval .vt { border-radius: 26px; padding: 26px 22px 24px; color: #fff; box-shadow: 0 2px 4px rgba(60,45,20,.08), 0 10px 24px rgba(60,45,20,.10); }
  #sval .vt b { display: block; font-size: 96px; line-height: .95; letter-spacing: -.05em; font-variant-numeric: tabular-nums; }
  #sval .vt span { display: block; font-size: 27px; font-weight: 800; margin-top: 10px; letter-spacing: -.01em; line-height: 1.1; }
  #sval .vt.empty { background: var(--empty); } #sval .vt.low { background: var(--low); color: #2B1D00; }
  #sval .vt.wrong { background: var(--wrong); } #sval .vt.ok { background: var(--ok); }
  #sval.wait .vt { opacity: .55; }
  #sval .vchk { font-size: 30px; font-weight: 700; color: var(--muted); margin-top: 34px; }
  #sval .vchk i { font-style: normal; color: var(--ok); }
  #sval .vr { flex: none; width: 720px; }
  #sval .vr img { width: 720px; height: auto; max-height: 820px; object-fit: cover; object-position: top center; }
  #sval .vph { width: 720px; height: 540px; border-radius: 28px; border: 4px dashed #CFC6B4; display: flex; align-items: center; justify-content: center; text-align: center; padding: 40px; font-size: 34px; font-weight: 700; color: #A39A8A; line-height: 1.3; }
</style>"""


def status(cell: dict) -> str:
    """Same rule as sensei/dashboard.py _status: wrong product > empty > low (half) > ok."""
    if cell.get("planogram_compliant") is False:
        return "wrong"
    level = cell.get("stock_level")
    if level == "empty":
        return "empty"
    if level == "half":
        return "low"
    return "ok"


def read_counts(pred_path: Path) -> dict:
    doc = json.loads(pred_path.read_text(encoding="utf-8"))
    counts = {k: 0 for k, _ in TILES}
    pictures, areas = 0, 0
    for _cam, imgs in doc.items():
        for _img, cells in imgs.items():
            pictures += 1
            for _aid, cell in cells.items():
                areas += 1
                counts[status(cell)] += 1
    return {"pictures": pictures, "areas": areas, "counts": counts}


def read_seconds(sub: Path):
    """Time taken, from a run log if there is one (e.g. SUBMIT.bat output saved next to the files)."""
    for name in ("submit_log.txt", "submit.log", "run.log", "log.txt"):
        p = sub / name
        if p.is_file():
            txt = p.read_text(encoding="utf-8", errors="replace")
            m = re.findall(r"Total time:\s*([\d.]+)\s*s", txt) or re.findall(r"predicted in\s*([\d.]+)\s*s", txt)
            if m:
                return float(m[-1])
    return None


def format_check(pred_path: Path, details_path: Path):
    """Re-run the submission's own format check; True/False, or None if it cannot be run."""
    try:
        sys.path.insert(0, str(ROOT))
        from sensei.data import load_planogram  # noqa: PLC0415
        from sensei.submit import validate_predictions  # noqa: PLC0415
        planogram = {c: [x.area_id for x in v]
                     for c, v in load_planogram(ROOT / "models" / "real_v3_cal" / "planogram.json").items()}
        rows = json.loads(details_path.read_text(encoding="utf-8")).get("rows") if details_path.is_file() else None
        return bool(validate_predictions(pred_path, planogram, (), rows)["ok"])
    except Exception as exc:  # noqa: BLE001
        print(f"note: format check not re-run ({type(exc).__name__}: {exc})")
        return None


def edge(args: list, timeout=60):
    prof = tempfile.mkdtemp(prefix="edge_vs_")
    try:
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                        "--virtual-time-budget=4000"] + args, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def shoot_app(dash: Path, out_jpg: Path) -> bool:
    index = dash / "index.html"
    if not index.is_file():
        print(f"note: no staff app at {index}; the slide keeps the placeholder box")
        return False
    png = Path(tempfile.mkdtemp(prefix="valshot_")) / "app.png"
    edge(["--window-size=1200,900", "--force-device-scale-factor=2", f"--screenshot={png}", index.as_uri()])
    if not png.is_file():
        print("note: staff app screenshot failed")
        return False
    from PIL import Image  # noqa: PLC0415
    im = Image.open(png).convert("RGB")
    im = im.resize((1440, round(im.height * 1440 / im.width)), Image.LANCZOS)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_jpg, "JPEG", quality=86, optimize=True)
    shutil.rmtree(png.parent, ignore_errors=True)
    return True


def block(res, seconds, ok, has_img: bool) -> str:
    wait = res is None
    if wait:
        big = "&ndash; pictures &middot; &ndash; areas &middot; read in &ndash; s"
        nums = {k: "&ndash;" for k, _ in TILES}
        chk = 'Results appear here after the validation run'
    else:
        big = f'{res["pictures"]} pictures <span>&middot;</span> {res["areas"]} areas'
        if seconds is not None:
            big += f' <span>&middot;</span> read in {seconds:.0f}&nbsp;s'
        nums = {k: f'{v:,}' for k, v in res["counts"].items()}
        chk = {True: 'Format check: <i>passed</i>', False: 'Format check: not passed', None: ''}[ok]
    tiles = "".join(f'<div class="vt {k}"><b>{nums[k]}</b><span>{lab}</span></div>' for k, lab in TILES)
    right = ('<img class="shot" src="assets/val_app.jpg" alt="The staff app on the validation pictures">'
             if has_img else '<div class="vph">The staff app on your pictures<br>appears here</div>')
    return (f'{BEGIN}\n<!-- 7 · Validation (generated by tools/validation_slide.py; do not edit by hand) -->\n'
            f'<section class="slide{" wait" if wait else ""}" id="sval" data-title="Your validation pictures">\n{CSS}\n'
            f'  <div class="vl">\n    <div class="label">Validation set &middot; run after submissions closed</div>\n'
            f'    <h2>Your validation pictures.</h2>\n    <p class="vbig">{big}</p>\n'
            f'    <div class="vtiles">{tiles}</div>\n'
            + (f'    <p class="vchk">{chk}</p>\n' if chk else '')
            + f'  </div>\n  <div class="vr">{right}</div>\n</section>\n{END}')


def pdf_pages(p: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)", p.read_bytes()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", default="submission")
    ap.add_argument("--slides", default="pitch/slides.html")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--placeholder", action="store_true", help="reset the slide to the placeholder")
    a = ap.parse_args()
    t0 = time.perf_counter()
    sub = Path(a.submission)
    sub = sub if sub.is_absolute() else ROOT / sub
    slides = Path(a.slides)
    slides = slides if slides.is_absolute() else ROOT / slides
    html = slides.read_text(encoding="utf-8")
    if BEGIN not in html or END not in html:
        sys.exit(f"ERROR: markers {BEGIN} / {END} not found in {slides}")
    res = seconds = ok = None
    has_img = False
    if not a.placeholder:
        pred = sub / "predictions.json"
        if not pred.is_file():
            sys.exit(f"ERROR: {pred} not found. Run SUBMIT.bat on the validation pictures first.")
        res = read_counts(pred)
        seconds = read_seconds(sub)
        ok = format_check(pred, sub / "details.json")
        has_img = shoot_app(sub / "dashboard", slides.parent / "assets" / "val_app.jpg")
    i, j = html.index(BEGIN), html.index(END) + len(END)
    slides.write_text(html[:i] + block(res, seconds, ok, has_img) + html[j:], encoding="utf-8")
    print(f"updated {slides}")
    pdf = None
    if slides.parent.resolve() == (ROOT / "pitch").resolve():
        subprocess.run([sys.executable, str(ROOT / "pitch" / "build_standalone.py")], check=False)
    if not a.no_pdf:
        pdf = slides.parent / ("slides_backup.pdf" if slides.name == "slides.html" else slides.stem + ".pdf")
        if pdf.exists():
            pdf.unlink()
        edge(["--no-pdf-header-footer", f"--print-to-pdf={pdf}", slides.resolve().as_uri()], timeout=80)
        if not pdf.is_file():
            print("WARNING: the PDF was not written")
            pdf = None
    dt = time.perf_counter() - t0
    if res:
        c = res["counts"]
        summary = (f"{res['pictures']} pictures, {res['areas']} areas"
                   + (f", read in {seconds:.0f}s" if seconds is not None else "")
                   + f" | Vazio {c['empty']} Baixo {c['low']} Produto errado {c['wrong']} OK {c['ok']}"
                   + f" | format check {'passed' if ok else 'not passed' if ok is False else 'n/a'}")
    else:
        summary = "placeholder"
    print(f"SLIDE: {summary} | PDF: {pdf if pdf else 'not built'}"
          + (f" ({pdf_pages(pdf)} pages)" if pdf else "") + f" | {dt:.0f}s")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()

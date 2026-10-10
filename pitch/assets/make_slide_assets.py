"""Build the extra pictures used by pitch/slides.html from raw camera frames (no model output).

Usage (project root):  .venv/Scripts/python pitch/assets/make_slide_assets.py
Writes:
  frame_6215_opening.jpg  copy of the 06:14 frame of camera 6215 (planogram areas drawn)
  frame_6462_early.jpg    copy of the 06:12 frame of camera 6462
  empty_strip.jpg         five EMPTY areas on four cameras, rectified with the pipeline's warp
  dash_*_web.jpg          smaller JPEG copies of the dashboard screenshots
  warp_strip.jpg          one frame's areas rectified: the 224x224 crops the models actually see
"""
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sensei.data import load_image, load_planogram, warp_area  # noqa: E402

OUT = Path(__file__).resolve().parent
SIZE = 224
GAP = 10


def crop_of(areas, cam, ts, area_no, size=SIZE):
    area = next(a for a in areas[cam] if a.area_id == f"{cam}_{area_no}")
    img = load_image(ROOT / "data" / "raw" / "images" / cam / f"{ts}.jpg")
    crop, _ = warp_area(img, area.quad, size, 0.06)
    return crop


def strip(crops, name):
    h = crops[0].shape[0]
    w = sum(c.shape[1] for c in crops) + GAP * (len(crops) - 1)
    canvas = np.full((h, w, 3), 255, np.uint8)
    x = 0
    for c in crops:
        canvas[:, x:x + c.shape[1]] = c
        x += c.shape[1] + GAP
    cv2.imwrite(str(OUT / name), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])


def web_copies():
    """Smaller JPEG copies of the dashboard screenshots (the PNGs stay the originals)."""
    from PIL import Image
    for name, box in (("dash_gondola", (1700, 1700)), ("dash_desktop", (1700, 1700)),
                      ("dash_mobile", (800, 1700)), ("dash_mobile_gondola", (800, 1800))):
        src = OUT / f"{name}.png"
        if src.exists():
            im = Image.open(src).convert("RGB")
            im.thumbnail(box)
            im.save(OUT / f"{name}_web.jpg", quality=85, optimize=True)


def main():
    web_copies()
    shutil.copy(ROOT / "data/teacher/6215/1751001268_overview.jpg", OUT / "frame_6215_opening.jpg")
    shutil.copy(ROOT / "data/teacher/6462/1751001155_overview.jpg", OUT / "frame_6462_early.jpg")
    areas = load_planogram(ROOT / "data/raw/planogram.json")

    # empty areas on four cameras, chosen by eye on the overview frames (all clearly empty)
    picks = [("6215", "1751001268", "2"), ("6462", "1751001155", "7"), ("6462", "1751001155", "5"),
             ("6373", "1751048467", "2"), ("6491", "1751048611", "5")]
    print("empty picks:", picks)
    strip([crop_of(areas, *p) for p in picks], "empty_strip.jpg")

    # rectified crops of the 6215 opening frame: empty tray, oranges in a banana area, ...
    seq = [("6215", "1751001268", n) for n in (2, 3, 5, 7, 10)]
    strip([crop_of(areas, *p) for p in seq], "warp_strip.jpg")


if __name__ == "__main__":
    main()

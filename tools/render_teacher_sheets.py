"""Render labelling material for teacher (vision-model) annotation.

For every frame writes, under data/teacher/<cam>/:
  <ts>_overview.jpg  the frame with every planogram area outlined and numbered
  <ts>_areas.jpg     one tile per area: zoomed context crop with the quad drawn,
                     header "#<n>  <area_id>", the planogram product name underneath

Usage: .venv/Scripts/python tools/render_teacher_sheets.py [data/raw] [data/teacher]
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")
FONTS = ("arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")   # first one Pillow can find
TILE_W, TILE_H, HEADER = 420, 300, 64
COLS = 4


def font(size: int):
    """A bold TrueType font of ``size`` px (Arial on Windows, DejaVu / Liberation elsewhere), else Pillow's default."""
    for name in FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_areas(planogram):
    areas = {}
    for section in json.loads(Path(planogram).read_text(encoding="utf-8")).values():
        for cam, cam_data in section["cameras"].items():
            areas[cam] = [(a["area_id"], a["product_name"],
                           np.array([a["image_coordinates"][c] for c in CORNERS], np.float32))
                          for a in cam_data["products"]]
    return areas


def overview(img, areas):
    im = Image.fromarray(img)
    draw = ImageDraw.Draw(im)
    f = font(30)
    for area_id, _, quad in areas:
        draw.polygon([tuple(p) for p in quad], outline=(255, 230, 0), width=3)
        n = area_id.split("_")[-1]
        cx, cy = quad.mean(0)
        cx, cy = min(max(cx, 20), img.shape[1] - 40), min(max(cy, 20), img.shape[0] - 30)
        box = draw.textbbox((cx, cy), n, font=f, anchor="mm")
        draw.rectangle([box[0] - 6, box[1] - 4, box[2] + 6, box[3] + 4], fill=(0, 0, 0))
        draw.text((cx, cy), n, font=f, fill=(255, 255, 255), anchor="mm")
    return im


def area_tile(img, area_id, name, quad):
    h, w = img.shape[:2]
    x0, y0 = quad.min(0)
    x1, y1 = quad.max(0)
    mx, my = 0.25 * (x1 - x0) + 10, 0.25 * (y1 - y0) + 10
    bx0, by0 = int(max(0, x0 - mx)), int(max(0, y0 - my))
    bx1, by1 = int(min(w, x1 + mx)), int(min(h, y1 + my))
    tile = Image.new("RGB", (TILE_W, TILE_H + HEADER), (20, 20, 20))
    if bx1 - bx0 > 4 and by1 - by0 > 4:
        crop = Image.fromarray(img[by0:by1, bx0:bx1])
        scale = min(TILE_W / crop.width, TILE_H / crop.height)
        crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.LANCZOS)
        ox, oy = (TILE_W - crop.width) // 2, HEADER + (TILE_H - crop.height) // 2
        tile.paste(crop, (ox, oy))
        pts = [((px - bx0) * scale + ox, (py - by0) * scale + oy) for px, py in quad]
        ImageDraw.Draw(tile).polygon(pts, outline=(255, 230, 0), width=3)
    draw = ImageDraw.Draw(tile)
    draw.text((8, 4), f"#{area_id.split('_')[-1]}  ({area_id})", font=font(26), fill=(255, 230, 0))
    draw.text((8, 36), name[:38], font=font(20), fill=(255, 255, 255))
    return tile


def area_sheet(img, areas):
    rows = (len(areas) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TILE_W + (COLS - 1) * 6, rows * (TILE_H + HEADER) + (rows - 1) * 6), (90, 90, 90))
    for i, (area_id, name, quad) in enumerate(areas):
        r, c = divmod(i, COLS)
        sheet.paste(area_tile(img, area_id, name, quad), (c * (TILE_W + 6), r * (TILE_H + HEADER + 6)))
    return sheet


def main(raw="data/raw", out="data/teacher"):
    raw, out = Path(raw), Path(out)
    areas_by_cam = load_areas(raw / "planogram.json")
    manifest = {}
    for cam_dir in sorted((raw / "images").iterdir()):
        cam = cam_dir.name
        if cam not in areas_by_cam:
            continue
        (out / cam).mkdir(parents=True, exist_ok=True)
        frames = sorted(p for p in cam_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"} and not p.name.startswith("."))
        manifest[cam] = []
        for p in frames:
            img = cv2.cvtColor(cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
            overview(img, areas_by_cam[cam]).save(out / cam / f"{p.stem}_overview.jpg", quality=88)
            area_sheet(img, areas_by_cam[cam]).save(out / cam / f"{p.stem}_areas.jpg", quality=88)
            manifest[cam].append(p.name)
    (out / "manifest.json").write_text(json.dumps(
        {"frames": manifest,
         "areas": {cam: [[a, n] for a, n, _ in v] for cam, v in areas_by_cam.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rendered {sum(map(len, manifest.values()))} frames for {len(manifest)} cameras -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])

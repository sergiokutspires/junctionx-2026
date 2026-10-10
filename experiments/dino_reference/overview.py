"""Draw planogram quads on a morning and an evening frame per camera (for orientation only)."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "sheets"
OUT.mkdir(exist_ok=True)

plan = json.loads((ROOT / "data/raw/planogram.json").read_text(encoding="utf-8"))
cams = {}
for sec in plan.values():
    for cam, c in sec["cameras"].items():
        cams[cam] = c["products"]

for cam, prods in cams.items():
    files = sorted((ROOT / "data/raw/images" / cam).glob("*.jpg"))
    tiles = []
    for f in (files[0], files[len(files) // 2], files[-1]):
        img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR)
        for p in prods:
            ic = p["image_coordinates"]
            q = np.array([ic["top_left"], ic["top_right"], ic["bottom_right"], ic["bottom_left"]], np.int32)
            cv2.polylines(img, [q], True, (0, 255, 255), 2)
            c = q.mean(0).astype(int)
            cv2.putText(img, p["area_id"].split("_")[1], (int(c[0]) - 8, int(c[1]) + 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
        cv2.putText(img, f"{cam} {f.name}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
        tiles.append(cv2.resize(img, (640, 360)))
    sheet = np.concatenate(tiles, 0)
    cv2.imwrite(str(OUT / f"overview_{cam}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("ok")

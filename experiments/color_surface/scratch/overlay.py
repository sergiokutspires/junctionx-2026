"""Draw planogram quads on frames for visual inspection (scratch helper)."""
import json, sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
plan = json.loads((ROOT / "data/raw/planogram.json").read_text(encoding="utf-8"))
cams = {}
for sec in plan.values():
    for cam, c in sec["cameras"].items():
        cams[cam] = c["products"]

which = sys.argv[1:] or sorted(cams)
for cam in which:
    files = sorted((ROOT / "data/raw/images" / cam).glob("*.jpg"))
    picks = [files[0], files[len(files) // 2], files[-1]]
    tiles = []
    for f in picks:
        img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR)
        for a in cams[cam]:
            ic = a["image_coordinates"]
            q = np.array([ic["top_left"], ic["top_right"], ic["bottom_right"], ic["bottom_left"]], np.int32)
            cv2.polylines(img, [q], True, (0, 0, 255), 2)
            c = q.mean(0).astype(int)
            cv2.putText(img, a["area_id"].split("_")[1], tuple(c), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)
        cv2.putText(img, f"{cam} {f.name}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        tiles.append(cv2.resize(img, (640, 360)))
    sheet = np.vstack(tiles)
    cv2.imwrite(str(OUT / f"ov_{cam}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("ok")

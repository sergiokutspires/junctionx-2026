"""Draw the planogram quads on frames (for looking at the scene)."""
import sys

import cv2
import numpy as np

from common import SHEETS, load_image, load_planogram, list_images

pg = load_planogram()
SHEETS.mkdir(parents=True, exist_ok=True)
cams = sys.argv[1:] or sorted(pg)
which = "first"
for cam in cams:
    recs = list_images([cam])
    picks = [recs[0], recs[len(recs) // 2], recs[-1]] if recs else []
    for tag, (c, fn, path) in zip(["a", "b", "c"], picks):
        img = load_image(path)
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        for a in pg[cam]:
            q = a["quad"].astype(np.int32)
            cv2.polylines(bgr, [q], True, (0, 255, 255), 2)
            cx, cy = a["quad"].mean(0).astype(int)
            txt = a["area_id"].split("_")[1] + " " + a["product_name"][:22]
            cv2.putText(bgr, txt, (int(cx) - 70, int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(bgr, txt, (int(cx) - 70, int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(bgr, f"{cam} {fn}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.imwrite(str(SHEETS / f"overlay_{cam}_{tag}.jpg"), bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("ok")

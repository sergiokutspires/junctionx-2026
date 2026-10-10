"""Stage 1: warp every (frame, area) quad to a rectified SxS crop and cache it."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cs_lib as L  # noqa: E402

CACHE = L.HERE / "cache"


def extract(force=False):
    CACHE.mkdir(exist_ok=True)
    out = CACHE / f"crops_{L.S}.npz"
    if out.exists() and not force:
        return dict(np.load(out, allow_pickle=False))
    t0 = time.time()
    areas = L.load_planogram()
    imgs = L.list_images(sorted(areas))
    keys, cams, names, aids, ts, crops, vis = [], [], [], [], [], [], []
    for cam in sorted(areas):
        for p in imgs[cam]:
            img = L.read_bgr(p)
            if img is None:
                print("corrupt", p)
                continue
            for a in areas[cam]:
                c, v = L.warp(img, a["quad"])
                keys.append(f"{cam}|{p.name}|{a['area_id']}")
                cams.append(cam); names.append(p.name); aids.append(a["area_id"])
                ts.append(int(p.stem) if p.stem.isdigit() else -1)
                crops.append(c); vis.append(v)
    d = dict(keys=np.array(keys), cams=np.array(cams), names=np.array(names), aids=np.array(aids),
             ts=np.array(ts, np.int64), crops=np.stack(crops), vis=np.stack(vis))
    np.savez(out, **d)
    print(f"extracted {len(keys)} crops in {time.time() - t0:.1f}s")
    return d


if __name__ == "__main__":
    d = extract(force="--force" in sys.argv)
    print(len(d["keys"]), d["crops"].shape, d["vis"].mean())
    areas = L.load_planogram()
    for cam in sorted(areas):
        print(cam, [(a["area_id"].split("_")[1], L.base_of(a["product_name"]), int(L.is_packaged(a["product_name"])))
                    for a in areas[cam]])

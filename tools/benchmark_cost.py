"""Measure the compute cost per analysed image (Sensei's resource-efficiency criterion).

  .venv/Scripts/python tools/benchmark_cost.py [--model models/real_v3_cal] [--images 14] [--repeat 2] [--detect]
  SENSEI_THREADS=1 .venv/Scripts/python tools/benchmark_cost.py     # cost on a single CPU core

Reports wall seconds and CPU-seconds per image (marginal: the models are loaded by a first warm-up call
and reused, loading is reported separately; best of --repeat timed passes), peak RAM, the model's
feature precision settings, and writes outputs/benchmark/cost_<threads>t_<model>.json. No feature cache.
"""
import argparse
import ctypes
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sensei import data, pipeline  # noqa: E402


def peak_rss_mb() -> float | None:
    if os.name != "nt":
        import resource  # noqa: PLC0415
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                           "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                           "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PeakWorkingSetSize / 2**20


def timed(fn):
    w, c = time.perf_counter(), time.process_time()
    out = fn()
    return out, time.perf_counter() - w, time.process_time() - c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/real_v3_cal")
    ap.add_argument("--images", type=int, default=14, help="frames to time (spread over cameras)")
    ap.add_argument("--repeat", type=int, default=2, help="timed passes over the frames (the best is kept)")
    ap.add_argument("--detect", action="store_true", help="also time the optional OWLv2 boxes (dashboard only)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    threads = int(os.environ.get("SENSEI_THREADS", 0)) or os.cpu_count()

    model, t_load, _ = timed(lambda: pipeline.SenseiModel.load(a.model))
    cfg = model.cfg
    cfg.extra["cache_dir"] = None                       # measure real compute, not the feature cache
    cams = sorted(model.areas_by_cam)
    recs = data.discover_images("data/raw/images", cams)
    by_cam: dict[str, list] = {}
    for r in recs:
        by_cam.setdefault(r.camera_id, []).append(r)
    picked, k = [], 0                                   # round-robin over cameras, middle frames first
    while len(picked) < a.images and any(by_cam.values()):
        cam = cams[k % len(cams)]; k += 1
        if by_cam.get(cam):
            picked.append(by_cam[cam].pop(len(by_cam[cam]) // 2))
    areas = sum(len(model.areas_by_cam[r.camera_id]) for r in picked)

    _, w1, c1 = timed(lambda: pipeline.predict(model, picked[:1], cfg))       # includes loading CLIP + DINOv2
    passes = [timed(lambda: pipeline.predict(model, picked, cfg))[1:] for _ in range(max(1, a.repeat))]
    wn, cn = min(p[0] for p in passes), min(p[1] for p in passes)
    n = len(picked)
    res = {"model": a.model, **{f: getattr(cfg, f) for f in ("clip_model", "dino_model", "int8_clip", "int8_dino", "bf16")},
           "threads": threads, "images": n, "areas": areas,
           "model_load_s": round(t_load + max(0.0, w1 - wn / n), 2),
           "wall_s_per_image": round(wn / n, 3), "cpu_s_per_image": round(cn / n, 3),
           "cpu_s_per_area": round(cn / max(areas, 1), 3),
           "areas_per_image": round(areas / n, 1), "peak_ram_mb": round(peak_rss_mb() or 0)}
    if a.detect:
        from sensei.dashboard import make_owl_detector  # noqa: PLC0415
        det, w_l, _ = timed(make_owl_detector)
        imgs = [data.load_image(r.path) for r in picked[:min(n, 5)]]
        _, wd, cd = timed(lambda: [det(im) for im in imgs])
        res.update({"owl_load_s": round(w_l, 1), "owl_wall_s_per_image": round(wd / len(imgs), 2),
                    "owl_cpu_s_per_image": round(cd / len(imgs), 2), "peak_ram_mb": round(peak_rss_mb() or 0)})
    out = Path("outputs/benchmark"); out.mkdir(parents=True, exist_ok=True)
    tag = f"_{Path(a.model).name}"
    (out / f"cost_{threads}t{tag}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

"""Read-only backtest: does 'running out soon' (forecast_empty < 2h on a half-full area) predict a really empty shelf later?
Truth = AI answer key v2 (every frame). Model series = models/real_v2/series.json (label-free fill timeline)."""
import sys, json, os, collections
sys.path.insert(0, "C:/Users/alifa/learning/junctionx-sensei"); os.chdir("C:/Users/alifa/learning/junctionx-sensei")
import numpy as np
from sensei.temporal import forecast_empty
S = json.load(open("models/real_v2/series.json"))
V2 = json.load(open("data/labels/teacher_labels_v2.json", encoding="utf-8"))
ts2lab = {}   # (area) -> {ts: level}
for cam, imgs in V2.items():
    for img, areas in imgs.items():
        ts = int(img.split(".")[0])
        for a, v in areas.items():
            ts2lab.setdefault(a, {})[ts] = v["stock_level"]
H2 = 7200
rows = []
for a, series in S.items():
    series = sorted(series, key=lambda r: r[0])
    for i in range(1, len(series) - 1):
        t, fill, p = series[i]
        lv = ["empty", "half", "full"][int(np.argmax(p))]
        fc = forecast_empty([(r[0], r[1]) for r in series[:i + 1]], t)
        lab_now = ts2lab.get(a, {}).get(t)
        # future labelled frames within 2h
        fut = [(tt, ts2lab[a][tt]) for tt in sorted(ts2lab.get(a, {})) if t < tt <= t + H2 + 900]
        if lab_now is None or not fut:
            continue
        empty_later = any(l == "empty" for _, l in fut)
        rows.append(dict(a=a, t=t, lv=lv, fc=fc, now=lab_now, empty_later=empty_later))
print("evaluable (area,frame) pairs:", len(rows))
def rate(sel, name):
    n = len(sel); k = sum(r["empty_later"] for r in sel)
    print(f"{name:<58} n={n:4d} empty-within-2h={k:4d} ({100*k/max(n,1):.0f}%)")
nonempty_now = [r for r in rows if r["now"] != "empty"]          # truth: shelf not empty yet
rate(nonempty_now, "BASE: any not-yet-empty area (truth)")
half_now = [r for r in nonempty_now if r["lv"] == "half"]
rate(half_now, "model says half (low)")
flag = [r for r in half_now if r["fc"] is not None and 0 < r["fc"] < H2]
rate(flag, "model says half AND forecast < 2h  (= 'Running out soon')")
rate([r for r in half_now if not (r["fc"] is not None and 0 < r["fc"] < H2)], "model says half, NOT flagged by forecast")
rate([r for r in nonempty_now if r["lv"] == "full"], "model says full")
rate([r for r in nonempty_now if r["now"] == "half"], "TRUTH half now (oracle) ")
# recall of flag among future-empty
fe = [r for r in nonempty_now if r["empty_later"]]
print("areas not empty now that were empty within 2h:", len(fe), "| model said half:", sum(r["lv"] == "half" for r in fe), "| flagged by forecast:", sum(1 for r in fe if r in flag))

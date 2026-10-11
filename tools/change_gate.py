"""Cost study: how much compute would "re-analyse only the areas that changed" save?

  .venv/Scripts/python tools/change_gate.py [--max-miss 0.0] [--repeat 3] [--out outputs/benchmark/change_gate.json]

Standalone (does not touch sensei/ beyond importing data.load_planogram / discover_images / load_image /
warp_area and the root scoring.py). For every camera and every pair of consecutive frames (about 1 h apart) and
every planogram area it compares the two 64x64 warped crops with a cheap, label-free change score:

  * grey: mean |difference| of the blurred greyscale after removing brightness gain and offset (median-centred),
  * chroma: mean |difference| of the blurred Lab a/b channels,
  * colour histogram: Hellinger distance between the hue/saturation histograms,

each log-transformed and robust-z-scored (median / 1.4826 MAD over the study pairs, no labels) and averaged.
The gate says "unchanged, reuse the last answer" when score < threshold.

The labels (data/labels/teacher_labels_v2.json) only enter to pick and judge the threshold: a pair is "unchanged" if
stock_level and planogram_compliant are both equal in the two frames; the threshold is the largest one whose
share of skipped label-changed pairs stays <= the target (0 = never). Thresholds are reported in-sample and
leave-one-camera-out (threshold chosen on the 13 other cameras, applied to the held-out one), the honest figure.
Also reported: the points a stale answer would cost (scoring.py rules), an "anchor" simulation (compare with the last
analysed frame, as a real deployment would), the unanimous-votes-only subset, an ablation (incl. per-area noise
normalisation) and the measured gating cost (ms per area, one core). Output: outputs/benchmark/change_gate.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scoring  # noqa: E402
from sensei import data  # noqa: E402

SIZE = 64                      # warp resolution of the gate
BLUR_SIGMA = 1.5               # at 64 px
HIST_BINS = (12, 4)            # hue x saturation
MIN_VISIBLE = 0.25             # share of the crop that must be visible in both frames, else "analyse"
EPS = 1e-4
COMPONENTS = ("grey", "chroma", "hist")
MISS_TARGETS = (0.0, 0.005, 0.01, 0.02, 0.05, 0.10)


# --------------------------------------------------------------------------- per-area features and change score

@dataclass
class Feat:
    """Everything the gate keeps from one area in one frame (about 40 KB)."""

    grey: np.ndarray    # (S, S) float32 blurred greyscale
    ab: np.ndarray      # (S, S, 2) float32 blurred Lab a/b
    hist: np.ndarray    # (12*4,) float32 normalised hue/saturation histogram
    vis: np.ndarray     # (S, S) bool visible pixels


def area_features(crop: np.ndarray, vis: np.ndarray) -> Feat:
    grey = cv2.GaussianBlur(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), BLUR_SIGMA)
    lab = cv2.cvtColor(crop, cv2.COLOR_RGB2LAB)[..., 1:].astype(np.float32)
    ab = cv2.GaussianBlur(lab, (0, 0), BLUR_SIGMA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1], vis.astype(np.uint8), list(HIST_BINS), [0, 180, 0, 256]).ravel()
    return Feat(grey, ab, (h / max(float(h.sum()), 1.0)).astype(np.float32), vis)


def pair_components(a: Feat, b: Feat) -> tuple[float, float, float] | None:
    """(grey, chroma, hist) change components of one area between two frames; None if too little is visible."""
    m = a.vis & b.vis
    if m.sum() < MIN_VISIBLE * m.size:
        return None
    ga, gb = a.grey[m], b.grey[m]
    d = ga / max(float(ga.mean()), 1.0) - gb / max(float(gb.mean()), 1.0)      # removes lighting gain
    grey = float(np.abs(d - np.median(d)).mean())                               # ... and offset (median-centred)
    chroma = float(np.abs(a.ab[m] - b.ab[m]).mean())
    hist = float(np.sqrt(0.5 * np.sum((np.sqrt(a.hist) - np.sqrt(b.hist)) ** 2)))
    return grey, chroma, hist


@dataclass
class Standardiser:
    """Robust z-score of log components (median, 1.4826 MAD); the gate score is the mean over components."""

    mu: np.ndarray
    sd: np.ndarray

    @classmethod
    def fit(cls, comps: np.ndarray) -> "Standardiser":
        lg = np.log(np.maximum(comps, EPS))
        mu = np.median(lg, axis=0)
        sd = 1.4826 * np.median(np.abs(lg - mu), axis=0)
        return cls(mu, np.maximum(sd, 1e-6))

    def score(self, comps: np.ndarray) -> np.ndarray:
        return ((np.log(np.maximum(comps, EPS)) - self.mu) / self.sd).mean(axis=-1)


# --------------------------------------------------------------------------- threshold logic

def auc(score: np.ndarray, positive: np.ndarray) -> float:
    """P(score of a random positive > score of a random negative), ties counted half (Mann-Whitney)."""
    pos, neg = score[positive], score[~positive]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    _, inv, counts = np.unique(allv, return_inverse=True, return_counts=True)
    ranks = (np.cumsum(counts) - (counts - 1) / 2.0)[inv]
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg)))


def choose_threshold(score: np.ndarray, changed: np.ndarray, max_miss: float) -> float:
    """Largest tau such that skipping every pair with score < tau skips at most floor(max_miss * #changed) changed ones."""
    cs = np.sort(score[changed])
    if len(cs) == 0:
        return float("inf")
    k = int(math.floor(max_miss * len(cs) + 1e-9))
    return float(cs[min(k, len(cs) - 1)])


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def summarise(skip: np.ndarray, changed: np.ndarray, loss: np.ndarray) -> dict:
    """Skip share, miss rate and cost of the stale answers for a boolean skip decision per pair."""
    n, nc, ns = len(skip), int(changed.sum()), int(skip.sum())
    missed = int((skip & changed).sum())
    lo, hi = wilson(missed, nc)
    return {"pairs": n, "skipped": ns, "skip_share": round(ns / n, 4) if n else None,
            "changed_pairs": nc, "changed_skipped": missed,
            "miss_rate": round(missed / nc, 4) if nc else None,
            "miss_rate_ci95": [round(lo, 4), round(hi, 4)],
            "stale_share_of_skipped": round(missed / ns, 4) if ns else None,
            "stale_areas_per_100_pairs": round(100 * missed / n, 3) if n else None,
            "points_lost_per_area": round(float(loss[skip & changed].sum()) / n, 4) if n else None,
            "points_lost_per_stale_area": round(float(loss[skip & changed].mean()), 2) if missed else 0.0}


def loco(comps: np.ndarray, ok: np.ndarray, cams: np.ndarray, changed: np.ndarray, max_miss: float):
    """Leave-one-camera-out: score constants and threshold from the other cameras, decision on the held-out one.

    ``ok`` marks scorable pairs; the others (too little visible) are never skipped.
    """
    skip = np.zeros(len(cams), bool)
    taus = {}
    safe = np.where(ok[:, None], comps, 1.0)
    for c in np.unique(cams):
        te = cams == c
        tr = ~te & ok
        std = Standardiser.fit(comps[tr])
        tau = choose_threshold(std.score(safe[~te]), changed[~te] & ok[~te], max_miss)
        skip[te] = ok[te] & (std.score(safe[te]) < tau)
        taus[str(c)] = round(tau, 3)
    return skip, taus


# --------------------------------------------------------------------------- data

def load_labels(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def label_changed(a: dict, b: dict) -> bool:
    return a["stock_level"] != b["stock_level"] or bool(a["planogram_compliant"]) != bool(b["planogram_compliant"])


def stale_loss(truth: dict, old: dict) -> float:
    """Points lost against a perfect answer (2) when ``old`` (the previous label) is reused for ``truth``."""
    ident, stock, _ = scoring.score_area(truth, old)
    return 2.0 - (ident + stock)


def unanimous(votes: dict, cam: str, img: str, aid: str) -> bool | None:
    v = votes.get(f"{cam}|{img}|{aid}")
    if not v:
        return None
    return len({x["stock_level"] for x in v}) == 1 and len({bool(x["compliant"]) for x in v}) == 1


# --------------------------------------------------------------------------- extraction + timing

def extract(records, planogram, repeat: int):
    """Decode, warp and featurise every frame; the stage timings are the best of ``repeat`` full passes.

    Returns (features[(cam, image_name)] -> list of Feat in planogram order, timings).
    """
    best: dict[str, float] = {}
    feats: dict = {}
    for rep in range(max(1, repeat)):
        tot = dict.fromkeys(("decode", "warp", "features", "pair", "cpu_total"), 0.0)
        n_pairs = n_areas = 0
        cpu0 = time.process_time()
        prev: dict[str, list[Feat]] = {}
        std = Standardiser(np.zeros(3), np.ones(3))          # timing of the scalar scoring only
        for r in records:
            t0 = time.perf_counter()
            img = data.load_image(r.path)
            tot["decode"] += time.perf_counter() - t0
            cur = []
            for a in planogram[r.camera_id]:
                t0 = time.perf_counter()
                crop, vis = data.warp_area(img, a.quad, size=SIZE)
                t1 = time.perf_counter()
                f = area_features(crop, vis)
                tot["warp"] += t1 - t0
                tot["features"] += time.perf_counter() - t1
                cur.append(f)
                n_areas += 1
            for old, new in zip(prev.get(r.camera_id, []), cur):
                t0 = time.perf_counter()
                comps = pair_components(old, new)
                if comps is not None:
                    std.score(np.array(comps))
                tot["pair"] += time.perf_counter() - t0
                n_pairs += 1
            prev[r.camera_id] = cur
            if rep == 0:
                feats[(r.camera_id, r.image_name)] = cur
        tot["cpu_total"] = time.process_time() - cpu0
        tot["n_areas"], tot["n_pairs"], tot["n_frames"] = n_areas, n_pairs, len(records)
        for k, v in tot.items():
            best[k] = v if k not in best or k.startswith("n_") else min(best[k], v)
    ms = lambda s, n: round(1000.0 * s / max(n, 1), 4)  # noqa: E731
    timings = {
        "decode_ms_per_frame": ms(best["decode"], best["n_frames"]),
        "warp64_ms_per_area": ms(best["warp"], best["n_areas"]),
        "features_ms_per_area": ms(best["features"], best["n_areas"]),
        "score_ms_per_area_pair": ms(best["pair"], best["n_pairs"]),
        "areas_per_frame": round(best["n_areas"] / best["n_frames"], 2),
    }
    timings["gate_ms_per_area"] = round(timings["warp64_ms_per_area"] + timings["features_ms_per_area"]
                                        + timings["score_ms_per_area_pair"], 4)
    timings["gate_ms_per_area_incl_decode"] = round(timings["gate_ms_per_area"]
                                                    + timings["decode_ms_per_frame"] / timings["areas_per_frame"], 4)
    timings["full_pass_cpu_s"] = round(best["cpu_total"], 2)
    return feats, timings


def model_cost_per_area() -> dict:
    for name in ("cost_1t_real_v2.json", "cost_1t.json"):
        p = ROOT / "outputs" / "benchmark" / name
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            return {"source": f"outputs/benchmark/{name}", "model": d.get("model"), "bf16": d.get("bf16"),
                    "cpu_s_per_area": d["cpu_s_per_area"], "cpu_s_per_image": d["cpu_s_per_image"]}
    return {"source": None, "cpu_s_per_area": None, "cpu_s_per_image": None}


# --------------------------------------------------------------------------- study

def run(a: argparse.Namespace) -> dict:
    cv2.setNumThreads(1)                                    # gate cost on one core, like tools/benchmark_cost.py
    planogram = data.load_planogram(ROOT / a.planogram)
    labels = load_labels(ROOT / a.labels)
    votes = load_labels(ROOT / a.votes) if (ROOT / a.votes).is_file() else {}
    records = data.discover_images(ROOT / a.images, planogram.keys())
    records = [r for r in records if r.image_name in labels.get(r.camera_id, {})]
    feats, timings = extract(records, planogram, a.repeat)

    by_cam: dict[str, list] = {}
    for r in records:
        by_cam.setdefault(r.camera_id, []).append(r)

    rows, comps, gaps = [], [], []
    for cam, recs in sorted(by_cam.items()):
        for i in range(len(recs) - 1):
            r0, r1 = recs[i], recs[i + 1]
            gaps.append(r1.timestamp - r0.timestamp)
            for k, area in enumerate(planogram[cam]):
                l0, l1 = labels[cam][r0.image_name].get(area.area_id), labels[cam][r1.image_name].get(area.area_id)
                if l0 is None or l1 is None:
                    continue
                c = pair_components(feats[(cam, r0.image_name)][k], feats[(cam, r1.image_name)][k])
                rows.append({"cam": cam, "aid": area.area_id, "i": i, "k": k,
                             "changed": label_changed(l0, l1), "stock_changed": l0["stock_level"] != l1["stock_level"],
                             "comp_changed": bool(l0["planogram_compliant"]) != bool(l1["planogram_compliant"]),
                             "loss": stale_loss(l1, l0),
                             "clean": bool(unanimous(votes, cam, r0.image_name, area.area_id)
                                           and unanimous(votes, cam, r1.image_name, area.area_id))})
                comps.append(c if c is not None else (np.inf,) * 3)     # not enough visible: never skippable
    C = np.array(comps, dtype=np.float64)
    cams = np.array([r["cam"] for r in rows])
    areas = np.array([r["cam"] + "|" + r["aid"] for r in rows])
    changed = np.array([r["changed"] for r in rows])
    loss = np.array([r["loss"] for r in rows])
    clean = np.array([r["clean"] for r in rows])
    n = len(rows)
    ok = np.isfinite(C).all(axis=1)
    unchanged_share = 1 - float(changed.mean())

    # ------------------------------------------------------------ headline score: in-sample and leave-one-camera-out
    std = Standardiser.fit(C[ok])
    S = np.where(ok, std.score(np.where(ok[:, None], C, 1.0)), np.inf)
    points = []
    for mm in MISS_TARGETS:
        tau = choose_threshold(S, changed, mm)
        ins = summarise(S < tau, changed, loss)
        skip_l, taus = loco(C, ok, cams, changed, mm)
        lo = summarise(skip_l, changed, loss)
        c_tau = choose_threshold(S[clean], changed[clean], mm)
        c_ins = summarise((S < c_tau)[clean], changed[clean], loss[clean])
        points.append({"target_miss_rate": mm, "threshold": round(tau, 3), "in_sample": ins,
                       "leave_one_camera_out": lo, "loco_thresholds": taus,
                       "unanimous_pairs_only_in_sample": {"threshold": round(c_tau, 3), **c_ins}})

    # ------------------------------------------------------------ ablation (in-sample, all pairs, same labels)
    def variant(name: str, score: np.ndarray, note: str = "") -> dict:
        s = np.where(ok, score, np.inf)
        t0, t1 = choose_threshold(s, changed, 0.0), choose_threshold(s, changed, 0.01)
        return {"variant": name, "auc_all": round(auc(s[ok], changed[ok]), 3),
                "auc_unanimous": round(auc(s[ok & clean], changed[ok & clean]), 3),
                "skip_at_0_miss": round(float((s < t0).mean()), 4), "skip_at_1pct_miss": round(float((s < t1).mean()), 4),
                "note": note}

    lg = np.log(np.maximum(np.where(ok[:, None], C, 1.0), EPS))
    z = (lg - std.mu) / std.sd
    abl = [variant("combined (grey+chroma+hist), global scale  [used]", z.mean(1)),
           variant("grey only", z[:, 0]), variant("chroma only", z[:, 1]), variant("colour histogram only", z[:, 2]),
           variant("grey + hist (no chroma)", z[:, [0, 2]].mean(1))]
    cam_floor = z.mean(1).copy()                                # per-camera quiet floor (25th percentile)
    for c in np.unique(cams):
        m = cams == c
        cam_floor[m] -= np.quantile(cam_floor[m & ok], 0.25)
    abl.append(variant("combined, minus per-camera noise floor (q25)", cam_floor))
    for q in (0.10, 0.25):                                      # per-area floor from the area's OTHER pairs
        zf = np.zeros_like(lg)
        for ar in np.unique(areas):
            idx = np.where((areas == ar) & ok)[0]
            for j in idx:
                oth = [x for x in idx if x != j]
                zf[j] = lg[j] - (np.quantile(lg[oth], q, axis=0) if oth else lg[j])
        med = np.median(zf[ok], axis=0)
        zf = (zf - med) / (1.4826 * np.median(np.abs(zf[ok] - med), axis=0))
        abl.append(variant(f"combined, divided by the area's own noise floor (q{int(q * 100)} of its other pairs)",
                           zf.mean(1), "per-area normalisation: worse ranking than the global scale"))

    # ------------------------------------------------------------ headline operating point + frame level + anchor protocol
    head = next(p for p in points if abs(p["target_miss_rate"] - a.max_miss) < 1e-9)
    skip_h, _ = loco(C, ok, cams, changed, a.max_miss)
    frame_key = np.array([f"{r['cam']}|{r['i']}" for r in rows])
    uniq = np.unique(frame_key)
    all_skipped = sum(bool(skip_h[frame_key == f].all()) for f in uniq)

    anchor = []
    for mm in (0.0, a.max_miss, 0.05):
        taus = next(p for p in points if abs(p["target_miss_rate"] - mm) < 1e-9)["loco_thresholds"]
        tot = skipped = stale = 0
        lost = 0.0
        run_len, longest = 0, 0
        for cam, recs in sorted(by_cam.items()):
            std_c = Standardiser.fit(C[ok & (cams != cam)])
            for k, area in enumerate(planogram[cam]):
                # re-fit exactly as in loco(): constants and tau from the other cameras
                anc = 0
                for t in range(1, len(recs)):
                    comp = pair_components(feats[(cam, recs[anc].image_name)][k], feats[(cam, recs[t].image_name)][k])
                    tot += 1
                    skip = comp is not None and float(std_c.score(np.array(comp))) < taus[cam]
                    if skip:
                        skipped += 1
                        run_len += 1
                        longest = max(longest, run_len)
                        la, lt = labels[cam][recs[anc].image_name][area.area_id], labels[cam][recs[t].image_name][area.area_id]
                        if label_changed(la, lt):
                            stale += 1
                            lost += stale_loss(lt, la)
                    else:
                        anc, run_len = t, 0
        anchor.append({"target_miss_rate_for_threshold": mm, "frames_x_areas": tot, "skip_share": round(skipped / tot, 4),
                       "stale_answers": stale, "stale_share_of_skipped": round(stale / skipped, 4) if skipped else None,
                       "stale_share_of_all": round(stale / tot, 4), "points_lost_per_area": round(lost / tot, 4),
                       "longest_skip_run_frames": longest})

    # ------------------------------------------------------------ cost
    mc = model_cost_per_area()
    gate_s = timings["gate_ms_per_area_incl_decode"] / 1000.0
    cost = {"gate_per_area_ms": timings, "model_reference": mc}
    if mc["cpu_s_per_area"]:
        cost["gate_cost_as_share_of_model_cost_per_area"] = round(gate_s / mc["cpu_s_per_area"], 5)
        sk = head["leave_one_camera_out"]["skip_share"]
        cost["net_cpu_saving_at_headline"] = round(sk - gate_s / mc["cpu_s_per_area"], 4)
        cost["cpu_s_per_image_with_gate_at_headline"] = round(
            mc["cpu_s_per_area"] * timings["areas_per_frame"] * (1 - sk) + gate_s * timings["areas_per_frame"], 3)
        cost["per_operating_point"] = []
        for p in points:
            sk_p = p["leave_one_camera_out"]["skip_share"]
            cost["per_operating_point"].append({
                "target_miss_rate": p["target_miss_rate"], "skip_share_loco": sk_p,
                "miss_rate_loco": p["leave_one_camera_out"]["miss_rate"],
                "net_cpu_saving": round(sk_p - gate_s / mc["cpu_s_per_area"], 4),
                "cpu_s_per_image_with_gate": round(mc["cpu_s_per_area"] * timings["areas_per_frame"] * (1 - sk_p)
                                                   + gate_s * timings["areas_per_frame"], 3)})
        cost["note"] = ("assumes model cost is proportional to the number of areas analysed (CLIP + DINOv2 run per 224x224 "
                        "area crop, ~98% of the time); sensei.pipeline.predict has no per-area skip yet and the per-area "
                        "fill normalisation uses the whole day, so a real implementation would reuse cached features/answers.")

    out = {
        "study": {"frames": len(records), "cameras": len(by_cam), "area_pairs": n, "scorable_pairs": int(ok.sum()),
                  "frame_spacing_s": {"min": int(min(gaps)), "median": int(np.median(gaps)), "max": int(max(gaps))},
                  "gate_resolution": SIZE, "labels": a.labels, "protocol": "consecutive frames of the same camera, all planogram areas"},
        "labels": {"changed_pairs": int(changed.sum()), "unchanged_share": round(unchanged_share, 4),
                   "oracle_max_skip_share": round(unchanged_share, 4),
                   "changed_stock_level": int(sum(r["stock_changed"] for r in rows)),
                   "changed_compliance": int(sum(r["comp_changed"] for r in rows)),
                   "unanimous_pairs": int(clean.sum()), "unanimous_changed": int((clean & changed).sum()),
                   "mean_points_lost_per_stale_changed_area": round(float(loss[changed].mean()), 2)},
        "score": {"components": list(COMPONENTS), "blur_sigma_px": BLUR_SIGMA, "hist_bins": list(HIST_BINS),
                  "combination": "mean of robust z-scores of log components", "log_median": std.mu.round(4).tolist(),
                  "log_mad_sd": std.sd.round(4).tolist(), "auc_label_changed_all": round(auc(S[ok], changed[ok]), 3),
                  "auc_label_changed_unanimous": round(auc(S[ok & clean], changed[ok & clean]), 3)},
        "operating_points": points,
        "headline": {"target_miss_rate": a.max_miss, "leave_one_camera_out": head["leave_one_camera_out"],
                     "in_sample": head["in_sample"],
                     "frames_fully_skipped_share": round(all_skipped / len(uniq), 4)},
        "anchor_simulation": anchor,
        "ablation": abl,
        "cost": cost,
        "extrapolation_5min": (
            "No 5-minute frames exist, so no 5-minute figure is measured. The hourly measurement above is the evidence: at "
            "1 h spacing %.1f%% of area-pairs keep their label and the gate (threshold chosen for <=%.1f%% missed label "
            "changes) skips %.1f%% leave-one-camera-out. At shorter spacing fewer things change, so the skippable share can only "
            "be higher than the hourly figure; treat the hourly numbers as a lower bound. What is NOT known is the miss rate: "
            "the label changes that do occur within 5 minutes may be mostly small threshold crossings (half<->full), which "
            "are the hardest to see, so the per-change miss rate at the same threshold could be worse even though far fewer "
            "areas are stale (unmeasured). "
            "Measure it on real 5-minute frames before relying on it."
            % (100 * unchanged_share, 100 * a.max_miss, 100 * head["leave_one_camera_out"]["skip_share"])),
        "notes": [
            "Labels are AI-teacher labels (84% of areas unanimous over 3 votes), not store truth; many tiny 'changes' are half/full "
            "borderline flips and compliance flips between similar-looking products, which no pixel gate can see.",
            "Thresholds in-sample use the same labels that judge them (optimistic); leave_one_camera_out is the honest figure.",
            "The per-area noise normalisation asked for was tried (ablation) and ranks label changes worse than a global scale.",
            "A skipped area keeps the previous answer; points_lost assumes that answer was perfect (best case), see scoring.py.",
        ],
    }
    return out


def print_summary(res: dict) -> None:
    s, lb, h = res["study"], res["labels"], res["headline"]
    print(f"frames {s['frames']}, cameras {s['cameras']}, area-pairs {s['area_pairs']}, spacing median {s['frame_spacing_s']['median']} s")
    print(f"label changed in {lb['changed_pairs']} pairs ({100 - 100 * lb['unchanged_share']:.1f}%); oracle skip share {100 * lb['oracle_max_skip_share']:.1f}%")
    print(f"score AUC for label change: all {res['score']['auc_label_changed_all']}, unanimous {res['score']['auc_label_changed_unanimous']}")
    print("target miss | in-sample skip / miss | leave-one-camera-out skip / miss (n/N) | points lost per area")
    for p in res["operating_points"]:
        i, lo = p["in_sample"], p["leave_one_camera_out"]
        print(f"  {100 * p['target_miss_rate']:4.1f}%    {100 * i['skip_share']:5.1f}% / {100 * i['miss_rate']:4.1f}%    "
              f"{100 * lo['skip_share']:5.1f}% / {100 * lo['miss_rate']:4.1f}% ({lo['changed_skipped']}/{lo['changed_pairs']})    "
              f"{lo['points_lost_per_area']:.4f}")
    c = res["cost"]["gate_per_area_ms"]
    print(f"gate cost: {c['gate_ms_per_area']:.3f} ms/area (warp {c['warp64_ms_per_area']:.3f} + features {c['features_ms_per_area']:.3f} "
          f"+ score {c['score_ms_per_area_pair']:.3f}), +{c['decode_ms_per_frame']:.1f} ms decode per frame")
    if "net_cpu_saving_at_headline" in res["cost"]:
        print(f"model {res['cost']['model_reference']['cpu_s_per_area']} CPU-s/area -> gate = "
              f"{100 * res['cost']['gate_cost_as_share_of_model_cost_per_area']:.3f}% of it; "
              f"net saving at headline {100 * res['cost']['net_cpu_saving_at_headline']:.1f}%")
    print(f"headline (<= {100 * h['target_miss_rate']:.1f}% missed changes): frames fully skipped {100 * h['frames_fully_skipped_share']:.1f}%")
    print("anchor protocol (compare with the last analysed frame; thresholds leave-one-camera-out):")
    for r in res["anchor_simulation"]:
        print(f"  target {100 * r['target_miss_rate_for_threshold']:.1f}%: skip {100 * r['skip_share']:.1f}%, stale answers {r['stale_answers']} "
              f"({100 * r['stale_share_of_all']:.2f}% of area-frames), {r['points_lost_per_area']:.4f} points/area, longest run {r['longest_skip_run_frames']} frames")
    print("ablation (AUC all / unanimous, skip share at 0 and 1% misses, in-sample):")
    for v in res["ablation"]:
        print(f"  {v['auc_all']:.3f} / {v['auc_unanimous']:.3f}  {100 * v['skip_at_0_miss']:4.1f}% {100 * v['skip_at_1pct_miss']:4.1f}%  {v['variant']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--images", default="data/raw/images", help="image folder (default: %(default)s)")
    ap.add_argument("--planogram", default="data/raw/planogram.json", help="planogram (default: %(default)s)")
    ap.add_argument("--labels", default="data/labels/teacher_labels_v2.json",
                    help="answer key used to choose and judge the threshold (default: %(default)s)")
    ap.add_argument("--votes", default="data/labels/votes_v2.json", help="only used for the unanimous-votes subset")
    ap.add_argument("--max-miss", type=float, default=0.0, choices=MISS_TARGETS,
                    help="headline target: max share of label-changed pairs the gate may skip (0 = never, in-sample)")
    ap.add_argument("--repeat", type=int, default=3, help="timing passes (best kept)")
    ap.add_argument("--out", default="outputs/benchmark/change_gate.json", help="result JSON (default: %(default)s)")
    a = ap.parse_args()
    res = run(a)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print_summary(res)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

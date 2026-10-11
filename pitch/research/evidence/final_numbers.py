"""Read-only: held-out numbers on the FINAL answer key (key v2, 1,962 areas, all 181 frames) for a given model.

  .venv/Scripts/python pitch/research/evidence/final_numbers.py models/real_v2 pitch/research/evidence/final_numbers_real_v2.json

Same protocol as staff_terms.py / calibrate.cross_validate: leave one camera out; the last two labelled frames of every
camera; the last labelled frame of every camera. Heads are refitted without the test cameras / frames in every fold; the
label-free core ("unsup") never sees a label. Also scores the baseline "always compliant and full". Writes only the json given as argument 2.
"""
import sys, json, time, os
ROOT = "C:/Users/alifa/learning/junctionx-sensei"
sys.path.insert(0, ROOT); os.chdir(ROOT)
import logging; logging.basicConfig(level=logging.WARNING)
import numpy as np
import scoring
from sensei import pipeline
from sensei.calibrate import HeadParams, fit_heads, label_arrays, load_labels, predictions_from_probs, _folds, _summ

MODEL = sys.argv[1]
OUT = sys.argv[2]
m = pipeline.SenseiModel.load(MODEL, load_fit_feats=True)
ff = m.fit_feats
fill, p_lv, p_comp, _ = pipeline.zero_shot(m, ff)
prod = getattr(getattr(m.stock, "coder", None), "productness", None)
LV = ["empty", "half", "full"]


def put(out, c, i, a, v):
    out.setdefault(c, {}).setdefault(i, {})[a] = v


def run(label_files, scheme, ho, only=None):
    labels = load_labels(*label_files)
    idx, ys, yc = label_arrays(ff, labels)
    truth, pred_h, pred_u, pred_b = {}, {}, {}, {}
    for _, tr, te in _folds(ff, idx, scheme, ho):
        h = fit_heads(ff.subset(tr), fill[tr], labels, m.cfg, HeadParams(), p_lv[tr], p_comp[tr], prod)
        te_f = ff.subset(te)
        keys = [ff.keys[r] for r in te]
        ph = predictions_from_probs(keys, h.stock_proba(te_f, fill[te], p_lv[te]), h.compliance_proba(te_f, fill[te], p_comp[te]))
        pu = predictions_from_probs(keys, p_lv[te], p_comp[te])
        for P, out in ((ph, pred_h), (pu, pred_u)):
            for c, imgs in P.items():
                for i, areas in imgs.items():
                    for a, v in areas.items():
                        if only is None or a in only.get(c, {}).get(i, {}):
                            put(out, c, i, a, v)
        for r in te:
            c, i, a = ff.keys[r]
            if only is None or a in only.get(c, {}).get(i, {}):
                put(truth, c, i, a, labels[c][i][a])
                put(pred_b, c, i, a, scoring.make_entry(True, 1.0))
    res = {}
    for name, pred in (("heads", pred_h), ("unsup", pred_u), ("always_compliant_full", pred_b)):
        s = _summ(scoring.score(truth, pred))
        cm = np.zeros((3, 3), int)  # truth x pred
        tp = fp = fn = tn = 0
        for c, imgs in truth.items():
            for i, areas in imgs.items():
                for a, t in areas.items():
                    p = pred[c][i][a]
                    cm[LV.index(t["stock_level"]), LV.index(p["stock_level"])] += 1
                    tw, pw = (not t["planogram_compliant"]), (not p["planogram_compliant"])
                    tp += tw and pw; fp += (not tw) and pw; fn += tw and (not pw); tn += (not tw) and (not pw)
        res[name] = {"per_area": s["per_area"], "areas": s["areas"], "ident_acc": s["ident_acc"], "stock_acc": s["stock_acc"],
                     "cm_truth_rows_e_h_f_pred_cols": cm.tolist(), "wrong_product": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}}
    return res


out = {"model": MODEL}
t0 = time.time()
for tag, files, only in (("keyV2_1962", ["data/labels/teacher_labels_v2.json"], None),):
    for scheme, ho in (("camera", 2), ("time", 2), ("time", 1)):
        k = f"{tag}/{scheme}{ho if scheme == 'time' else ''}"
        out[k] = run(files, scheme, ho, only)
        print(k, {n: (v["per_area"], v["areas"]) for n, v in out[k].items()}, f"{time.time()-t0:.0f}s", flush=True)
json.dump(out, open(OUT, "w"), indent=1)

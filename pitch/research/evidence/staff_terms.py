"""Read-only: out-of-fold confusion in staff terms for the shipped recipe. Writes nothing to the project."""
import sys, json, time
sys.path.insert(0, "C:/Users/alifa/learning/junctionx-sensei")
import os; os.chdir("C:/Users/alifa/learning/junctionx-sensei")
import logging; logging.basicConfig(level=logging.WARNING)
import numpy as np
import scoring
from sensei import pipeline, calibrate as C
from sensei.calibrate import HeadParams, fit_heads, label_arrays, load_labels, predictions_from_probs, _folds, _summ

m = pipeline.SenseiModel.load("models/real_v1_cal", load_fit_feats=True)
ff = m.fit_feats
fill, p_lv, p_comp, _ = pipeline.zero_shot(m, ff)
prod = getattr(getattr(m.stock, "coder", None), "productness", None)
LV = ["empty", "half", "full"]

def run(label_files, scheme, ho):
    labels = load_labels(*label_files)
    idx, ys, yc = label_arrays(ff, labels)
    truth, pred_h, pred_u = {}, {}, {}
    for _, tr, te in _folds(ff, idx, scheme, ho):
        h = fit_heads(ff.subset(tr), fill[tr], labels, m.cfg, HeadParams(), p_lv[tr], p_comp[tr], prod)
        te_f = ff.subset(te)
        ph = predictions_from_probs([ff.keys[r] for r in te], h.stock_proba(te_f, fill[te], p_lv[te]), h.compliance_proba(te_f, fill[te], p_comp[te]))
        pu = predictions_from_probs([ff.keys[r] for r in te], p_lv[te], p_comp[te])
        for P, out in ((ph, pred_h), (pu, pred_u)):
            for c, imgs in P.items():
                for i, areas in imgs.items():
                    out.setdefault(c, {}).setdefault(i, {}).update(areas)
        for r in te:
            c, i, a = ff.keys[r]
            truth.setdefault(c, {}).setdefault(i, {})[a] = labels[c][i][a]
    res = {}
    for name, pred in (("heads", pred_h), ("unsup", pred_u)):
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

out = {}
t0 = time.time()
for tag, files in (("key1240", ["data/labels/teacher_labels.json", "data/labels/teacher_labels_mid.json"]),
                   ("key756", ["data/labels/teacher_labels.json"])):
    for scheme, ho in (("camera", 2), ("time", 2), ("time", 1)):
        k = f"{tag}/{scheme}{ho if scheme == 'time' else ''}"
        out[k] = run(files, scheme, ho)
        print(k, {n: (v["per_area"], v["areas"]) for n, v in out[k].items()}, f"{time.time()-t0:.0f}s", flush=True)
json.dump(out, open("C:/Users/alifa/learning/junctionx-sensei/pitch/research/evidence/staff_terms.json", "w"), indent=1)

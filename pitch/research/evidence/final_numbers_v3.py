"""Read-only: held-out numbers in staff terms for the FINAL model (models/real_v3_cal) on the FINAL key (teacher_labels_v2.json).

  .venv/Scripts/python pitch/research/evidence/final_numbers_v3.py pitch/research/evidence/final_numbers_real_v3_cal.json

Same protocol as experiments/final_integration/heldout.py (it imports its fold logic and its cached zero-shot arrays):
heads refitted per fold on the full v2 key minus the held-out camera / frames, WITH the per-area memory (default HeadParams);
folds = leave one camera out; last two labelled frames of every camera; last labelled frame of every camera.
Also scores the label-free core ("unsup": zero-shot probabilities, no heads, never sees a label) and the baseline "always
compliant and full", and tallies the confusion matrices the pitch quotes in staff terms. Writes only the json given as argument 1.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "experiments/final_integration"))
import numpy as np
import scoring
import heldout as H
from sensei.calibrate import HeadParams, fit_heads, label_arrays, load_labels, predictions_from_probs, _summ

OUT = Path(sys.argv[1])
MODEL = "models/real_v3_cal"
KEY = H.L / "teacher_labels_v2.json"
LV = ["empty", "half", "full"]


def put(d, c, i, a, v):
    d.setdefault(c, {}).setdefault(i, {})[a] = v


def run(scheme):
    m, ff, fill, p_lv, p_comp, prod = H.load(MODEL)
    labels = load_labels(KEY)
    idx, _, _ = label_arrays(ff, labels)
    cams = np.array(ff.camera_ids)
    truth, ph, pu, pb = {}, {}, {}, {}
    for (kind, cam), test in H.folds(ff, idx, scheme):
        if kind == "cam":
            train = idx[cams[idx] != cam]
        else:
            held = {(ff.camera_ids[r], int(ff.timestamps[r])) for r in test}
            train = np.array([r for r in idx if (ff.camera_ids[r], int(ff.timestamps[r])) not in held])
        heads = fit_heads(ff.subset(train), fill[train], labels, m.cfg, HeadParams(), p_lv[train], p_comp[train], prod)
        te = ff.subset(test)
        keys = [ff.keys[r] for r in test]
        P = {"heads": predictions_from_probs(keys, heads.stock_proba(te, fill[test], p_lv[test]),
                                            heads.compliance_proba(te, fill[test], p_comp[test])),
             "unsup": predictions_from_probs(keys, p_lv[test], p_comp[test])}
        for name, dst in (("heads", ph), ("unsup", pu)):
            for c, imgs in P[name].items():
                for i, areas in imgs.items():
                    for a, v in areas.items():
                        put(dst, c, i, a, v)
        for r in test:
            c, i, a = ff.keys[r]
            put(truth, c, i, a, labels[c][i][a])
            put(pb, c, i, a, scoring.make_entry(True, 1.0))
    res = {}
    for name, pred in (("heads", ph), ("unsup", pu), ("always_compliant_full", pb)):
        s = _summ(scoring.score(truth, pred))
        cm = np.zeros((3, 3), int)  # truth rows x pred cols, empty/half/full
        tp = fp = fn = tn = 0
        for c, imgs in truth.items():
            for i, areas in imgs.items():
                for a, t in areas.items():
                    p = pred[c][i][a]
                    cm[LV.index(t["stock_level"]), LV.index(p["stock_level"])] += 1
                    tw, pw = (not t["planogram_compliant"]), (not p["planogram_compliant"])
                    tp += tw and pw; fp += (not tw) and pw; fn += tw and (not pw); tn += (not tw) and (not pw)
        e_list, e_full = int(cm[0, 0] + cm[0, 1]), int(cm[0, 2])
        tasks, wasted = int(cm[:, :2].sum()), int(cm[2, :2].sum())
        res[name] = {"per_area": s["per_area"], "areas": s["areas"], "ident_acc": s["ident_acc"], "stock_acc": s["stock_acc"],
                     "stock_cases": s.get("stock_cases"), "cm_truth_rows_e_h_f_pred_cols": cm.tolist(),
                     "wrong_product": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
                     "staff": {"empty_total": int(cm[0].sum()), "empty_on_todo_list": e_list, "empty_shown_full": e_full,
                               "restock_tasks": tasks, "restock_tasks_on_full_shelf": wasted,
                               "half_total": int(cm[1].sum()), "half_shown_full": int(cm[1, 2])}}
    return res


out = {"model": MODEL, "key": str(KEY.name)}
for scheme, tag in (("camera", "camera"), ("time2", "time2"), ("time1", "time1")):
    out[tag] = run(scheme)
    print(tag, {n: (v["per_area"], v["areas"]) for n, v in out[tag].items()}, flush=True)
OUT.write_text(json.dumps(out, indent=1))

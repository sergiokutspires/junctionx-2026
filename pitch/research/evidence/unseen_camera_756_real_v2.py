import sys, os
sys.path.insert(0, "C:/Users/alifa/learning/junctionx-sensei"); os.chdir("C:/Users/alifa/learning/junctionx-sensei")
import logging; logging.basicConfig(level=logging.WARNING)
import numpy as np, scoring
from sensei import pipeline
from sensei.calibrate import HeadParams, fit_heads, label_arrays, load_labels, predictions_from_probs, _folds, _summ
m = pipeline.SenseiModel.load("models/real_v2", load_fit_feats=True); ff = m.fit_feats
fill, p_lv, p_comp, _ = pipeline.zero_shot(m, ff)
prod = getattr(getattr(m.stock, "coder", None), "productness", None)
L1240 = load_labels("data/labels/teacher_labels.json", "data/labels/teacher_labels_mid.json")
L756 = load_labels("data/labels/teacher_labels.json")
idx, _, _ = label_arrays(ff, L1240)
truth, pred, pred_u = {}, {}, {}
for _, tr, te in _folds(ff, idx, "camera", 2):
    h = fit_heads(ff.subset(tr), fill[tr], L1240, m.cfg, HeadParams(), p_lv[tr], p_comp[tr], prod)
    tf = ff.subset(te)
    for P, out, ps, pc in ((None, pred, h.stock_proba(tf, fill[te], p_lv[te]), h.compliance_proba(tf, fill[te], p_comp[te])), (None, pred_u, p_lv[te], p_comp[te])):
        pass
    keys = [ff.keys[r] for r in te]
    for out, ps, pc in ((pred, h.stock_proba(tf, fill[te], p_lv[te]), h.compliance_proba(tf, fill[te], p_comp[te])), (pred_u, p_lv[te], p_comp[te])):
        for c, imgs in predictions_from_probs(keys, ps, pc).items():
            for i, areas in imgs.items():
                for a, v in areas.items():
                    if a in L756.get(c, {}).get(i, {}):      # score only the original 756-area part
                        out.setdefault(c, {}).setdefault(i, {})[a] = v
    for r in te:
        c, i, a = ff.keys[r]
        if a in L756.get(c, {}).get(i, {}):
            truth.setdefault(c, {}).setdefault(i, {})[a] = L756[c][i][a]
for n, p in (("heads", pred), ("unsup", pred_u)):
    s = _summ(scoring.score(truth, p)); print(n, s["per_area"], s["areas"], "ident", s["ident_acc"], "stock", s["stock_acc"])

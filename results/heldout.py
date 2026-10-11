"""Held-out table behind the README Results (copy of the team's experiments/final_integration/heldout.py,
moved here so it is published; only the paths changed).

  .venv/Scripts/python results/heldout.py [v1cal v3cal v1mem v3nomem]

Needs the fitted models in models/ (not published) and the AI answer key in data/labels/ (published); reads
no images. Writes results/heldout_<recipes>.json. The unsupervised part of each model was fitted on all 181
frames (pixels only, no labels), so only the heads are refitted per fold.

Final-integration held-out table: camera / time2 / time1, on the full v2 key and on the original 756 key.

Recipes (heads refitted per fold on the recipe's own training key, minus the held-out camera or frames):
  v1cal : models/real_v1_cal features, labels teacher_labels + teacher_labels_mid (1,240), no memory (the old submission)
  v3cal : models/real_v3_cal features (= real_v2, bf16), labels teacher_labels_v2 (1,962), per-area memory (default params)
  v1mem : real_v1_cal features, v2 labels, memory (check)
Test keys: "v2" = all 1,962 areas scored against v2 labels; "756" = the original 756-area key scored against
teacher_labels.json (frames of time folds = last k labelled frames per camera of that key; they equal v2's).
"""
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
logging.basicConfig(level=logging.WARNING)
import numpy as np  # noqa: E402
import scoring  # noqa: E402
from sensei import pipeline  # noqa: E402
from sensei.calibrate import HeadParams, fit_heads, load_labels, label_arrays, predictions_from_probs, _summ  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "heldout"  # zero-shot outputs per model (git-ignored)
L = ROOT / "data/labels"


def load(model):
    m = pipeline.SenseiModel.load(ROOT / model, load_fit_feats=True)
    ff = m.fit_feats
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"zs_{Path(model).name}.npz"
    if cache.is_file():
        z = np.load(cache)
        fill, p_lv, p_comp = z["fill"], z["p_lv"], z["p_comp"]
    else:
        fill, p_lv, p_comp, _ = pipeline.zero_shot(m, ff)
        np.savez(cache, fill=fill, p_lv=p_lv, p_comp=p_comp)
    return m, ff, np.asarray(fill), np.asarray(p_lv), np.asarray(p_comp), m.stock.coder.productness


def folds(ff, test_idx, scheme):
    cams = np.array(ff.camera_ids)
    if scheme == "camera":
        for cam in sorted(set(cams[test_idx])):
            yield ("cam", cam), test_idx[cams[test_idx] == cam]
        return
    k = int(scheme[4:])
    sel_all = []
    for cam in sorted(set(cams[test_idx])):
        rows = test_idx[cams[test_idx] == cam]
        frames = sorted(set(int(t) for t in ff.timestamps[rows]))
        kk = min(k, len(frames) - 1)
        last = set(frames[-kk:])
        sel_all.append(rows[[int(t) in last for t in ff.timestamps[rows]]])
    yield ("time", None), np.concatenate(sel_all)


def evaluate(model, train_labels, params, test_key, schemes=("camera", "time2", "time1")):
    m, ff, fill, p_lv, p_comp, prod = load(model)
    lab_tr = load_labels(*train_labels)
    truth_all = load_labels(test_key)
    idx_tr, _, _ = label_arrays(ff, lab_tr)
    idx_te, _, _ = label_arrays(ff, truth_all)
    cams = np.array(ff.camera_ids)
    out = {}
    for scheme in schemes:
        truth, preds = {}, {}
        for (kind, cam), test in folds(ff, idx_te, scheme):
            if kind == "cam":
                train = idx_tr[cams[idx_tr] != cam]
            else:
                held = {(ff.camera_ids[r], int(ff.timestamps[r])) for r in test}
                train = np.array([r for r in idx_tr if (ff.camera_ids[r], int(ff.timestamps[r])) not in held])
            heads = fit_heads(ff.subset(train), fill[train], lab_tr, m.cfg, params, p_lv[train], p_comp[train], prod)
            te = ff.subset(test)
            ps = heads.stock_proba(te, fill[test], p_lv[test])
            pc = heads.compliance_proba(te, fill[test], p_comp[test])
            p = predictions_from_probs([ff.keys[r] for r in test], ps, pc)
            for c, imgs in p.items():
                for img, areas in imgs.items():
                    preds.setdefault(c, {}).setdefault(img, {}).update(areas)
            for r in test:
                c, img, a = ff.keys[r]
                truth.setdefault(c, {}).setdefault(img, {})[a] = truth_all[c][img][a]
        out[scheme] = _summ(scoring.score(truth, preds))
    return out


RECIPES = {
    "v1cal": ("models/real_v1_cal", [L / "teacher_labels.json", L / "teacher_labels_mid.json"], replace(HeadParams(), memory=False)),
    "v3cal": ("models/real_v3_cal", [L / "teacher_labels_v2.json"], HeadParams()),
    "v1mem": ("models/real_v1_cal", [L / "teacher_labels_v2.json"], HeadParams()),
    "v3nomem": ("models/real_v3_cal", [L / "teacher_labels_v2.json"], replace(HeadParams(), memory=False)),
}
KEYS = {"v2": L / "teacher_labels_v2.json", "756": L / "teacher_labels.json"}

if __name__ == "__main__":
    names = sys.argv[1:] or list(RECIPES)
    res = {}
    for name in names:
        model, tr, params = RECIPES[name]
        for key, path in KEYS.items():
            r = evaluate(model, tr, params, path)
            res[f"{name}|{key}"] = r
            print(f"{name:8s} key {key:4s} " + " | ".join(f"{s} {v['per_area']:.3f} (n {v['areas']}, id {v['ident_acc']:.3f}, st {v['stock_acc']:.3f})" for s, v in r.items()), flush=True)
    (HERE / f"heldout_{'_'.join(names)}.json").write_text(json.dumps(res, indent=1))

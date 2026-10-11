"""Label-free score of a model: its zero-shot (no heads, no labels) answers scored against the AI answer key.

  .venv/Scripts/python results/labelfree.py [models/real_v1 ...]

Same test sets as results/heldout.py: all 1,962 labelled areas ("camera"; no heads are fitted, so nothing needs
holding out), the last two labelled frames of every camera ("time2") and the last one ("time1"). Uses the
model's unsupervised outputs exactly as the "baseline" method of `python -m sensei calibrate`. Needs the fitted
model in models/ (not published); reads no images. Writes results/labelfree_<model>.json.
"""
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "results"))
logging.basicConfig(level=logging.WARNING)
import numpy as np  # noqa: E402

import scoring  # noqa: E402
from heldout import folds, load  # noqa: E402
from sensei.calibrate import _summ, label_arrays, load_labels, predictions_from_probs  # noqa: E402

KEY = ROOT / "data/labels/teacher_labels_v2.json"


def evaluate(model: str) -> dict:
    m, ff, fill, p_lv, p_comp, _ = load(model)
    truth_all = load_labels(KEY)
    idx, _, _ = label_arrays(ff, truth_all)
    out = {}
    for scheme in ("camera", "time2", "time1"):
        test = np.concatenate([t for _, t in folds(ff, idx, scheme)])
        preds = predictions_from_probs([ff.keys[r] for r in test], p_lv[test], p_comp[test])
        truth = {}
        for r in test:
            c, img, a = ff.keys[r]
            truth.setdefault(c, {}).setdefault(img, {})[a] = truth_all[c][img][a]
        out[scheme] = _summ(scoring.score(truth, preds))
    return out


if __name__ == "__main__":
    for model in sys.argv[1:] or ["models/real_v1"]:
        r = evaluate(model)
        print(model, " | ".join(f"{s} {v['per_area']:.3f} (n {v['areas']})" for s, v in r.items()), flush=True)
        (ROOT / "results" / f"labelfree_{Path(model).name}.json").write_text(json.dumps(r, indent=1))

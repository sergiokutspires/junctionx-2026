"""Local copy of the Sensei challenge scorer, plus score-optimal decision rules.

Usage:  python scoring.py annotations.json predictions.json

Both files use the challenge format:
    {camera_id: {image_name: {area_id: {"planogram_compliant": bool,
                                        "stock_level": "empty|half|full",
                                        "stock_value": 0 | 0.5 | 1}}}}
"""
import json
import sys
from collections import Counter

LEVELS = {"empty": 0.0, "half": 0.5, "full": 1.0}
NAMES = {0.0: "empty", 0.5: "half", 1.0: "full"}

ID_RIGHT, ID_WRONG = 1, -2
STOCK_RIGHT, STOCK_BELOW, STOCK_ABOVE = 1, -2, -3


def stock_value(entry):
    if entry.get("stock_value") is not None:
        return float(entry["stock_value"])
    return LEVELS[entry["stock_level"]]


def score_area(truth, pred):
    """Return (identification_points, stock_points, stock_case) for one area."""
    if pred is None:  # annotated but missing: staff get no warning
        return ID_WRONG, STOCK_ABOVE, "missing"
    ident = ID_RIGHT if bool(pred["planogram_compliant"]) == bool(truth["planogram_compliant"]) else ID_WRONG
    t, p = stock_value(truth), stock_value(pred)
    if abs(t - p) < 1e-9:
        return ident, STOCK_RIGHT, "correct"
    if p < t:
        return ident, STOCK_BELOW, "below"
    return ident, STOCK_ABOVE, "above"


def score(annotations, predictions):
    total, cases, ident_cases, n = 0, Counter(), Counter(), 0
    for cam, images in annotations.items():
        for image, areas in images.items():
            for area_id, truth in areas.items():
                pred = predictions.get(cam, {}).get(image, {}).get(area_id)
                ident, stock, case = score_area(truth, pred)
                total += ident + stock
                cases[case] += 1
                ident_cases["right" if ident == ID_RIGHT else "wrong"] += 1
                n += 1
    return {"total": total, "max": 2 * n, "areas": n,
            "identification": dict(ident_cases), "stock": dict(cases)}


# --- decision rules: pick the answer with the best EXPECTED score -----------

def best_compliance(p_compliant):
    """Both mistakes cost the same, so the threshold is plain 0.5."""
    return p_compliant >= 0.5


def best_stock(p_empty, p_half, p_full):
    """Pick the level maximising expected points given a posterior over the truth.

    Predicting l scores +1 if right, -2 for each unit of truth above l (too low),
    -3 for truth below l (too high), so the optimum leans towards lower levels.
    """
    probs = {0.0: p_empty, 0.5: p_half, 1.0: p_full}
    best = None
    for guess in probs:
        ev = sum(p * (STOCK_RIGHT if truth == guess else STOCK_BELOW if truth > guess else STOCK_ABOVE)
                 for truth, p in probs.items())
        if best is None or ev > best[1]:
            best = (guess, ev)
    return best[0], NAMES[best[0]]


def make_entry(compliant, value):
    return {"planogram_compliant": bool(compliant), "stock_level": NAMES[value], "stock_value": value}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f_truth, open(sys.argv[2]) as f_pred:
        result = score(json.load(f_truth), json.load(f_pred))
    print(json.dumps(result, indent=2))
    print(f"\nScore: {result['total']} / {result['max']}")

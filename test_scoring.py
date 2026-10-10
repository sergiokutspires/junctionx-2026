"""Reproduce the worked example from the brief (320 / 578) and sanity-check the decision rules."""
from scoring import best_compliance, best_stock, make_entry, score

# 289 areas: ident 270 right / 19 wrong; stock 230 correct / 35 below / 24 above.
truth, pred = {}, {}
for i in range(289):
    area = f"c_{i}"
    t_val = 0.5  # truth is "half" for areas predicted too low / correct / too high alike
    p_val = 0.0 if i < 35 else 1.0 if i < 59 else 0.5  # 35 below, 24 above, 230 correct
    truth.setdefault("c", {}).setdefault("img.jpg", {})[area] = make_entry(True, t_val)
    pred.setdefault("c", {}).setdefault("img.jpg", {})[area] = make_entry(i >= 19, p_val)  # first 19 wrong

result = score(truth, pred)
assert result["total"] == 320 and result["max"] == 578, result

# A missing area costs -2 and -3.
assert score(truth, {})["total"] == 289 * -5

# Sure of the answer -> pick it; unsure between half/full -> lean low (over costs 3, under costs 2).
assert best_stock(0, 0, 1)[0] == 1.0
assert best_stock(0, 0.5, 0.5)[0] == 0.5
assert best_stock(0.34, 0.33, 0.33)[0] == 0.0
assert best_compliance(0.5) and not best_compliance(0.49)
print("ok: example reproduces 320 / 578, decision rules behave")

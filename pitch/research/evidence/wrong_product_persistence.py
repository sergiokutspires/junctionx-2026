"""Read-only: how many distinct areas are ever 'wrong product' in the AI answer key, how long they stay wrong, and when."""
import json, collections
ROOT = "C:/Users/alifa/learning/junctionx-sensei/"
def load(p): return json.load(open(ROOT + p, encoding="utf-8"))
for name, files in (("key1240 (headline key)", ["teacher_labels", "teacher_labels_mid"]), ("v2 (all 181 frames, pending)", ["teacher_labels_v2"])):
    t = {}
    for f in files:
        for c, imgs in load(f"data/labels/{f}.json").items():
            for i, a in imgs.items():
                t.setdefault(c, {}).setdefault(i, {}).update(a)
    per_area = collections.defaultdict(lambda: [0, 0]); byhour = collections.Counter(); tot_h = collections.Counter()
    for c, imgs in t.items():
        for i, areas in imgs.items():
            ts = int(i.split(".")[0]); h = (ts + 3600) % 86400 // 3600      # Europe/Lisbon summer time = UTC+1
            for a, v in areas.items():
                per_area[a][1] += 1; tot_h[h] += 1
                if not v["planogram_compliant"]:
                    per_area[a][0] += 1; byhour[h] += 1
    wrong = {a: v for a, v in per_area.items() if v[0]}
    print(name, "| wrong (area,frame) instances:", sum(v[0] for v in wrong.values()), "| distinct areas ever wrong:", len(wrong), "of", len(per_area))
    print("  share of labelled frames each such area is wrong:", sorted(round(v[0] / v[1], 2) for v in wrong.values()))
    print("  wrong/total by local hour:", {h: f"{byhour[h]}/{tot_h[h]}" for h in sorted(tot_h)})

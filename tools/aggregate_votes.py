"""Merge all teacher votes into one answer key (majority vote) and list the disagreements.

  .venv/Scripts/python tools/aggregate_votes.py <workflow journal.jsonl> [<adjudications.json>]

Inputs: the new votes (a workflow journal whose agents are labelled "label:<cam>#<job><L>:<kind>"),
the single votes already in data/labels/teacher_labels_{late,mid}.json (counted as vote "A") and the
3-camera key in data/labels/teacher_labels_partial.json (kept as is). Outputs in data/labels/:
votes_v2.json (every vote), disputes_v2.json (no level majority or split compliance) and
teacher_labels_v2.json (consensus; disputes use adjudications when given, else the median level and
the majority / "compliant" on ties).
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "data" / "labels"
ORDER = ["empty", "half", "full"]
VALUE = {"empty": 0.0, "half": 0.5, "full": 1.0}


def load(name: str) -> dict:
    return json.loads((LAB / name).read_text(encoding="utf-8"))


def main(journal: str, adjudications: str | None = None) -> None:
    votes: dict[str, list] = collections.defaultdict(list)
    for name in ("teacher_labels_late.json", "teacher_labels_mid.json"):
        for cam, imgs in load(name).items():
            for img, areas in imgs.items():
                for aid, a in areas.items():
                    votes[f"{cam}|{img}|{aid}"].append({"L": "A", "stock_level": a["stock_level"],
                                                        "compliant": a["planogram_compliant"], "src": name})
    started = {}
    for line in open(journal, encoding="utf-8"):
        e = json.loads(line)
        if e.get("type") == "started":
            started[e["key"]] = e.get("label", "")
        elif e.get("type") == "result" and started.get(e["key"], "").startswith("label:"):
            lab = started[e["key"]]
            cam, rest = lab.split(":")[1].split("#")          # "label:6376#0A:new" -> "6376", "0A"
            letter = [c for c in rest if c.isalpha()][0]
            for fr in e["result"]["frames"]:
                img = fr["image_name"] if fr["image_name"].endswith(".jpg") else fr["image_name"] + ".jpg"
                for a in fr["areas"]:
                    key = f"{cam}|{img}|{a['area_id']}"
                    if not any(v["L"] == letter and v.get("src") == "new" for v in votes[key]):
                        votes[key].append({"L": letter, "stock_level": a["stock_level"], "compliant": a["compliant"],
                                           "seen": a.get("seen", ""), "confidence": a.get("confidence", ""), "src": "new"})
    plan = json.loads((ROOT / "data/raw/planogram.json").read_text(encoding="utf-8"))
    valid = {a["area_id"] for s in plan.values() for c in s["cameras"].values() for a in c["products"]}
    adj = json.loads(Path(adjudications).read_text(encoding="utf-8")) if adjudications else {}

    key2 = load("teacher_labels_partial.json")          # 3 cameras, 2-3 votes each, already consensus
    labels: dict = {}
    disputes, stats = [], collections.Counter()
    for cam, imgs in key2.items():
        for img, areas in imgs.items():
            labels.setdefault(cam, {})[img] = dict(areas)
            stats["partial_key"] += len(areas)
    for key, vs in sorted(votes.items()):
        cam, img, aid = key.split("|")
        if aid not in valid or cam in key2:
            continue
        counts = collections.Counter(v["stock_level"] for v in vs)
        level, top = counts.most_common(1)[0]
        n_true = sum(v["compliant"] for v in vs)
        level_ok = len(vs) >= 2 and top * 2 > len(vs)
        comp_ok = n_true in (0, len(vs))
        if key in adj:
            level, comp = adj[key]["stock_level"], bool(adj[key]["planogram_compliant"])
            stats["adjudicated"] += 1
        elif level_ok and comp_ok:
            comp = n_true == len(vs)
            stats["unanimous" if top == len(vs) else "majority"] += 1
        else:
            level = level if level_ok else ORDER[sorted(ORDER.index(v["stock_level"]) for v in vs)[(len(vs) - 1) // 2]]
            comp = n_true * 2 >= len(vs)
            disputes.append({"key": key, "votes": vs})
            stats["disputed"] += 1
        labels.setdefault(cam, {}).setdefault(img, {})[aid] = {"planogram_compliant": comp, "stock_level": level,
                                                              "stock_value": VALUE[level]}
    (LAB / "votes_v2.json").write_text(json.dumps(votes, ensure_ascii=False), encoding="utf-8")
    (LAB / "disputes_v2.json").write_text(json.dumps(disputes, ensure_ascii=False, indent=0), encoding="utf-8")
    (LAB / "teacher_labels_v2.json").write_text(json.dumps(labels, indent=1), encoding="utf-8")
    rows = [a for c in labels.values() for i in c.values() for a in i.values()]
    n_votes = collections.Counter(len(v) for k, v in votes.items() if k.split("|")[0] not in key2)
    print(f"areas {len(rows)} in {sum(len(i) for i in labels.values())} frames; votes per area {dict(n_votes)}")
    print(dict(stats), "| levels", dict(collections.Counter(a["stock_level"] for a in rows)),
          "| non-compliant", sum(not a["planogram_compliant"] for a in rows))


if __name__ == "__main__":
    main(*sys.argv[1:])

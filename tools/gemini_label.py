"""Label planogram areas with Gemini (free API tier) as a second, independent teacher.

Reads the key from gemini_key.txt in the project root (git-ignored) or $GEMINI_API_KEY, and the
labelling sheets rendered by tools/render_teacher_sheets.py (data/teacher/<cam>/<ts>_{overview,areas}.jpg).

  .venv/Scripts/python tools/gemini_label.py --frames labelled     # agreement check vs the Claude labels
  .venv/Scripts/python tools/gemini_label.py --frames unlabelled   # new labels for the remaining frames
  .venv/Scripts/python tools/gemini_label.py --report              # agreement + write data/labels/gemini_labels.json

Raw answers are cached per frame in data/labels/gemini/, so re-running resumes after a quota stop.
"""
import argparse
import base64
import collections
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEACHER = ROOT / "data" / "teacher"
OUT = ROOT / "data" / "labels" / "gemini"
API = "https://generativelanguage.googleapis.com/v1beta"
LEVELS = {"empty": 0.0, "half": 0.5, "full": 1.0}

GUIDE = """You are a careful annotator labelling planogram areas in ceiling-camera photos of the fruit & vegetable section of a Portuguese supermarket (Continente).
Image 1 is the full frame with every planogram area outlined in yellow and numbered. Image 2 has one zoomed tile per area (yellow outline = the area; header "#n (area_id)" and the planogram product name in Portuguese).
Label ONLY what is inside each yellow outline (it may be slightly offset; judge the crate/compartment it mostly covers).
stock_level: "full" = (nearly) fully covered, crate/tray bottom essentially not visible (>= ~75% covered), a normal well-stocked display even if not heaped; "half" = clearly partially stocked, a substantial part of the bottom visible (~25-75%) or a visibly depleted pile; "empty" = no product or only a few scattered units (< ~25% covered). Large single items (melons, pineapples, cabbages): judge coverage / how many more would fit. Packaged products: same rule on the surface.
compliant: true if the product shown is the planogram product (same kind and, when visible, same form: loose vs bagged/packed, colour/variety such as red vs green pepper, white vs red grapes, red vs white potatoes); true if the area is empty; false if the area mainly shows a different product. Fine varieties you cannot tell apart (Gala vs Fuji, peach vs nectarine) -> true unless clearly different. Two products sharing -> judge the dominant one.
Portuguese hints: BANANA PAO = large cooking banana; CITRINOS/CITR...LARANJA = oranges (KG loose, 1.5 KG/3KG net bags); CLEMENTINA; LIMAO lemon; LIMA lime; MACA/MAÇÃ apple; PERA pear; KIWI (500 G/400 G packs); MELANCIA watermelon; MELAO melon; MELOA cantaloupe/galia; MANGA mango; ABACAXI pineapple; MAMAO/PAPAIA papaya; MARACUJA/GRANADILHA passion fruit; PITAYA dragon fruit (packs); GOIABA guava; UVA BRANCA/RED GLOBE white/red grapes; CEREJA cherries; MORANGO strawberries; ALPERCE apricot; PESSEGO peach (PARAGUAYO flat peach); NECTARINA; TOMATE (CACHO vine, CHERRY, CORACAO DE BOI oxheart, CHUCHA plum; EMB/grams = packs); BATATA potato (DOCE sweet, VERMELHA red, BRANCA white, EMB. 3KG bags); CEBOLA onion (ROXA red; EMB bags); CEBOLINHA FRANCESA small onions/shallots pack; ALHO garlic; ABOBORA pumpkin; GENGIBRE ginger; ALFACE lettuce; ABACATE avocado; PIMENTO pepper (VERDE green, VERMELHO red); COUVE cabbage (BROCOLO broccoli, FLOR cauliflower, ROXA red, BRANCA white, PORTUGUESA kale); CURGETE zucchini; BERINGELA eggplant; CHUCHU chayote; FEIJAO VERDE green beans; PEPINO cucumber. "KG" = loose.
Return every listed area exactly once."""

SCHEMA = {"type": "OBJECT", "properties": {"areas": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "area_id": {"type": "STRING"}, "stock_level": {"type": "STRING", "enum": ["empty", "half", "full"]},
    "compliant": {"type": "BOOLEAN"}, "seen": {"type": "STRING"}},
    "required": ["area_id", "stock_level", "compliant", "seen"]}}}, "required": ["areas"]}


def api_key() -> str:
    f = ROOT / "gemini_key.txt"
    key = f.read_text(encoding="utf-8").strip() if f.exists() else os.environ.get("GEMINI_API_KEY", "")
    if not key:
        sys.exit("No key: create gemini_key.txt in the project root (one line, the key from aistudio.google.com/apikey).")
    return key


def call(url: str, key: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def pick_model(key: str, wanted: str | None) -> str:
    if wanted:
        return wanted
    names = [m["name"].split("/")[-1] for m in call(f"{API}/models?pageSize=200", key).get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    stable = [n for n in names if n.startswith("gemini-") and not any(t in n for t in ("exp", "lite", "tts", "image", "live", "embedding"))]
    for tier in ("pro", "flash"):
        cands = sorted((n for n in stable if tier in n), key=lambda n: (("preview" not in n), n), reverse=True)
        if cands:
            return cands[0]
    sys.exit(f"no suitable Gemini model in: {names}")


def b64(path: Path) -> dict:
    return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(path.read_bytes()).decode()}}


def label_frame(key: str, model: str, cam: str, ts: str, areas: list) -> dict:
    listing = "\n".join(f"- {a} : {name}" for a, name in areas)
    body = {"contents": [{"parts": [{"text": f"{GUIDE}\n\nCAMERA {cam}, frame {ts}.jpg. Areas:\n{listing}"},
                                    b64(TEACHER / cam / f"{ts}_overview.jpg"), b64(TEACHER / cam / f"{ts}_areas.jpg")]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": SCHEMA}}
    out = call(f"{API}/models/{model}:generateContent", key, body)
    return json.loads(out["candidates"][0]["content"]["parts"][0]["text"])


def frames_to_do(which: str) -> list[tuple[str, str]]:
    manifest = json.loads((TEACHER / "manifest.json").read_text(encoding="utf-8"))
    labelled = json.loads((ROOT / "data/labels/teacher_labels.json").read_text(encoding="utf-8"))
    todo = []
    for cam, frames in manifest["frames"].items():
        for f in frames:
            is_lab = f in labelled.get(cam, {})
            if which == "all" or (which == "labelled") == is_lab:
                todo.append((cam, f[:-4]))
    return todo


def run(which: str, model_arg: str | None, rpm: float) -> None:
    key = api_key()
    model = pick_model(key, model_arg)
    areas = {cam: v for cam, v in json.loads((TEACHER / "manifest.json").read_text(encoding="utf-8"))["areas"].items()}
    OUT.mkdir(parents=True, exist_ok=True)
    todo = [(c, t) for c, t in frames_to_do(which) if not (OUT / f"{c}_{t}.json").exists()]
    print(f"model {model}: {len(todo)} frames to label ({which})")
    for i, (cam, ts) in enumerate(todo, 1):
        for attempt in range(6):
            try:
                res = label_frame(key, model, cam, ts, areas[cam])
                (OUT / f"{cam}_{ts}.json").write_text(json.dumps({"model": model, **res}, ensure_ascii=False), encoding="utf-8")
                print(f"[{i}/{len(todo)}] {cam} {ts}: {len(res.get('areas', []))} areas", flush=True)
                break
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                if e.code == 429 and "PerDay" in msg:
                    sys.exit(f"Daily free quota reached after {i - 1} frames - re-run tomorrow or with --model <a flash model>. {msg}")
                wait = 20 * (attempt + 1) if e.code in (429, 500, 503) else None
                if wait is None:
                    sys.exit(f"HTTP {e.code}: {msg}")
                print(f"  HTTP {e.code}, retry in {wait}s", flush=True)
                time.sleep(wait)
            except (json.JSONDecodeError, KeyError, IndexError, TimeoutError, urllib.error.URLError) as e:
                print(f"  bad answer ({e.__class__.__name__}), retry", flush=True)
                time.sleep(5)
        time.sleep(60.0 / rpm)


def report() -> None:
    teacher = json.loads((ROOT / "data/labels/teacher_labels.json").read_text(encoding="utf-8"))
    plan = json.loads((TEACHER / "manifest.json").read_text(encoding="utf-8"))["areas"]
    labels, agree, conf, n_comp = {}, collections.Counter(), collections.Counter(), collections.Counter()
    for f in sorted(OUT.glob("*.json")):
        cam, ts = f.stem.split("_", 1)
        img = f"{ts}.jpg"
        valid = {a for a, _ in plan[cam]}
        got = {a["area_id"]: a for a in json.loads(f.read_text(encoding="utf-8")).get("areas", []) if a.get("area_id") in valid}
        if len(got) != len(valid):
            print(f"skip {cam} {img}: {len(got)}/{len(valid)} areas")
            continue
        for aid, a in got.items():
            labels.setdefault(cam, {}).setdefault(img, {})[aid] = {
                "planogram_compliant": bool(a["compliant"]), "stock_level": a["stock_level"], "stock_value": LEVELS[a["stock_level"]]}
            t = teacher.get(cam, {}).get(img, {}).get(aid)
            if t:
                agree["n"] += 1
                agree["level"] += t["stock_level"] == a["stock_level"]
                agree["comp"] += t["planogram_compliant"] == bool(a["compliant"])
                conf[(t["stock_level"], a["stock_level"])] += 1
                n_comp[(t["planogram_compliant"], bool(a["compliant"]))] += 1
    n = sum(len(i) for c in labels.values() for i in c.values())
    (ROOT / "data/labels/gemini_labels.json").write_text(json.dumps(labels, indent=1), encoding="utf-8")
    print(f"wrote data/labels/gemini_labels.json: {n} areas")
    if agree["n"]:
        print(f"agreement with Claude labels on {agree['n']} areas: level {agree['level'] / agree['n']:.1%}, "
              f"compliance {agree['comp'] / agree['n']:.1%}")
        print("level confusion (claude -> gemini):", {f"{a}->{b}": v for (a, b), v in sorted(conf.items())})
        print("compliance (claude, gemini):", dict(n_comp))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", choices=["labelled", "unlabelled", "all"])
    ap.add_argument("--model", help="Gemini model id (default: newest available pro, else flash)")
    ap.add_argument("--rpm", type=float, default=4.0, help="requests per minute (free tier is low)")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.frames:
        run(a.frames, a.model, a.rpm)
    if a.report or not a.frames:
        report()

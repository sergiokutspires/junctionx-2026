"""Fingerprint the shipped models so anyone can check the model run on the validation images is the submitted one.

Writes results/model_manifest.json with the SHA-256 of every file in each model folder (the models themselves
are not in the public repo because they contain features of the store's images).

  .venv/Scripts/python tools/model_manifest.py            # write the manifest
  .venv/Scripts/python tools/model_manifest.py --check    # verify the local models still match it
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("real_v3_cal", "real_v1")          # submission model, label-free fallback
OUT = ROOT / "results" / "model_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint() -> dict:
    out = {}
    for name in MODELS:
        folder = ROOT / "models" / name
        files = sorted(p for p in folder.rglob("*") if p.is_file())
        out[name] = {str(p.relative_to(folder)).replace("\\", "/"): {"sha256": sha256(p), "bytes": p.stat().st_size}
                     for p in files}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare local models with results/model_manifest.json")
    args = ap.parse_args()
    current = fingerprint()
    if args.check:
        saved = json.loads(OUT.read_text(encoding="utf-8"))["models"]
        bad = [f"{m}/{f}" for m in saved for f in set(saved[m]) | set(current.get(m, {}))
               if saved[m].get(f, {}).get("sha256") != current.get(m, {}).get(f, {}).get("sha256")]
        print("models match the manifest" if not bad else f"MISMATCH in {len(bad)} file(s): {bad[:10]}")
        sys.exit(1 if bad else 0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"note": "SHA-256 of the shipped model files; check with tools/model_manifest.py --check",
                               "models": current}, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{m} ({len(v)} files)" for m, v in current.items()))


if __name__ == "__main__":
    main()

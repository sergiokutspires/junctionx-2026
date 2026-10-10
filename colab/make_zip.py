"""Zip the project for Google Colab: ``python colab/make_zip.py [--out junctionx-sensei.zip] [--with-images]``.

Uses Python's zipfile with forward-slash entry names (PowerShell 5.1 ``Compress-Archive`` writes
backslashes, which Linux unzips as flat file names). Leaves out .venv, cache, outputs,
experiments, __pycache__, data/teacher (labelling sheets) and, unless ``--with-images``, the raw images (the notebook unpacks the
dataset zip itself). Keeps data/labels (teacher labels for ``--labels``) and models/.
"""
from __future__ import annotations

import argparse
import logging
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "cache", "outputs", "experiments", "__pycache__", ".pytest_cache", ".git", ".ipynb_checkpoints"}
log = logging.getLogger("make_zip")


def make_zip(out: Path, with_images: bool = False) -> Path:
    """Write the project archive to ``out`` (entries under ``junctionx-sensei/``) and return it."""
    out = out.resolve()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if not path.is_file() or path == out or any(p in SKIP_DIRS for p in rel.parts):
                continue
            if rel.parts[:2] == ("data", "teacher") or (not with_images and rel.parts[:3] == ("data", "raw", "images")):
                continue
            if path.suffix == ".zip":
                continue
            z.write(path, "junctionx-sensei/" + rel.as_posix())
            n += 1
    log.info("%d files -> %s (%.1f MB)", n, out, out.stat().st_size / 1e6)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT.parent / "junctionx-sensei.zip"))
    ap.add_argument("--with-images", action="store_true", help="also pack data/raw/images")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    make_zip(Path(args.out), args.with_images)


if __name__ == "__main__":
    main()

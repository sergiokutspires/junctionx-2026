"""Add a password-protected "Sensei team" area with the SHARP store pictures to a built public site.

    python tools/build_vault.py --site outputs/site
        [--app outputs/rehearsal_final/dashboard] [--day outputs/day_replay/dashboard]
        [--password-file docs/team_password.txt] [--base-url https://sergiokutspires.github.io/junctionx-2026/]

Creates <site>/team/:
  index.html, vault.css, vault.js   login page (password -> PBKDF2 key in the browser)
  sw.js                             service worker (scope team/): decrypts img/*.jpg on the fly
  guard.js                          injected into the app copies: no key -> back to the login page
  vault.json                        public KDF parameters + an encrypted check string
  app/, day/                        copies of the sharp staff apps; every picture is ONLY stored as
                                    <name>.enc = IV(12) || AES-256-GCM ciphertext || tag(16)

Security model: GitHub Pages is a static host, so there is no server-side login. Instead, the
pictures are encrypted at build time; only someone with the password can derive the AES key
(PBKDF2-HMAC-SHA256, 600 000 iterations, random salt). The plaintext pictures never leave the laptop.

The password lives ONLY in docs/team_password.txt (git-ignored). It is generated once and reused,
so it stays stable across rebuilds. Delete that file to rotate the password. NOTE: the site is
published through git, so old .enc files + old vault.json stay in the Pages branch history; a real
rotation (revoking an old password / magic link) also needs that history rewritten (orphan branch +
force push). That is a publishing decision for the owner. Share the magic link only privately.

Only an allowlist of file types is copied in plain form (html/js/css/json/txt/map); pictures are
encrypted; any other file type (gif, svg, video, ...) stops the build so nothing sharp slips through.
Every copied text file is scanned: embedded raster pictures (data:image base64) larger than a small
icon stop the build too.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import secrets
import shutil
import sys
import io
import time
from pathlib import Path

from PIL import Image

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parents[1]
VAULT_SRC = ROOT / "site" / "vault"
PICS = {".jpg", ".jpeg", ".png", ".webp"}
PLAIN = {".html", ".htm", ".js", ".css", ".json", ".txt", ".map"}
MAX_EMBEDDED_PX = 256      # data:image rasters up to this size (favicon, small logo) may stay in plain text
DATA_IMG = re.compile(r"data:image/([a-z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)", re.I)
ITERATIONS = 600_000
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CHECK_TEXT = b"fresh-vault-check-v1"
DEFAULT_BASE_URL = "https://sergiokutspires.github.io/junctionx-2026/"


# ---------------------------------------------------------------- crypto helpers
def generate_password() -> str:
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(4))


def derive_key(password: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def encrypt(key: bytes, data: bytes) -> bytes:
    iv = secrets.token_bytes(12)
    return iv + AESGCM(key).encrypt(iv, data, None)


def decrypt(key: bytes, blob: bytes) -> bytes:
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


def make_vault_meta(key: bytes, salt: bytes, iterations: int, n_files: int) -> dict:
    return {
        "v": 1,
        "kdf": "PBKDF2-HMAC-SHA256",
        "cipher": "AES-256-GCM",
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "check": base64.b64encode(encrypt(key, CHECK_TEXT)).decode("ascii"),
        "files": n_files,
    }


def check_password(meta: dict, password: str) -> bool:
    key = derive_key(password, base64.b64decode(meta["salt"]), int(meta["iterations"]))
    try:
        return decrypt(key, base64.b64decode(meta["check"])) == CHECK_TEXT
    except Exception:
        return False


# ---------------------------------------------------------------- password file
def load_or_create_password(path: Path, base_url: str) -> str:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*password\s*:\s*(\S+)", line, re.I)
            if m:
                return m.group(1)
        raise SystemExit(f"{path} exists but has no 'password: ...' line. Fix or delete it.")
    pw = generate_password()
    path.parent.mkdir(parents=True, exist_ok=True)
    link = base_url.rstrip("/") + "/team/#k=" + pw
    path.write_text(
        "Sensei team access to the SHARP pictures (keep private, never commit, never paste in public).\n"
        f"password: {pw}\n"
        f"magic link: {link}\n"
        "The magic link logs in automatically; the part after # never reaches the server.\n",
        encoding="utf-8",
    )
    return pw


# ---------------------------------------------------------------- site build
def _patch_tour_home(js: str) -> str:
    # in team/app and team/day, "home" must go to the public landing page two levels up
    js = js.replace('href="../"', 'href="../../"')
    js = re.sub(r"href\s*=\s*'\.\./'", "href = '../../'", js)
    # the team copies show the SHARP pictures: the public tour's "pixelated" sentence would be wrong
    js = js.replace("Pictures are pixelated here for privacy.", "These are the real, sharp camera pictures.")
    js = re.sub(r"[^'\"\n.!?;{}()<>]*pixelat[^'\"\n.!?;{}()<>]*[.!?]?", " These are the real, sharp camera pictures.", js, flags=re.I)
    return js


def check_text_file(path: Path) -> None:
    """Stop the build if a plain text file embeds a real picture (data:image base64 bigger than an icon)."""
    txt = path.read_text(encoding="utf-8", errors="ignore")
    for m in DATA_IMG.finditer(txt):
        kind, payload = m.group(1).lower(), re.sub(r"\s+", "", m.group(2))
        if kind.startswith("svg"):
            if len(payload) > 64_000:
                raise SystemExit(f"{path}: embeds a large base64 SVG (may wrap a picture); refusing to publish it")
            continue
        try:
            w, h = Image.open(io.BytesIO(base64.b64decode(payload + "=" * (-len(payload) % 4)))).size
        except Exception as err:
            raise SystemExit(f"{path}: unreadable embedded data:image/{kind}; refusing to publish it") from err
        if max(w, h) > MAX_EMBEDDED_PX:
            raise SystemExit(f"{path}: embeds a {w}x{h} data:image/{kind}: would leak a picture in plaintext")
    if re.search(r"[A-Za-z0-9+/]{200000,}", txt):
        raise SystemExit(f"{path}: contains a very long base64 run (embedded file?); refusing to publish it")


def copy_sharp_app(src: Path, dst: Path, key: bytes, sub: str) -> int:
    if not (src / "index.html").exists():
        raise SystemExit(f"No staff app in {src}")
    # allowlist: text files are copied in plain form, pictures ONLY as ciphertext, anything else stops the build
    files = [p for p in sorted(src.rglob("*")) if p.is_file()]
    odd = [p for p in files if p.suffix.lower() not in PICS | PLAIN]
    if odd:
        raise SystemExit(f"{src}: unexpected file types (not encrypted, not allowed in plain): {odd[:5]}")
    n = 0
    for p in files:
        out = dst / p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() in PICS:
            out.with_name(out.name + ".enc").write_bytes(encrypt(key, p.read_bytes()))
            n += 1
        else:
            check_text_file(p)
            shutil.copy2(p, out)
    html = (dst / "index.html").read_text(encoding="utf-8")
    guard = '<meta name="robots" content="noindex, nofollow">\n<script src="../guard.js" data-next="%s"></script>\n' % sub
    html = html.replace("</head>", guard + "</head>", 1)
    tour = ROOT / "site" / "tour.js"
    if tour.exists() and "tour.js" not in html:
        shutil.copy2(ROOT / "site" / "tour.css", dst / "tour.css")
        (dst / "tour.js").write_text(_patch_tour_home(tour.read_text(encoding="utf-8")), encoding="utf-8")
        html = html.replace("</body>", '<link rel="stylesheet" href="tour.css">\n<script src="tour.js" charset="utf-8"></script>\n</body>', 1)
    (dst / "index.html").write_text(html, encoding="utf-8")
    return n


def build(site: Path, apps: dict[str, Path], password: str, iterations: int = ITERATIONS) -> dict:
    team = site / "team"
    stray = site / "vault"   # build_site copies every site/ entry; the raw vault sources belong only in team/
    if stray.is_dir() and {p.name for p in stray.iterdir()} <= {p.name for p in VAULT_SRC.iterdir()}:
        shutil.rmtree(stray)
    if team.exists():
        shutil.rmtree(team)
    team.mkdir(parents=True)
    salt = secrets.token_bytes(16)
    key = derive_key(password, salt, iterations)
    for f in ("index.html", "vault.js", "vault.css", "sw.js", "guard.js"):
        shutil.copy2(VAULT_SRC / f, team / f)
    n = 0
    for sub, src in apps.items():
        if src and src.exists():
            n += copy_sharp_app(src, team / sub, key, sub)
        else:
            print(f"  (skipped {sub}: {src} not found)")
    meta = make_vault_meta(key, salt, iterations, n)
    (team / "vault.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    # final leak check: in app/ and day/ only .enc + allowlisted text may exist
    leaks = [p for p in team.rglob("*") if p.is_file() and p.suffix.lower() not in PLAIN | {".enc"}]
    if leaks:
        raise SystemExit(f"non-allowlisted / plaintext files in team/: {leaks[:3]}")
    for p in team.rglob("*"):
        if p.is_file() and p.suffix.lower() in PLAIN:
            check_text_file(p)
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="built site folder (from tools/build_site.py)")
    ap.add_argument("--app", default="outputs/rehearsal_final/dashboard")
    ap.add_argument("--day", default="outputs/day_replay/dashboard")
    ap.add_argument("--password-file", default="docs/team_password.txt")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="public site URL, for the magic link line")
    args = ap.parse_args()
    t0 = time.time()
    site = (ROOT / args.site).resolve()
    if not (site / "index.html").exists():
        raise SystemExit(f"{site} is not a built site (no index.html)")
    pw = load_or_create_password(ROOT / args.password_file, args.base_url)
    meta = build(site, {"app": ROOT / args.app, "day": ROOT / args.day}, pw)
    print(f"team vault -> {site / 'team'}")
    print(f"  encrypted pictures: {meta['files']} (AES-256-GCM, PBKDF2 {meta['iterations']} it.)")
    print(f"  password + magic link: {ROOT / args.password_file} (git-ignored; never publish it)")
    print(f"  done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    sys.exit(main())

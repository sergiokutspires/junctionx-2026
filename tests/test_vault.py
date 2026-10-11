"""Sensei team vault (tools/build_vault.py): crypto round trip, password check, no plaintext pictures."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import numpy as np
import pytest
from cryptography.exceptions import InvalidTag
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_vault as bv  # noqa: E402

FAST = 1000  # iterations for tests only; the real build uses 600 000


def test_round_trip_small_file():
    key = bv.derive_key("abcd-efgh-jkmn-pqrs", b"0123456789abcdef", FAST)
    data = bytes(range(256)) * 7
    blob = bv.encrypt(key, data)
    assert len(blob) == 12 + len(data) + 16
    assert data not in blob
    assert bv.decrypt(key, blob) == data
    assert bv.encrypt(key, data)[:12] != blob[:12]  # fresh IV per file
    with pytest.raises(InvalidTag):
        bv.decrypt(bv.derive_key("wrong", b"0123456789abcdef", FAST), blob)


def test_check_blob_only_right_password():
    salt = b"s" * 16
    meta = bv.make_vault_meta(bv.derive_key("good-pass-word-1234", salt, FAST), salt, FAST, 0)
    assert base64.b64decode(meta["salt"]) == salt
    assert bv.check_password(meta, "good-pass-word-1234")
    assert not bv.check_password(meta, "good-pass-word-1235")
    assert not bv.check_password(meta, "")


def test_password_format(tmp_path):
    pw = bv.load_or_create_password(tmp_path / "pw.txt", "https://example.org/x/")
    parts = pw.split("-")
    assert len(parts) == 4 and all(len(p) == 4 and set(p) <= set(bv.ALPHABET) for p in parts)
    assert bv.load_or_create_password(tmp_path / "pw.txt", "https://example.org/x/") == pw  # stable
    assert "https://example.org/x/team/#k=" + pw in (tmp_path / "pw.txt").read_text()


def _fake_app(root: Path) -> Path:
    app = root / "dash"
    (app / "img" / "frames").mkdir(parents=True)
    (app / "index.html").write_text("<html><head></head><body><img src='img/frames/a.jpg'></body></html>")
    (app / "data.js").write_text("window.DATA={frames:['img/frames/a.jpg']};")
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 255, (40, 60, 3), dtype=np.uint8)).save(app / "img" / "frames" / "a.jpg")
    Image.fromarray(rng.integers(0, 255, (20, 20, 3), dtype=np.uint8)).save(app / "img" / "b.png")
    return app


def test_built_team_folder_has_no_plaintext_pictures(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>")
    app = _fake_app(tmp_path)
    meta = bv.build(site, {"app": app, "day": app}, "abcd-efgh-jkmn-pqrs", iterations=FAST)
    team = site / "team"
    assert meta["files"] == 4
    for f in ("index.html", "vault.js", "vault.css", "sw.js", "guard.js", "vault.json"):
        assert (team / f).exists()
    files = [p for p in team.rglob("*") if p.is_file()]
    assert not [p for p in files if p.suffix.lower() in bv.PICS]
    encs = [p for p in files if p.suffix == ".enc"]
    assert len(encs) == 4
    key = bv.derive_key("abcd-efgh-jkmn-pqrs", base64.b64decode(meta["salt"]), FAST)
    for p in encs:
        assert bv.decrypt(key, p.read_bytes()) == (app / p.relative_to(team / p.relative_to(team).parts[0])).with_suffix("").read_bytes()
    html = (team / "app" / "index.html").read_text()
    assert "../guard.js" in html and 'data-next="app"' in html
    assert "abcd-efgh-jkmn-pqrs" not in "".join(p.read_text(errors="ignore") for p in files if p.suffix != ".enc")


def test_team_tour_not_pixelated_and_home_two_levels_up():
    js = bv._patch_tour_home(
        "var a='<a href=\"../\">Back</a>'; home.href = '../';\n"
        "text: 'Tap one. Pictures are pixelated here for privacy.' },\n"
        "text: 'Faces are pixelated for the demo!' }")
    assert "pixelat" not in js.lower()
    assert 'href="../../"' in js and "href = '../../'" in js
    assert js.count("'") == 8  # string quoting untouched


def test_unexpected_file_type_stops_build(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>")
    app = _fake_app(tmp_path)
    (app / "img" / "clip.gif").write_bytes(b"GIF89a")
    with pytest.raises(SystemExit):
        bv.build(site, {"app": app}, "abcd-efgh-jkmn-pqrs", iterations=FAST)


def test_embedded_big_picture_stops_build(tmp_path):
    import io
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>")
    app = _fake_app(tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (200, 10, 10)).save(buf, "JPEG")
    (app / "app.js").write_text("var x='data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode() + "';")
    with pytest.raises(SystemExit):
        bv.build(site, {"app": app}, "abcd-efgh-jkmn-pqrs", iterations=FAST)
    # a small icon is fine
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, "PNG")
    (app / "app.js").write_text("var x='data:image/png;base64," + base64.b64encode(buf.getvalue()).decode() + "';")
    bv.build(site, {"app": app}, "abcd-efgh-jkmn-pqrs", iterations=FAST)

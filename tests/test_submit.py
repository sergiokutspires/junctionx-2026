"""`python -m sensei submit`: folder / zip / flat input, independent validation, safety nets."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

import scoring
from sensei import pipeline, submit
from sensei.__main__ import main as cli
from sensei.config import Config
from sensei.data import discover_images, load_planogram


def _read(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def synth(tmp_path_factory) -> dict:
    from sensei.synth import generate_dataset
    return generate_dataset(tmp_path_factory.mktemp("synth") / "d", n_cameras=3, images_per_camera=8,
                            seed=1, val_per_camera=2)


@pytest.fixture(scope="module")
def mdir(synth, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("model") / "m"
    pipeline.fit(synth["images_dir"], synth["planogram"], out, Config(backend="lite", extra={"cache_dir": None}))
    return out


def _submit(images, mdir, out, *extra) -> None:
    imgs = images if isinstance(images, (list, tuple)) else [images]
    cli(["submit", "--images", *map(str, imgs), "--model", str(mdir), "--out", str(out), "--no-detect", "-q", *extra])


def _score(synth, pred_path: Path) -> dict:
    return scoring.score(_read(synth["annotations"]), _read(pred_path))


def test_folder_run_passes_and_is_scoreable(synth, mdir, tmp_path, capsys):
    out = tmp_path / "sub"
    _submit(synth["val_dir"], mdir, out)             # returns normally = exit code 0
    text = capsys.readouterr().out
    assert "PASSED" in text and f"HAND IN THIS FILE: {out.resolve() / 'predictions.json'}" in text
    assert f"Open the staff app: {out.resolve() / 'dashboard' / 'index.html'}" in text
    assert (out / "details.json").is_file() and (out / "dashboard" / "index.html").is_file()
    res = _score(synth, out / "predictions.json")
    assert res["stock"].get("missing", 0) == 0 and res["areas"] > 0
    # the validator sees the same thing as the scorer
    planogram = {c: [a.area_id for a in areas] for c, areas in load_planogram(mdir / "planogram.json").items()}
    rep = submit.validate_predictions(out / "predictions.json", planogram, submit.list_images(Path(synth["val_dir"])))
    assert rep["ok"] and rep["areas"] == rep["expected_areas"] == res["areas"]
    assert sum(rep["levels"].values()) == res["areas"]


def test_zip_with_junk_and_nesting(synth, mdir, tmp_path):
    src = Path(synth["val_dir"])
    zp = tmp_path / "validation.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for p in submit.list_images(src):
            z.write(p, f"validation/{p.relative_to(src).as_posix()}")
            z.writestr(f"__MACOSX/validation/{p.relative_to(src).parent.as_posix()}/._{p.name}", b"junk")
        z.writestr(".DS_Store", b"x")
        z.writestr("validation/readme.txt", b"hello")
        z.writestr("../evil.jpg", b"not escaping")
    out = tmp_path / "sub"
    _submit(zp, mdir, out)
    extracted = out / "val_images"
    names = {p.name for p in extracted.rglob("*") if p.is_file()}
    assert not any(n.startswith("._") or n in {".DS_Store", "readme.txt", "evil.jpg"} for n in names - {submit.SENTINEL})
    assert not (tmp_path / "evil.jpg").exists() and not (out.parent / "evil.jpg").exists()
    folder_out = tmp_path / "sub_folder"
    _submit(src, mdir, folder_out)
    assert _read(out / "predictions.json") == _read(folder_out / "predictions.json")
    assert _score(synth, out / "predictions.json")["stock"].get("missing", 0) == 0


def test_flat_folder_camera_from_picture(synth, mdir, tmp_path):
    flat = tmp_path / "flat"
    flat.mkdir()
    recs = discover_images(synth["val_dir"], load_planogram(mdir / "planogram.json"))
    for r in recs:
        shutil.copy(r.path, flat / r.image_name)
    out = tmp_path / "sub"
    _submit(flat, mdir, out)
    assert _score(synth, out / "predictions.json")["stock"].get("missing", 0) == 0


def test_several_dropped_files_and_nested_zip(synth, mdir, tmp_path):
    files = [r.path for r in discover_images(synth["val_dir"], load_planogram(mdir / "planogram.json"))]
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as z:
        for p in files[:2]:
            z.write(p, f"{p.parent.name}/{p.name}")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.write(inner, "parts/inner.zip")
    out = tmp_path / "sub1"
    _submit(outer, mdir, out)
    assert len(submit.list_images(out / "val_images")) == 2
    out2 = tmp_path / "sub2"                         # several files dragged onto SUBMIT.bat
    _submit(files[:3], mdir, out2)
    assert len(submit.list_images(out2 / "val_images")) == 3
    # a folder that only holds a zip is unpacked too
    holder = tmp_path / "downloads"
    holder.mkdir()
    shutil.copy(inner, holder / "val.zip")
    _submit(holder, mdir, tmp_path / "sub3")
    assert len(submit.list_images(tmp_path / "sub3" / "val_images")) == 2


def test_no_matching_image_exits_2_and_removes_stale_files(mdir, tmp_path, capsys):
    out = tmp_path / "sub"
    out.mkdir()
    (out / "predictions.json").write_text("{\"old\": 1}", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    for args in ([empty], [tmp_path / "nope"]):
        with pytest.raises(SystemExit) as exc:
            _submit(args, mdir, out)
        assert exc.value.code == 2
    stranger = tmp_path / "stranger" / "9999"        # image of a camera that is not in the planogram
    stranger.mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (64, 36), (10, 200, 30)).save(stranger / "1751000000.jpg")
    with pytest.raises(SystemExit) as exc:
        _submit(tmp_path / "stranger", mdir, out)
    assert exc.value.code == 2 and not (out / "predictions.json").exists()
    assert "Nothing was written" in capsys.readouterr().err


def test_unreadable_pictures_fail_validation_loudly(synth, mdir, tmp_path, capsys):
    bad = tmp_path / "bad"
    for r in discover_images(synth["val_dir"], load_planogram(mdir / "planogram.json")):
        (bad / r.camera_id).mkdir(parents=True, exist_ok=True)
        (bad / r.camera_id / r.image_name).write_bytes(b"this is not a jpeg")
    out = tmp_path / "sub"
    with pytest.raises(SystemExit) as exc:
        _submit(bad, mdir, out)
    assert exc.value.code == 1
    text = capsys.readouterr().out
    assert "FAILED" in text and "HAND IN THIS FILE" not in text
    assert (out / "predictions.json").is_file()      # still written (every area answered), but flagged


def _good_doc() -> dict:
    e = {"planogram_compliant": True, "stock_level": "half", "stock_value": 0.5}
    return {"1001": {"1751000000.jpg": {"1001_1": dict(e), "1001_2": dict(e)}}}


def _validate(tmp_path, doc, text=None, files=()):
    p = tmp_path / "p.json"
    p.write_text(text if text is not None else json.dumps(doc), encoding="utf-8")
    return submit.validate_predictions(p, {"1001": ["1001_1", "1001_2"], "1002": ["1002_1"]}, files)


def test_validator_accepts_good_and_counts_aliases_once(tmp_path):
    doc = _good_doc()
    doc["1001"]["1751000000.JPG"] = doc["1001"]["1751000000.jpg"]       # on-disk alias
    rep = _validate(tmp_path, doc)
    assert rep["ok"] and rep["images"] == 1 and rep["areas"] == 2 and rep["levels"]["half"] == 2


@pytest.mark.parametrize("mutate, needle", [
    (lambda d: d["1001"]["1751000000.jpg"].pop("1001_2"), "missing"),
    (lambda d: d["1001"]["1751000000.jpg"].update({"1001_9": {}}), "unknown area"),
    (lambda d: d["1001"]["1751000000.jpg"]["1001_1"].update(planogram_compliant="yes"), "invalid entry"),
    (lambda d: d["1001"]["1751000000.jpg"]["1001_1"].update(stock_level="medium"), "invalid entry"),
    (lambda d: d["1001"]["1751000000.jpg"]["1001_1"].update(stock_value=1.0), "invalid entry"),
    (lambda d: d["1001"]["1751000000.jpg"]["1001_1"].update(stock_value=True), "invalid entry"),
    (lambda d: d["1001"].update({"notes": {}}), "not an image file name"),
    (lambda d: d.update({"7777": d["1001"]}), "not in the planogram"),
])
def test_validator_rejects_defects(tmp_path, mutate, needle):
    doc = _good_doc()
    mutate(doc)
    rep = _validate(tmp_path, doc)
    assert not rep["ok"] and any(needle in e for e in rep["errors"]), rep["errors"]


def test_validator_duplicates_unanswered_images_and_garbage(tmp_path):
    dup = '{"1001": {"1751000000.jpg": {"1001_1": {"planogram_compliant": true, "stock_level": "full", "stock_value": 1},' \
          ' "1001_1": {"planogram_compliant": true, "stock_level": "full", "stock_value": 1}, "1001_2": {"planogram_compliant": true,' \
          ' "stock_level": "full", "stock_value": 1}}}}'
    rep = _validate(tmp_path, None, dup)
    assert not rep["ok"] and any("duplicate" in e for e in rep["errors"])
    rep = _validate(tmp_path, _good_doc(), files=[tmp_path / "1751000000.jpg", tmp_path / "1751999999.jpg"])
    assert not rep["ok"] and any("1751999999.jpg" in e for e in rep["errors"])
    assert not _validate(tmp_path, None, "{not json")["ok"] and not _validate(tmp_path, {})["ok"]


def test_extract_zip_refuses_escaping_paths(tmp_path):
    zp = tmp_path / "z.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("a/../../x.jpg", b"1")
        z.writestr("C:/win.jpg", b"1")
        z.writestr("/abs/ok.jpg", b"1")
    dest = tmp_path / "d"
    assert submit.extract_zip(zp, dest) == 1
    assert (dest / "abs" / "ok.jpg").is_file() and not (tmp_path / "x.jpg").exists()


def test_new_out_folder_ignores_itself_in_git(synth, mdir, tmp_path):
    out = tmp_path / "fresh"
    _submit(synth["val_dir"], mdir, out)
    assert (out / ".gitignore").read_text(encoding="utf-8").strip() == "*"


def test_dashboard_problems_never_fail_the_submission(synth, mdir, tmp_path, monkeypatch, capsys):
    from sensei import dashboard
    real_build = dashboard.build
    calls = []

    def flaky(details, data_root, out_dir, *a, detect=False, **kw):
        calls.append(detect)
        if detect:
            raise RuntimeError("owl exploded")
        return real_build(details, data_root, out_dir, *a, detect=False, **kw)

    monkeypatch.setattr(dashboard, "build", flaky)
    out = tmp_path / "a"
    cli(["submit", "--images", str(synth["val_dir"]), "--model", str(mdir), "--out", str(out), "-q"])   # detection on
    text = capsys.readouterr().out
    assert calls == [True, False] and "product detection failed" in text and "PASSED" in text
    assert (out / "dashboard" / "index.html").is_file()

    def broken(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(dashboard, "build", broken)
    out = tmp_path / "b"
    cli(["submit", "--images", str(synth["val_dir"]), "--model", str(mdir), "--out", str(out), "--no-detect", "-q"])
    text = capsys.readouterr().out
    assert "NOT built" in text and "HAND IN THIS FILE" in text and (out / "predictions.json").is_file()

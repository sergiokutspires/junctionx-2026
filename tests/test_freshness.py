"""Tests for sensei.freshness: produce biology loading/overrides, freshness watch and ethylene neighbours."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sensei import freshness as F

ROOT = Path(__file__).resolve().parents[1]
HEADER = ("type;product_english;planogram_name_pt;loose_or_packed;areas;shelf_life_class (fast/medium/slow);"
          "hours_on_display_before_checking;ethylene_producer (high/medium/low);ethylene_sensitive (high/medium/low);"
          "visible_spoilage_signs;source (link or book)")
H = 3600
T0 = 1751000000


def write(path: Path, lines: list[str], header: str = HEADER, encoding: str = "utf-8-sig") -> Path:
    path.write_text("\n".join([header, *lines]) + "\n", encoding=encoding)
    return path


@pytest.fixture
def ref(tmp_path):
    return write(tmp_path / "ref.csv", [
        "banana;banana;BANANA CAT I CNT KG;loose;1_1;medium;24;medium;high;Brown spots;USDA AH-66 Banana pp.224-229 (a long note about ripening rooms): https://example.org/x;high",
        "kiwi;zespri kiwi;KIWI ZESPRI KG;loose;1_2;medium;24;high;high;Soft;USDA AH-66 Kiwifruit pp.372-376: https://example.org/k | Ethylene class (Pesis, high): https://doi.org/1;medium",
        "lettuce;frisee lettuce;ALFACE FRISADA SACO;packed;1_3;fast;8;low;high;Brown spots;AH-66;medium",
    ], HEADER + ";confidence")


# --------------------------------------------------------------------------- biology table

def test_load_reference_and_validated_values(ref):
    bio = F.load_biology(ref, None)
    assert set(bio) == {"BANANA CAT I CNT KG", "KIWI ZESPRI KG", "ALFACE FRISADA SACO"}
    k = bio["KIWI ZESPRI KG"]
    assert (k["type"], k["cls"], k["lim"], k["prod"], k["sens"], k["conf"]) == ("kiwi", "medium", 24, "high", "high", "medium")
    assert k["edited"] == []
    assert F.name_key("  kiwi   zespri kg ") == "KIWI ZESPRI KG"


def test_template_overrides_only_non_empty_cells(ref, tmp_path):
    tpl = write(tmp_path / "tpl.csv", [
        "banana;banana;BANANA CAT I CNT KG;loose;1_1;;12;;;;",          # teammate shortened the check interval only
        "kiwi;zespri kiwi;KIWI ZESPRI KG;loose;1_2;;;;;;",              # untouched row
        "lettuce;frisee lettuce;ALFACE FRISADA SACO;packed;1_3;rotten;-4;HIGH;;;",   # bad class / hours ignored, case fixed
        "pear;pear;PERA ROCHA KG;loose;9_9;medium;24;high;medium;;My notes",  # a product the reference lacks
    ])
    bio = F.load_biology(ref, tpl)
    b = bio["BANANA CAT I CNT KG"]
    assert b["lim"] == 12 and b["cls"] == "medium" and b["sens"] == "high" and b["edited"] == ["lim"]
    assert "conf" not in b                                            # the researcher's confidence no longer applies
    assert bio["KIWI ZESPRI KG"]["edited"] == [] and bio["KIWI ZESPRI KG"]["conf"] == "medium"
    lt = bio["ALFACE FRISADA SACO"]
    assert lt["cls"] == "fast" and lt["lim"] == 8 and lt["prod"] == "high" and lt["edited"] == ["prod"]
    assert bio["PERA ROCHA KG"]["lim"] == 24 and bio["PERA ROCHA KG"]["source"] == "My notes"


def test_missing_files_and_excel_variants(tmp_path):
    assert F.load_biology(tmp_path / "nope.csv", tmp_path / "nope2.csv") == {}
    assert F.load_biology(None, None) == {}
    comma = HEADER.replace(";", ",")
    p = write(tmp_path / "excel.csv", ["apple,apple,MAÇÃ GALA KG,loose,1_1,slow,48,high,medium,Wrinkles,AH-66"],
              comma, encoding="cp1252")
    bio = F.load_biology(p, None)
    assert bio["MAÇÃ GALA KG"]["lim"] == 48 and bio["MAÇÃ GALA KG"]["prod"] == "high"
    assert F.read_biology_csv(write(tmp_path / "empty.csv", [], "")) == []


def test_short_source_drops_urls_and_long_notes():
    s = ("USDA AH-66 (2016) Apple pp.176-190, Grocery display p.59: https://www.ars.usda.gov/x.pdf | "
         "Ethylene class (Pesis, high): https://doi.org/10.22271/phyto | Bagnato et al. 2003 (a very long note about shelf life at 20 C) | four | five")
    out = F.short_source(s)
    assert "http" not in out and "very long note" not in out
    assert out == "USDA AH-66 (2016) Apple pp.176-190, Grocery display p.59; Ethylene class (Pesis, high); Bagnato et al. 2003"
    assert F.short_source("") == ""


@pytest.mark.skipif(not F.REFERENCE.is_file(), reason="biology reference not present")
def test_real_reference_is_complete_and_valid():
    bio = F.load_biology(F.REFERENCE, None)
    assert len(bio) == 94
    assert all(b["lim"] in (8, 12, 24, 48, 72) and b["cls"] in F.CLASSES for b in bio.values())
    assert all(b.get("prod") in F.LEVELS and b.get("sens") in F.LEVELS and b.get("type") for b in bio.values())
    assert all(F.short_source(b["source"]) and "http" not in F.short_source(b["source"]) for b in bio.values())


# --------------------------------------------------------------------------- freshness watch

def tl(*fills, step=H, start=T0):
    return [[start + i * step, f, "full" if f > 0.7 else "half" if f > 0.2 else "empty"] for i, f in enumerate(fills)]


def test_restock_rule_matches_insights():
    pts = tl(0.9, 0.5, 0.95, 0.7, 0.85, 0.2, 0.9)
    assert F.restock_times(pts) == [T0 + 2 * H, T0 + 6 * H]           # +0.45 and +0.7; +0.15 is not a restock
    assert F.restock_times(pts, now_ts=T0 + 5 * H) == [T0 + 2 * H]     # later pictures are not "seen" yet
    assert F.restock_times(tl(0.5, 0.75)) == []                        # +0.25 is a small top-up or noise, not a restock
    assert F.restock_times([]) == []


def test_freshness_from_last_restock_or_first_picture():
    pts = tl(0.1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)    # restocked at T0+1h, then 10 pictures
    f = F.freshness_status(pts, T0 + 10 * H, "half", 8)
    assert f == {"h": 9.0, "lim": 8, "since": T0 + H, "basis": "restock", "due": True}
    assert F.freshness_status(pts, T0 + 10 * H, "half", 12)["due"] is False
    assert F.freshness_status(pts, T0 + 10 * H, "empty", 8)["due"] is False          # nothing left to check
    steady = F.freshness_status(tl(0.9, 0.9, 0.85, 0.8), T0 + 3 * H, "full", 2)
    assert steady["basis"] == "first" and steady["since"] == T0 and steady["h"] == 3.0 and steady["due"]
    assert F.freshness_status(pts, T0 + 10 * H, "full", None) is None                 # no interval: no badge
    assert F.freshness_status([], T0, "full", 8) is None
    assert F.freshness_status(pts, T0 - H, "full", 8) is None                         # no picture up to now


# --------------------------------------------------------------------------- neighbours

SQ = [[0, 0], [100, 0], [100, 100], [0, 100]]


def shift(q, dx, dy=0):
    return [[x + dx, y + dy] for x, y in q]


def test_polygon_gap_and_neighbours():
    assert F.polygon_gap(SQ, shift(SQ, 100)) == 0.0                    # sharing an edge
    assert F.polygon_gap(SQ, shift(SQ, 50, 50)) == 0.0                 # overlapping
    assert F.polygon_gap(SQ, shift(SQ, 120)) == pytest.approx(20.0)
    cross = [[40, -20], [60, -20], [60, 120], [40, 120]]               # crosses SQ with no corner inside it
    assert F.polygon_gap(SQ, cross) == 0.0
    assert F.are_neighbours(SQ, shift(SQ, 120))[0] is True             # 20 px <= 0.25 * sqrt(100*100)
    assert F.are_neighbours(SQ, shift(SQ, 130))[0] is False            # 30 px > 25 px
    assert F.are_neighbours(SQ, None)[0] is False and F.are_neighbours(SQ, [[1, 2]])[0] is False


def item(aid, cam, quad, type_, prod, sens):
    return {"id": aid, "cam": cam, "quad": quad, "type": type_, "prod": prod, "sens": sens}


def test_ethylene_pairs_rules():
    items = [
        item("1_1", "1", SQ, "avocado", "high", "high"),
        item("1_2", "1", shift(SQ, 105), "lettuce", "low", "high"),            # next to the avocado: flagged
        item("1_3", "1", shift(SQ, 400), "kiwi", "high", "high"),              # far away: never
        item("1_5", "1", shift(SQ, -105), "tomato", "medium", "medium"),       # medium -> high and high -> medium: mild
        item("2_1", "2", shift(SQ, 105), "kiwi", "high", "high"),              # other camera: not a neighbour
        item("1_6", "1", None, "banana", "medium", "high"),                    # no quad: ignored
    ]
    pairs, mild = F.ethylene_pairs(items)
    assert [(p["src"], p["dst"], p["src_type"], p["dst_type"]) for p in pairs] == [("1_1", "1_2", "avocado", "lettuce")]
    assert pairs[0]["cam"] == "1" and pairs[0]["gap"] == pytest.approx(5.0)
    assert mild == 2                                                            # tomato->avocado and avocado->tomato
    assert F.ethylene_pairs([]) == ([], 0)
    same = [item("1_1", "1", SQ, "avocado", "high", "high"), item("1_4", "1", shift(SQ, 105), "avocado", "high", "high")]
    assert F.ethylene_pairs(same) == ([], 0)                                    # same type: they ripen together anyway


REAL_DETAILS = next((p for p in (ROOT / "outputs" / m / "details.json" for m in ("real_v3_cal", "real_v1_cal"))
                     if p.is_file()), ROOT / "outputs" / "real_v3_cal" / "details.json")


@pytest.mark.skipif(not (REAL_DETAILS.is_file() and F.REFERENCE.is_file()), reason="real details / biology not present")
def test_real_planogram_pairs_match_the_research_tool():
    """The 7 strong pairs of tools/ethylene_neighbours.py (checked by eye on the store photos) and its 49 mild ones."""
    bio = F.load_biology(F.REFERENCE, None)
    rows = json.loads(REAL_DETAILS.read_text(encoding="utf-8-sig"))["rows"]
    items = []
    for r in rows:
        b = bio[F.name_key(r["product_name"])]
        items.append(item(r["area_id"], r["camera_id"], r["quad"], b["type"], b["prod"], b["sens"]))
    pairs, mild = F.ethylene_pairs(items)
    assert {(p["src"], p["dst"]) for p in pairs} == {
        ("6383_2", "6383_1"), ("6383_2", "6383_8"), ("6383_2", "6383_9"),            # ready-to-eat avocado -> lettuce, beans, cucumber
        ("6371_7", "6371_4"), ("6371_7", "6371_6"), ("6371_7", "6371_8"),            # cantaloupe -> three watermelons
        ("6376_2", "6376_10")}                                                        # Galia melon -> Zespri kiwi
    assert mild == 49

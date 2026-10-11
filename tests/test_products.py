"""Tests for sensei.products: name parsing, translation, prompts, catalog."""
from __future__ import annotations

import pytest

from sensei.data import load_planogram
from sensei.products import (EMPTY_PROMPTS, OCCLUSION_PROMPTS, Catalog, base_prompts, parse_name,
                             prompts_for)


@pytest.mark.parametrize("name, english, base, loose", [
    ("BANANA CAT I CNT KG", "banana", "banana", True),
    ("TOMATE CHERRY EMB. 250 G", "cherry tomato", "tomato", False),
    ("MACA GALA KG", "gala apple", "apple", True),
    ("MAÇÃ GALA CNT CAL 70/80 KG IMP", "gala apple", "apple", True),
    ("LIMÃO CNT 60/75 KG", "lemon", "lemon", True),
    ("LIMAO CNT 60/75 KG", "lemon", "lemon", True),
    ("FEIJÃO VERDE CNT KG", "green beans", "green beans", True),
    ("TOMATE CORAÇÃO DE BOI CNT KG", "oxheart tomato", "tomato", True),
    ("ABÓBORA HOKAIDO R0 KG", "hokkaido pumpkin", "pumpkin", True),
    ("CHUCHU CNT KG", "chayote", "chayote", True),
    ("TOMATE CHUCHA CNT KG", "plum tomato", "tomato", True),
    ("CITR ALGARVE IGP LARANJA 3/4/5 1.5 KG", "algarve orange", "orange", False),
    ("COUVE PORTUGUESA/PENCA CNT KG", "portuguese cabbage", "cabbage", True),
    ("BATATA VERMELHA EMB:. 5 KG", "red potato", "potato", False),
    ("PESSEGO R0 A/AA KG", "peach", "peach", True),
    ("TOMATE CHERRY BIO EMB. 250 GR", "organic cherry tomato", "tomato", False),
])
def test_parse_name_examples(name: str, english: str, base: str, loose: bool) -> None:
    p = parse_name(name)
    assert (p["english"], p["base"], p["loose"]) == (english, base, loose)
    assert p["packaged"] is (not loose) and p["raw"] == name
    assert set(p) >= {"raw", "english", "base", "variety", "loose", "packaged", "organic"}


def test_parse_name_flags_and_fallbacks() -> None:
    assert parse_name("KIWI CNT BIO 400 G")["organic"] is True
    assert parse_name("BANANA CNT KG")["organic"] is False
    p = parse_name("XPTO DESCONHECIDO KG")
    assert p["english"] and p["base"]  # unknown words never crash nor give empty text
    assert parse_name("")["english"] == "produce"
    for code in ("CNT", "IGP", "CAL", "KG", "R0", "ZER0", "SC"):
        assert code.lower() not in parse_name("MACA FUJI CNT CAL. 73/85 KG IMP")["english"].split()


def test_prompts() -> None:
    loose = prompts_for("BANANA CAT I CNT KG")
    packed = prompts_for("TOMATE CHERRY EMB. 250 G")
    assert len(loose) >= 4 and all("banana" in t for t in loose)
    assert any("pile" in t or "loose" in t for t in loose)
    assert any("package" in t or "punnet" in t for t in packed)
    assert len(set(loose)) == len(loose)
    assert EMPTY_PROMPTS and OCCLUSION_PROMPTS
    assert base_prompts("apple", packaged=False) and base_prompts("apple", packaged=True)


def test_catalog_real(real_planogram_path, real_areas) -> None:
    cat = Catalog.from_planogram(real_areas)
    assert len(cat) == 94
    assert sum(len(p["areas"]) for p in cat.products.values()) == 152
    assert len(cat.area_product()) == 152
    for _pid, p in cat.products.items():
        assert p["english"].strip() and p["base"].strip(), p["name"]
        assert not p["unknown_tokens"], (p["name"], p["unknown_tokens"])
        assert prompts_for(p["name"]), p["name"]
    assert {"banana", "orange", "apple", "tomato", "potato", "onion"} <= set(cat.bases())


def test_catalog_tiny(tiny_planogram) -> None:
    cat = Catalog.from_planogram(load_planogram(tiny_planogram))
    assert len(cat) == 4 and cat["21413"]["english"] == "green beans"
    assert cat.relation("11908", "11908") == "same"
    assert cat.relation("11908", "22304") in ("group", "different")

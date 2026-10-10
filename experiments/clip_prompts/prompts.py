"""Prompt ensembles for stock level (empty / half / full), product identity and dense patches."""
from __future__ import annotations

from catalog import translate

CONTAINERS = ["plastic crate", "green plastic crate", "wicker basket", "cardboard box",
              "metal tray", "black display shelf"]

# ----------------------------------------------------------------------------- stock (global)

def stock_prompts(product_id, name):
    """-> {"empty": [...], "half": [...], "full": [...]} for one planogram product."""
    t = translate(product_id, name)
    x = t["unit"]
    empty = [f"a photo of an empty {c} in a supermarket" for c in CONTAINERS]
    empty += [
        "a photo of an empty supermarket display with nothing in it",
        "the bare bottom of an empty produce crate",
        f"an empty crate where {x} are usually sold",
        f"an almost empty crate with only one or two {x} left",
    ]
    half = [
        f"a photo of a half-empty crate with a few {x}",
        f"a crate half full of {x}",
        f"a partly stocked crate of {x} with the bottom of the crate visible",
        f"some {x} in a half-empty supermarket display",
        f"a depleted display of {x} with gaps",
    ]
    full = [
        f"a photo of a crate full of {x}",
        f"a crate piled high with {x}",
        f"a fully stocked supermarket display of {x}",
        f"a crate completely filled with {x}",
        f"lots of {x} covering the whole crate",
    ]
    return {"empty": empty, "half": half, "full": full}


# ----------------------------------------------------------------------------- identity

def identity_prompts(product_id, name):
    t = translate(product_id, name)
    en, look = t["en"], t["look"]
    p = [
        f"a photo of {en} in a supermarket",
        f"a photo of {look}",
        f"{en} for sale at a grocery store",
        f"a close-up photo of {en} in a crate",
    ]
    return p


EMPTY_ID_PROMPTS = [f"a photo of an empty {c}" for c in CONTAINERS] + [
    "an empty supermarket display",
    "the bare bottom of an empty produce crate",
]

# base-category prompts (one per base fruit / vegetable)
def base_prompts(base):
    return [
        f"a photo of {base}s in a supermarket" if not base.endswith("s") else f"a photo of {base} in a supermarket",
        f"a pile of {base} at a grocery store",
        f"{base} for sale",
    ]


# ----------------------------------------------------------------------------- dense (patch-level)

SURFACE_PROMPTS = [
    "an empty plastic crate", "the bottom of a green plastic crate", "teal plastic",
    "a wicker basket", "a cardboard box", "white foam packaging", "a metal tray",
    "a black plastic shelf", "a grey metal shelf", "a price label", "a floor tile",
    "a white egg carton tray", "brown paper",
]


def product_patch_prompts(product_id, name):
    t = translate(product_id, name)
    return [f"{t['unit']}", f"a photo of {t['look']}", f"{t['en']}", "fruit", "vegetables",
            "fresh produce"]

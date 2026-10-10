"""Hand translation of the 94 planogram products (PT -> EN) for CLIP prompting.

Every product gets:
  en      : short English description used in prompts ("bananas", "bags of red potatoes")
  base    : base category used for compliance (banana, orange, apple, ...)
  unit    : plural noun for loose units / packages used in level prompts
  pack    : True when sold packaged (bag / net / punnet / clamshell)
  look    : extra visual hint (colour etc.), used in the product-identity prompts

A keyword fallback (`translate`) handles unseen names (validation planogram is the same,
but keep it robust).
"""
from __future__ import annotations

import re
import unicodedata

# product_id -> (en, base, unit, pack, look)
TABLE = {
    # --- 6215 bananas / oranges
    "20923": ("Madeira bananas", "banana", "small bananas", False, "small yellow bananas in bunches"),
    "11908": ("bananas", "banana", "bananas", False, "bunches of yellow bananas"),
    "11906": ("oranges", "orange", "oranges", False, "loose round orange oranges"),
    # --- 6371 melons
    "15600": ("striped watermelons", "watermelon", "watermelons", False, "large striped green watermelons"),
    "16143": ("dark green watermelons", "watermelon", "watermelons", False, "large dark green watermelons"),
    "16336": ("green melons", "melon", "melons", False, "oval green melons"),
    "30633": ("cantaloupe melons", "cantaloupe", "cantaloupes", False, "round beige netted cantaloupe melons"),
    "16137": ("mini watermelons", "watermelon", "mini watermelons", False, "small striped watermelons"),
    # --- 6373 apples / pears
    "13702": ("Gala apples", "apple", "apples", False, "red and yellow gala apples"),
    "32748": ("bags of Gala apples", "apple", "bags of apples", True, "red apples in plastic bags"),
    "19133": ("Pink Lady apples", "apple", "apples", False, "pink red apples"),
    "26786": ("Golden Delicious apples", "apple", "apples", False, "yellow green golden apples"),
    "32749": ("bags of golden apples", "apple", "bags of apples", True, "yellow apples in plastic bags"),
    "32262": ("Cosmic Crisp apples", "apple", "apples", False, "dark red apples"),
    "11901": ("Packham pears", "pear", "pears", False, "green pears"),
    "11909": ("Conference pears", "pear", "pears", False, "long brown green conference pears"),
    # --- 6376 citrus / kiwi / melon
    "11889": ("lemons", "lemon", "lemons", False, "yellow lemons"),
    "11891": ("Galia melons", "melon", "melons", False, "round yellow netted galia melons"),
    "15781": ("packs of gold kiwis", "kiwi", "packs of kiwis", True, "small boxes of kiwi fruit"),
    "1164": ("packs of kiwis", "kiwi", "packs of kiwis", True, "small boxes of kiwi fruit"),
    "20508": ("packs of organic kiwis", "kiwi", "packs of kiwis", True, "small boxes of kiwi fruit"),
    "11890": ("limes", "lime", "limes", False, "small green limes"),
    "15730": ("net bags of oranges", "orange", "net bags of oranges", True, "oranges in red net bags"),
    "14646": ("kiwis", "kiwi", "kiwis", False, "loose brown hairy kiwi fruit"),
    "12756": ("clementines", "clementine", "clementines", False, "small orange clementines"),
    "26600": ("net bags of oranges", "orange", "net bags of oranges", True, "oranges in red net bags"),
    # --- 6383 vegetables (wicker baskets)
    "21254": ("bags of curly lettuce", "lettuce", "bags of lettuce", True, "green curly lettuce in plastic bags"),
    "16429": ("Hass avocados", "avocado", "avocados", False, "dark green bumpy avocados"),
    "11896": ("green bell peppers", "green pepper", "green peppers", False, "shiny green bell peppers"),
    "15651": ("Portuguese cabbage", "leafy cabbage", "cabbage leaves", False, "large dark green leafy cabbage"),
    "11897": ("red bell peppers", "red pepper", "red peppers", False, "shiny red bell peppers"),
    "21208": ("eggplants", "eggplant", "eggplants", False, "dark purple eggplants"),
    "18329": ("chayotes", "chayote", "chayotes", False, "pale green chayote squash"),
    "21413": ("green beans", "green beans", "green beans", False, "long thin green beans"),
    "11895": ("cucumbers", "cucumber", "cucumbers", False, "long dark green cucumbers"),
    # --- 6385 apples
    "16633": ("Fuji apples", "apple", "apples", False, "pink red fuji apples"),
    "30491": ("packs of organic red apples", "apple", "packs of apples", True, "red apples in a plastic tray"),
    "20818": ("bags of Fuji apples", "apple", "bags of apples", True, "red apples in plastic bags"),
    "11919": ("Granny Smith apples", "apple", "apples", False, "bright green apples"),
    "32170": ("Reinette apples", "apple", "apples", False, "brownish russet apples"),
    # --- 6386 cabbages
    "21178": ("broccoli", "broccoli", "heads of broccoli", False, "green broccoli heads"),
    "21152": ("white cabbages", "white cabbage", "cabbages", False, "round pale green white cabbages"),
    "15653": ("red cabbages", "red cabbage", "red cabbages", False, "round purple red cabbages"),
    "21114": ("cauliflowers", "cauliflower", "cauliflowers", False, "white cauliflowers with green leaves"),
    "11893": ("zucchini", "zucchini", "zucchini", False, "long dark green zucchini courgettes"),
    # --- 6443 tomatoes
    "21134": ("round tomatoes", "tomato", "tomatoes", False, "round red tomatoes"),
    "21120": ("tomatoes on the vine", "tomato", "tomatoes on the vine", False, "red tomatoes on green vines"),
    "1267": ("packs of tomatoes", "tomato", "packs of tomatoes", True, "red tomatoes in plastic packs"),
    "22304": ("punnets of organic cherry tomatoes", "tomato", "punnets of cherry tomatoes", True, "small cherry tomatoes in plastic punnets"),
    "19959": ("packs of tomatoes", "tomato", "packs of tomatoes", True, "red tomatoes in plastic packs"),
    "18514": ("oxheart tomatoes", "tomato", "oxheart tomatoes", False, "large ribbed red orange heirloom tomatoes"),
    "18254": ("punnets of cherry tomatoes", "tomato", "punnets of cherry tomatoes", True, "small cherry tomatoes in plastic punnets"),
    "21223": ("punnets of mini plum tomatoes", "tomato", "punnets of plum tomatoes", True, "small plum tomatoes in plastic punnets"),
    "23042": ("punnets of sweet mini plum tomatoes", "tomato", "punnets of plum tomatoes", True, "small plum tomatoes in plastic punnets"),
    "11898": ("plum tomatoes", "tomato", "plum tomatoes", False, "elongated red plum tomatoes"),
    "18533": ("packs of mini vine tomatoes", "tomato", "packs of tomatoes", True, "small red vine tomatoes in plastic packs"),
    # --- 6462 mango / grapes / berries
    "1156": ("punnets of strawberries", "strawberry", "punnets of strawberries", True, "red strawberries in plastic punnets"),
    "11913": ("mangoes", "mango", "mangoes", False, "red green mangoes"),
    "21307": ("white seedless grapes", "grape", "bunches of grapes", False, "green grapes in bunches"),
    "19032": ("packs of white seedless grapes", "grape", "packs of grapes", True, "green grapes in plastic packs"),
    "15597": ("Red Globe grapes", "grape", "bunches of red grapes", False, "red purple grapes in bunches"),
    "3579": ("punnets of cherries", "cherry", "punnets of cherries", True, "dark red cherries in plastic punnets"),
    # --- 6468 tropical
    "23366": ("pineapples", "pineapple", "pineapples", False, "pineapples with spiky green leaves"),
    "15855": ("red dragon fruit", "dragon fruit", "dragon fruits", True, "pink red dragon fruit"),
    "15835": ("yellow dragon fruit", "dragon fruit", "dragon fruits", True, "yellow spiky dragon fruit"),
    "30368": ("guavas", "guava", "guavas", False, "round light green guavas"),
    "22108": ("purple passion fruit", "passion fruit", "passion fruits", False, "dark purple wrinkled passion fruit"),
    "25211": ("granadillas", "passion fruit", "granadillas", False, "orange yellow granadilla fruit"),
    "21122": ("papayas", "papaya", "papayas", False, "large yellow green papayas"),
    "11892": ("papayas", "papaya", "papayas", False, "yellow orange papayas"),
    "15591": ("plantains", "plantain", "plantains", False, "large green plantain bananas"),
    "21789": ("Palmer mangoes", "mango", "mangoes", False, "red purple mangoes in foam nets"),
    # --- 6491 stone fruit
    "31228": ("apricots", "apricot", "apricots", False, "small orange apricots"),
    "32533": ("flat peaches", "peach", "flat peaches", False, "flat paraguayo peaches"),
    "32530": ("peaches", "peach", "peaches", False, "red yellow peaches"),
    "32532": ("nectarines", "nectarine", "nectarines", False, "shiny red nectarines"),
    # --- 6591 potatoes / roots
    "11912": ("red potatoes", "potato", "red potatoes", False, "loose red skinned potatoes"),
    "22965": ("bags of roasting potatoes", "potato", "bags of potatoes", True, "potatoes in plastic bags"),
    "19454": ("bags of potatoes", "potato", "bags of potatoes", True, "potatoes in large bags"),
    "21965": ("bags of red potatoes", "potato", "bags of potatoes", True, "red potatoes in red and white plastic bags"),
    "12661": ("sweet potatoes", "sweet potato", "sweet potatoes", False, "long reddish sweet potatoes"),
    "22411": ("ginger", "ginger", "ginger roots", False, "beige knobbly ginger roots"),
    "22176": ("bags of boiling potatoes", "potato", "bags of potatoes", True, "yellow potatoes in plastic bags"),
    # --- 6594 onions / garlic / pumpkin
    "15816": ("Hokkaido pumpkins", "pumpkin", "pumpkins", False, "round orange pumpkins"),
    "15753": ("bags of red potatoes", "potato", "bags of potatoes", True, "red potatoes in large plastic bags"),
    "11914": ("onions", "onion", "onions", False, "loose yellow brown onions"),
    "22083": ("net bags of onions", "onion", "bags of onions", True, "onions in mesh bags"),
    "31119": ("packs of garlic", "garlic", "packs of garlic", True, "white garlic bulbs in nets"),
    "11916": ("garlic", "garlic", "garlic bulbs", False, "loose white garlic bulbs"),
    "11917": ("red onions", "red onion", "red onions", False, "loose purple red onions"),
    "19127": ("bags of red onions", "red onion", "bags of red onions", True, "red onions in mesh bags"),
    "18090": ("bags of shallots", "onion", "bags of shallots", True, "small shallots in mesh bags"),
    "21915": ("bags of sweet onions", "onion", "bags of onions", True, "onions in mesh bags"),
    # --- 6781
    "22193": ("bags of white potatoes", "potato", "bags of potatoes", True, "potatoes in red and white plastic bags"),
}

# base categories that are visually near-identical: a swap between them is weak evidence
SIMILAR = [
    {"orange", "clementine"},
    {"banana", "plantain"},
    {"watermelon"},
    {"melon", "cantaloupe"},
    {"peach", "nectarine", "apricot"},
    {"lemon", "lime"},
    {"onion", "red onion"},
    {"white cabbage", "leafy cabbage"},
    {"cucumber", "zucchini"},
    {"potato", "sweet potato"},
    {"mango", "papaya"},
]

# keyword fallback for unseen names (accents stripped, uppercase)
_FALLBACK = [
    ("BANANA PAO", "plantains", "plantain"), ("BANANA", "bananas", "banana"),
    ("CLEMENTINA", "clementines", "clementine"), ("TANGERINA", "tangerines", "clementine"),
    ("LARANJA", "oranges", "orange"), ("LIMAO", "lemons", "lemon"), ("LIMA", "limes", "lime"),
    ("MELANCIA", "watermelons", "watermelon"), ("MELOA", "melons", "melon"), ("MELAO", "melons", "melon"),
    ("MACA", "apples", "apple"), ("PERA", "pears", "pear"), ("KIWI", "kiwis", "kiwi"),
    ("ALFACE", "lettuce", "lettuce"), ("ABACATE", "avocados", "avocado"),
    ("PIMENTO", "bell peppers", "green pepper"), ("BERINGELA", "eggplants", "eggplant"),
    ("CHUCHU", "chayotes", "chayote"), ("FEIJAO", "green beans", "green beans"),
    ("PEPINO", "cucumbers", "cucumber"), ("BROCOLO", "broccoli", "broccoli"),
    ("COUVE FLOR", "cauliflowers", "cauliflower"), ("COUVE ROXA", "red cabbages", "red cabbage"),
    ("COUVE", "cabbages", "white cabbage"), ("CURGETE", "zucchini", "zucchini"),
    ("TOMATE", "tomatoes", "tomato"), ("MORANGO", "strawberries", "strawberry"),
    ("MANGA", "mangoes", "mango"), ("UVA", "grapes", "grape"), ("CEREJA", "cherries", "cherry"),
    ("ABACAXI", "pineapples", "pineapple"), ("ANANAS", "pineapples", "pineapple"),
    ("PITAYA", "dragon fruit", "dragon fruit"), ("GOIABA", "guavas", "guava"),
    ("MARACUJA", "passion fruit", "passion fruit"), ("GRANADILHA", "granadillas", "passion fruit"),
    ("MAMAO", "papayas", "papaya"), ("PAPAIA", "papayas", "papaya"), ("ALPERCE", "apricots", "apricot"),
    ("PESSEGO", "peaches", "peach"), ("NECTARINA", "nectarines", "nectarine"),
    ("BATATA DOCE", "sweet potatoes", "sweet potato"), ("BATATA", "potatoes", "potato"),
    ("GENGIBRE", "ginger", "ginger"), ("ABOBORA", "pumpkins", "pumpkin"),
    ("CEBOLA ROXA", "red onions", "red onion"), ("CEBOLA", "onions", "onion"),
    ("ALHO", "garlic", "garlic"), ("CENOURA", "carrots", "carrot"),
]


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def is_packaged(name):
    n = strip_accents(name).upper()
    if re.search(r"\bEMB\b|\bEMB[.:]", n):
        return True
    if re.search(r"\d+(\.\d+)?\s*(G|GR)\b", n):
        return True
    if re.search(r"\d+(\.\d+)?\s*KG\b", n) and not re.search(r"\bKG\s*(IMP)?$", n.strip()):
        return True
    if re.search(r"\b\d+(\.\d+)?KG\b", n):
        return True
    return False


def translate(product_id, name):
    """-> dict(en, base, unit, pack, look)."""
    if str(product_id) in TABLE:
        en, base, unit, pack, look = TABLE[str(product_id)]
        return dict(en=en, base=base, unit=unit, pack=pack, look=look)
    n = strip_accents(name).upper()
    pack = is_packaged(name)
    for kw, en, base in _FALLBACK:
        if kw in n:
            unit = ("packs of " + en) if pack else en
            return dict(en=unit, base=base, unit=unit, pack=pack, look=en)
    return dict(en="produce", base="produce", unit="produce", pack=pack, look="fruit and vegetables")


def similar(b1, b2):
    if b1 == b2:
        return True
    return any(b1 in g and b2 in g for g in SIMILAR)

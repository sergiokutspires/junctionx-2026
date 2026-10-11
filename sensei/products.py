"""Portuguese product names -> English, coarse base category, loose/packaged, CLIP prompts.

The planogram only gives store names such as "MAÇÃ GALA CNT CAL 70/80 KG IMP". This module turns them
into an English description (for CLIP and the English UI), a coarse base fruit or vegetable (the level at
which compliance is judged) and whether the product is sold loose or packed. ``Catalog`` holds the parsed
products of one planogram.

``parse_name("MAÇÃ GALA CNT CAL 70/80 KG IMP")`` ->
``{"english": "gala apple", "base": "apple", "variety": "gala", "loose": True, ...}``.

The parser normalises accents (MAÇÃ / MAÇÂ / MACA all work), strips store codes (CNT, IGP,
CAT I, R0, A/AA, CAL. 73/85, ZER0%D, SC, IMP ...), finds the head noun (first produce word,
Portuguese is noun-first) and orders the remaining modifiers the English way.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- lexicon
# PT phrase (upper case, no accents) -> (English noun, coarse base). Longest phrase wins.
BASES: dict[str, tuple[str, str]] = {
    # fruit
    "BANANA": ("banana", "banana"),
    "BANANAS": ("banana", "banana"),
    "BANANA PAO": ("plantain banana", "banana"),
    "BANANA DA TERRA": ("plantain", "banana"),
    "PLATANO": ("plantain", "banana"),
    "LARANJA": ("orange", "orange"),
    "LARANJAS": ("orange", "orange"),
    "LARANJA SANGUINEA": ("blood orange", "orange"),
    "LIMAO": ("lemon", "lemon"),
    "LIMOES": ("lemon", "lemon"),
    "LIMA": ("lime", "lime"),
    "LIMAS": ("lime", "lime"),
    "CLEMENTINA": ("clementine", "clementine"),
    "CLEMENTINAS": ("clementine", "clementine"),
    "TANGERINA": ("tangerine", "clementine"),
    "MANDARINA": ("mandarin", "clementine"),
    "TANGERA": ("tangor", "clementine"),
    "TORANJA": ("grapefruit", "grapefruit"),
    "MACA": ("apple", "apple"),
    "MACAS": ("apple", "apple"),
    "PERA": ("pear", "pear"),
    "PERAS": ("pear", "pear"),
    "MARMELO": ("quince", "quince"),
    "KIWI": ("kiwi", "kiwi"),
    "KIWIS": ("kiwi", "kiwi"),
    "KIWI GOLD": ("gold kiwi", "kiwi"),
    "MELAO": ("melon", "melon"),
    "MELOA": ("melon", "melon"),
    "MELANCIA": ("watermelon", "watermelon"),
    "MANGA": ("mango", "mango"),
    "MANGAS": ("mango", "mango"),
    "ANANAS": ("pineapple", "pineapple"),
    "ABACAXI": ("pineapple", "pineapple"),
    "PAPAIA": ("papaya", "papaya"),
    "PAPAIAS": ("papaya", "papaya"),
    "PAPAYA": ("papaya", "papaya"),
    "MAMAO": ("papaya", "papaya"),
    "MARACUJA": ("passion fruit", "passion fruit"),
    "GRANADILHA": ("granadilla", "granadilla"),
    "PITAYA": ("pitaya", "pitaya"),
    "PITAIA": ("pitaya", "pitaya"),
    "FRUTA DO DRAGAO": ("pitaya", "pitaya"),
    "GOIABA": ("guava", "guava"),
    "LICHIA": ("lychee", "lychee"),
    "LICHIAS": ("lychee", "lychee"),
    "COCO": ("coconut", "coconut"),
    "CARAMBOLA": ("star fruit", "star fruit"),
    "FISALIS": ("physalis", "physalis"),
    "PHYSALIS": ("physalis", "physalis"),
    "ROMA": ("pomegranate", "pomegranate"),
    "DIOSPIRO": ("persimmon", "persimmon"),
    "DIOSPIROS": ("persimmon", "persimmon"),
    "FIGO": ("fig", "fig"),
    "FIGOS": ("fig", "fig"),
    "NESPERA": ("loquat", "loquat"),
    "ANONA": ("cherimoya", "cherimoya"),
    "UVA": ("grapes", "grapes"),
    "UVAS": ("grapes", "grapes"),
    "CEREJA": ("cherries", "cherries"),
    "CEREJAS": ("cherries", "cherries"),
    "GINJA": ("sour cherries", "cherries"),
    "MORANGO": ("strawberries", "strawberries"),
    "MORANGOS": ("strawberries", "strawberries"),
    "FRAMBOESA": ("raspberries", "raspberries"),
    "FRAMBOESAS": ("raspberries", "raspberries"),
    "MIRTILO": ("blueberries", "blueberries"),
    "MIRTILOS": ("blueberries", "blueberries"),
    "AMORA": ("blackberries", "blackberries"),
    "AMORAS": ("blackberries", "blackberries"),
    "GROSELHA": ("currants", "currants"),
    "AMEIXA": ("plum", "plum"),
    "AMEIXAS": ("plum", "plum"),
    "PESSEGO": ("peach", "peach"),
    "PESSEGOS": ("peach", "peach"),
    "NECTARINA": ("nectarine", "nectarine"),
    "NECTARINAS": ("nectarine", "nectarine"),
    "ALPERCE": ("apricot", "apricot"),
    "ALPERCES": ("apricot", "apricot"),
    "DAMASCO": ("apricot", "apricot"),
    "ABACATE": ("avocado", "avocado"),
    "ABACATES": ("avocado", "avocado"),
    "TAMARA": ("dates", "dates"),
    "TAMARAS": ("dates", "dates"),
    "CASTANHA": ("chestnuts", "chestnuts"),
    "CASTANHAS": ("chestnuts", "chestnuts"),
    "NOZ": ("walnuts", "walnuts"),
    "NOZES": ("walnuts", "walnuts"),
    "AMENDOA": ("almonds", "almonds"),
    # vegetables
    "TOMATE": ("tomato", "tomato"),
    "TOMATES": ("tomato", "tomato"),
    "BATATA": ("potato", "potato"),
    "BATATAS": ("potato", "potato"),
    "BATATA DOCE": ("sweet potato", "sweet potato"),
    "BATATA-DOCE": ("sweet potato", "sweet potato"),
    "INHAME": ("yam", "sweet potato"),
    "MANDIOCA": ("cassava", "cassava"),
    "CEBOLA": ("onion", "onion"),
    "CEBOLAS": ("onion", "onion"),
    "CEBOLINHA": ("baby onion", "onion"),
    # verified on camera 6594: small onions in 500 g net bags (not chives)
    "CEBOLINHA FRANCESA": ("french baby onion", "onion"),
    "CEBOLINHO": ("chives", "chives"),
    "CEBOLINHO FRANCES": ("chives", "chives"),
    "CHALOTA": ("shallot", "onion"),
    "ECHALOTA": ("shallot", "onion"),
    "ALHO": ("garlic", "garlic"),
    "ALHO FRANCES": ("leek", "leek"),
    "ALHO PORRO": ("leek", "leek"),
    "ALFACE": ("lettuce", "lettuce"),
    "RUCULA": ("rocket", "lettuce"),
    "AGRIAO": ("watercress", "lettuce"),
    "ESPINAFRE": ("spinach", "spinach"),
    "ESPINAFRES": ("spinach", "spinach"),
    "ACELGA": ("chard", "spinach"),
    "ENDIVIA": ("endive", "lettuce"),
    "CHICORIA": ("chicory", "lettuce"),
    "COUVE": ("cabbage", "cabbage"),
    "REPOLHO": ("cabbage", "cabbage"),
    "COUVE FLOR": ("cauliflower", "cauliflower"),
    "COUVE-FLOR": ("cauliflower", "cauliflower"),
    "COUVE BROCOLO": ("broccoli", "broccoli"),
    "COUVE BROCOLOS": ("broccoli", "broccoli"),
    "BROCOLO": ("broccoli", "broccoli"),
    "BROCOLOS": ("broccoli", "broccoli"),
    "BROCULOS": ("broccoli", "broccoli"),
    "COUVE PORTUGUESA": ("portuguese cabbage", "cabbage"),
    "COUVE TRONCHUDA": ("portuguese cabbage", "cabbage"),
    "COUVE PENCA": ("portuguese cabbage", "cabbage"),
    "COUVE GALEGA": ("collard greens", "cabbage"),
    "COUVE LOMBARDA": ("savoy cabbage", "cabbage"),
    "COUVE CORACAO": ("pointed cabbage", "cabbage"),
    "COUVE CHINESA": ("chinese cabbage", "cabbage"),
    "COUVE KALE": ("kale", "cabbage"),
    "COUVE DE BRUXELAS": ("brussels sprouts", "brussels sprouts"),
    "NABO": ("turnip", "turnip"),
    "NABICA": ("turnip greens", "turnip"),
    "GRELOS": ("turnip tops", "turnip"),
    "CENOURA": ("carrot", "carrot"),
    "CENOURAS": ("carrot", "carrot"),
    "BETERRABA": ("beetroot", "beetroot"),
    "RABANETE": ("radish", "radish"),
    "AIPO": ("celery", "celery"),
    "FUNCHO": ("fennel", "fennel"),
    "ALCACHOFRA": ("artichoke", "artichoke"),
    "ESPARGO": ("asparagus", "asparagus"),
    "ESPARGOS": ("asparagus", "asparagus"),
    "COGUMELO": ("mushrooms", "mushrooms"),
    "COGUMELOS": ("mushrooms", "mushrooms"),
    "CURGETE": ("zucchini", "zucchini"),
    "CURGETES": ("zucchini", "zucchini"),
    "COURGETTE": ("zucchini", "zucchini"),
    "ABOBRINHA": ("zucchini", "zucchini"),
    "ABOBORA": ("pumpkin", "pumpkin"),
    "PEPINO": ("cucumber", "cucumber"),
    "PEPINOS": ("cucumber", "cucumber"),
    "PIMENTO": ("bell pepper", "pepper"),
    "PIMENTOS": ("bell pepper", "pepper"),
    "PIMENTA": ("chili pepper", "chili"),
    "MALAGUETA": ("chili pepper", "chili"),
    "BERINGELA": ("eggplant", "eggplant"),
    "BERINJELA": ("eggplant", "eggplant"),
    "CHUCHU": ("chayote", "chayote"),
    "PIMPINELA": ("chayote", "chayote"),
    "FEIJAO VERDE": ("green beans", "green beans"),
    "ERVILHA": ("peas", "peas"),
    "ERVILHAS": ("peas", "peas"),
    "FAVA": ("broad beans", "peas"),
    "FAVAS": ("broad beans", "peas"),
    "MILHO": ("corn", "corn"),
    "MILHO DOCE": ("sweet corn", "corn"),
    "QUIABO": ("okra", "okra"),
    "GENGIBRE": ("ginger", "ginger"),
    "CURCUMA": ("turmeric", "ginger"),
    "SALSA": ("parsley", "herbs"),
    "COENTROS": ("coriander", "herbs"),
    "HORTELA": ("mint", "herbs"),
    "MANJERICAO": ("basil", "herbs"),
    "ALECRIM": ("rosemary", "herbs"),
    "TOMILHO": ("thyme", "herbs"),
    "TOPINAMBO": ("jerusalem artichoke", "ginger"),
    # generic words: used only when nothing more specific is in the name
    "CITRINOS": ("citrus fruit", "orange"),
    "CITRINO": ("citrus fruit", "orange"),
    "CITR": ("citrus fruit", "orange"),
    "FRUTA": ("fruit", "fruit"),
    "FRUTOS VERMELHOS": ("berries", "strawberries"),
    "LEGUMES": ("vegetables", "vegetables"),
    "SALADA": ("salad", "lettuce"),
}
GENERIC = {"CITRINOS", "CITRINO", "CITR", "FRUTA", "LEGUMES", "SALADA"}

# Variety implied by a base phrase (shown in "variety").
BASE_VARIETY = {"BANANA PAO": "plantain (banana pão)", "CEBOLINHA FRANCESA": "french baby",
                "KIWI GOLD": "gold", "COUVE PORTUGUESA": "portuguese", "BATATA DOCE": "sweet"}

# English adjective order: organic, opinion, size, age, shape, colour, origin, variety, type, noun.
KIND_ORDER = ("opinion", "size", "age", "shape", "colour", "origin", "variety", "type", "purpose")
# These kinds are kept in the translation but left out of the visual description for CLIP.
NON_VISUAL_KINDS = {"opinion", "origin", "purpose"}

# PT phrase -> (English, kind)
MODS: dict[str, tuple[str, str]] = {
    # colours
    "VERDE": ("green", "colour"), "VERDES": ("green", "colour"),
    "VERMELHO": ("red", "colour"), "VERMELHA": ("red", "colour"), "VERMELHAS": ("red", "colour"),
    "VERMELHOS": ("red", "colour"),
    "AMARELO": ("yellow", "colour"), "AMARELA": ("yellow", "colour"), "AMARELAS": ("yellow", "colour"),
    "BRANCO": ("white", "colour"), "BRANCA": ("white", "colour"), "BRANCAS": ("white", "colour"),
    "ROXO": ("purple", "colour"), "ROXA": ("purple", "colour"), "ROXAS": ("purple", "colour"),
    "PRETO": ("black", "colour"), "PRETA": ("black", "colour"), "NEGRA": ("black", "colour"),
    "ROSA": ("pink", "colour"), "ROSADO": ("pink", "colour"), "ROSADA": ("pink", "colour"),
    "LARANJA": ("orange", "colour"), "DOURADO": ("golden", "colour"), "DOURADA": ("golden", "colour"),
    "RISCADA": ("striped", "colour"), "RISCADO": ("striped", "colour"),
    "MALHADO": ("spotted", "colour"), "BICOLOR": ("bicolour", "colour"),
    "MULTICOLOR": ("mixed colour", "colour"), "TRICOLOR": ("tricolour", "colour"),
    # size / age / shape
    "MINI": ("mini", "size"), "BABY": ("baby", "size"), "GRANDE": ("large", "size"),
    "GRANDES": ("large", "size"), "PEQUENO": ("small", "size"), "PEQUENA": ("small", "size"),
    "MEDIO": ("medium", "size"), "MEDIA": ("medium", "size"), "GIGANTE": ("giant", "size"),
    "NOVA": ("new", "age"), "NOVO": ("new", "age"), "NOVAS": ("new", "age"),
    "REDONDO": ("round", "shape"), "REDONDA": ("round", "shape"),
    "COMPRIDO": ("long", "shape"), "COMPRIDA": ("long", "shape"),
    "ACHATADO": ("flat", "shape"), "ACHATADA": ("flat", "shape"), "CHATO": ("flat", "shape"),
    # opinion / quality
    "DOCE": ("sweet", "opinion"), "SWEET": ("sweet", "opinion"), "SUPER SWEET": ("super sweet", "opinion"),
    "SUPER": ("super", "opinion"), "EXTRA": ("extra", "opinion"), "ESPECIAL": ("special", "opinion"),
    "PREMIUM": ("premium", "opinion"), "SELECAO": ("selection", "opinion"),
    "TASTY": ("tasty", "opinion"), "SABOROSO": ("tasty", "opinion"),
    "PRONTO COMER": ("ready-to-eat", "opinion"), "PRONTO A COMER": ("ready-to-eat", "opinion"),
    "PRONTO": ("ready-to-eat", "opinion"), "MADURO": ("ripe", "opinion"), "MADURA": ("ripe", "opinion"),
    "ZERORESIDUE": ("zero-residue", "opinion"), "ZERO RESIDUOS": ("zero-residue", "opinion"),
    # origin / brand
    "NACIONAL": ("portuguese", "origin"), "PORTUGAL": ("portuguese", "origin"),
    "PORTUGUES": ("portuguese", "origin"), "PORTUGUESA": ("portuguese", "origin"),
    "MADEIRA": ("madeira", "origin"), "ALGARVE": ("algarve", "origin"), "ACORES": ("azores", "origin"),
    "OESTE": ("oeste", "origin"), "ESPANHA": ("spanish", "origin"), "IMPORTADO": ("imported", "origin"),
    "AVIAO": ("air-flown", "origin"), "ZESPRI": ("zespri", "origin"), "CARIOCA": ("carioca", "origin"),
    "CANARIAS": ("canary islands", "origin"),
    # varieties
    "GALA": ("gala", "variety"), "ROYAL GALA": ("royal gala", "variety"), "FUJI": ("fuji", "variety"),
    "GRANNY SMITH": ("granny smith", "variety"), "GRANNY": ("granny smith", "variety"),
    "PINK LADY": ("pink lady", "variety"), "REINETA": ("reinette", "variety"),
    "REINETA PARDA": ("russet reinette", "variety"), "GOLDEN": ("golden", "variety"),
    "GOLDEN DELICIOUS": ("golden delicious", "variety"), "COSMIC CRISP": ("cosmic crisp", "variety"),
    "JONAGORED": ("jonagored", "variety"), "RED DELICIOUS": ("red delicious", "variety"),
    "STARKING": ("starking", "variety"), "BRAVO DE ESMOLFE": ("bravo de esmolfe", "variety"),
    "HONEYCRUNCH": ("honeycrisp", "variety"), "OPAL": ("opal", "variety"),
    "ROCHA": ("rocha", "variety"), "CONFERENCE": ("conference", "variety"),
    "PACKAMS": ("packham", "variety"), "PACKHAMS": ("packham", "variety"), "PACKHAM": ("packham", "variety"),
    "WILLIAMS": ("williams", "variety"), "ABATE": ("abate", "variety"),
    "HASS": ("hass", "variety"), "PALMER": ("palmer", "variety"), "KENT": ("kent", "variety"),
    "KEITT": ("keitt", "variety"), "TOMMY": ("tommy atkins", "variety"), "OSTEEN": ("osteen", "variety"),
    "GOLD": ("gold", "variety"), "GALIA": ("galia", "variety"),
    "CANTALUPE": ("cantaloupe", "variety"), "CANTALUPE CHARENTAIS": ("cantaloupe", "variety"),
    "CHARENTAIS": ("charentais", "variety"), "PELE DE SAPO": ("piel de sapo", "variety"),
    "HOKAIDO": ("hokkaido", "variety"), "HOKKAIDO": ("hokkaido", "variety"),
    "BUTTERNUT": ("butternut", "variety"), "MANTEIGA": ("butternut", "variety"),
    "RED GLOBE": ("red globe", "variety"), "CRIMSON": ("crimson", "variety"),
    "THOMPSON": ("thompson", "variety"), "VITORIA": ("victoria", "variety"),
    "MOSCATEL": ("muscat", "variety"), "CAVENDISH": ("cavendish", "variety"),
    "PARAGUAYO": ("paraguayo flat", "variety"), "PARAGUAIO": ("paraguayo flat", "variety"),
    "MARMANDE": ("marmande", "variety"), "RAF": ("raf", "variety"), "KUMATO": ("kumato", "variety"),
    "DATTERINO": ("datterino", "variety"), "ICEBERG": ("iceberg", "variety"),
    "ROMANA": ("romaine", "variety"), "LISA": ("butterhead", "variety"),
    "NAVEL": ("navel", "variety"), "VALENCIA": ("valencia", "variety"), "NADORCOTT": ("nadorcott", "variety"),
    "ORRI": ("orri", "variety"), "HAYWARD": ("hayward", "variety"),
    # type / use
    "CHERRY": ("cherry", "type"), "CEREJA": ("cherry", "type"), "CACHO": ("bunch", "type"),
    "CHUCHA": ("plum", "type"), "PERA": ("plum", "type"), "CORACAO DE BOI": ("oxheart", "type"),
    "ROMA": ("roma", "type"),
    "ASSAR": ("roasting", "purpose"), "COZER": ("boiling", "purpose"),
    "FRITAR": ("frying", "purpose"), "SALADA": ("salad", "purpose"), "SOPA": ("soup", "purpose"),
    "SECO": ("dry", "type"), "SECA": ("dry", "type"), "FRISADA": ("frisee", "type"),
    "CRESPA": ("curly", "type"), "SEM GRAINHA": ("seedless", "type"),
    "SEM SEMENTES": ("seedless", "type"), "SEM CAROCO": ("pitted", "type"),
    "POUCAS SEMENTES": ("few-seed", "type"), "COM SEMENTES": ("seeded", "type"),
    "LAVADA": ("washed", "type"), "DESCASCADA": ("peeled", "type"), "CORTADA": ("cut", "type"),
    "RALADA": ("grated", "type"), "FATIADO": ("sliced", "type"), "CUBOS": ("diced", "type"),
    "METADE": ("half", "type"), "BOLA": ("round", "shape"),
}
# Same PT word, different English depending on the head noun's base.
CONTEXT_MODS: dict[tuple[str, str], str] = {
    ("onion", "ROXA"): "red", ("onion", "ROXO"): "red", ("cabbage", "ROXA"): "red",
    ("cabbage", "ROXO"): "red", ("lettuce", "ROXA"): "red", ("potato", "ROXA"): "purple",
    ("tomato", "CACHO"): "vine", ("tomato", "PERA"): "plum", ("tomato", "CEREJA"): "cherry",
    ("banana", "CACHO"): "bunch", ("grapes", "BRANCA"): "white", ("pear", "ROCHA"): "rocha",
}
IGNORED_MODS = {"PENCA", "TRONCHUDA"}  # redundant synonyms of the head noun

CODES = {"CNT", "CONTINENTE", "IGP", "IG", "DOP", "IMP", "SC", "R0", "R1", "R2", "CAL", "CALIBRE",
         "KG", "KGS", "KGR", "G", "GR", "GRS", "UN", "UND", "UNID", "UNIDADE", "UNIDADES", "CAT",
         "CATEGORIA", "I", "II", "III", "INT", "INTEIRA", "INTEIRO", "INTEIR", "INTEIRAS",
         "INTEIROS", "INTEIR.", "DE", "DA", "DO", "DAS", "DOS", "E", "A", "O", "AO", "EM", "P",
         "S", "C", "ZERO", "PCT", "LT", "ML", "MIX"}
ORGANIC = {"BIO", "BIOLOGICO", "BIOLOGICA", "BIOLOGICOS", "ORGANICO", "ORGANICA"}
PACK_WORDS = {"EMB", "EMBALAGEM", "EMBALADO", "EMBALADA", "PACK", "EMBAL"}
CONTAINERS = {"SACO": "plastic bags", "SACOS": "plastic bags", "REDE": "net bags",
              "CUVETE": "plastic punnets", "TERRINA": "tubs", "CX": "boxes", "CAIXA": "boxes",
              "BANDEJA": "trays", "FRASCO": "jars"}
BUNCH_WORDS = {"MOLHO", "MACO", "RAMO"}  # sold in bunches, still "loose"
# Proper Portuguese spelling for the UI name (the store file mixes MACA / MAÇA / MAÇÂ ...).
PT_SPELLING = {"MACA": "MAÇÃ", "MACAS": "MAÇÃS", "MAMAO": "MAMÃO", "MELAO": "MELÃO",
               "PESSEGO": "PÊSSEGO", "MARACUJA": "MARACUJÁ", "LIMAO": "LIMÃO", "FEIJAO": "FEIJÃO",
               "AVIAO": "AVIÃO", "CORACAO": "CORAÇÃO", "ABOBORA": "ABÓBORA", "BROCOLO": "BRÓCOLO",
               "PAO": "PÃO", "CITR": "CITRINOS", "INTEIR": "INTEIRA", "ROMA": "ROMÃ",
               "AGRIAO": "AGRIÃO", "HORTELA": "HORTELÃ", "MANJERICAO": "MANJERICÃO"}

# --------------------------------------------------------------------------- appearance
# Coarse base -> (visual plural description, similarity group). Also the list of distractor
# categories for zero-shot recognition (ALL_BASES).
BASE_INFO: dict[str, tuple[str, str]] = {
    "banana": ("bunches of yellow bananas", "banana"),
    "orange": ("oranges", "citrus"),
    "clementine": ("small orange clementines", "citrus"),
    "lemon": ("yellow lemons", "citrus"),
    "lime": ("small green limes", "citrus"),
    "grapefruit": ("large grapefruits", "citrus"),
    "apple": ("apples", "pome"),
    "pear": ("pears", "pome"),
    "quince": ("yellow quinces", "pome"),
    "kiwi": ("brown fuzzy kiwi fruits", "kiwi"),
    "melon": ("whole melons", "melon"),
    "watermelon": ("whole green striped watermelons", "melon"),
    "mango": ("red and green mangoes", "tropical"),
    "pineapple": ("pineapples with green crowns", "tropical"),
    "papaya": ("yellow-green papayas", "tropical"),
    "passion fruit": ("dark purple passion fruits", "passion fruit"),
    "granadilla": ("orange granadilla fruits", "passion fruit"),
    "pitaya": ("dragon fruits", "tropical"),
    "guava": ("round light green guavas", "tropical"),
    "lychee": ("red lychees", "tropical"),
    "coconut": ("brown hairy coconuts", "tropical"),
    "star fruit": ("yellow star fruits", "tropical"),
    "physalis": ("orange physalis berries", "berries"),
    "pomegranate": ("red pomegranates", "pomegranate"),
    "persimmon": ("orange persimmons", "persimmon"),
    "fig": ("purple figs", "fig"),
    "loquat": ("orange loquats", "stone fruit"),
    "cherimoya": ("green cherimoyas", "tropical"),
    "grapes": ("bunches of grapes", "grapes"),
    "cherries": ("dark red cherries", "berries"),
    "strawberries": ("red strawberries", "berries"),
    "raspberries": ("red raspberries", "berries"),
    "blueberries": ("blueberries", "berries"),
    "blackberries": ("blackberries", "berries"),
    "currants": ("red currants", "berries"),
    "plum": ("purple plums", "stone fruit"),
    "peach": ("red and yellow peaches", "stone fruit"),
    "nectarine": ("red nectarines", "stone fruit"),
    "apricot": ("orange apricots", "stone fruit"),
    "avocado": ("dark green avocados", "avocado"),
    "dates": ("brown dates", "dates"),
    "chestnuts": ("brown chestnuts", "nuts"),
    "walnuts": ("walnuts in shell", "nuts"),
    "almonds": ("almonds", "nuts"),
    "tomato": ("red tomatoes", "tomato"),
    "potato": ("potatoes", "potato"),
    "sweet potato": ("reddish-brown sweet potatoes", "potato"),
    "cassava": ("brown cassava roots", "potato"),
    "onion": ("yellow onions", "onion"),
    "chives": ("bunches of green chives", "herbs"),
    "garlic": ("white garlic bulbs", "onion"),
    "leek": ("long green and white leeks", "onion"),
    "lettuce": ("heads of green lettuce", "leafy"),
    "spinach": ("green spinach leaves", "leafy"),
    "cabbage": ("whole cabbages", "brassica"),
    "cauliflower": ("white cauliflower heads", "brassica"),
    "broccoli": ("green broccoli heads", "brassica"),
    "brussels sprouts": ("brussels sprouts", "brassica"),
    "turnip": ("white turnips", "root"),
    "carrot": ("orange carrots", "root"),
    "beetroot": ("dark red beetroots", "root"),
    "radish": ("red radishes", "root"),
    "celery": ("green celery stalks", "leafy"),
    "fennel": ("white fennel bulbs", "leafy"),
    "artichoke": ("green artichokes", "artichoke"),
    "asparagus": ("bundles of green asparagus", "asparagus"),
    "mushrooms": ("white mushrooms", "mushrooms"),
    "zucchini": ("dark green zucchinis", "squash"),
    "pumpkin": ("orange pumpkins", "squash"),
    "cucumber": ("long green cucumbers", "squash"),
    "chayote": ("pale green chayote squashes", "squash"),
    "pepper": ("bell peppers", "pepper"),
    "chili": ("small red chili peppers", "pepper"),
    "eggplant": ("dark purple eggplants", "eggplant"),
    "green beans": ("green beans", "beans"),
    "peas": ("green pea pods", "beans"),
    "corn": ("corn cobs", "corn"),
    "okra": ("green okra pods", "beans"),
    "ginger": ("knobbly ginger roots", "root"),
    "herbs": ("bunches of fresh herbs", "herbs"),
    "fruit": ("fresh fruit", "fruit"),
    "vegetables": ("fresh vegetables", "vegetables"),
}
ALL_BASES: list[str] = sorted(b for b in BASE_INFO if b not in ("fruit", "vegetables"))

# What the real products look like (checked on the camera crops). Keyed by English name.
VISUAL: dict[str, str] = {
    "madeira banana": "bunches of small yellow madeira bananas",
    "plantain banana": "large green plantain bananas",
    "algarve orange": "oranges",
    "gala apple": "red and yellow gala apples",
    "fuji apple": "red and yellow fuji apples",
    "granny smith apple": "green granny smith apples",
    "pink lady apple": "pinkish red pink lady apples",
    "reinette apple": "russet brown reinette apples",
    "portuguese golden apple": "yellow-green golden delicious apples",
    "golden apple": "yellow-green golden delicious apples",
    "cosmic crisp apple": "dark red cosmic crisp apples",
    "organic red apple": "red apples",
    "red apple": "red apples",
    "packham pear": "green packham pears",
    "conference pear": "long brown-green conference pears",
    "zespri gold kiwi": "golden kiwi fruits",
    "gold kiwi": "golden kiwi fruits",
    "galia melon": "round netted galia melons",
    "cantaloupe melon": "round pale netted cantaloupe melons",
    "green melon": "oval green-yellow piel de sapo melons",
    "mini watermelon": "small striped mini watermelons",
    "black few-seed watermelon": "round dark green watermelons",
    "striped few-seed watermelon": "large striped green watermelons",
    "red pitaya": "pink dragon fruits (red pitaya)",
    "yellow pitaya": "yellow dragon fruits (yellow pitaya)",
    "purple passion fruit": "dark purple passion fruits",
    "papaya": "large yellow-green papayas",
    "air-flown papaya": "small orange-yellow papayas",
    "air-flown palmer mango": "red and green palmer mangoes",
    "white seedless grapes": "green seedless grapes",
    "red globe grapes": "large red globe grapes",
    "paraguayo flat peach": "flat paraguayo peaches",
    "red potato": "red-skinned potatoes",
    "white potato": "white potatoes",
    "new onion": "fresh yellow onions",
    "sweet onion": "sweet yellow onions",
    "red onion": "purple red onions",
    "french baby onion": "small yellow onions",
    "dry garlic": "white garlic bulbs",
    "ready-to-eat hass avocado": "dark green hass avocados",
    "frisee lettuce": "curly frisee lettuce",
    "green bell pepper": "green bell peppers",
    "red bell pepper": "red bell peppers",
    "portuguese cabbage": "large leafy portuguese cabbages",
    "white cabbage": "pale green white cabbages",
    "red cabbage": "purple red cabbages",
    "green zucchini": "dark green zucchinis",
    "hokkaido pumpkin": "orange hokkaido pumpkins",
    "green beans": "long flat green beans",
    "round tomato": "large round red tomatoes",
    "vine tomato": "red tomatoes on the vine",
    "oxheart tomato": "large ribbed oxheart tomatoes",
    "plum tomato": "elongated red plum tomatoes",
    "cherry tomato": "small red cherry tomatoes",
    "red cherry tomato": "small red cherry tomatoes",
    "organic cherry tomato": "small red cherry tomatoes",
    "mini red plum tomato": "small elongated red plum tomatoes",
    "sweet mini plum tomato": "small elongated red plum tomatoes",
    "mini vine tomato": "small red tomatoes on the vine",
}
# Packaging seen on the real shelves, by base (used for packaged products).
PACK_CONTAINER: dict[str, str] = {
    "potato": "printed plastic bags", "sweet potato": "plastic bags", "onion": "net bags",
    "garlic": "small net bags", "orange": "net bags", "clementine": "net bags", "lemon": "net bags",
    "lime": "net bags", "kiwi": "small punnets", "apple": "plastic bags", "pear": "plastic bags",
    "tomato": "plastic punnets", "grapes": "plastic clamshell punnets",
    "cherries": "plastic clamshell punnets", "strawberries": "plastic punnets",
    "blueberries": "small punnets", "raspberries": "small punnets", "lettuce": "plastic bags",
    "carrot": "plastic bags", "mushrooms": "plastic trays", "green beans": "plastic trays",
}
PACK_CONTAINER_BY_NAME = {"organic red apple": "film-wrapped cardboard trays",
                          "red onion": "purple printed net bags"}
# Priced by weight but displayed as single fruit (e.g. PITAYA 200G, GRANADILHA 80 G).
SINGLE_FRUIT_BASES = {"pitaya", "granadilla", "passion fruit", "mango", "papaya", "pineapple",
                      "melon", "watermelon", "avocado", "coconut", "pumpkin", "cabbage",
                      "cauliflower", "broccoli", "pomegranate", "guava"}
# Extra loose-display prompt per base (how the store shows it).
LOOSE_EXTRA: dict[str, str] = {
    "grapes": "{visual} in brown paper bags in a crate",
    "banana": "{visual} on a black curved banana display",
}

EMPTY_PROMPTS: list[str] = [
    "an empty supermarket display crate",
    "an empty shelf",
    "an empty teal plastic crate seen from above",
    "an empty green plastic produce crate",
    "an empty grey metal tray",
    "an empty cardboard box",
    "a white foam egg-crate liner in an empty crate",
    "an empty black curved banana display shelf",
    "an empty wicker basket on a shelf",
    "the bare bottom of an empty produce bin in a grocery store",
]
OCCLUSION_PROMPTS: list[str] = [
    "a hand reaching into a shelf",
    "a shopper's arm",
    "a person's head and shoulders seen from above",
    "a shopping basket",
    "a shopping cart",
    "a store employee restocking a shelf",
    "a grey fabric cover over a closed shelf",
]


# --------------------------------------------------------------------------- parsing

def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_WEIGHT_RE = re.compile(r"(?<![\w/,])(\d+(?:[.,]\d+)?)\s*(KGS?|GRS?|G)(?![A-Z0-9])")
_PRE_SUBS = [
    (re.compile(r"ZER[O0]\s*%\s*D?\b"), " ZERORESIDUE "),
    (re.compile(r"\bS/\s*"), " SEM "),
    (re.compile(r"\bC/\s*"), " COM "),
    (re.compile(r"\bP/\s*"), " POUCAS "),   # "P/ SEMENTES" next to "POUCAS SEMENTES" in the same file
    (re.compile(r"\bCAT\.?\s*(?:III|II|I)\b"), " "),
    (re.compile(r"\bA{1,3}(?:\s*/\s*A{1,3})+\b"), " "),
    (re.compile(r"\b\d+(?:/\d+)+\+?"), " "),
    (re.compile(r"\b\d+\+"), " "),
    (re.compile(r"[/.,:;()%+*'\"!?#&]"), " "),
    (re.compile(r"\b\d+(?:[.,]\d+)?\b"), " "),
]
_MAX_PHRASE = max(len(k.split()) for k in list(BASES) + list(MODS))


def _extract_weight(s: str) -> tuple[str, float | None]:
    """Remove pack weights (``500 G``, ``EMB. 3KG``, ``1.5 KG``) -> (rest, grams or None)."""
    grams = None
    for m in _WEIGHT_RE.finditer(s):
        value = float(m.group(1).replace(",", "."))
        if value > 0:
            grams = value * (1000.0 if m.group(2).startswith("K") else 1.0)
    return _WEIGHT_RE.sub(" ", s), grams


def _tokens(norm: str) -> list[str]:
    for rx, rep in _PRE_SUBS:
        norm = rx.sub(rep, norm)
    return norm.split()


def _format_weight(grams: float | None) -> str | None:
    if grams is None:
        return None
    if grams >= 1000:
        kg = grams / 1000.0
        return f"{kg:g} kg"
    return f"{grams:g} g"


def plural(phrase: str) -> str:
    """English plural of the last word ('bell pepper' -> 'bell peppers', 'potato' -> 'potatoes')."""
    words = phrase.split()
    if not words:
        return phrase
    last = words[-1]
    irregular = {"potato": "potatoes", "tomato": "tomatoes", "mango": "mangoes", "cherry": "cherries",
                 "strawberry": "strawberries", "peach": "peaches", "radish": "radishes",
                 "squash": "squashes", "leaf": "leaves", "zucchini": "zucchinis", "kiwi": "kiwis"}
    uncountable = {"garlic", "ginger", "broccoli", "chives", "celery", "spinach", "kale", "rocket",
                   "asparagus", "corn", "parsley", "coriander", "mint", "basil", "rosemary", "thyme",
                   "watercress", "okra", "chard", "lettuce", "fruit", "produce", "turmeric",
                   "collard greens", "greens", "cassava"}
    if last in irregular:
        last = irregular[last]
    elif last in uncountable and last != "fruit":
        pass
    elif last == "fruit":
        last = "fruits"
    elif last.endswith("s"):
        pass
    elif last.endswith(("ch", "sh", "x")):
        last += "es"
    elif last.endswith("y") and len(last) > 1 and last[-2] not in "aeiou":
        last = last[:-1] + "ies"
    else:
        last += "s"
    return " ".join(words[:-1] + [last])


def _pt_display(name: str) -> str:
    """Clean Portuguese name for the UI: codes/weights removed, accents kept, title case."""
    up = unicodedata.normalize("NFC", name.upper())
    up, _ = _extract_weight(up)
    toks = []
    for t in _tokens(up):
        n = _strip_accents(t)
        if n in CODES - {"DE", "DA", "DO", "DAS", "DOS", "E"} or n in PACK_WORDS or n == "ZERORESIDUE":
            continue
        toks.append(PT_SPELLING.get(n, t))
    small = {"DE", "DA", "DO", "DAS", "DOS", "E", "SEM", "COM"}
    out = [t.lower() if (i and t in small) else t.capitalize() for i, t in enumerate(toks)]
    return " ".join(out)


def parse_name(name: str) -> dict:
    """Parse a Portuguese store product name.

    Returns {"raw", "english", "base", "variety", "loose", "packaged", "organic"} plus extras:
    "pt" (clean Portuguese for the UI), "group" (similar-looking bases share a group),
    "visual" (plural visual description used in prompts), "appearance" ("loose" | "packaged":
    how it looks on the shelf), "container" (e.g. "net bags" or None), "pack_weight" ("500 g"
    or None) and "unknown_tokens" (words not in the dictionary, kept as variety names).
    """
    raw = name
    norm = _strip_accents(unicodedata.normalize("NFC", str(name))).upper().strip()
    norm, grams = _extract_weight(norm)
    toks = _tokens(norm)

    head: tuple[str, str, str] | None = None        # (pt phrase, english noun, base)
    generic: tuple[str, str, str] | None = None
    mods: list[tuple[str, str, str]] = []           # (pt, english, kind)
    late_bases: list[str] = []                      # base words after the head -> modifiers
    unknown: list[str] = []
    organic = packed = False
    container: str | None = None

    i = 0
    while i < len(toks):
        matched = False
        for length in range(min(_MAX_PHRASE, len(toks) - i), 0, -1):
            phrase = " ".join(toks[i:i + length])
            in_base, in_mod = phrase in BASES, phrase in MODS
            if not (in_base or in_mod):
                continue
            if in_base and phrase in GENERIC:
                if generic is None:
                    generic = (phrase, *BASES[phrase])
            elif in_base and head is None:          # Portuguese is noun-first
                head = (phrase, *BASES[phrase])
            elif in_mod:
                mods.append((phrase, *MODS[phrase]))
            else:
                late_bases.append(phrase)
            i += length
            matched = True
            break
        if matched:
            continue
        t = toks[i]
        i += 1
        if t in ORGANIC:
            organic = True
        elif t in PACK_WORDS:
            packed = True
        elif t in CONTAINERS:
            container, packed = CONTAINERS[t], True
        elif t in BUNCH_WORDS:
            mods.append((t, "bunch", "type"))
        elif t in CODES or t in IGNORED_MODS:
            continue
        elif re.fullmatch(r"[A-Z]?\d+[A-Z]?", t):   # stray codes like R0, C12
            continue
        else:
            unknown.append(t)

    if head is None:
        head = generic
    if head is None:  # nothing known: fall back to the words themselves
        words = " ".join(t.lower() for t in unknown) or norm.lower() or "produce"
        head = ("", words, words.split()[-1] if words.split() else "produce")
        unknown = []
    head_pt, noun, base = head

    for pt in late_bases:
        mods.append((pt, BASES[pt][0], "variety"))
    resolved: list[tuple[str, str]] = []  # (english, kind)
    for pt, en, kind in mods:
        en = CONTEXT_MODS.get((base, pt), en)
        if en and en not in noun.split():
            resolved.append((en, kind))
    resolved += [(u.lower(), "variety") for u in unknown]
    order = {k: n for n, k in enumerate(KIND_ORDER)}
    resolved.sort(key=lambda x: order.get(x[1], len(order)))  # stable: keeps PT order inside a kind
    words: list[str] = []
    for en, _ in resolved:
        if en not in words:
            words.append(en)

    english = " ".join((["organic"] if organic else []) + words + [noun])
    variety = " ".join(w for w in [BASE_VARIETY.get(head_pt, "")] + words if w)
    visual_words = [en for en, kind in resolved if kind not in NON_VISUAL_KINDS]
    visual_key = " ".join(dict.fromkeys(visual_words + [noun]))
    if english in VISUAL:
        visual = VISUAL[english]
    elif visual_key in VISUAL:
        visual = VISUAL[visual_key]
    elif not visual_words and noun == base and base in BASE_INFO:
        visual = BASE_INFO[base][0]
    else:
        visual = plural(visual_key)

    packaged = bool(packed or (grams is not None))
    appearance = "packaged" if packaged and base not in SINGLE_FRUIT_BASES else "loose"
    if packaged and container is None and appearance == "packaged":
        container = PACK_CONTAINER_BY_NAME.get(english, PACK_CONTAINER.get(base, "packages"))
    if unknown:
        log.debug("parse_name(%r): unknown words %s kept as variety", raw, unknown)
    return {
        "raw": raw,
        "english": english,
        "base": base,
        "variety": variety,
        "loose": not packaged,
        "packaged": packaged,
        "organic": organic,
        "pt": _pt_display(raw),
        "group": BASE_INFO.get(base, ("", base))[1],
        "visual": visual,
        "appearance": appearance,
        "container": container,
        "pack_weight": _format_weight(grams),
        "unknown_tokens": unknown,
    }


# --------------------------------------------------------------------------- prompts

_COLLECTIVE = ("bunches of", "heads of", "bundles of", "curly")


def _prompts(p: dict) -> list[str]:
    english, visual, base = p["english"].replace("organic ", ""), p["visual"], p["base"]
    pl = plural(english)
    if p["appearance"] == "packaged":
        c = p["container"] or "packages"
        out = [f"packages of {pl} on a supermarket shelf",
               f"{c} of {visual} on a supermarket shelf",
               f"a crate full of {c} of {pl}, seen from above",
               f"packaged {visual} at a grocery store",
               f"a photo of {pl} in {c}"]
    else:
        pile = "" if visual.startswith(_COLLECTIVE) else "a pile of "
        out = [f"a photo of {pile}{visual} in a supermarket",
               f"loose {pl} at a grocery store",
               f"a crate full of {visual}",
               f"{visual} on a supermarket produce display, seen from above",
               f"a close-up photo of {visual}"]
        if base in LOOSE_EXTRA:
            out.append(LOOSE_EXTRA[base].format(visual=visual))
        if p["packaged"]:  # weight-priced single fruit: may also be wrapped
            out.append(f"packaged {visual} at a grocery store")
    return list(dict.fromkeys(out))


def prompts_for(name: str) -> list[str]:
    """CLIP text prompts for one product name (loose piles vs packaged bags/nets/punnets)."""
    return _prompts(parse_name(name))


def base_prompts(base: str, packaged: bool | None = None) -> list[str]:
    """Prompts for a coarse base category ('banana', 'apple' ...) for base-level recognition.

    packaged=None gives loose and packaged prompts together.
    """
    visual = BASE_INFO.get(base, (plural(base), base))[0]
    pl = plural(base)
    pile = "" if visual.startswith(_COLLECTIVE) else "a pile of "
    loose = [f"a photo of {pile}{visual} in a supermarket",
             f"loose {pl} at a grocery store",
             f"a crate full of {visual}"]
    if base in LOOSE_EXTRA:
        loose.append(LOOSE_EXTRA[base].format(visual=visual))
    c = PACK_CONTAINER.get(base, "packages")
    packed = [f"packages of {pl} on a supermarket shelf", f"{c} of {visual} on a supermarket shelf"]
    if packaged is None:
        return loose + packed
    return packed if packaged else loose


# --------------------------------------------------------------------------- catalog

@dataclass
class Catalog:
    """Products of a planogram: product_id -> parse_name(...) + {"areas": [area_ids], "name": raw}."""

    products: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_planogram(cls, areas_by_cam: dict[str, Iterable]) -> "Catalog":
        products: dict[str, dict] = {}
        for areas in areas_by_cam.values():
            for a in areas:
                entry = products.get(a.product_id)
                if entry is None:
                    entry = parse_name(a.product_name)
                    entry.update(name=a.product_name, areas=[])
                    products[a.product_id] = entry
                elif entry["name"] != a.product_name:
                    log.warning("product %s has two names: %r / %r (keeping the first)",
                                a.product_id, entry["name"], a.product_name)
                entry["areas"].append(a.area_id)
        return cls(products)

    def __len__(self) -> int:
        return len(self.products)

    def __contains__(self, product_id: object) -> bool:
        return product_id in self.products

    def __getitem__(self, product_id: str) -> dict:
        return self.products[product_id]

    def ids(self) -> list[str]:
        return list(self.products)

    def area_product(self) -> dict[str, str]:
        """area_id -> product_id."""
        return {a: pid for pid, p in self.products.items() for a in p["areas"]}

    def bases(self) -> list[str]:
        """Distinct coarse bases present in the catalog, sorted."""
        return sorted({p["base"] for p in self.products.values()})

    def ids_by_base(self) -> dict[str, list[str]]:
        """Coarse base -> product ids of that base, in catalog order."""
        out: dict[str, list[str]] = {}
        for pid, p in self.products.items():
            out.setdefault(p["base"], []).append(pid)
        return out

    def relation(self, a: str, b: str) -> str:
        """How alike two products are: 'same' | 'variety' (same base) | 'group' | 'different'."""
        if a == b:
            return "same"
        pa, pb = self.products[a], self.products[b]
        if pa["base"] == pb["base"]:
            return "variety"
        if pa["group"] == pb["group"]:
            return "group"
        return "different"

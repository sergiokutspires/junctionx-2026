# Produce biology reference: method, classes, sources

Companion to `docs/produce_biology_reference.csv` (94 planogram rows, `;`-separated, UTF-8 with BOM, same
columns as `produce_biology_template.csv` plus `confidence`). The template was only read, never modified.
Built 2026-10-11 for the staff app's "Freshness watch" and "ethylene neighbours" features.

## 1. Method

1. **One evidence record per product type.** Every row of a type shares its values. Rows differ only where the
   biology differs: delivered ripe (air-flown mango and papaya, ready-to-eat avocado), a different melon group
   (Galia, Charentais, Piel de Sapo), uncured onions, oxheart tomato, and Portuguese cabbage, which is a leafy
   cabbage, not a head.
2. **Source order.** (a) USDA Agriculture Handbook 66 (AH-66, 2016 revision, 138 commodity summaries). Many of
   its authors are UC Davis Postharvest Center faculty: Kader, Cantwell, Crisosto, Saltveit and Thompson.
   (b) FAO / UC Davis manual by Kitinoja and Kader (2002), for perishability and storage-life tables.
   (c) Peer-reviewed papers for products that AH-66 does not cover, or for direct measurements at 20 °C.
   The UC Davis Produce Facts pages could not be read: they sit behind a Cloudflare bot check, which was
   **not** bypassed. AH-66 was used in their place.
3. **Display assumption.** Unrefrigerated supermarket display at about 18-22 °C, under store lighting, at
   normal store humidity.
4. **Never invent.** If no number was found, the row says so in `source` or below, takes the **conservative**
   class (shorter life, higher sensitivity or production), and gets `confidence` = low or medium.

## 2. Class definitions

**LB (lower-bound display life, days at ~20 °C).** This is the earliest day by which a defect that makes the
product unsaleable is plausible. It is not the average.
- Where a direct measurement at about 20 °C exists, it is used (for example guava, banana, garlic,
  potato greening and chayote).
- Otherwise LB is extrapolated from the storage life at the product's optimum temperature. The extrapolation
  uses AH-66's temperature table (Saltveit, *Respiratory Metabolism*, p.69, Table 2). That table gives
  relative shelf life 100 at 0 °C, 33 at 10 °C and 13 at 20 °C, so the life at 20 °C is about
  - 0.13 × the life at an optimum of 0 °C,
  - about 0.23 × at 5 °C,
  - about 0.28 × at 7 °C,
  - 0.39 × at 10 °C,
  - about 0.52 × at 13 °C.
- The lower end of the range is taken. LB is then shortened when the product is delivered ripe or loses water
  quickly.

| Column | Rule |
|---|---|
| `shelf_life_class` | **fast** if LB < 3 d, **medium** if 3-7 d, **slow** if > 7 d. Exception: **potato** is classed *slow* (decay and sprouting take weeks), but its hours follow the light-greening risk (see below). |
| `hours_on_display_before_checking` | **LB × 24 / 3, rounded down** to 8 / 12 / 24 / 48 / 72 h. This gives 2-3 staff looks before the earliest expected defect. 8 h is the floor (once per shift). 72 h is the cap: every crate is looked at at least every 3 days. One packed adjustment: **oranges in nets/bags are 48 h** instead of 72 h, because blue/green mould spreads from fruit to fruit (AH-66). |
| `ethylene_producer` | Kader's five classes at 20 °C, as tabulated by Pesis (2004; reproduced in Mithapara & Butani 2023), collapsed to three. **high** = ≥10 µL/kg/h (Kader *high* and *very high*: apple, apricot, avocado, cantaloupe, kiwifruit, nectarine, papaya, peach, pear, passion fruit). **medium** = 1-10 (banana, plantain, guava, mango, tomato). **low** = <1. The AH-66 per-commodity rates at 20 °C are used where they exist. Where AH-66 and Pesis disagree (papaya 6-10 vs *high*, apricot firm-ripe 4-6 vs *high*), the higher class is kept. |
| `ethylene_sensitive` | **high** = the source calls it *very* or *extremely* sensitive, or reports damage at ≤1 µL/L or after short exposure. **medium** = ethylene speeds ripening, softening, yellowing or decay with prolonged exposure, or the source says *moderate*. **low** = not sensitive, or does not respond. These follow the definitions of the postharvest.net.au summary table. If sources disagree, the higher class is kept (for example pepper: AH-66 says keep it away from ethylene, the AU table says *low*, so it is *medium*). |
| `visible_spoilage_signs` | Written for a ceiling camera: colour shifts, mould patches, collapse, leakage, shrivel and sprouts. Signs marked *close-up only* or *internal* are not visible from the ceiling. Packed rows add a reminder that the camera sees only the top layer. |
| `confidence` | **high** = ethylene classes from a primary source for this commodity **and** display life backed by a direct ambient or 20 °C statement. **medium** = ethylene classes direct, but LB extrapolated or partly inferred. **low** = proxy species or uncertain product identity, or no measured rate. |

## 3. Per-type evidence (summary)

Rates are AH-66 values at 20 °C unless noted (µL C2H4/kg/h). Page numbers are AH-66 pages.

| Type / product | LB (d) | Basis for LB | Class / h | C2H4 production | Sensitivity basis | Conf. |
|---|---|---|---|---|---|---|
| apple (all 11) | 8 | 2-4 mo air storage at 0 °C × 0.13. AH-66 p.59 lists apple as fine for ambient display. | slow / 48 | "varies greatly" by variety. Pesis: high | ethylene advances ripening and firmness loss | med |
| apricot | 1.5 | 1-2 wk at 0 °C. Cold-table display recommended, softens very fast (p.195). | fast / 12 | 4-6 firm-ripe, higher soft-ripe. Pesis: high | hastens ripening and decay | med |
| avocado (ready-to-eat) | 1 | Delivered ripe. "Check ripeness every day", hold ripe fruit at 1-6 °C (p.219). | fast / 8 | >100 when ripe | unripe "very sensitive" | med |
| banana, Madeira banana | 3 | **Direct:** 3 d half-ripe to over-ripe at 20 °C (Bagnato 2003). About 6 d at 22 °C after ripening (Bagnato 2002). | medium / 24 | 0.3-10 | responds to 0.3-0.5 µL/L | high / med |
| plantain (banana-pão) | 3 | As banana (AH-66 covers both). | medium / 24 | Pesis: moderate | as banana | med |
| broccoli | 1.5 | 2-3 wk at 0 °C | fast / 12 | <0.1 | "extremely sensitive". 2 µL/L halves shelf-life | med |
| white, red cabbage | 3 | Early cabbage 3-6 wk at 0 °C | medium / 24 | <0.1 | 1 µL/L speeds yellowing and senescence | med |
| Portuguese cabbage | 1.5 | **Proxy:** collards and kale, 10-14 d / 2-3 wk at 0 °C | fast / 12 | low (greens) | all leafy greens sensitive | low |
| cauliflower | 1.5 | Storage life is 3 d at 15 °C (p.271), extrapolated to 20 °C | fast / 12 | <1 | "extremely sensitive" | med |
| chayote | 7 | **Direct:** about 10 d at room temperature (24 °C). Sprouting costs commercial quality from about 13 d. | medium / 48 | nonclimacteric (no rate found) | ethephon promoted sprouting, so *inferred* medium | med |
| cherries | 1 | 2-3 wk at -1 to 0 °C. "Refrigeration during display is critical" (p.283). | fast / 8 | very low | more respiration and quality loss | med |
| clementine | 3 | 2-4 wk at 4-8 °C | medium / 24 | <0.1 | ethylene stimulates citrus decay | med |
| cucumber | 3 | <14 d at 10-12.5 °C. Rapid yellowing already at 15 °C. | medium / 24 | 0.1-1.0 | 1-5 µL/L causes yellowing and decay | med |
| eggplant | 3 | 1-2 wk at 10-12 °C | medium / 24 | 0.1-0.7 (12.5 °C) | "moderate to high", so high | med |
| garlic | 30 | **Direct:** 1-2 months at 20-30 °C (p.333) | slow / 72 | very low | not particularly sensitive | high |
| ginger | 10 | 60-90 d at 12-14 °C. Dehydration is the main problem. | slow / 72 | "very low" | 1-MCP reduced sprouting at 23 °C (Lv 2021), so *inferred* medium | med |
| granadilla | 7 | 3-4 wk at 10 °C. 15 d limit at 27 °C with 1-MCP. | medium / 48 | **no rate found**. Assumed high like *P. edulis* | 1-MCP delays ripening | low |
| grapes (loose and punnet) | 1.5 | 2-4 wk at 0 °C without SO2. AH-66: ambient only for "a few hours", cold table. | fast / 12 | <0.1 | "not very sensitive" | med |
| green beans | 1.5 | 8-12 d at 5-7.5 °C. Quality drops fast above 7.5 °C. | fast / 12 | <0.05 (5 °C) | >0.1 µL/L cuts life 30-50% | med |
| guava | 3 | **Direct:** "about 7 days at 20 °C" from green, less if delivered riper | medium / 24 | 1-20. Pesis: moderate | speeds ripening | high |
| kiwi (all 4) | 5 | Ambient display acceptable (p.374). No 20 °C figure, so assumed. | medium / 24 | 0.1-0.5 unripe, 50-100 ripe | 5-10 **ppb** speeds softening | med |
| lemon | 10 | 1-6 mo at 10-13 °C | slow / 72 | <0.1 | may speed deterioration and decay | med |
| lettuce (frisée, bagged) | 1 | Leaf lettuce ≤2 wk at 0 °C | fast / 8 | very low | russet spotting, yellowing | med |
| lime | 7 | 6-8 wk at 9-10 °C, shortened because of yellowing | medium / 48 | <0.1 | degreening (yellowing) | med |
| mango / air-flown Palmer | 3 / 2 | 2-3 wk at 13 °C for mature-green. Air-flown fruit is tree-ripe. | medium 24 / fast 12 | 1-2 | faster softening | med |
| cantaloupe/Charentais, Galia | 2 | Netted melon 10-14 d at 2-7 °C. Galia trials use 3 d at 20 °C as the shelf-life phase. | fast / 12 | 10-100 | exposure shortens shelf-life | med |
| green melon (Piel de Sapo type) | 7 | Inodorus melons less perishable. Casaba-type 3 wk at 10 °C. | medium / 48 | non-climacteric, low | inodorus melons respond to ethylene | med |
| nectarine, peach, flat peach | 1.5 | 2-4 wk at -0.5 to 0 °C. Cold table once soft. | fast / 12 | 0.1-160 | uniform ripening | med |
| dry onions (bags, red, baby) | 14 | FAO: dry onion has low perishability. Warmth induces sprouting. | slow / 72 | <0.1 | low (sprouting only at >1500 µL/L) | med / low |
| new onion / sweet onion | 5 / 10 | Not fully cured (no data) / mild onions keep 1-3 mo | medium 24 / slow 72 | <0.1 | low | low / med |
| orange (loose / nets) | 10 | 3-12 wk optimum. AH-66: non-refrigerated display, "inspect often". | slow / 72, nets 48 | <0.1 | ethylene stimulates decay | med |
| papaya / air-flown | 3 / 2 | Ripens 10-16 d from colour-break at 23-28 °C. Anthracnose from about 25% yellow. | medium 24 / fast 12 | 6-10. Pesis: high | speeds softening | med |
| passion fruit | 4 | Purple 3-5 wk at 3-5 °C. Shrivel is the main defect. | medium / 24 | 160-400 | speeds ripening | med |
| pear (Conference, Packham's) | 4 | **Direct:** ripens in 4-7 d at 20 °C, then over-ripens | medium / 24 | peak 10-200 | cultivar-dependent | med |
| pepper | 4 | 2-3 wk at 7 °C. Soft rot above 13 °C. | medium / 24 | 0.2 | AH-66 "store away" vs AU table low, so medium | med |
| pineapple | 4 | 14-20 d at 7-12 °C | medium / 24 | 0.1-1.0 | ethephon slightly shortens shelf-life | med |
| pitaya (red, yellow) | 4 | 14 d at 10 °C | medium / 24 | 0.025-0.091 | ethylene does not trigger colour | med |
| potato (all 7) | 1.5\* | **Direct:** unacceptable greening after **24-60 h of retail LED light at 20 °C** (Larsen & Molteberg 2022) | slow / **12** | <0.1 | not very sensitive | high |
| pumpkin (Hokkaido) | 21 | 2-3 mo at 10-13 °C. AH-66: ambient display. | slow / 72 | trace | stem abscission, rind yellowing | high |
| strawberries | 0.5 | ≤7 d at 0 °C. AH-66: ambient only for "a few hours". | fast / 8 | <0.1 | do not respond | high |
| sweet potato | 14 | **Direct:** normally displayed at about 21 °C. Sprouting only after months at ≥19 °C. | slow / 72 | low | minor concern | high |
| tomato (10) / oxheart | 3 / 2 | Firm-ripe 4-7 d at 13-15 °C. Oxheart is soft and large: no data, so conservative. | medium 24 / fast 12 | 1-10 | 0.5 µL/L triggers ripening | med / low |
| watermelon (3) | 7 | 2-3 wk at 10-15 °C | medium / 48 | 0.1-1.0 | 5 µL/L causes softening and over-ripeness | med |
| zucchini | 2 | 1-2 wk at 5-10 °C. Shrivel shows at 3% weight loss. | fast / 12 | 0.1-1.0 | yellowing | med |

\*Potato: LB refers to greening, not decay. If the store's potato bags block light (Larsen & Molteberg: total
transmittance <0.02 W/m²), 72 h is defensible for the bagged SKUs.

## 4. Ethylene neighbours found in this planogram

Pairs of a **high producer** next to a **high-sensitivity** product on the same camera. Two areas count as
neighbours when their image polygons are within 0.25 × √(area of the smaller polygon) of each other.

| Camera | Producer (area) | Sensitive neighbour (areas) |
|---|---|---|
| 6383 | ready-to-eat Hass avocado (6383_2) | frisée lettuce 6383_1, green beans 6383_8, cucumber 6383_9 |
| 6371 | cantaloupe/Charentais melon (6371_7) | watermelons 6371_4, 6371_6, 6371_8 |
| 6376 | Galia melon (6376_2) | Zespri kiwi 6376_10 (side-by-side crates) |

Checked by eye on the `data/teacher/*_overview.jpg` frames: all three layouts are real neighbours.
- 49 more *amber* directional pairs exist (high producer next to medium sensitivity, or medium next to high).
- Most amber pairs are climacteric fruit next to climacteric fruit, such as peach next to nectarine, papaya
  next to mango, and apple next to pear. For those the practical effect is that both ripen faster, so they
  are lowest priority.

**Keep these warnings in proportion.**
- Warton et al. (2000) measured mean ethylene of only about 0.017-0.035 µL/L in supermarket receiving,
  storage and display areas. They rated about 0.015 µL/L as *low* (<10% of postharvest life lost) and about
  0.1 µL/L as *high* (>30% lost).
- Most damage thresholds above are 0.1-5 µL/L, measured in closed rooms.
- Kiwifruit is the exception: it responds to 5-10 ppb.
- So the neighbour feature should advise ("move the avocados away from the lettuce"). It should not alarm.

Reproduce with `.venv/Scripts/python tools/ethylene_neighbours.py [--gap 0.25] [--json out.json]`. It only reads
`data/raw/planogram.json` and this CSV. Re-run it whenever the planogram or the CSV changes.

## 5. Caveats

- **Display temperature.** The classes assume an unrefrigerated display at 18-22 °C. Camera 6383 (and probably
  6386, the same multideck with the brassicas) looks like an **open refrigerated multideck**: front air
  grille, vegetables in baskets. If it is refrigerated, real life on display is longer and the hours are conservative.
  Confirm with the store. The Q10 rule also implies that a 25 °C summer display shortens every LB by about
  1.4-1.6× (Q10 2-2.5).
- **Ripeness at delivery** dominates for banana, avocado, mango, papaya, kiwi, pear, stone fruit and melons.
  The rows assume typical retail ripeness. Fruit delivered riper needs the next shorter interval.
- **Cultivar and history.** Apple and pear ethylene output "varies greatly". Fruit treated with 1-MCP
  (SmartFresh) or held in CA storage can produce and respond much less. Long cold storage can bring out
  scald or chilling symptoms only *after* fruit warms up on display.
- **Q10 extrapolation is crude.** AH-66 itself warns that respiration "does not follow ideal behavior".
  Water loss in dry store air, which the Q10 ignores, can matter more for leafy greens, beans, zucchini,
  cherries and grapes.
- **Packaging** cuts water loss (good for grapes, cherries, lettuce) but hides mould and condensation from the
  camera. Hours were kept the same for packed rows, except the orange nets (48 h).
- **Camera limits.** From the ceiling you see colour, mould patches, collapse, leakage and empty space. You do
  not see firmness, internal browning, flavour loss or stem browning on small fruit. Hass avocado and red
  potatoes hide their key colour cue.
- **Product identity assumptions.**
  - *banana pão* = plantain-type cooking banana.
  - *melão verde* = Piel de Sapo type. This is consistent with the oval mottled melons in the camera 6371
    frames.
  - *cebolinha francesa* = small dry onions.
  - *couve portuguesa* behaves like collards and kale.
- **Not used:** paid databases and UC Davis Produce Facts (blocked by a bot check). No store images left this
  machine.

## 6. Sources

1. Gross, K.C., Wang, C.Y., Saltveit, M. (eds.) 2016. *The Commercial Storage of Fruits, Vegetables, and
   Florist and Nursery Stocks*. USDA Agriculture Handbook 66.
   https://www.ars.usda.gov/is/np/CommercialStorage/CommercialStorage.pdf
   - Used: Respiration and ethylene table p.7-10. Wholesale compatibility p.54-58. Grocery store display
     (Kader & Thompson) p.59-61. Respiratory metabolism (Q10 table) p.68-70. Ethylene effects p.76-82.
   - Commodity summaries at the pages cited in the CSV.
2. Kitinoja, L., Kader, A.A. 2002. *Small-Scale Postharvest Handling Practices: A Manual for Horticultural
   Crops* (4th ed.), UC Davis / FAO.
   - Relative perishability table: https://www.fao.org/4/ae075e/ae075e02.htm
   - Storage table after McGregor 1989, USDA AH-668: https://www.fao.org/4/ae075e/ae075e15.htm
3. Pesis, E. 2004, ethylene production classes, as reproduced in Mithapara, K.D., Butani, A.M. 2023, J.
   Pharmacogn. Phytochem. 12(6):107-119. https://doi.org/10.22271/phyto.2023.v12.i6b.14768
4. Postharvest physiology summary table (respiration, ethylene production and sensitivity classes; from the
   UC Davis database and AH-66). https://www.postharvest.net.au/summary-tables/physiology/
5. Bagnato, N., Klieber, A., Barrett, R., Sedgley, M. 2002. Aust. J. Exp. Agric. 42:1017-1022.
   https://doi.org/10.1071/EA01162
6. Bagnato, N., Barrett, R., Sedgley, M., Klieber, A. 2003. Int. J. Food Sci. Technol. 38(7):745-750
   (banana shelf-life at 20 °C, with and without 1-MCP).
7. Larsen, H., Molteberg, E.L. 2022. Discolouration of potato tubers under retail light. Potato Research.
   https://doi.org/10.1007/s11540-022-09585-6
8. Ramírez-Rodas, Y.C. et al. 2022. Chayote fruit development. Plants 12:108.
   https://doi.org/10.3390/plants12010108
9. Ramírez-Rodas, Y. et al. 2021. Postharvest storage of three chayote varieties. Scientia Agropecuaria
   12(2):239-247. https://doi.org/10.17268/sci.agropecu.2021.027
10. Dussán Sarria, S., Serna Cock, L., Perengüez Cuarán, A.M. 2011. 1-MCP on granadilla. Acta Agronómica.
    https://revistas.unal.edu.co/index.php/acta_agronomica/article/view/28786
11. Habibi, F. et al. *Passion Fruit: Postharvest Handling Practices and Physiological Disorders*. UF/IFAS
    HS1527. https://ask.ifas.ufl.edu/publication/HS1527
12. Gal, S., Alkalai-Tuvia, S., Elkind, Y., Fallik, E. 2006. 'Galia' melon and 1-MCP. J. Hortic. Sci.
    Biotechnol. 81(6):975-982. https://doi.org/10.1080/14620316.2006.11512185
13. Santo Domingo, M. et al. 2022. Modulating climacteric intensity in melon. Hortic. Res. 9:uhac131.
    https://doi.org/10.1093/hr/uhac131
14. Lv, J. et al. 2021. 1-MCP and ginger sprouting at room temperature. Food Chem. 349:129004.
    https://doi.org/10.1016/j.foodchem.2021.129004
15. Warton, M.A., Wills, R.B.H., Ku, V.V.V. 2000. Ethylene levels associated with fruit and vegetables during
    marketing. Aust. J. Exp. Agric. 40:465-470. https://doi.org/10.1071/EA99125
16. Banana da Madeira IGP specification (Cavendish subgroup, AAA). Diário da República.
    https://diariodarepublica.pt/dr/detalhe/aviso/42-2026-1161801109

## 7. Suggested app rules

- **Freshness watch.** Flag a planogram area for a look when `hours since last restock >=
  hours_on_display_before_checking`.
  - Order the flags fast > medium > slow.
  - Show `visible_spoilage_signs` as the checklist.
- **Ethylene neighbours.**
  - **Red** when a `high` producer is adjacent to a `high`-sensitivity product.
  - **Amber** for high/medium mixes.
  - Suppress amber between two climacteric fruits of the same family.
- **Show `confidence`** next to each tip, so staff (and judges) can see which numbers are measured and which are
  inferred.

## 8. Independent review (2026-10-11)

- Re-checked against freshly fetched sources: AH-66 PDF (text identical to the copy used), FAO perishability table,
  the Pesis table in Mithapara & Butani 2023, Bagnato 2002, Warton 2000, Larsen & Molteberg 2022 (abstract:
  cultivars "unacceptable at different times (24-60 h)"; no tested bag protected Folva), Santo Domingo 2022
  (Piel de Sapo "classical non-climacteric"), Ramírez-Rodas 2022 (nonclimacteric, ~10 d at 24 °C).
- Rows spot-checked and supported: avocado, banana, broccoli, cauliflower, cherries, cucumber, garlic, grapes,
  green beans, guava, kiwi, mango, papaya, passion fruit, pear, pepper, pineapple, potato, strawberries,
  sweet potato, tomato, watermelon, zucchini, apricot, onion, chayote, green melon.
- Fixed: the 15 `source` cells that said "Ethylene class (Pesis, ...)" now name where the table is published
  ("Pesis 2004 table in Mithapara & Butani 2023 Table 4"). Pesis 2004 is unpublished course notes.
- Judgement calls kept on purpose (conservative, as section 2 says): cherries and pineapple *medium* sensitivity
  (Kader lists them low); eggplant and beans *high* (the AU table says moderate); ready-to-eat avocado *high*
  sensitivity (AH-66 says "very sensitive" only for unripe fruit).


## Team biologist review (Inês Matias Medeiros, 11 Oct 2026)

- **Review:** Inês reviewed all 94 planogram products and confirmed every shelf-life class, check interval, ethylene
  production class and ethylene sensitivity class in this reference; she rewrote the visible-spoilage notes of the 8
  products sold both loose and packed (packaging-specific checks). Her table is `docs/ines/fruit_shelf_life_ethylene.xlsx`
  and is applied through `docs/produce_biology_template.csv` (her values override the reference cell by cell).
- **Ethylene profiles:** `docs/ines/ethylene_profiles.csv` gives each product a role (strong emitter; moderate emitter;
  emitter and highly sensitive; highly sensitive, low emitter; mildly sensitive, low emitter; neutral) and practical
  advice for staff.
- **Compatibility score (her design):** for two products A and B, with Low = 1, Medium = 2, High = 3,
  `risk = max(producer(A) x sensitivity(B), producer(B) x sensitivity(A))`, from 1 to 9. Bands: **1-3 compatible**
  (can share space), **4-6 caution** (separate shelves, remove damaged items quickly), **7-9 avoid** (keep apart).
  Matrices: `docs/ines/ethylene_compatibility_fruit.csv` (24 fruit types: 87 compatible, 148 caution, 41 avoid pairs)
  and `docs/ines/ethylene_compatibility_vegetable.csv` (17 vegetable types: 124 compatible, 12 caution, 0 avoid).
  The app's "strong" ethylene pairs (high producer next to high sensitivity) are exactly her score 9 ("avoid").

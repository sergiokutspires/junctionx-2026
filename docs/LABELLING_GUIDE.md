# How the AI answer key was made

The challenge gives images and a planogram but **no answers**. To measure our system (and to fit its small
calibration heads) we built an answer key with AI labellers. This page says how, so anyone can judge how much to
trust it.

**In one line:** `data/labels/teacher_labels_v2.json` holds an `empty / half / full` level and a
compliant / wrong-product flag for **all 1,962 planogram areas of all 181 frames** (14 cameras). Every area got
three AI votes (36 areas got two); disagreements were settled by a fourth AI pass. It is **AI-made, not the
store's truth.**

## What the labellers saw

For each frame, `tools/render_teacher_sheets.py` drew two pictures:

1. the full camera frame with every planogram area outlined in yellow and numbered;
2. one zoomed tile per area, headed `#n (area_id)` plus the planogram product name in Portuguese.

The labeller returned, per area: `stock_level`, `compliant`, and a short free-text `seen` note (kept in the
vote files).

## The rubric

The labellers' rubric is the `GUIDE` text in [`tools/gemini_label.py`](../tools/gemini_label.py), copied here
unchanged:

> You are a careful annotator labelling planogram areas in ceiling-camera photos of the fruit & vegetable section
> of a Portuguese supermarket (Continente).
> Image 1 is the full frame with every planogram area outlined in yellow and numbered. Image 2 has one zoomed tile
> per area (yellow outline = the area; header "#n (area_id)" and the planogram product name in Portuguese).
> Label ONLY what is inside each yellow outline (it may be slightly offset; judge the crate/compartment it mostly
> covers).
>
> stock_level: "full" = (nearly) fully covered, crate/tray bottom essentially not visible (>= ~75% covered), a
> normal well-stocked display even if not heaped; "half" = clearly partially stocked, a substantial part of the
> bottom visible (~25-75%) or a visibly depleted pile; "empty" = no product or only a few scattered units
> (< ~25% covered). Large single items (melons, pineapples, cabbages): judge coverage / how many more would fit.
> Packaged products: same rule on the surface.
>
> compliant: true if the product shown is the planogram product (same kind and, when visible, same form: loose vs
> bagged/packed, colour/variety such as red vs green pepper, white vs red grapes, red vs white potatoes); true if
> the area is empty; false if the area mainly shows a different product. Fine varieties you cannot tell apart
> (Gala vs Fuji, peach vs nectarine) -> true unless clearly different. Two products sharing -> judge the dominant
> one.
>
> Portuguese hints: BANANA PAO = large cooking banana; CITRINOS/CITR...LARANJA = oranges (KG loose, 1.5 KG/3KG net
> bags); CLEMENTINA; LIMAO lemon; LIMA lime; MACA/MAÇÃ apple; PERA pear; KIWI (500 G/400 G packs); MELANCIA
> watermelon; MELAO melon; MELOA cantaloupe/galia; MANGA mango; ABACAXI pineapple; MAMAO/PAPAIA papaya;
> MARACUJA/GRANADILHA passion fruit; PITAYA dragon fruit (packs); GOIABA guava; UVA BRANCA/RED GLOBE white/red
> grapes; CEREJA cherries; MORANGO strawberries; ALPERCE apricot; PESSEGO peach (PARAGUAYO flat peach); NECTARINA;
> TOMATE (CACHO vine, CHERRY, CORACAO DE BOI oxheart, CHUCHA plum; EMB/grams = packs); BATATA potato (DOCE sweet,
> VERMELHA red, BRANCA white, EMB. 3KG bags); CEBOLA onion (ROXA red; EMB bags); CEBOLINHA FRANCESA small
> onions/shallots pack; ALHO garlic; ABOBORA pumpkin; GENGIBRE ginger; ALFACE lettuce; ABACATE avocado; PIMENTO
> pepper (VERDE green, VERMELHO red); COUVE cabbage (BROCOLO broccoli, FLOR cauliflower, ROXA red, BRANCA white,
> PORTUGUESA kale); CURGETE zucchini; BERINGELA eggplant; CHUCHU chayote; FEIJAO VERDE green beans; PEPINO
> cucumber. "KG" = loose.
> Return every listed area exactly once.

**"Empty counts as compliant" is our assumption.** The brief does not say how its hidden annotations treat an
empty area. It lists empty shelves separately from wrong products, so we answer "compliant" for empty areas. The
labellers were given the same rule, so the key cannot test this choice.

## Rounds and models

| Round | Cameras / areas | Labellers | Output file |
|---|---|---|---|
| 1 | 3 cameras (6215, 6371, 6373): 393 areas | 3 Claude Opus 5.5 labellers (votes A, B, C), then adjudication | `votes_round1.json`, `teacher_labels_partial.json` |
| 2 | the other 11 cameras: 1,569 areas | one Claude Sonnet 5.5 vote per area (vote A) | `teacher_labels_late.json`, `teacher_labels_mid.json` |
| 3 | the same 1,569 areas | 2 more votes per area: Claude Sonnet 5.5 and Claude Opus 5.5 (votes B, C) | `votes_v2.json` |
| 4 | 34 disputed areas | Claude Opus 5.5 adjudication | `disputes_v2.json`, `adjudications_v2.json` |
| check | 192 areas (20 frames, cameras 6215 and 6371) | Gemini Flash, free tier, same rubric (`tools/gemini_label.py`) | `gemini_labels.json`, `gemini/*.json` |

All files are in [`data/labels/`](../data/labels/). Every area of the final key has three votes, except 36 areas
of camera 6373 from round 1, which have two (6 of those 36 are split).

## Voting and adjudication rules

[`tools/aggregate_votes.py`](../tools/aggregate_votes.py) merges the votes:

- **Majority vote** on the stock level and on the compliance flag.
- An area is a **dispute** when there is no level majority or the compliance votes are split. The 34 disputes
  are in `disputes_v2.json`.
- Disputes take the **adjudicator's answer** (`adjudications_v2.json`). Without one, the script would take the
  median level and the compliance majority ("compliant" on ties).
- The adjudicator could overrule the votes: in 6 of the 34 adjudications the chosen level differs from a 2-of-3
  level majority, and in 1 it is a level no labeller voted for; in 11 the compliance answer differs from a 2-of-3
  compliance majority.

The original round's workflow journal is not in the repository, so the script cannot be re-run end to end from
tracked files; every vote it read is saved in `votes_v2.json` and `votes_round1.json`.

## Agreement

| Measure | Value | How to check |
|---|---|---|
| Areas where all three votes agree (11 re-voted cameras) | 1,325 of 1,569 (84%) | `votes_v2.json` |
| Round 1 areas where all votes agree | 366 of 393 | `votes_round1.json` |
| Gemini Flash vs the key, wrong-product calls | 24 of 24 (100%); compliance agreed on all 192 areas | `gemini_labels.json` |
| Gemini Flash vs the key, stock level | 155 of 192 (81%) | `gemini_labels.json` |

The final key: 181 frames, 1,962 areas; 1,440 full, 340 half, 182 empty; 117 areas show a wrong product.

## What the key is, and what it is not

- **It is** a consistent, fully documented second opinion on every area, made the same way for every camera. We
  use it to rank models and to fit the small calibration heads.
- **It is not** the store's truth or Sensei's hidden annotations. The labellers are runs of the same model
  family looking at the same two pictures, so their errors can be correlated, and their agreement overstates
  accuracy.
- **Stock level is noisy.** A different model family (Gemini Flash) agreed on the stock level of only 81% of the
  192 areas it re-labelled. Our model's own stock accuracy on held-out areas is 82 to 86%, so stock-level
  differences of a few points are hard to separate from label noise.
- **It was also used to tune defaults** (thresholds and priors of the unsupervised part), so every score measured
  against it is optimistic to that extent. See [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md).

The older 756-area key (`teacher_labels.json`) is kept so that earlier numbers stay comparable.

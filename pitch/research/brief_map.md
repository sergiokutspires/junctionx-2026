> **Superseded working note (written ~01:20 on 11 Oct).** Numbers here predate the final model. The current brief-to-evidence table is in [README.md](../../README.md); the numbers we say are in [pitch/pitch.md](../pitch.md) ("Numbers you may say").

# Brief map: Sensei's words versus what we built and measured

> **SUPERSEDED (2026-10-11).** The numbers in this file are pre-final (for example 1.20 / 1.30 / 1.39, +15.5 CPU-s,
> $0.00009 per image, ~$440 a month per 1,000 cameras, ~$6 a month per section). Do not quote them: the final numbers and
> their sources are the table at the end of `pitch/pitch.md`. Kept for the gap analysis and the brief's wording.

Written 2026-10-11 from `docs/brief.txt`, `README.md`, `pitch/pitch.md`, `pitch/slides.html`, `pitch/qa_prep.md`,
`pitch/demo_script.md`, the code, the labels and the model folders. All numbers are the **current** ones and will be
replaced when the final numbers arrive. Paths are relative to the project root.

Tags: **[MEASURED]** number backed by a file. **[BUILT]** exists, never validated. **[PARTIAL]** part of it exists.
**[GAP]** nothing yet. **[DERIVED]** my arithmetic on measured inputs, labelled as such. **[NEW]** a number I computed
in this pass by re-running our own code on our own key; scripts and raw output are in `pitch/research/evidence/`
(`results.txt`, `staff_terms.json`) and are **not yet in `pitch.md`'s allowed-numbers table**, so the team must okay them.

---

## 0. Sensei's real problem, in three constraints (what the pitch must solve)

The brief is a scaling problem wearing a computer-vision costume. Three sentences of theirs carry it:

1. **Labels do not scale** (page 1): nobody can label every image, every day, across hundreds of stores and thousands of
   cameras, so the system must learn without being told what is right.
2. **Cost per camera must be near zero** (the added judging criterion, plus "fleet" on page 5): cost per image is stated in the pitch.
3. **Staff must keep trusting the app** (page 4): false alarm, missed problem, repeated errors.

Our best answer to each, with the honest number:

| Constraint | Our answer | Honest number | Evidence |
|---|---|---|---|
| No labels at scale | Label-free core (DINOv2 surface-vs-product fill + CLIP zero-shot); answer key made by AI labellers only to measure and calibrate | Label-free core alone: **1.19** per area on unseen cameras (1,240 areas), **0.97 / 0.93** on late frames / last frame. With the two small heads: **1.20 / 1.30 / 1.39**. Always "compliant + full": 0.64 / 0.36 / 0.06 | `models/real_v1_cal/calibration_cv.json` (the "baseline" method is the label-free core, "heads" is shipped), `pitch/research/evidence/staff_terms.json` |
| Near-zero cost | 1 CPU core, no GPU, no API | ~7 CPU-s and ~$0.00009 per image; ~$6/month per 14-camera section; Sonnet 5.5 would be ~$0.014 per image (~160x) | `outputs/benchmark/*.json`, `tools/benchmark_cost.py`, `tools/llm_cost_compare.py` |
| Staff trust | Cost-aware decisions, conservative wrong-product flag, confidence chip, "estimate" labels, age chip | Late-day: 98% of empty shelves are on the Do-now list, 1 in 40 shown as full; 0 false wrong-product alerts in 294 compliant late-frame areas. But 10% of late-day restock tasks point at a shelf the key calls full (26% on unseen cameras) | `pitch/research/evidence/staff_terms.json` [NEW] |

Two tensions the pitch must not hide (they are in section 8): the "no labels" headline and the "360 to 400 points" projection
are two different configurations, and the wrong-product detector is precise but not complete on unseen cameras.

---

## 1. Pain points (brief: Introduction, page 1)

| ID | Sensei's pain point | What we built and measured | Evidence | In pitch now | Gap or risk |
|---|---|---|---|---|---|
| A1 | Loose, no barcode, piled not aligned | **[MEASURED]** We do not count piles to score. Per-area fill = share of "product" patches vs "surface" patches (crates, trays), then empty/half/full. Stock level right on 80.6% (unseen cameras), 81.9% (late frames), 83.6% (last frame) | `sensei/stock.py`, `calibration_cv.json` (`stock_acc`) | Slide 3 (container repeats, product changes), slide 4 | Half vs full is the weak call: of 240 truly-half areas (unseen cameras) 97 are called full |
| A2 | Change shape, size, colour as they ripen | **[PARTIAL]** CLIP zero-shot at base-fruit level (banana vs orange vs apple) is tolerant to colour and shape drift. Varieties (Gala vs Fuji) are weak, so we flag only on clear evidence | `sensei/compliance.py`, `sensei/products.py`, README Limitations | Slide 4 (base-fruit level) | **[GAP]** Ripeness itself is not modelled or tested |
| A3 | Hidden by shoppers' and staff hands | **[BUILT]** Every crop carries a visibility mask; fill uses visible patches only; empty/occluded/barely visible counts as compliant (no false alarm); hands, baskets and shelf-sized boxes are dropped from the boxes | `sensei/data.py` (warp + mask), `sensei/dashboard.py` (`DET_*`, label filter list) | qa_prep Q4 only | **[GAP]** No accuracy split by occlusion level (qa_prep says "we have not measured") |
| A4 | Empty gondola, lost sales, unhappy customers | **[MEASURED] [NEW]** Truly empty areas that land on the Do-now list (as Empty or Low): 127 of 129 (98%) unseen cameras, 39 of 40 (98%) late frames, 24 of 24 last frame. Shown as full: 2 (1.6%), 1 (2.5%), 0. Called "empty" and right: 82%, 88%, 91% | `pitch/research/evidence/staff_terms.py` and `.json`; scoring `scoring.py` | Slide 2 names it; slide 6 shows Do-now | Only 75 to 88% of true empties are labelled "Empty" (the rest "Low"): still on the list, but not first |
| A5 | Overstocked, left too long, waste | **[PARTIAL]** The scale tops out at "full", so overstock is not a level. One proxy: Insights highlight "N products barely moved all day. Check they are still fresh" (drop under 1% of a shelf per hour over 10 h or more, no restock) | `ui/app.js` `insHints()` (`hint_slow`), `sensei/dashboard.py` `compute_insights()`, screenshot `pitch/assets/dash_insights.png` shows "26 products" | Not in pitch text; slide 9 lists "Less waste" as a next step | **[GAP]** Proxy never validated; no shelf-age, no ripeness, no delivery dates. Safe claim: "flags slow movers to inspect", not "predicts waste" |
| A6 | Wrong product in the wrong place, confused customers, wrong prices | **[MEASURED] [NEW]** In the AI key, 23 of 152 areas are wrong at some point (72 area-frame cases of 1,240 are those 23 areas repeated). Share of areas wrong falls from 18/152 (12%) in the 06h frames to 2/129 (1.6%) at 19h; 4 to 7 areas stay wrong most of the day (stale planogram?). Detector, late frames: found 8 of 10, 0 false alarms in 294; last frame 5 of 5, 0 in 147; unseen cameras 26 of 72 (36%), 1 false alarm in 1,168 | `pitch/research/evidence/wrong_product_persistence.py`, `staff_terms.json`, `data/labels/teacher_labels*.json` | Slide 3 ("broken at opening", "72 of 1,240") | Recall on unseen cameras is 36%. "72 of 1,240" overstates distinct problems; "at opening" is our inference (first frame 06:12, opening time unknown). Tone: it can read as "your store is messy" |
| A7 | Today staff walk the store | **[BUILT]** Static staff app replaces the walk with a ranked list | `ui/`, `outputs/real_v1_cal/dashboard/` | Slide 2 band | Never tried with staff |
| A8 | Labelling is hard and subjective; counting bananas is hard even for a person | **[MEASURED] [NEW]** Our own labellers prove the point: 3 AI votes agree on the stock level for 93.6% of 393 areas but only 84% of "half" areas (empty 94%, full 96%). A second AI (Gemini) matched all 192 compliance calls (all 24 wrong-product calls) but only 155 of 192 (81%) stock levels | `data/labels/votes_round1.json`, `data/labels/gemini_labels.json`, `tools/aggregate_votes.py`, `tools/gemini_label.py` | Slide 5 mentions 3 votes and 94%; "half is subjective" only in qa_prep Q8 | Slide 5 says "3 votes per area" for the whole 1,240 key; only 393 areas had 3 votes (see section 8) |
| A9 | Hundreds of stores, thousands of cameras | **[DERIVED]** 1,000 cameras x 1 picture per 5 min x 14 h = 168,000 images a day: ours ~$15/day (~$440/month); Sonnet 5.5 ~$2,370/day (~$71,000/month). Per 14-camera section: ours ~$6/month, Sonnet ~$1,000/month. Assumptions are ours (cadence, AWS c7i.large price) | `outputs/benchmark/llm_cost_compare.json`, `cost_1t.json` | Slide 2 says "thousands of cameras" in words only; no fleet arithmetic, no LLM comparison anywhere in deck or qa_prep | One store, one day: nothing measured at fleet scale. Sensei's real cadence and price per core are unknown |

---

## 2. Core, tasks and submission (brief pages 1 to 4)

| ID | Sensei asks | What we built and measured | Evidence | In pitch now | Gap or risk |
|---|---|---|---|---|---|
| B1 | "Recognise, count and check", continuously, without human help | **[BUILT]** Pipeline answers every area of every picture; works picture by picture so it can run continuously; the staff app is a static page rebuilt per batch | `sensei/pipeline.py`, `sensei/submit.py` | Slide 8 command box | **[GAP]** No live feed, no folder watcher, no hook into Sensei's systems; "re-analyse only changed areas" is slide-8 future work |
| B2 | Task 1: find the products in the image and name them | **[BUILT]** OWLv2 (free, local) boxes with product names, behind a "Show detections" button; CLIP names the product per area. Not scored by the brief (validation has area labels only) | `sensei/dashboard.py`, `colab/sensei_bigfeatures.ipynb`, `pitch/assets/dash_gondola_web.jpg` | Slide 4 step 5, slide 6 | **[GAP]** Box quality never measured (no box ground truth); boxes cost +15.5 CPU-s per image on top of the headline |
| B3 | Task 2: stock as an item count or a fill level | **[MEASURED]** Fill level is the scored output (1.20 / 1.30 / 1.39 points per area with the shipped heads). Counts are "about N visible units / packs", per area and added up per product | `calibration_cv.json`, `sensei/dashboard.py` `product_totals()` | Slides 4, 5, 7 | **[GAP]** Unit counts never checked against a hand count; bananas are bunches |
| B4 | Task 3: compliant, low, empty or wrong product, per area | **[MEASURED]** Four app states (Empty, Low, Wrong product, OK). Identification right on 96.2% / 99.3% / 100% of areas, but "always compliant" already gets 94.2% / 96.7% / 96.7%, so the real signal is wrong-product recall (A6) | `calibration_cv.json`, `staff_terms.json` | Not in the deck or qa_prep (README says 98% and 99%) | Quote identification only next to wrong-product recall |
| B5 | Count per area, then add up per product | **[BUILT]** Products tab adds visible units across areas; 36 of 94 products occupy more than one area (up to 6) | `sensei/dashboard.py` `product_totals()`, `data/raw/planogram.json` | Slide 7 | None |
| B6 | Partly visible areas (negative coordinates, 5 areas) | **[BUILT]** Visibility mask; app shows "Partly out of view" | `sensei/data.py`, `ui/app.js` (`partly`) | Not mentioned | Cheap trust point: say it |
| B7 | Loose (KG) vs packaged (unit = package) | **[BUILT]** "visible units" vs "visible packs" by catalogue name; Portuguese names kept, English added | `sensei/products.py`, `ui/app.js` (`cnt_u`, `cnt_p`) | Not mentioned | None |
| B8 | Recognise generically (banana, orange), no brands | **[MEASURED]** Catalogue names become CLIP prompts ("MACA GALA KG" becomes "gala apple"); no product images needed; 94 distinct products | `sensei/products.py`, `experiments/compliance_zeroshot/` | Slide 4 | Variety level is weak; say "base fruit" on purpose |
| B9 | Run our code on the hidden images and submit the outputs in their format | **[BUILT]** One command or double-click; unpacks zips, answers every area, re-reads the JSON and checks it, then builds the app. Missing area would cost -2 and -3, so none are skipped | `SUBMIT.bat`, `sensei/submit.py`, `tests/test_submit.py`, `outputs/dryrun_submit/` | Slide 8 | Not yet run on the real hidden pictures (pending by design) |
| B10 | Hidden set: 289 areas, max 578, example 320 | **[MEASURED]** Projection 360 to 400 from 1.25 to 1.40 per area | `pitch.md` numbers table; `calibration_cv.json`; `pitch/research/evidence/unseen_camera_756.py` | Slide 5 | Assumes hidden frames are late in the day (inferred from the brief's one example file name, about 20:24 Lisbon, later than all our frames) |

---

## 3. The shift scenario and staff trust (brief page 4)

| ID | Sensei says | What we built and measured | Evidence | In pitch now | Gap or risk |
|---|---|---|---|---|---|
| C1 | Staff open the app, see every gondola's stock level and every mismatch | **[BUILT]** Four counters (Empty, Low, Wrong product, OK), tabs Do now / Gondolas / Products / Insights, 375 px phone layout, light/dark, Portuguese by default | `ui/app.js`, `ui/index.html`, `pitch/assets/dash_desktop_web.jpg`, `dash_mobile_web.jpg` | Slide 6 | No usability trial with staff; "gondola" in the app means one camera view (a camera can see several modules, the planogram has no module field) |
| C2 | What to restock first, what to move back, what to leave alone | **[BUILT]** The app's three verbs are the brief's three: "Restock", "Move back", and "Leave alone: N areas look right". Order: "Do first: wrong product and empty", then "Then: running low"; By priority or By gondola (route); Mark done; progress bar; print | `ui/app.js` strings `act_restock`, `act_move`, `leave`, `urgent`, `soon`, `by_route` | Slide 6 covers the first two, **not** "leave alone" | Free echo of their own sentence |
| C3 | False alarm: staff walk to a shelf that needed nothing | **[MEASURED] [NEW]** Wrong-product alerts: 1 false alarm in 1,168 compliant areas (unseen cameras), 0 in 294 and 0 in 147 (late folds). Restock tasks (Empty or Low) pointing at a shelf the key calls full: 97 of 367 (26%) unseen cameras, 9 of 93 (10%) late frames, 6 of 62 (10%) last frame | `staff_terms.json` | Not quoted; deck says "no false alarms" on slide 4 | "No false alarms" is too strong for stock tasks; say "about 1 in 10 on late frames" or do not claim |
| C4 | Missed problem: empty or wrong shelf left in front of customers | **[MEASURED] [NEW]** Empty shown as full: 1.6% / 2.5% / 0%. Wrong product missed: 46 of 72 (unseen cameras), 2 of 10 (late), 0 of 5 (last). Lean-low decision rule from the scoring costs (-3 for too high) | `scoring.py` `best_stock`, `staff_terms.json` | Slide 4 step 4 (lean low) | Wrong-product misses on unseen cameras are the largest hole |
| C5 | Repeated errors, staff stop trusting the app | **[BUILT]** Confidence chip (Sure at 0.85 or more, Likely at 0.65 or more, else "Not sure: check by eye"); "estimate" on every count; age chip ("1.5 h old") on stale pictures; "Picture unreadable: not checked" instead of a guess; "Show detections" to inspect the reasoning | `ui/app.js` (`confKey`, `ageChip`, strings `c_check`, `cnt_est`, `unreadable`, `det_show`) | Slide 6 mentions boxes; trust is not named anywhere in the deck (only qa_prep) | **[GAP]** Confidence never calibrated: no check that "Sure" is right more often than "Likely" |
| C6 | Scoring rewards information staff can act on | **[BUILT]** Their penalties become our objective: pick the answer with the best expected score; always answer every area | `scoring.py` (`best_stock`), `test_scoring.py` | Slide 4 step 4, qa_prep Q9 | Compliment opportunity: their scoring is good design |
| C7 | UI/UX 1 to 5, "how clearly and quickly" staff see what to do (tie-break) | **[BUILT]** One glance: counters, ordered cards, outlined area on the photo, one plain sentence ("Nothing left to sell. Restock Banana."), Portuguese first | `ui/`, `demo_script.md` | Slide 6, demo | Tie-break only; no staff trial |

---

## 4. "Future potential and benefits" (brief pages 5 and 6)

| ID | Sensei's bullet | What we built and measured | Evidence | In pitch now | Gap or risk |
|---|---|---|---|---|---|
| F1 | Fleet of stores; a no-label solution switches on in a new store with no extra hardware and no labelling effort | **[PARTIAL]** Inputs are only the existing 1280x720 ceiling frames plus `planogram.json`; CPU only; `sensei fit` without `--labels` gives the label-free model. Leave-one-camera-out is our proxy for a new camera: 1.25 per area (original 756 areas, heads trained on the other cameras) | `README.md` (Run it), `models/real_v1/` (label-free), `pitch/research/evidence/unseen_camera_756.py` | Slide 1 hook and slide 10 ("No labels. No new hardware.") | **[GAP]** Only one store. Label-free alone scores lower on late frames (0.93 to 0.97). Cost of the calibration labels is unmeasured: **[DERIVED]** about $1.6 to $7.7 of AI labelling per store-day at API list price (115 frames x 1 vote, 181 frames x 3 votes at $0.0141). Time to fit a new store is not stated anywhere |
| F2a | When each product needs restocking, before the gondola runs empty | **[BUILT] [NEW backtest]** "Running out soon" = low area with forecast empty within 2 h; also "Empty in ~N min" on cards. Backtest on the AI key (every frame, hourly pictures): 27 flags, 9 (33%) really empty within ~2 h, vs 4% for a random not-yet-empty area and 11% for any "half" area; but it catches only 9 of the 60 (15%) shelves that emptied within 2 h | `sensei/temporal.py` `forecast_empty`, `sensei/dashboard.py` `compute_insights`, `pitch/research/evidence/forecast_backtest.py`, `results.txt` | Slides 7 and 9, labelled estimate | Indicative only: 9 hits, hourly pictures, AI truth (key v2, still moving). Their cameras at 5-minute cadence should sharpen it; untested |
| F2b | Which products stay too long and end up as waste | **[PARTIAL]** See A5 | `ui/app.js` `insHints()` | Slide 9 "Less waste" | **[GAP]** Slow-mover flag unvalidated |
| F2c | How well each store follows its planogram, without manual audits | **[MEASURED]** Planogram adherence per camera view, wrong-product views first; compliance measured as in A6 | `sensei/dashboard.py` `compute_insights()` (`adherence`) | Slide 7 | Shows "right now" only; no adherence-over-time curve, although the 12% to 2% fall during the day is in our data |
| F2d | How each product sells, hour by hour and store by store | **[BUILT]** Sales speed per product (share of a shelf lost per hour, restocks spotted), store-wide hourly bars, peak windows | `sensei/dashboard.py` `compute_insights()`, `pitch/assets/dash_insights.png` | Slide 7 ("all estimates") | **[GAP]** Never checked against real sales: Sensei holds the till data and we do not; one store, one day, so "store by store" is not shown. Fill drop is not a sale (customers rearrange, restocks are partial) |
| F2e | How the gondola layout affects what customers pick | **[GAP]** Nothing built | n/a | Slide 9 as a "where this leads" bullet | Natural experiment is in the data (36 of 94 products sit in 2 to 6 areas, with per-area fill timelines `tl`), but one day of hourly pictures is anecdote. Keep it a next step |
| F3a | Most modern stores have ceiling cameras: extend beyond autonomous stores | **[BUILT]** Needs only a ceiling picture, area quads and product names; no store-specific hardware | `README.md`, `sensei/data.py` | **Not echoed** (slide 9 has bakery and flowers but not this) | Not tested outside one store |
| F3b | Same methods for bakery or flowers | **[PARTIAL]** Zero-shot by design: new catalogue names become prompts, so no retraining images | `sensei/products.py` | Slide 9 ("Beyond fruit and veg") | **[GAP]** No bakery or flower picture tried |

---

## 5. The added criterion: processing cost and resource efficiency

| ID | Item | Number | Evidence | In pitch now | Gap or risk |
|---|---|---|---|---|---|
| E1 | CPU per image, one core, all ~11 areas | **[MEASURED]** 5.6 to 7.1 s wall = 5.6 to 7.0 CPU-s; peak RAM 1.1 GB; model load ~6 s once; 16 threads: 1.4 s but 18.2 CPU-s | `outputs/benchmark/cost_1t.json` (3 images, 31 areas), `cost_16t.json` (14 images, 152 areas), `tools/benchmark_cost.py` | Slide 8 | The one-core run used only 3 pictures; repeat on all 14 before the final slide |
| E2 | Cost per image | **[DERIVED]** 7 CPU-s x $0.0892/h per 2 vCPU (AWS c7i.large, us-east-1) = ~$0.00009 (~$0.09 per 1,000) | `outputs/benchmark/llm_cost_compare.json` (8.67e-05) | Slide 8 title | Price is our assumption; on a PC the store already owns it is ~$0 |
| E3 | Per 14-camera section | **[DERIVED]** 14 x 12 pictures per hour x 14 h = 2,352 images a day = 4.6 CPU-h = ~$0.20/day, ~$6/month, a third of one core | `pitch.md` numbers table | Slide 8 | Cadence is our assumption |
| E4 | Versus asking a frontier model about every picture | **[DERIVED]** ~4,600 input + ~490 output tokens per picture: Sonnet 5.5 ~$0.0141 (~160x), Opus 5.5 ~$0.0282 (~325x), Haiku 5.5 ~$0.0007 (~8x, accuracy untested) | `tools/llm_cost_compare.py`, `outputs/benchmark/llm_cost_compare.json` | README only; **absent from slides, pitch.md, qa_prep** | It is a cost ratio, not an accuracy comparison; our key was itself labelled by such a model |
| E5 | Optional product boxes | **[MEASURED]** +15.5 CPU-s one core (~$0.0002) | README, `cost_16t.json` | Slide 8 tile 3 | Headline $0.00009 excludes the boxes that every app screenshot shows; say "~$0.0003 with boxes" once |
| E6 | Smaller and faster variants | **[BUILT]** CLIP B/32, bf16 and int8 options exist; experiment folders built, no result file | `experiments/cost/`, `sensei/config.py` (`int8_clip`, `int8_dino`, `bf16`) | Not in pitch | Final numbers "will replace" these; slide 8 and qa_prep must be refreshed together |
| E7 | Energy per image, model size on disk | **[GAP]** Not measured | n/a | n/a | Only if the jury asks about "resource" |

---

## 6. The brief's exact words worth echoing (short fragments, in order of the brief)

"Use" = already in the deck. Where unused, the suggested place is a pitch slide or the Q&A.

| Brief fragment (page) | Use now? | Suggested use |
|---|---|---|
| "Fresh eyes on fresh produce" (1) | Yes, slide 1 tag | Keep; close on it |
| "the most demanding section of a store for computer vision" (1) | No | Open: "You gave us the hardest section" (flatters them, sets the bar) |
| "sold loose, with no barcode or packaging" / "piled rather than aligned" (1) | No | Slide 3: why we measure fill, not counts |
| "change shape, size and color as they ripen" (1) | No | Slide 4: why base-fruit level |
| "constantly hidden by the hands of shoppers and staff" (1) | No | Slide 4 or Q&A: the visibility mask |
| "perishable" (1) | Yes, slide 2 title | Keep |
| "Empty gondola", "Overstocked gondola", "Wrong product in the wrong place" (1) | Yes, slide 2 | Keep their three chains verbatim |
| "staff walking the store" (1) | Yes, slide 2 | Keep |
| "counting bananas in a pile is a challenge even for a person" (1) | No | Slide 5: our own labellers split on "half" (84% agreement) |
| "nobody can label every image, every day" (1) | Partly (slide 2) | Slide 5 lead-in |
| "learn to see the shelf without being told what is right" (1) | Yes, slide 2 | Say it again on slide 4 |
| "a store that knows its own shelves" (1) | Yes, slide 9 title | Move to the close |
| "continuously and without human help" (1) | No | Slide 8: "picture in, checked file out" |
| "the largest autonomous store in the world, powered by Sensei" (1) | **No** | Slide 1 or 3: credit the store and the data ("Continente Bom Dia, S. Romão, Leiria") |
| "recognised generically" (2) | No | Slide 4: base-fruit level was their design, not our shortcut |
| "counted per area and then added up per product" (2) | No (we do it) | Slide 7 |
| "an item count or a fill level" (3) | No | Slide 4: "you allowed a fill level; we chose it" |
| "what to restock first, what to move back, what to leave alone" (4) | Partly | Slide 6: name all three; show the "Leave alone" line |
| "False alarm", "Missed problem", "Repeated errors" (4) | No | Slide 6 or 5: our false-alarm and miss numbers (C3, C4) |
| "stop trusting the app" (4) | No | Slide 6: confidence chip, "estimate", "check by eye" |
| "information staff can act on" (4) | No | Slide 4 step 4: "your scoring is our objective" |
| "how clearly and quickly" (4) | No | Demo: 10-second shift start |
| "staff get no warning" (5) | No | Slide 8: "every area answered, always" |
| "a fleet of autonomous stores" / "switched on in a new store" (5) | **No** | Slide 8 or 10: day-0 recipe: frames + planogram, no labels |
| "no extra hardware and no labelling effort" (5) | We say "no new hardware" | Use their wording exactly |
| "watch every gondola, all day long" (5) | No | Slide 7 |
| "before the gondola runs empty" (5) | No | Slide 7 "Running out soon" |
| "without manual audits" (5) | No | Slide 7 adherence |
| "hour by hour and store by store" (6) | Partly (slide 9) | Slide 7: be honest, one store |
| "most modern stores already have ceiling cameras" / "extend well beyond autonomous stores" (6) | **No** | Slide 9: their market is bigger than their own stores |
| "bakery or flowers" (6) | Yes, slide 9 | Keep |

Sponsor-flattering and true (all evidenced above): their existing 720p ceiling cameras and their `planogram.json`
were enough; their scoring rule is a sound objective (we turned it into our decision rule); their store's
planogram drifts in a measurable way (12% of areas to 2% over the day), which is the reason a camera beats a walk.

---

## 7. Gaps, ranked by pitch value, with the cheapest honest closure

| Rank | Gap | Closure | Effort |
|---|---|---|---|
| 1 | "No labels" vs "360 to 400": the label-free core alone is 0.93 to 0.97 per area on late frames (about 268 to 280 points, under the brief's 320) | Show two rows: label-free floor and calibrated result; describe calibration as a one-off AI-labelling step (~$2 to $8 per store-day, **[DERIVED]**), not as zero effort | Wording only, plus time one `sensei fit` |
| 2 | No second store | Say "one store, 14 cameras; leave-one-camera-out is our new-camera test"; ask Sensei for a second store | Wording |
| 3 | Wrong-product recall is 36% on unseen cameras (80 to 100% on late frames) | Quote precision and recall together; lead with late-frame recall | Wording, or look at why unseen cameras miss |
| 4 | "Sure" confidence never calibrated | Bucket the out-of-fold predictions by confidence and check accuracy per bucket | About an hour |
| 5 | Counts never checked | Hand-count 20 to 30 areas, report mean error | About an hour |
| 6 | Sales speed and forecast unvalidated against real sales | Offer to calibrate on Sensei's till or restock logs; show the 33% vs 4% backtest as the early signal | Wording, or backtest at finer cadence |
| 7 | Waste: only a slow-mover proxy | Rename the claim "slow movers to inspect"; keep "waste tracking" under next steps | Wording |
| 8 | Layout effects: nothing | Keep as a next step; mention the multi-area natural experiment | Wording |
| 9 | No staff trial | Even three people doing the 10-second task and a timing | About an hour |
| 10 | Integration into Sensei's systems | Say the output is their own JSON format and a static page; "only re-analyse changed areas" is next | Wording |
| 11 | Energy per image, disk size | Only if asked | Optional |

---

## 8. Number and claim hygiene (fix before the final slides)

1. **Evidence file for 1.25.** `pitch.md` cites `models/real_v1_cal/calibration_cv.json`, but that file says **1.20** on all 1,240 areas
   (unseen cameras). 1.25 reproduces only on the original 756-area part with heads trained on the other cameras and
   scored on those 756: `pitch/research/evidence/unseen_camera_756.py` gives 1.2526. 1.30 (304 areas) and 1.395 (152 areas) reproduce;
   1.395 is in `staff_terms.json`. Save the 756-part result into a model-folder file, or quote 1.20 on all 1,240.
2. **"3 votes per area, 94% unanimous" (slide 5)** is true of the first 393 areas only (3 cameras). The other 847 areas of the
   headline key have one vote. The new key `data/labels/teacher_labels_v2.json` (1,962 areas, all 181 frames, 108 wrong-product areas, 3 votes everywhere)
   has 85.7% unanimous on level over its 1,569 new areas (about 87% overall). Update when the final numbers arrive.
3. **"72 of 1,240 areas show the wrong product" (slide 3)** is 72 area-frame cases from 23 distinct areas (15% of the 152).
   Safer: "1 area in 8 holds the wrong product in the first pictures of the day, about 1 in 60 by evening" (18/152 at 06h, 2/129 at 19h, key v2; **[NEW]**).
4. **"The planogram is broken at opening" (slide 3).** First frame is 06:12 to 06:14; the store's opening time is not in the data. Reframe as what the camera finds
   in the early pictures, not as a failing of the store.
5. **"Hidden frames are later in the day than every labelled one"** is inferred from one example file name in the brief (`1751052241.jpg` = about 20:24 Lisbon;
   our last frame is about 19:44). If it is wrong the late-frame rows do not apply; the unseen-camera 1.19 to 1.25 range (about 343 to 362 points) is the safer floor.
6. **"No false alarms" (slide 4)** holds for wrong-product alerts (1 in 1,168, 0, 0), not for restock tasks (10% late frames, 26% unseen cameras).
7. **Cost headline excludes the boxes** that the screenshots show; the one-core benchmark used 3 pictures; the cost-reduction experiments (B/32, bf16, int8) may change every cost number.
8. **"Gondola" in the app is one camera view**, not a module.
9. **Pitch files are older than the README** (`pitch.md`, `slides.html`, `qa_prep.md` were last saved around 00:08; the README, including the LLM cost comparison, at 00:51).
10. **Product name.** Slide 1 calls ours "Sensei shelf monitor". The app itself is titled "Shelf check". Decide whether using the sponsor's name as our product name helps or reads as presumptuous.

---

## 9. What the pitch currently echoes and misses (keyword scan of `pitch.md`, `slides.html`, `qa_prep.md`, `demo_script.md`)

Zero mentions: Leiria, Continente, "largest", "autonomous", "fleet", "hundreds", "beyond autonomous stores", "leave alone" on the Do-now slide.
One mention only: "thousands" (slide 2), "trust" (qa_prep and README, never on a slide), "hour by hour" (slide 9), "waste" (slides 2 and 9).
Strongest unused moves: credit the store by name; tell the day-0 switch-on recipe in their words; show false-alarm and miss numbers under their own three headings (page 4);
put the 160x frontier-model comparison and the fleet arithmetic next to the per-image cost.

---

## 10. Evidence index

| What | File |
|---|---|
| Held-out scores, unseen cameras and late frames, label-free vs heads | `models/real_v1_cal/calibration_cv.json` |
| Same folds with confusion matrices, and 1.395 (last frame) and 1.2526 (756 part) | `pitch/research/evidence/staff_terms.py`, `staff_terms.json`, `unseen_camera_756.py`, `results.txt` |
| Wrong-product persistence and time of day | `pitch/research/evidence/wrong_product_persistence.py`, `results.txt` |
| Forecast backtest | `pitch/research/evidence/forecast_backtest.py`, `results.txt` |
| Answer keys, votes, Gemini cross-check | `data/labels/teacher_labels.json`, `teacher_labels_mid.json`, `teacher_labels_v2.json`, `votes_round1.json`, `votes_v2.json`, `gemini_labels.json` |
| Cost | `outputs/benchmark/cost_1t.json`, `cost_16t.json`, `llm_cost_compare.json`, `tools/benchmark_cost.py`, `tools/llm_cost_compare.py`, `experiments/cost/` |
| Staff app and Insights logic | `ui/app.js`, `ui/index.html`, `sensei/dashboard.py`, `sensei/temporal.py`, `outputs/real_v1_cal/dashboard/` |
| Screenshots (store pictures, keep private) | `pitch/assets/dash_*.png`, `dash_*_web.jpg` |
| Submission flow | `SUBMIT.bat`, `sensei/submit.py`, `tests/test_submit.py`, `outputs/dryrun_submit/` |
| Dataset facts | `data/raw/planogram.json` (14 cameras, 152 areas, 94 products, 181 pictures, 1280x720), `SPEC.md` section 2b |

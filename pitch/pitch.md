# Fresh.: 3-minute pitch

Deck: `pitch/slides.html` (arrow keys, F for fullscreen, 1-9 jump, 0 = the close). Ten main slides, then five
appendix slides (A1-A5) for Q&A only. Single-file copy for another laptop: `pitch/slides_standalone.html`
(rebuild with `.venv/Scripts/python pitch/build_standalone.py`). Team: NovaLotus (Sérgio Kuts Pires, Inês Matias
Medeiros), see `pitch/team.md`.

**Timing.** The spoken text below is **390 words** including the optional lines, **367 words** without
them. At a calm 140 words a minute that is about 2:47 with them and 2:37 without them. Hard stop 3:00. Say
the lines marked *(optional)* only if the stopwatch rehearsal comes in under 2:40. Slide changes and the Portuguese
words cost a few seconds each, so rehearse with a stopwatch, twice.

**Speakers.** Inês: cold open, what it is, staff app, manager and freshness, the close. Sérgio: how it works,
results, trust, cost, the ask. The hand-over is at slide 5 ("How, without labels?") and back at slide 10.

**Memorable line** (said at 0:15 and again as the last sentence): *The plan says where things go. The camera sees
what is there.*

**Rules.** Every number below is in the "Numbers you may say" table at the end, with its source. Do not say any
other number. Never say "we beat 320": 320 is a worked scoring example in the brief, not a benchmark. Never say "zero
effort" or "no labels" about the calibrated score: day 0 needs no labels at all; day 1 uses an answer key made by AI
models (automated, no human labelling).

---

## 1. 06:14 (Inês, 0:00 - 0:15)

**Inês:** Six fourteen in the morning. Leiria, camera 6215, the first picture of the day. Four banana trays are
empty. Two banana crates hold oranges. The plan says where things go. The camera sees what is there.

## 2. Fresh. (Inês, 0:15 - 0:30)

**Inês:** Your brief calls produce the most demanding section of a store for computer vision. We are NovaLotus,
and this is Fresh. It reads the produce shelf from the cameras Sensei already has, on one CPU core.

## 3. For staff (Inês, 0:30 - 0:55)

**Inês:** You asked three questions: what to restock first, what to move back, what to leave alone. The staff app
answers in Portuguese. Repor: it is empty. Trocar: oranges should be here, but it holds bananas. Deixar: these areas
are right. Wrong products and empty shelves come first. When it is unsure, it says so: confirmar à vista.

## 4. For the manager (Inês, 0:55 - 1:10)

**Inês:** The same pictures warn the manager before a shelf runs empty, and turn time on display into freshness
checks. *(optional: In a one-day backtest, flagged areas emptied eight times as often as the rest.)*

## 5. How it works (Sérgio, 1:10 - 1:30)

**Sérgio:** How, without labels? Empty trays look the same under every product. So it learns what empty looks like
from the store's own pictures, and names the fruit from your catalogue. Then your scoring rule decides: too full costs
most, so when unsure, it answers lower.

## 6. Results (Sérgio, 1:30 - 1:55)

**Sérgio:** Day zero, with no labels at all, it already beats the always-full guess. Day one, we add an answer key
made by AI models, with no human labelling. Late in the day, on pictures held out from calibration, it scores 1.4 points out of 2.
Our estimate for the hidden set is 355 to 430 of 578: an estimate, not a promise.

## 7. Can staff trust it? (Sérgio, 1:55 - 2:12)

**Sérgio:** It catches 99 percent of empty shelves, with two false wrong-product alarms in over eighteen hundred correct areas. Our
honest limit: on a brand-new camera, it finds only one wrong product in four, until it is calibrated.

## 8. Cost (Sérgio, 2:12 - 2:27)

**Sérgio:** Cost: about five cents per thousand images, on one CPU core, no GPU. A fourteen-camera produce section
costs about three dollars a month. *(optional: Switching on a new store costs about a cent.)*

## 9. Our ask (Sérgio, 2:27 - 2:45)

**Sérgio:** Our ask: a four-week shadow pilot. One silent week at Leiria against your restock logs, then a second
store. We need a frame feed and one contact. You get a weekly accuracy report.

## 10. Obrigado (Inês, 2:45 - 2:55)

**Inês:** At six fourteen, the plan and the shelf disagreed. The plan says where things go. The camera sees what is there. Obrigado.

---

## If something goes wrong on stage

- Running long by slide 6: drop "an estimate, not a promise" and point at the caveat on the slide.
- Running long by slide 8: say only the first sentence.
- Never cut the ask (slide 9) or the honest limit (slide 7).
- Asked to show the app: use the short demo in `demo_script.md` after slide 10, never in the middle.
- Asked about 320: "That is the worked scoring example in your brief, not a benchmark. Our number is an estimate on
  an AI-made key, and the upper end assumes late-day pictures" (appendix A5).
- Asked "is 300 times fair?": a cost ratio at list price for the same pictures with our labelling prompt, not an
  accuracy comparison; at batch prices about 150 times (appendix A3, Q&A 5).
- Slide 9's area events and the pilot are a design. Never say the connector, the scale loop or a closing-time mode
  are built: they are not.

## Numbers you may say

Sources are files in the project; "evidence" = `pitch/research/evidence/`. Key = `data/labels/teacher_labels_v2.json`
(1,962 areas, all 181 frames) unless stated. Held-out protocol (same for every row): heads are refitted without the test
camera or frames; folds are "one camera held out" (all 14), "last two pictures of every camera" (304 areas) and "last
picture of every camera" (152 areas). Status: **OK** = re-checked against the file named; **DERIVED** = our arithmetic
on measured inputs (shown in the row).

| Claim | Number | Status | Where it comes from |
|---|---|---|---|
| Whole day, one camera held out, calibrated (`models/real_v3_cal`) | **1.23** points per area (max 2), 1,962 areas (1.2329) | OK | `evidence/final_numbers_real_v3_cal.json` `camera.heads`; same value in `experiments/final_integration/heldout_v1cal_v3cal_v1mem_v3nomem.json` (entry v3cal on key v2). The previous model `real_v1_cal` scored 1.18 on the same protocol |
| Label-free core (day 0), whole day | **1.18** (1.1825) | OK | `final_numbers_real_v3_cal.json` `camera.unsup` = method `baseline` in `models/real_v3_cal/calibration_cv.json` (the label-free core of the submitted model, the `real_v2` fit). Fitted without labels on the unlabelled pictures of all 14 cameras, so never say "on cameras it never saw". Its default thresholds were tuned once on this store's key: a second store is the real test. The documented fallback `models/real_v1` scores 1.21 / 1.01 / 0.98 on the same folds (audit re-run, 11 Oct) |
| Last two pictures of each camera (304 areas): calibrated / label-free / baseline | **1.41** (1.4112) / **0.99** (0.9901) / 0.46 | OK | `final_numbers_real_v3_cal.json` `time2` |
| Last picture of each camera (152 areas): calibrated / label-free / baseline | **1.48** (1.4803) / **0.88** (0.8816) / 0.18 | OK | `final_numbers_real_v3_cal.json` `time1` |
| Baseline, always "compliant" + "full", whole day | 0.76 (0.7569) | OK | `final_numbers_real_v3_cal.json` `camera.always_compliant_full` |
| Older 756-area key (kept as a second test) | 1.17 / 1.35 / 1.43 for camera / last two / last picture (`real_v1_cal`: 1.25 / 1.30 / 1.39). Q&A only | OK | `heldout_...json` entries v3cal and v1cal on key 756. The camera row loses there because three cameras with 12-13 labelled frames dominate it |
| Hidden set | 289 areas, max 578, brief example 320 | fixed | the brief |
| Projection | say **"355 to 430 of 578, an estimate"** (slide 6). Late rows: about **410 to 430** (1.41 to 1.48 x 289 = 408 to 428) if the hidden pictures are late in the day; about **355** (1.23 x 289 = 356) if they span the day. On the older 756-area key the late rows give about 390 to 410 | DERIVED | assumes the hidden pictures are late (the brief's example file name, 1751052241 = 20:24 Lisbon, is later than any picture we have: the latest is 20:16 and the last pictures of the 14 cameras run from 18:07 to 20:16). An estimate on an AI-labelled key, not the store's truth. Day 0, no labels: 0.88 to 0.99 x 289 = about **255 to 285**. Per camera, late two-picture scores run 0.50 to 2.00 (`calibration_cv.json` `schemes.time.per_camera`). Never present 320 as a bar we beat: it is the brief's worked scoring example |
| Answer key | AI labellers only, no human labelling; 1,962 areas, 181 frames, 14 cameras; 3 votes per area (2 on 36 areas of camera 6373, six of them split); on the 11 newly voted cameras (1,569 areas) 84% unanimous (84.45%), 34 disputes adjudicated; cameras 6215, 6371, 6373 (393 areas) come from the earlier round (stock level agreed on 93.6%, including the 36 two-vote areas); 117 areas show a wrong product | OK | `data/labels/votes_v2.json`, `disputes_v2.json`, `adjudications_v2.json`, `teacher_labels_v2.json`, `tools/aggregate_votes.py`; `data/labels/votes_round1.json` for the 393 (357 with three votes, 36 with two) |
| Labeller agreement by stock level (Q&A 11) | three votes agreed on the stock level for **57%** of the areas the key calls half (154 of 268), against 88% for empty (130 of 147) and 92% for full (1,061 of 1,154); the 11 newly voted cameras, 1,569 areas | OK | computed from `data/labels/votes_v2.json` and `teacher_labels_v2.json` on 11 Oct |
| Areas holding another product than planned | about **1 in 8** at 06h (18 of 152), **1 in 65** at 19h (2 of 129); 23 distinct areas ever wrong | OK | `evidence/wrong_product_persistence.py` (v2 line), re-run on the final key |
| Empty shelves on the to-do list | **99%** (181 of 182) one camera held out; **98%** (39 of 40) last two pictures; 24 of 24 last picture | OK | `final_numbers_real_v3_cal.json` `staff` blocks |
| Empty shown as full | 1 of 182 (camera held out), 1 of 40 (last two), 0 of 24 (last) | OK | same |
| Wrong-product false alarms | 2 in 1,845 correct areas (camera held out), 0 in 296 (last two), 0 in 148 (last) | OK | same, `wrong_product` blocks |
| Wrong products found | 31 of 117, "about a quarter" (camera held out: the weak spot); 6 of 8 (last two); 4 of 4 (last). The late folds hold only 8 and 4 wrong-product areas, and about half of the late finds come from remembering an earlier labelled wrong product (label-free finds 4 of 8 and 2 of 4); 31 of 117 is the recognition figure | OK | same |
| Restock tasks on a shelf the key calls full | about **1 in 4** (148 of 539) camera held out; about **1 in 10** (9 of 91) last two; 6 of 60 last picture | OK | same, `restock_tasks_on_full_shelf` |
| Half shelves shown as full | about **4 in 10**: 130 of 340 (camera held out), 28 of 71 (last two), 12 of 42 (last) | OK | same |
| Stock errors, last two pictures, calibrated | 35 answers too high, 11 too low (so "we lean low" describes the rule, not the outcome) | OK | `heldout_...json` entry v3cal on key v2, `time2.stock_cases` |
| Staff app, evening pictures of the dataset day | 24 Vazio, 41 Baixo, 1 Produto errado, 86 OK (152 areas, 14 cameras, 18:07 to 20:16); header **"Fazer agora · 66 tarefas"** = Primeiro 25 (wrong product and empty) + Depois 41 (low); the 13 freshness checks ("Quando houver tempo: verificar frescura") are extras, not counted; "Deixar: 86 zonas estão certas". Camera 6215 alone: 7 tarefas, "Deixar: 3 zonas estão certas". Verbs on the cards: **Repor**, **Trocar**, "Reforçar em breve"; confidence **Alta / Média / Baixa: confirmar à vista** | OK (read off the page) | `outputs/rehearsal_0850/dashboard` (11 Oct, 08:48 build); screenshots `assets/pt_mobile.jpg`, `pt_card_restock.jpg`, `pt_card_move.jpg`, `pt_insights.jpg` retaken from it on 11 Oct |
| Cost per image | **3.8 CPU-seconds** (3.765, median of three back-to-back runs: 3.661 / 3.765 / 3.837) on 1 core, 3.63 s wall, 1.24 GB peak RAM, no GPU; 14 frames, 152 areas, bf16, model load excluded (about 5 s once). x $0.045 per vCPU-hour = **$0.0000467 = $0.00005** (about 5 cents per 1,000). An earlier single run gave 3.59, two others about 4.5 (not saved; `cost_1t_real_v3_cal_detect.json` holds 4.53 for its predict part): at 4.5 CPU-s the cost is still about $0.00006. Measured on an AMD Ryzen AI 7 350 laptop with native bf16 (without bf16: about 1.6x more); priced at a cloud vCPU, which may be slower. `real_v2` 3.43 | OK | `tools/benchmark_cost.py`, `outputs/benchmark/cost_1t_real_v3_cal_b2b_run{1,2,3}.json` (`cost_1t_real_v3_cal.json` = the median run); AWS c7i.large on-demand $0.0892/h for 2 vCPU (us-east-1). Replaces the first draft's ~7 CPU-s and $0.00009 (fp32, 3 pictures) |
| Per section | 14 cameras x 1 picture / 5 min x 14 h = 2,352 images a day = 2.46 CPU-hours = ~$0.11 a day; 70,560 images a month = **$3** (3.29); 14 / 300 s x 3.765 CPU-s = 0.18 cores, "a sixth of a core" | DERIVED | arithmetic on the line above |
| Per camera, per month | 5,040 images x $0.0000467 = **$0.24**; Claude Sonnet 5.5 $71 | DERIVED | same cadence, 30 days |
| 1,000 cameras, per month | **~$235** ours; ~$71,000 Claude Sonnet 5.5; a 14-camera section on Sonnet ~$1,000 | DERIVED | `llm_cost_compare.json` x cadence. If asked about all of Leiria: about 1,700 cameras, as trade press reported at launch (Retail-Optimiser, Jan 2025; not a Sensei figure), would be about $395 a month, an upper bound since most cameras do not look at produce |
| Switch-on, new store | one day of pictures (181 frames) x 3.765 CPU-s = 681 CPU-s of feature extraction, plus a fit that took 11.5 s wall-clock (cached features) = about **12 CPU-minutes**, $0.009, "about a cent"; no labels (audit re-measured a cold fit at 720 CPU-s) | DERIVED | `models/real_v3_cal/model.json` (181 images, fit 11.5 s) x the cost line |
| Optional AI calibration | about **$2.5 to $7.7** per store-day: 181 frames x 1 to 3 Claude Sonnet 5.5 votes x $0.0141 (2.55 to 7.66); say "our estimate" | DERIVED | `llm_cost_compare.json` |
| Frontier-model comparison | Claude Sonnet 5.5 ~$0.0141 per image (**~300x**, 302), Opus 5.5 ~$0.0282 (~600x, 605), Haiku 5.5 ~$0.0007 (~15x, 15.1); accuracy untested | OK | `tools/llm_cost_compare.py`: 4,610 input + 488 output tokens, API list price; a cost ratio, not an accuracy comparison. **Replaces the earlier ~160x / ~325x / ~8x**, which were against the 7 CPU-s fp32 figure. bf16 cut CPU time by about a third (5.2 -> 3.4 CPU-s, `real_v1_cal` vs `real_v2`, same heads); the per-area memory adds back about 0.3 (3.4 -> 3.8). Output tokens (488) are our estimate (45 per area), not measured; at Batch API prices the ratio is about 150x |
| "Running out soon" backtest (Q&A 17) | of 25 flags, 8 (32%) emptied within about 2 h, against 4% (58 of 1,550) for a not-yet-empty area; it catches 8 of the 58 that emptied | OK | `evidence/forecast_backtest_real_v3_cal.py` run on the final key (hourly pictures) |
| Optional boxes | +15.7 CPU-seconds per image (~$0.0002), peak RAM 1.76 GB | OK | `outputs/benchmark/cost_1t_real_v3_cal_detect.json` |
| Speed | about 25 s to predict the 14 frames (152 areas) on the laptop CPU (16 threads), including model load; about 90 s with the staff app and OWLv2 boxes. Not on the slides | OK (file times only, no saved log) | integration run, `outputs/dryrun_final_zip` (`SUBMIT.bat` on a zip of `data/val_sim`; format check PASSED) |
| Skipping unchanged areas (tested) | at 1-hour spacing, skipping **3.8%** of areas misses 1 of 281 label changes; skipping **11.9%** misses 5 of 281 (1.8%); net saving **3.6% to 11.7%** of the compute; the gate costs 0.29 ms per area (0.6 with JPEG decode), under 0.2% of the model. **No 5-minute figure: not measured.** Not wired into the pipeline | OK | `tools/change_gate.py`, `outputs/benchmark/change_gate.json` (threshold picked on the other 13 cameras). Slide 10 footer and Q&A 6 |

Pilot pass criteria on slide 9 (at least 95% of empty shelves caught, at most 1 wasted restock walk in 10) are targets we
propose, not results. Say "we propose". The calibrated store already measures about 1 in 10 on our AI key (9 of 91), so the
pilot checks it against Sensei's restock logs, not a new bar.

Market and sponsor lines (say the scope with the number):

| Line | Scope | Source |
|---|---|---|
| MC has publicly committed to halve food waste by 2028 against 2020 | all food waste, not produce only; company commitment (Feb 2025), we found no published progress figure. Q&A only | `market_facts.md` W8 (Agroportal 2025-02-20) |
| About 45% of food discarded by Austria's large retailers was fruit and veg | Austria, Q4 2023, mandatory retailer reporting; share among retailers that assigned product groups. Q&A only | `market_facts.md` P1 |
| About 1 in 4 empty-shelf events: stock in the store, not on the shelf (Q&A only, say "the share staff can fix at once") | 2002 study, packaged goods, not fresh | `research/market_facts.md` O3 |
| Leiria: opened 10 January 2025, 1,200 m²; built to show loose produce can sell autonomously, by weight (Sensei's framing: say "Sensei case study") | date and size verified | `research/sensei_facts.md` section 4 |
| Verona: fruit, veg and bread by weight; scales linked to the store system | Sensei case study (by weight); Forbes PT 2023-11-09 (scales linked to the store system) | `sensei_facts.md` section 5 |
| Planogram compliance and replenishment alerts at Leiria | say "Sensei reports" | `sensei_facts.md` section 6 |
| RTIH AI and Physical Stores 2026; EHI reta AI category 2026 (Sonae with Sensei) | verified | `sensei_facts.md` section 3 |

Insights and counts on the dry-run pictures are model estimates from one day, shown on screen as such: do not quote
their figures as findings. A count reads "about N visible units", and for bunches such as bananas a unit is a bunch.

Do not say any other number out loud. If asked something we have not measured, say so.

# Fresh Eyes: 3-minute pitch

Deck: `pitch/slides.html` (arrow keys to move, F for fullscreen, number keys 1-9 jump, 0 = last slide; P highlights
elements marked provisional, none are left). One block per slide, 12 slides. The plan behind it is `pitch/sensei_brief.md`.
Team: QuantumLotus (Sérgio Kuts Pires, Inês Matias Medeiros), see `pitch/team.md`.

Timing: the spoken text below is about 450 words, about 2:55 at 155 words a minute. The sentences marked
*(cut if short)* add about 20 words; say them only if rehearsal comes in under 2:45. If rehearsal runs long, cut the
sentences marked *(cut first)*. Hard stop: 3:00.

**All numbers are final** (2026-10-11): answer key `teacher_labels_v2.json` (1,962 areas, all 181 frames), submission
model `models/real_v3_cal`, cost measured on 14 frames at one core. They replace the provisional ones of the first
Sensei-centred draft. The table at the end says where each number comes
from; if a number is not in that table, do not say it.

---

## 1. Fresh Eyes (0:00 - 0:06)

Good afternoon. We are QuantumLotus, and this is Fresh Eyes: a produce-shelf layer for the Sensei platform.

## 2. What Sensei has built (0:06 - 0:23)

In January 2025, Sensei and MC opened Continente Bom Dia in Leiria: the store your brief calls the largest autonomous
store in the world, selling loose produce by weight. Your brief asks the next question: can the same cameras read the
produce shelf?

## 3. The real problem (0:23 - 0:33)

Across a fleet, three things decide it. It must learn without labels. Cost per camera must be close to zero. And
staff must keep trusting it. *(cut if short: And produce is where waste lives: MC has publicly committed to halve food
waste by 2028.)*

## 4. What a shift sees (0:33 - 0:49)

In Portuguese, the app answers your brief: repor, restock first; devolver ao lugar, move back;
deixar, leave alone. Wrong products and empty shelves come first, low shelves are the next round. And when it is
unsure, it says so: confirmar à vista.

## 5. What the camera sees (0:49 - 1:04)

Camera 6215, first picture of the day: banana trays empty, oranges where bananas are planned. In the first pictures,
one area in eight differs from the plan; by evening, one in sixty-five. The morning set-up, checked by the
camera.

## 6. How it works (1:04 - 1:18)

With no labels, we use what never changes: trays look the same under every product. DINOv2 splits each area into
surface and product; CLIP names the fruit from your catalogue. Your scoring rule is our decision rule.

## 7. Measured honestly (1:18 - 1:36)

Day zero, no labels: the core fits itself to the store's own pictures: **1.18** points per area. Day one, AI
labellers calibrate it; no person labels anything. Late in the day: **1.41 to 1.48**, about **410 to 430 of 578**,
against your example of 320.

## 8. Can staff trust it? (1:36 - 1:52)

Under your three headings: **98 to 99%** of empty shelves reach the list; wrong-product false alarms are rare,
**2 in 1,845** on a brand-new camera. The weak spot is on the slide: that camera finds only a quarter of wrong
products.

## 9. For the manager (1:52 - 2:03)

The same pictures give the manager shelves running out soon, sales speed by hour, planogram adherence, and slow
movers to check for freshness. All marked as estimates.

## 10. Cost per image (2:03 - 2:22)

Cost per image: **$0.00005**, about **3.8 CPU-seconds** on one core, no GPU: **300 times** cheaper than asking
Claude Sonnet 5.5 about every picture. A produce section needs a sixth of a core, **$3 a month**. No labelling bill
as the fleet grows: a new store switches on for about **a cent**.

## 11. A module for Sensei (2:22 - 2:46)

It plugs in: frames and planogram from your data API, one CPU container on servers you run, and events into
the replenishment alerts staff already get. And your store already weighs every kilo it sells. That is free
supervision: to calibrate each store, check sales speed and flag waste. *(cut first: the second half of that
sentence, after "free supervision".)* Our ask: a four-week shadow pilot, at Leiria and a second store.

## 12. Obrigado (2:46 - 2:54)

Same cameras, no labels, four cents per thousand images, and staff know what to do first. Fresh eyes on fresh
produce. Obrigado.

---

## If something goes wrong on stage

- Running long at slide 7: drop "against your example of 320" and point at the scale instead.
- Running long at slide 10: say only the first sentence and "a sixth of a core"; the table speaks for the rest.
- Asked to show the app: use the 40-second short demo in `demo_script.md` after slide 12, never in the middle.
- Slide 11 says "integration design" and "pilot design" on screen. Never say the connector, the scale loop or the
  closing-time mode are built: they are not.
- Asked "is 300 times a fair comparison?": it is a cost ratio on list prices for the same two pictures, not an accuracy
  comparison (Q&A 5).

## Numbers you may say

Sources are files in the project; "evidence" = `pitch/research/evidence/`. Key = `data/labels/teacher_labels_v2.json`
(1,962 areas, all 181 frames) unless stated. Held-out protocol (same for every row): heads are refitted without the test
camera or frames; folds are "one camera held out" (all 14), "last two pictures of every camera" (304 areas) and "last
picture of every camera" (152 areas). Status: **OK** = re-checked against the file named; **DERIVED** = our arithmetic
on measured inputs (shown in the row).

| Claim | Number | Status | Where it comes from |
|---|---|---|---|
| Whole day, one camera held out, calibrated (`models/real_v3_cal`) | **1.23** points per area (max 2), 1,962 areas (1.2329) | OK | `evidence/final_numbers_real_v3_cal.json` `camera.heads`; same value in `experiments/final_integration/heldout_v1cal_v3cal_v1mem_v3nomem.json` (entry v3cal on key v2). The previous model `real_v1_cal` scored 1.18 on the same protocol |
| Label-free core (day 0), whole day | **1.18** (1.1825) | OK | `final_numbers_real_v3_cal.json` `camera.unsup`. Fitted without labels on the unlabelled pictures of all 14 cameras, so never say "on cameras it never saw" |
| Last two pictures of each camera (304 areas): calibrated / label-free / baseline | **1.41** (1.4112) / **0.99** (0.9901) / 0.46 | OK | `final_numbers_real_v3_cal.json` `time2` |
| Last picture of each camera (152 areas): calibrated / label-free / baseline | **1.48** (1.4803) / **0.88** (0.8816) / 0.18 | OK | `final_numbers_real_v3_cal.json` `time1` |
| Baseline, always "compliant" + "full", whole day | 0.76 (0.7569) | OK | `final_numbers_real_v3_cal.json` `camera.always_compliant_full` |
| Older 756-area key (kept as a second test) | 1.17 / 1.35 / 1.43 for camera / last two / last picture (`real_v1_cal`: 1.25 / 1.30 / 1.39). Q&A only | OK | `heldout_...json` entries v3cal and v1cal on key 756. The camera row loses there because three cameras with 12-13 labelled frames dominate it |
| Hidden set | 289 areas, max 578, brief example 320 | fixed | the brief |
| Projection | about **410 to 430** (1.41 to 1.48 x 289 = 408 to 428) if the hidden pictures are late in the day; about **355** (1.23 x 289 = 356) if they span the day. On the older 756-area key the late rows give about 390 to 410 | DERIVED | assumes the hidden pictures are late (the brief's example file name, 1751052241 = 20:24 Lisbon, is later than any picture we have: the latest is 20:16 and the last pictures of the 14 cameras run from 18:07 to 20:16). An estimate on an AI-labelled key, not the store's truth |
| Answer key | AI labellers only, no human labelling; 1,962 areas, 181 frames, 14 cameras; 3 votes per area (2 on 36 areas of camera 6373, six of them split); on the 11 newly voted cameras (1,569 areas) 84% unanimous (84.45%), 34 disputes adjudicated; cameras 6215, 6371, 6373 (393 areas) come from the earlier round (stock level agreed on 93.6%, including the 36 two-vote areas); 117 areas show a wrong product | OK | `data/labels/votes_v2.json`, `disputes_v2.json`, `adjudications_v2.json`, `teacher_labels_v2.json`, `tools/aggregate_votes.py`; `data/labels/votes_round1.json` for the 393 (357 with three votes, 36 with two) |
| Labeller agreement by stock level (Q&A 11) | three votes agreed on the stock level for **58%** of the areas the key calls half (154 of 268), against 88% for empty (130 of 147) and 92% for full (1,061 of 1,154); the 11 newly voted cameras, 1,569 areas | OK | computed from `data/labels/votes_v2.json` and `teacher_labels_v2.json` on 11 Oct |
| Areas holding another product than planned | about **1 in 8** at 06h (18 of 152), **1 in 65** at 19h (2 of 129); 23 distinct areas ever wrong | OK | `evidence/wrong_product_persistence.py` (v2 line), re-run on the final key |
| Empty shelves on the to-do list | **99%** (181 of 182) one camera held out; **98%** (39 of 40) last two pictures; 24 of 24 last picture | OK | `final_numbers_real_v3_cal.json` `staff` blocks |
| Empty shown as full | 1 of 182 (camera held out), 1 of 40 (last two), 0 of 24 (last) | OK | same |
| Wrong-product false alarms | 2 in 1,845 correct areas (camera held out), 0 in 296 (last two), 0 in 148 (last) | OK | same, `wrong_product` blocks |
| Wrong products found | 31 of 117, "about a quarter" (camera held out: the weak spot); 6 of 8 (last two); 4 of 4 (last). The late folds hold only 8 and 4 wrong-product areas | OK | same |
| Restock tasks on a shelf the key calls full | about **1 in 4** (148 of 539) camera held out; about **1 in 10** (9 of 91) last two; 6 of 60 last picture | OK | same, `restock_tasks_on_full_shelf` |
| Half shelves shown as full | about **4 in 10**: 130 of 340 (camera held out), 28 of 71 (last two), 12 of 42 (last) | OK | same |
| Stock errors, last two pictures, calibrated | 35 answers too high, 11 too low (so "we lean low" describes the rule, not the outcome) | OK | `heldout_...json` entry v3cal on key v2, `time2.stock_cases` |
| Staff app, evening pictures of the dataset day | 24 Vazio, 41 Baixo, 1 Produto errado, 86 OK (152 areas, 14 cameras, 18:07 to 20:16); 79 tasks = Primeiro 25 (wrong product and empty) + Depois 41 (low) + 13 freshness checks | OK (read off the page) | `outputs/real_v3_cal/dashboard` built 11 Oct; screenshots in `assets/pt_*.jpg` retaken from it |
| Cost per image | **3.8 CPU-seconds** (3.765, median of three back-to-back runs: 3.661 / 3.765 / 3.837) on 1 core, 3.63 s wall, 1.24 GB peak RAM, no GPU; 14 frames, 152 areas, bf16, model load excluded (about 5 s once). x $0.045 per vCPU-hour = **$0.0000467 = $0.00005** (about 5 cents per 1,000). An earlier single run gave 3.59, two others 4.5 (not saved); `real_v2` 3.4 to 3.6 | OK | `tools/benchmark_cost.py`, `outputs/benchmark/cost_1t_real_v3_cal_b2b_run{1,2,3}.json` (`cost_1t_real_v3_cal.json` = the median run); AWS c7i.large on-demand $0.0892/h for 2 vCPU (us-east-1). Replaces the first draft's ~7 CPU-s and $0.00009 (fp32, 3 pictures) |
| Per section | 14 cameras x 1 picture / 5 min x 14 h = 2,352 images a day = 2.46 CPU-hours = ~$0.11 a day; 70,560 images a month = **$3** (3.29); 14 / 300 s x 3.765 CPU-s = 0.18 cores, "a sixth of a core" | DERIVED | arithmetic on the line above |
| Per camera, per month | 5,040 images x $0.0000467 = **$0.24**; Claude Sonnet 5.5 $71 | DERIVED | same cadence, 30 days |
| 1,000 cameras, per month | **~$235** ours; ~$71,000 Claude Sonnet 5.5; a 14-camera section on Sonnet ~$1,000 | DERIVED | `llm_cost_compare.json` x cadence. If asked about all of Leiria: 1,676 cameras (Sensei's launch figure) would be about $395 a month, an upper bound since most cameras do not look at produce |
| Switch-on, new store | one day of pictures (181 frames) x 3.765 CPU-s + 11.5 s fit = 693 CPU-s = **12 CPU-minutes**, $0.009, "about a cent"; no labels | DERIVED | `models/real_v3_cal/model.json` (181 images, fit 11.5 s) x the cost line |
| Optional AI calibration | about **$2.5 to $7.7** per store-day: 181 frames x 1 to 3 Claude Sonnet 5.5 votes x $0.0141 (2.55 to 7.66); say "our estimate" | DERIVED | `llm_cost_compare.json` |
| Frontier-model comparison | Claude Sonnet 5.5 ~$0.0141 per image (**~300x**, 302), Opus 5.5 ~$0.0282 (~600x, 605), Haiku 5.5 ~$0.0007 (~15x, 15.1); accuracy untested | OK | `tools/llm_cost_compare.py`: 4,610 input + 488 output tokens, API list price; a cost ratio, not an accuracy comparison. **Replaces the earlier ~160x / ~325x / ~8x**, which were against the 7 CPU-s fp32 figure. bf16 cut CPU time by about a quarter (5.2 -> 3.8 on the same 14 frames); the rest of the change from 7 CPU-s is the benchmark moving from 3 pictures to 14 frames |
| "Running out soon" backtest (Q&A 17) | of 25 flags, 8 (32%) emptied within about 2 h, against 4% (58 of 1,550) for a not-yet-empty area; it catches 8 of the 58 that emptied | OK | `evidence/forecast_backtest_real_v3_cal.py` run on the final key (hourly pictures) |
| Optional boxes | +15.7 CPU-seconds per image (~$0.0002), peak RAM 1.76 GB | OK | `outputs/benchmark/cost_1t_real_v3_cal_detect.json` |
| Speed | 27 s to predict the 14 frames (152 areas) on the laptop CPU (16 threads); the same run with the staff app and OWLv2 boxes took 98 s | OK | integration run, `outputs/dryrun_final_zip` (`SUBMIT.bat` on a zip of `data/val_sim`; format check PASSED) |
| Skipping unchanged areas (tested) | at 1-hour spacing, skipping **3.8%** of areas misses 1 of 281 label changes; skipping **11.9%** misses 5 of 281 (1.8%); net saving **3.6% to 11.7%** of the compute; the gate costs 0.29 ms per area (0.6 with JPEG decode), under 0.2% of the model. **No 5-minute figure: not measured.** Not wired into the pipeline | OK | `tools/change_gate.py`, `outputs/benchmark/change_gate.json` (threshold picked on the other 13 cameras). Slide 10 footer and Q&A 6 |

Pilot pass criteria on slide 11 (at least 95% of empty shelves caught, at most 1 wasted walk in 10) are targets we
propose, not results. Say "we propose".

Market and sponsor lines (say the scope with the number):

| Line | Scope | Source |
|---|---|---|
| MC has publicly committed to halve food waste by 2028 against 2020 | company commitment, no progress figure | `market_facts.md` W8 |
| About 45% of food discarded by Austria's large retailers was fruit and veg | Austria, Q4 2023, share not tonnes | `market_facts.md` P1 |
| About 1 in 4 empty-shelf events: stock in the store, not on the shelf (Q&A only, say "the share staff can fix at once") | 2002 study, packaged goods, not fresh | `research/market_facts.md` O3 |
| Leiria: opened 10 January 2025, 1,200 m², loose fruit and veg by weight | verified | `research/sensei_facts.md` section 4 |
| Verona: fruit, veg and bread by weight, scales talk to the store system | Sensei case study | `sensei_facts.md` section 5 |
| Planogram compliance and replenishment alerts at Leiria | say "Sensei reports" | `sensei_facts.md` section 6 |
| RTIH AI and Physical Stores 2026; EHI reta AI category 2026 (Sonae with Sensei) | verified | `sensei_facts.md` section 3 |

Insights and counts on the dry-run pictures are model estimates from one day, shown on screen as such: do not quote
their figures as findings. A count reads "about N visible units", and for bunches such as bananas a unit is a bunch.

Do not say any other number out loud. If asked something we have not measured, say so.

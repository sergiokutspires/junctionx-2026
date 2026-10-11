# Sensei brief: make Sensei the hero, solve their real problem

> **Update 2026-10-11, 09:00: the deck was restructured.** `slides.html` now has 10 main slides (cold open 06:14 on
> camera 6215, Fresh, staff app, manager and freshness, how it works, results, trust, cost, the ask, the close) and
> 5 appendix slides (A1 Sensei context, A2 trust table, A3 cost table, A4 method and answer key, A5 projection). The
> script (`pitch.md`) is about 390 spoken words with two speakers. The slide-by-slide plan in section 4 below is the
> earlier 12-slide plan, kept for the record. The current script, slide list and every number with its source are in
> `pitch.md`; where this file disagrees, `pitch.md` wins. The app's verbs are now **Repor, Trocar, Deixar**, and the
> header reads "Fazer agora · 66 tarefas".

Written 2026-10-11, revised the same day after two jury-style critiques (section 12). This is the plan the deck (`slides.html`), the script (`pitch.md`), the Q&A (`qa_prep.md`) and the
demo (`demo_script.md`) follow. Sources: `research/sensei_facts.md` (company facts, tags [S] Sensei's words, [P] third
party), `research/market_facts.md` (grades A/B), `research/brief_map.md` (plan-time gaps, SUPERSEDED for numbers: our measured numbers are the table at the end of `pitch.md`), `docs/brief.txt`.

**Status (2026-10-11, final numbers applied).** Every provisional number below has been replaced in `slides.html`,
`pitch.md`, `qa_prep.md`, `demo_script.md` and `README.md`; the narrative, slide order and wording are unchanged. The
numbers quoted in the plan tables of this file are the plan-time ones and are kept for the record: the final ones, with
their sources, are in the table at the end of `pitch.md`. Main changes: key 1,962 areas (all 181 frames); held-out
1.23 / 1.41 / 1.48 for camera / last two / last picture (label-free 1.18 / 0.99 / 0.88); projection about 410 to 430 of
578 (about 355 if the pictures span the day); cost $0.00005 per image (3.8 CPU-s, one core, median of three runs), $3 a month for the
section, about 12 CPU-minutes and a cent to switch on a store, about 300 times cheaper than asking Claude Sonnet 5.5
(replaces the 160x; slide 10 now shows that ratio as its own tile, labelled a cost ratio and not an accuracy comparison,
as requested; the table keeps Claude "for scale"); skipping unchanged areas tested and saves only 3.6% to 11.7% at
hourly spacing.

**Number rule (as written at plan time).** Every score, cost and staff-term number is provisional until the final run. In the Markdown files it is
followed by `[FINAL]`; in `slides.html` it sits in `<span class="fin" title="[FINAL] ...">`. Press **P** in the deck to
highlight every one of them. The next step replaces them; nothing else in the wording should need to change.

---

## 1. Who is in the room, and what they want

Sensei is the sponsor **and** the jury. They are a Portuguese computer-vision company that has built and runs
autonomous stores (ceiling cameras, shelf weight sensors, on-prem servers). They are engineers ("builders, not
theorists") and they sell a platform to retailers ("At the end of the day, it must work as a business case for the
retailer", quoted on their site). They wrote the brief, the scoring rule and the new cost criterion. So they will reward:

1. **Relevance to their business**: does this make their platform worth more to their retail customers, in every store?
2. **Their three constraints** (brief_map section 0): labels do not scale; cost per camera must be close to zero; staff must
   keep trusting the app.
3. **Evidence over adjectives**: measured on held-out pictures, honest about limits, numbers they can check.

They will **not** reward: being told what their own platform lacks, superlatives about our model, invented market
numbers, or flattery without substance.

## 2. Positioning (one sentence)

> **Fresh is a produce-shelf layer for the Sensei platform: it reads the crates Sensei's ceiling cameras already
> see, needs no extra hardware and no labelling effort, costs about $0.00005 an image on one CPU core, and tells store
> staff, in Portuguese, what to restock first, what to move back and what to leave alone.**

- A **module**, not a replacement. Their platform already does planogram compliance and replenishment alerts at Leiria
  (Sensei reports); we do not know how it handles loose produce piles and we never say it does not. The integration we
  show is a **design**: frames and planogram in from their data API, one CPU container on their on-prem servers, area
  events out into the replenishment alerts staff already get. Our staff page is the reference UI, not a second app.
- **Their moat, not ours.** Leiria sells loose produce by weight from scales on the gondola (visible in camera 6215's
  frame). The pilot design uses those weighed sales as free supervision: calibration per store, a check on sales speed,
  and a waste signal. This makes the module better on Sensei's platform than anywhere else. Labelled "pilot design".
- **Name.** **Fresh.**, taken from their own challenge title. The staff app keeps its own name, *Controlo de
  prateleiras* (Shelf check).
- **Who wins:** Sensei (new value per camera they already install, a sellable add-on, a fleet-wide view), their retail
  customer (Continente today, any store on the platform tomorrow), and store staff (the biggest problems first, in their
  language).

## 3. Narrative arc (hero = Sensei, guide = us)

| Beat | Slide | What the jury should feel |
|---|---|---|
| Their achievement | 1-2 | "They know what we built, and they got the facts right." |
| Their open question | 2 | "Leiria proved produce sells by weight; the shelf is the next step." |
| Their constraints | 3 | "They understood the real problem is scale, not one store." |
| The product, early (0:31) | 4 | "My staff would understand this in seconds." |
| Insight from their data | 5 | "They looked at our store carefully, and kindly: a morning set-up check." |
| Method that fits the constraints | 6 | "No labels, and our own scoring rule drives it." |
| Honest proof, as a fleet recipe | 7 | "Day 0 with no labels, day 1 calibrated: I know what a new store gets." |
| Trust, weak spots shown | 8 | "They put the bad numbers on the slide. I trust the good ones." |
| Manager value | 9 | "The same pictures give the store manager more." |
| Cost, unmissable | 10 | "Cost per image, and no labelling bill as we grow." |
| Business: a module for us | 11 | "It plugs into our alerts, our scales make it better, and the ask is concrete." |
| Close | 12 | Three sentences to remember. |

## 4. Slide-by-slide plan (12 slides, about 2:55, about 455 spoken words)

> **SUPERSEDED (2026-10-11).** Plan-time numbers, kept for the record only. Do not quote them: the final numbers and their sources are the table at the end of `pitch.md`.

| # | Title on screen | On screen | Spoken core | Evidence |
|---|---|---|---|---|
| 1 | **Fresh.** | Subtitle "A produce-shelf layer for the Sensei platform"; hook; pills Same cameras / No extra hardware / No labelling effort; camera 6215 frame credited to Continente Bom Dia S. Romão, Leiria; team | Team, product name | brief p1 and p5 wording |
| 2 | **From a lab store to a 1,200 m² autonomous supermarket** | Four timeline nodes: 2021 Labs; 2022 Muffato Go; 2023-24 DAO/Conad Verona and Trento ("Verona: fruit, veg and bread sold by weight"); Jan 2025 Leiria (hero). One awards line (RTIH, EHI reta 2026). Card "Already on your platform (Sensei reports)": planogram compliance and replenishment alerts (Leiria); real-time shelf inventory visibility (sensei.tech). Card: "Leiria proved loose produce sells autonomously, by weight, from a scale on the gondola. The shelf is the next step." | Leiria credit, produce by weight, the brief's question | sensei_facts sections 3-6 |
| 3 | **What decides a produce layer across a fleet** | Three constraint cards in the brief's words; card 3 answer "Biggest problems first, and it says when it is unsure"; three shelf failures; facts: MC's public goal to halve food waste by 2028 vs 2020; ~45% of Austrian large-retailer food waste was fruit and veg (Q4 2023) | The three constraints | brief p1, p4, p5; market_facts W8, P1 |
| 4 | **"What to restock first, what to move back to its place, what to leave alone"** | Portuguese phone; *Repor*, *Devolver ao lugar*, *Deixar* cards; "Biggest problems first": *Primeiro · 25* (wrong and empty), *Depois · 45* (low), *Incerto: confirmar à vista*, *Imprimir* | The product in the first 40 seconds | assets/pt_*.jpg |
| 5 | **The plan says where things go. The camera sees what is there.** | 06:14 frame with marks; "Morning set-up, checked by camera: 1 in 8 → 1 in 60" [FINAL]; "14 cameras, 152 areas, read in 26 seconds" [FINAL]; empty strip | Camera 6215; the set-up check, not a store failing | wrong_product_persistence.py; submit dry runs |
| 6 | **Seeing the shelf "without being told what is right"** | Warp strip; DINOv2 fill; CLIP on catalogue names; "Your scoring rule is our decision rule" (when two levels are equally likely the rule picks the lower); OWLv2 boxes | Method | README How it works |
| 7 | **Day 0: no labels. Day 1: calibrated.** | Recipe: day 0 label-free core fits itself to the store's own unlabelled pictures (~20 CPU-minutes) [FINAL]; day 1 optional AI-labeller calibration. Bars: whole day, one camera held out of calibration 0.64 / 1.19 / 1.20; late 0.36 / 0.97 / 1.30; last picture 0.06 / 0.93 / 1.40 [FINAL]. Projection: 375-400 of 578 for late pictures, about 350 if the pictures span the day, vs the brief's 320 [FINAL] | Fleet recipe and projection | calibration_cv.json, staff_terms.json, model.json |
| 8 | **Your brief's three headings, weak spots included** | Table, brand-new camera vs calibrated store: empty on list 98% / 98%; wrong products found 1 in 3 / 8 of 10; wrong-product false alarm 1 in 1,168 / 0 in 294; wasted restock walks ~1 in 4 / ~1 in 10; half shown as full 4 in 10 / 4 in 10 [FINAL]. Boxes: Repeated errors (today: Incerto + picture age; next, not built: self-closing tasks, *Está certo assim*); what it means for a new store | Trust, with the weak spot said aloud | staff_terms.json |
| 9 | **The same pictures, "before the gondola runs empty"** | Portuguese Produtos and Análise screens; counts, running out soon, sales speed, adherence, slow movers; "estimates from one day" | Manager view | dashboard |
| 10 | **$0.00009 per image, on one CPU core** | Tiles: ~7 CPU-s; ⅓ core, ~$6 a month for the section; $0 labelling as the fleet grows. Table "What grows with your fleet": ours vs Claude Sonnet 5.5 "for scale" per image / camera-month / section-month / 1,000 cameras; footnote with the ~160x ratio; callout "Switching on a new store: ~20 CPU-minutes, about 2 cents, no labels; optional AI calibration $2-8 (our estimate)"; strip "SUBMISSION FORMAT CHECK: PASSED" [FINAL] | Cost per image first; labelling is what grows | benchmark, model.json |
| 11 | **A module for your platform, not a project** | In → Run → Out integration line, tagged "Integration design"; card "Your scales can teach our cameras" with the scale crop from camera 6215, tagged "Pilot design"; "And beyond" (ceiling cameras in most stores, bakery, flowers, next: closing-time mode); ask band: 4-week shadow pilot, pass criteria we propose | Integration, the scale loop, the ask | brief p5-6; sensei_facts sections 5-6 |
| 12 | **Fresh eyes on fresh produce** | Three sentences; team; Obrigado | Close | |

## 5. The three sentences we want the jury to remember

1. **Sensei has cameras over every gondola; Fresh reads the produce shelf from them, with no extra hardware and no
   labelling effort, switched on the same day.**
2. **About $0.00005 per image on one CPU core, and no labelling bill as the fleet grows: about a cent of CPU to switch
   on a store.**
3. **Staff get the brief's three answers in Portuguese (Repor, Trocar, Deixar), biggest problems first, and
   the app says when it is unsure.**

Each one is said aloud once in the script and appears on the close slide. We no longer say "the app leans low": the
decision rule does, but on late frames the calibrated model is too high 35 times and too low 11 (appendix A2, Q&A 12).

## 6. What we say about Sensei, and how

Say (all verified in `sensei_facts.md`; [S] facts always as "Sensei reports"):

- Continente Bom Dia S. Romão, Leiria, opened 10 January 2025, 1,200 m², with MC; loose fruit and vegetables sold by
  weight. "Largest autonomous store in the world" only as "the brief calls it" (it is their claim, and contested).
- Continente Labs, Lisbon, 2021, billed as Europe's first autonomous store (launch wording). Muffato Go, Brazil, 2022.
  DAO/Conad Verona 2023 and Trento 2024, with fruit, veg and bread by weight in Verona.
- RTIH AI in Retail Awards 2026, winner "AI and Physical Stores"; EHI reta Awards 2026, AI category won by Sonae with
  Sensei (Top Supplier). Both third-party verified.
- Sensei reports that at Leiria its platform handles planogram compliance and automated replenishment alerts for staff,
  and generates 9 replenishment tasks a day (that number is now Q&A only: we do not know how it is counted, so we never
  set it against our app's list). Our area events are the same kind of object as their alerts, for the produce section.
- Leiria sells loose produce by weight from a scale on the gondola (camera 6215 shows the "Pese aqui" scale). Trade
  press (Retail-Optimiser, Jan 2025) reported about 1,700 cameras and 2,000 "scales" at launch; those are shelf weight
  sensors, not produce-weighing scales, and not a Sensei figure, so we never cite them as such (Q&A only).
- Leiria was built to show loose produce can sell autonomously, by weight: that is Sensei's framing (case study), so
  we say "Sensei's case study" and never "Leiria proved".
- Their vocabulary, used sparingly: "proactive replenishment", "planogram compliance", "replenishment alerts for staff",
  "real-time shelf inventory visibility", "tech-agnostic". One echo per slide at most.

Never say (from `sensei_facts.md` section 13): that Sensei lacks shelf, planogram or produce monitoring; any Leiria camera,
SKU or ranking number without "Sensei reports"; a headquarters city; a total funding figure; that the 1,000 points of sale
target was met; 99% accuracy, 20% uplift, Deloitte, Mastercard, any waste result; how their models work; that
label-free learning is their method (it is the brief's requirement); names of Sensei staff.

## 7. Market figures used (scope always on the slide or in the sentence)

| Where | Sentence | Scope | Grade |
|---|---|---|---|
| Slide 3, slide 11 | MC has publicly committed to halve food waste by 2028 against 2020 | Company commitment, no progress figure published | B |
| Slide 3 | About 45% of food discarded by Austria's large retailers was fruit and vegetables | Austria, Q4 2023, mandatory reporting, share not tonnes | B |
| Q&A only | About 1 in 4 empty-shelf events had the stock in the store: the share staff can fix at once | Gruen, Corsten and Bharadwaj, 2002, packaged goods, not fresh | B |
| Q&A only | Shopper meets an empty shelf: the retailer loses the sale about 40% of the time | 2002, 8 packaged categories | B |
| Q&A only | EU law: minus 30% per capita by 2030, jointly across retail, food service and households | Directive (EU) 2025/1892, not a retail-only target | A |
| Q&A only | Walmart Canada rolled out fixed shelf cameras chain-wide (2022), no results published | Fact of the rollout | A |
| Q&A only | Planogram compliance had a modest effect on out-of-stocks where compliance was already above 90% | One US retailer, 4 non-fresh categories | B |

No produce out-of-stock rate exists in our research (market_facts O8); we never quote one. The "1 in 4" figure left
the slides: it is 24 years old, about packaged goods, and it is not "the share a shelf camera can catch".

## 8. Fixes applied to old claims (brief_map section 8 and the critiques)

> **SUPERSEDED (2026-10-11).** The "New" column holds plan-time numbers (1.20, 1.19, 375-400, 1 in 60, 0 in 294, 1 in 1,168, Depois 45, ~2 cents, 160x) that are no longer current. Do not quote them: the final numbers and their sources are the table at the end of `pitch.md`.

| Old | New |
|---|---|
| "1.25 on cameras never seen" (756-area part) | 1.20 on all 1,240 areas, row named "Whole day, one camera held out of calibration" (`calibration_cv.json`); 1.25 only in Q&A if asked |
| "Label-free core scores 1.19 on cameras it never saw" | "Day 0: the label-free core fits itself to the store's own unlabelled pictures" and scores 1.19 over the day; it was fitted on all 14 cameras without labels, so "never saw" is gone |
| Projection 360-400 | 375-400 for late pictures (1.30-1.40 x 289), about 350 if the pictures span the day (1.20 x 289) |
| "We lean low when unsure" as an outcome | The decision rule leans low; the remaining miss (half shown as full, about 4 in 10) is on slide 8 |
| "3 votes per area, 94% unanimous" for the whole key | Slide says only "independent AI labellers, no person labelled anything"; Q&A gives the exact vote counts |
| "The planogram is broken at opening" / "1 in 8" as a finding | "Morning set-up, checked by camera: 1 in 8 → 1 in 60"; we do not know the opening hour, so we never say "at opening" |
| "No false alarms" | Only for wrong-product alerts (0 in 294 late; 1 in 1,168 camera held out); wasted restock walks shown (~1 in 10, ~1 in 4) |
| Trust numbers only for the easy case | Two columns on slide 8: brand-new camera and calibrated store |
| "9 replenishment tasks a day" next to a 70-task screenshot | Bullet dropped from slide 2; slide 4 shows the app's own rounds (*Primeiro · 25*, *Depois · 45*); Q&A 20 answers the comparison |
| "Real-time shelf inventory visibility" under the Leiria label | Attributed to sensei.tech |
| "Verona and Trento: fruit, veg and bread by weight" | "Verona: fruit, veg and bread sold by weight" (only Verona verified) |
| Awards as a timeline node | One line under the timeline; the space goes to "Leiria proved loose produce sells autonomously, by weight" |
| Cost slide led by 160x vs Claude, 1,676-camera callout | Table "What grows with your fleet", Claude column "for scale", 160x in the footnote and Q&A; $0 labelling tile; switch-on callout (~2 cents); 1,676 in Q&A only |
| "SENSEI SUBMISSION CHECK: PASSED" | "SUBMISSION FORMAT CHECK: PASSED" on the slide, in `sensei/submit.py` and in README |
| "Output in your own annotation format" as the integration story | In → Run → Out integration design on slide 11, tagged as design; staff page called the reference UI |
| "A second store and a week of pictures" | A 4-week shadow pilot with pass criteria we propose |
| Staff screen first appears at 1:37 | Moved to slide 4, about 0:31 |
| Demo page opened in English | Rebuilt from the current `ui/` on 11 Oct; opens on *Controlo de prateleiras / Fazer agora* |

## 9. New numbers that need the team's OK before they are said aloud

> **SUPERSEDED (2026-10-11).** Plan-time numbers, kept for the record only. Nothing here is open any more and none of these values is current: the final numbers and their sources are the table at the end of `pitch.md`.

These come from `research/evidence/` (re-runs of our own code on our own key) or are our arithmetic. They are in
`pitch.md`'s numbers table, marked NEW or DERIVED. If the team does not approve one, delete it from the slide and the
matching sentence in `pitch.md`.

- 98% of empty shelves land on the Do-now list (late frames 39 of 40; one camera held out 127 of 129).
- Empty shown as full: 1 of 40 late frames, 2 of 129 camera held out, 0 of 24 last frame.
- Wrong-product alerts: 0 false alarms in 294 compliant areas (late frames), 1 in 1,168 (camera held out).
- Wrong-product recall: 8 of 10 late frames, 5 of 5 last frame, 26 of 72 camera held out (slide 8, "1 in 3").
- Restock tasks on a shelf the key calls full: 9 of 93 late frames (about 1 in 10), 97 of 367 camera held out (about 1 in 4).
- Half shelves shown as full: 32 of 77 late frames, 97 of 240 camera held out (about 4 in 10).
- Areas differing from the plan: 18 of 152 at 06h, 2 of 129 at 19h (key v2).
- Label-free core: 1.19 whole day, 0.97 late, 0.93 last frame.
- Switch-on: ~20 CPU-minutes, about 2 cents (181 frames x ~7 CPU-s + 10.9 s fit) (DERIVED).
- Projection: 375-400 late, about 350 whole day (DERIVED).
- Running out soon backtest: 9 of 27 flags emptied within about 2 h, against 4% for a random area; catches 9 of 60 (Q&A only).
- Calibration cost per new store: about $2 to $8 of AI labelling per store-day (our estimate).

## 10. Tone rules

- Credit first, then contribute. Name the store and the people's work (MC and Sensei) before our work.
- Specific beats grand. "1,200 m²" and "RTIH, AI and Physical Stores" beat "amazing" and "world-class".
- Their words in quotation marks, attributed ("your brief calls it"). Our claims with their scope.
- One self-critical line per proof slide (the label-free floor, the 1 in 10, one store, one day). It is what makes the
  strong numbers believable to engineers.
- No Sensei logos, no images from their website. The only pictures are the dataset frames and our own app.
- Portuguese where staff would see it (app labels), English for the talk.

## 11. Open decisions for the team

> **SUPERSEDED (2026-10-11).** Plan-time numbers, kept for the record only. Items 1 and 3 are closed; numbers in this file are not current: the final numbers and their sources are the table at the end of `pitch.md`.

1. Approve or drop each NEW and DERIVED number in section 9.
2. Keep the 12-slide order with the staff screen at slide 4 (recommended), or go back to staff after the proof.
3. (Done 2026-10-11.) Re-ran `tools/benchmark_cost.py` at one core on all 14 frames; the ~7 CPU-s plan figure is
   superseded (see the cost rows in `pitch.md`).
4. (Done 2026-10-11.) When the final numbers land, replace every `[FINAL]` and every `class="fin"` value (press P in the deck), then
   rebuild `slides_standalone.html` with `.venv/Scripts/python pitch/build_standalone.py`.
5. Optional, if there is time to build before the pitch (not done, not claimed anywhere): closing-time mode, a capped
   first round ranked by time-to-empty, self-closing tasks, *Está certo assim*. If any gets built, move it from "Next"
   to the demo only after it works.

## 12. Critique round (2026-10-11): what was applied, what was skipped

Two jury-style critiques (Sensei CEO/CTO view, 7/10; produce operations manager view, 6.5/10). Applied: every fix in
section 8. Skipped, and why:

- **Measure tasks per shift and the frame-to-frame flip rate**: not measured; it needs a new analysis and the team's OK.
  Q&A 20 says we have not measured it.
- **Cap each round, rank by expected lost sales, merge repeated frames, closing-time mode, *Está certo assim*,
  self-closing tasks, shared done-state, tasks inside Sensei's app**: not built. Shown only as "Next" (slides 8 and 11)
  or as the integration design, never demoed.
- **Gondola names and positions instead of camera IDs**: we have no gondola names in the data; inventing them would be
  a made-up fact.
- **Re-time the 1-in-8 stat to the store's opening hour**: we do not know the opening hour; reframed as the morning
  set-up check instead.
- **Day-one "Certo-only" mode and its false-restock rate on new cameras**: not measured; slide 8 says the first week is
  *confirmar à vista* instead.
- **Wharton staff-time share**: left out; the scope (60 executives, all categories, estimates) needs more airtime than
  3 minutes allow. (The earlier slide-5 timing line was dropped in the 09:00 restructure: no saved log; about 25 s including model load.)
- **Re-run the one-core benchmark on 14 frames**: left for the final-numbers pass (section 11 item 3).
- **The "no threshold beats the current rule" re-score** reported by one critique: not reproduced in our evidence files,
  so not quoted anywhere.

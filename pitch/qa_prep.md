# Judge Q&A prep

Sensei is the sponsor and the jury, so most questions will come from people who built the platform. Rules for
answering: short first sentence, then one reason, then stop. Credit their work before ours. Say "we have not measured
that" instead of guessing. Numbers allowed are the ones in `pitch.md`'s table; all of them are final (11 October: answer key v2 with 1,962
areas, model `real_v3_cal`). Never say Sensei's platform lacks something: we do not know how it handles loose
produce, so we say what ours does.

---

## A. Questions about Sensei's platform and business

### 1. Our platform already does planogram compliance and replenishment alerts. Why do we need this?

**It is meant to sit inside what you have, for the loose-produce shelf.** Sensei reports planogram compliance and
automated replenishment alerts at Leiria; we do not know how your platform handles piles of loose fruit, and we do not
claim it lacks anything. What we add is a layer that reads produce crates from the same ceiling frames with no labels
and one CPU core, and emits the same kind of object your alerts already carry: an area, a state, how sure, since when.

### 2. How would it plug into our stack?

**Frames and the planogram in, area events out; the two pieces a connector would call are built, the connector to
your platform is not.** Today it reads ceiling frames and `planogram.json` and writes your annotation format
(compliant, stock level, stock value for every area), plus a static staff page we use as a reference UI. Two more
entry points, both local and standard-library only:

- `python -m sensei serve`: an HTTP endpoint on 127.0.0.1. POST one JPEG with the camera id and timestamp (or no
  camera: it recognises the view) and get every area's status, confidence and the challenge-format entries back.
  Measured: about 2 s per frame on a laptop CPU (2.0 to 2.4 s on 3 real frames while another job ran), identical
  answers to the batch run.
- `python -m sensei watch`: compares each area with its previous picture and writes one event per change
  (became empty, became low, restocked, back to OK, wrong product, wrong product fixed), with time, camera, area,
  product and confidence; `--confirm 2` waits for two pictures in a row. On the dataset day: 252 events; 87% match
  our AI key exactly and 80% of the key's events are found, in-sample, since the same key calibrated the model.
  Wrong-product events are weak (3 of 8 found).

The design: your data API calls `serve` for each frame (one CPU container on the on-prem servers you already have,
about a sixth of a core per 14-camera section), and `watch`-style events go into the replenishment alerts your staff
already get. No GPU, no internet, no paid API. We have not connected it to your API or measured it at 5-minute
cadence.

### 3. What does it take to switch it on in a new store?

**One day of that store's own pictures and its planogram; no labels.** Day 0: the label-free core fits itself to the
store's unlabelled pictures. For one day here (181 frames) that is about 12 CPU-minutes of feature extraction plus a fit
that took 11.5 s wall-clock, about a cent at cloud prices (our arithmetic); it then scores about 1.18 points per area
over the day. Its default thresholds were tuned once on this store's key, so a second store is the real test. Day 1,
optional: AI models label a sample of the store's pictures once (automated, no human labelling), a small stock head
is refitted and a same-day memory of those labels is kept; product recognition stays zero-shot.
At API list price that is about $2.5 to $7.7 per store-day (181 pictures, one to three Claude Sonnet 5.5 votes each),
our estimate. Late in the day the calibrated heads score 1.41 to 1.48 against the label-free 0.88 to 0.99, so day 1 is
where the late-day accuracy comes from. We have not timed this on a second store, because we have only one.

### 4. Would it scale to a fleet: hundreds of stores, thousands of cameras?

**On cost, yes; on accuracy, we need a second store to prove it.** At one picture per camera every 5 minutes, 14 hours
a day, it is about $0.24 per camera per month, about $235 a month for 1,000 cameras. What grows with a fleet is
usually labelling, and day 0 needs none: a new store is about a cent of CPU to switch on (day-1 calibration uses an AI-made key, about $2.5 to $7.7 per store). Each picture is independent,
so more stores means more cores running the same command. Our proxy for a new camera is holding a whole camera out of
calibration: 1.23 points per area over the day, against 1.18 for the label-free core, and a new store is our ask. (If
asked about all of Leiria: about 1,700 cameras, as trade press reported at launch (Retail-Optimiser, Jan 2025), at this
cadence would be about $395 a month, an upper bound, since most of those cameras do not look at produce.)

### 5. Why not just ask a vision-language model about every picture?

**Cost, and you asked about cost.** With the same two pictures our AI labellers saw (about 4,600 input and 490 output
tokens), Claude Sonnet 5.5 costs about $0.014 per image, about 300 times ours; Opus 5.5 about 600 times; Haiku 5.5
about 15 times, accuracy untested. That is a cost ratio at list price with our labelling prompt (output tokens are our estimate, 45 per area), not an
accuracy comparison; a leaner prompt or the Batch API (about 150 times) would narrow it. We used such models once, as
teachers to label a sample, and ship small open models as the student.

### 6. What exactly does it cost per image?

**About $0.00005 per image, measured.** One CPU core spends about 3.8 CPU-seconds on a frame (all ~11 areas; 14
frames, median of three back-to-back runs, 3.66 to 3.84; two earlier runs measured about 4.5, not saved, which would
be about $0.00006; `tools/benchmark_cost.py`), peak RAM 1.2 GB, no GPU, measured on an AMD Ryzen AI 7 350 laptop with
native bf16 (a CPU without bf16 needs about 1.6 times more). We price those CPU-seconds at a cloud vCPU, which may be
slower, so treat it as about $0.00005 to $0.0001. At on-demand cloud prices (AWS c7i.large, $0.0892/h for 2 vCPU, so ~$0.045 per vCPU-hour) that is
~$0.000047 per image, about 5 cents per thousand. A 14-camera section photographed every 5 minutes for 14 hours is
2,352 images a day: ~$0.11 a day, ~$3 a month, a sixth of one core, or nothing extra on a machine the store already
runs. How we got there: running CLIP and DINOv2 in bf16 cut the CPU time by about a third (5.2 to 3.4 CPU-s, same heads);
the per-area memory adds back about 0.3 (3.4 to 3.8). In quick tests whose results were not saved, int8 lost score,
and larger embeddings in the heads showed no gain; we do not quote numbers for those. Using 16 threads is faster (1.4 s
per image) but burns 18 CPU-seconds (an earlier full-precision measurement), so for cost we run one core per stream.
The optional product boxes (OWLv2) cost ~16 CPU-seconds more (about $0.00024 per image in total, peak RAM 1.76 GB) and only feed the staff app, not the score.

**Cheaper still: skipping areas whose pixels did not change. We tested it and the win is small.** Cameras are fixed,
so we compared consecutive pictures of every area (1,810 pairs, about an hour apart): 84.5% of them keep their label,
and a cheap pixel-change score picks the changed ones out (AUC 0.89). With the threshold chosen on the other 13
cameras, skipping 3.8% of areas misses 1 of 281 label changes, skipping 11.9% misses 5 of 281 (1.8%): a net compute
saving of 3.6% to 11.7%. The gate costs under 0.2% of the model. It is small because most changes in the key are
borderline half/full flips or swaps between similar-looking products, which pixels barely show. We have no 5-minute
pictures: fewer areas change then, so the share could be higher, but the missed-change rate could be worse; neither is
measured, and the gate is not built into the pipeline.

### 7. What would you need from us?

**A four-week shadow pilot.** Week 1: run silently at Leiria and compare our tasks with your restock logs and your
existing replenishment tasks. Weeks 2 to 4: a second store, switched on from its own pictures. Pass criteria we
propose: at least 95% of empty shelves caught, at most 1 wasted restock walk in 10 (on our AI key the calibrated store
already measures about 1 in 10, so the pilot checks that against your restock logs), and a first round short enough
for one person per shift. What we need: frames and planogram from your data API, restock logs, one contact. What you
get: a weekly accuracy report. With your scale data we would also test a design: kilos weighed per product per hour
against the drop in shelf fill, as free calibration and as a check on sales speed. None of that is tested yet.

### 8. Is planogram compliance even worth monitoring?

**Where compliance is high, the effect on out-of-stocks is modest; the value is where it is low.** In the one solid
study (one US retailer, four non-fresh categories), compliance was already above 90% and a 10-point change moved
out-of-stocks by about one point. In this produce section, on one day and our AI-made key, about 1 area in 8 held another product
than planned in the first pictures of the day (06h), 1 in 65 by evening; we cannot tell a set-up mistake from a
planned change, and a wrong product also means a wrong price on the
shelf. So we flag only clear cases and put them first.

## B. Questions about the method and the numbers

### 9. Did you use labels?

**Day 0 needs none; the submitted, calibrated model uses an answer key made by AI models, with no human
labelling.** The label-free core learns the store's look from unlabelled pictures: patch clusters for stock, CLIP
zero-shot for the product (its default thresholds were tuned once on this store's key). To measure it, and to
calibrate a small stock head, we built the key with AI labellers: round 1 (cameras 6215, 6371, 6373) three Claude Opus
5.5 labellers plus adjudication; then Claude Sonnet 5.5 votes plus two more votes per area (Sonnet 5.5 and Opus 5.5),
with the rubric in `tools/gemini_label.py`. The key has 1,962 areas over all 181 frames, three votes
per area: on the 11 cameras voted most recently (1,569 areas) the votes were unanimous for 84% and 34 disputes were
adjudicated; three cameras (393 areas) come from the earlier round, where 36 areas of camera 6373 got only two
votes (six of them split). The original 756-area key is kept as a
second test so older numbers stay comparable. A Gemini Flash cross-check on 192 areas agreed on 100% of wrong-product calls and 81% of stock levels. We never had the hidden
validation set.

### 10. How do you know the score will hold on the hidden set?

**We do not know; we estimate a range, 355 to 430 of 578, and we show the weak number too.** Calibrated scores are on labels the heads were not
fitted on: 1.23 points per area with a whole camera held out over the day (all 1,962 areas), 1.41 on the last two
frames of each camera, 1.48 on the last frame. Label-free core: 1.18, 0.99 and 0.88. The label-free core uses no labels
at all, but it was fitted on unlabelled pictures from all 14 cameras, so we never say it saw no camera. The hidden set
is the same 14 cameras; if its pictures are late in the day, which we assume because the brief's one example file name
(20:24) is later than our last picture (20:16), 1.41 to 1.48 x 289 is about 410 to 430 of 578; if they span the day,
about 355 (1.23 x 289). Day 0 with no labels would be about 255 to 285. Camera by camera, late scores run from 0.5 to
2.0 per area. The key is AI-labelled, not the store's truth. The brief's 320 is a worked scoring example, not a
benchmark, so we do not compare against it. If asked about the old 1.25: that was the first 756 areas with the previous model; the final
model scores 1.17 on that part (dominated by three cameras with 12 to 13 labelled frames each), 1.23 on all 1,962, and
the late rows, which are what the hidden set resembles, improved on both keys (on the 756 part 1.35 and 1.43, against
1.30 and 1.39 before; about 390 to 410 points). Sanity check: always answering "compliant" and "full" scores 0.76 per
area over the whole key but only 0.46 and 0.18 late in the day, because shelves empty.

### 11. What are the weak spots?

**Four, all measured, on slide 7 and appendix A2.** (1) Wrong product on a camera held out of calibration: it finds
31 of 117 cases, about a quarter, against 6 of 8 on late frames and 4 of 4 on the last frame (those folds hold very
few wrong products, and about half of those late finds come from remembering an earlier labelled wrong product: the
label-free run finds 4 of 8 and 2 of 4); it is precise (2 false alarms in 1,845 correct areas) but not complete. (2) Wasted walks: about 1 restock
task in 10 on late frames points at a shelf our key calls full (9 of 91), about 1 in 4 with a camera held out (148 of
539). (3) Half shelves shown as full: about 4 in 10 (28 of 71 late, 130 of 340 camera held out); our own labellers
disagreed most there: on the 11 voted cameras the three votes agreed on 57% of the areas the key calls half, against
88% for empty and 92% for full. (4) One store, one day.

### 12. Do you lean low on stock?

**The decision rule does; the remaining errors do not, and we say so.** Answering too high costs 3 points, too low 2.
Take an area that is half or full with equal chance: "half" has expected score 0.5 x 1 + 0.5 x (-2) = -0.5, "full"
has 0.5 x 1 + 0.5 x (-3) = -1.0, so the rule answers "half". We pick the answer with the best expected score for every
area, and we always answer. But on late frames the calibrated model is still too high 35 times and too low 11:
28 of the 35 too-high errors are half read as full, so the fix is in seeing, not in the threshold.

### 13. Why not train an object detector and count?

**Nobody can label boxes for loose, piled fruit at fleet scale, and the score is per area.** Counting bananas in a pile
is hard even for people, as your brief says. Your brief allows a fill level, and a fill level is more robust than a
count of overlapping fruit. We still show boxes from the free open-vocabulary detector OWLv2, because they help staff
trust the answer; they feed the "about N visible units" estimate, not the scored output.

### 14. What about hands, shoppers, baskets (occlusion)?

**We look only at what is visible, and we do not raise alarms we cannot support.** Every area crop carries a mask of
the visible pixels, and fill uses visible patches only. An area that is empty, occluded or barely visible counts as
compliant, because nothing wrong is shown. The optional box detector drops boxes it labels as hands or baskets. We have not measured how
much a large occluder degrades the stock estimate.

### 15. What happens when the planogram changes?

**Edit the planogram and re-run the label-free fit; no new labels for the product side.** Catalogue names become
CLIP prompts, so a new product needs no new training images. The refit took 11.5 s wall-clock with cached features, about
12 CPU-minutes for a new day of pictures; the labelled heads should then be refitted or dropped. The stock side looks
for "container versus product", which does not depend on the product. We compare the shelf against the planogram; we never assume the planogram
describes the shelf.

### 16. Why only base-fruit level for compliance?

**It matches what staff can act on, and it avoids false alarms.** Your brief chose products that can be recognised
generically. A false alarm sends staff to a shelf with nothing to arrange. Banana versus orange is what confuses
customers and prices; two apple varieties from a ceiling camera we would only flag with strong evidence.

### 17. Does "Running out soon" actually predict anything?

**An early signal, not a product yet.** Back-tested on our key (hourly pictures): of 25 "running out soon" flags, 8
(32%) really emptied within about 2 hours, against 4% for a random area that was not yet empty. But it
caught only 8 of the 58 shelves that emptied. Your 5-minute cadence and restock logs should sharpen it; we have not
tested that.

### 18. Can it tell you about waste?

**Only a first proxy today, and a design for more.** The app counts slow movers ("24 produtos quase não mexeram
durante o dia. Verifique se ainda estão frescos.") and turns time on display, against a shelf-life class, into
freshness checks ("Quando houver tempo: verificar frescura", an estimate); we have not validated either against waste
records. A design: where fill drops with no
matching weighed sale, that is culling or shrink, a waste signal. Untested. Context, with its scope: in Austria's
mandatory retailer reporting, fruit and vegetables were about 45% of the food discarded (Q4 2023, among large retailers
that assigned product groups), and MC has publicly committed to halve all food waste by 2028 against 2020 (Feb 2025; we
found no published progress figure). The brief's stock scale stops at "full", so
overstock cannot be scored; our waste levers are slow movers and not over-restocking (question 21).

### 19. You have scales and weight sensors. Isn't that enough?

**They answer different questions, and together they are stronger.** Your store weighs every kilo of loose produce it
sells; a ceiling camera says which product is in which crate and how full it looks. Our pilot design uses the first to
teach the second: kilos sold per product per hour against the drop in shelf fill calibrates each store with no AI
labeller and checks our sales-speed estimate. We have not seen your sensor or sales data, so we have not tested that.

## C. Questions a store or operations manager will ask

### 20. The app shows 66 tasks. Your platform generates about 9 replenishment tasks a day. Isn't that alert overload?

**Staff see 25 first, and those 66 are one evening snapshot of the whole section.** The header reads "Fazer agora · 66
tarefas" and groups the list: *Primeiro: produto errado e vazio* (25), *Depois: a ficar baixo* (16), *Deixar até
amanhã (perto do fecho)* (25, the closing-time mode of question 21; with it off, *Depois* has 41), then 13 freshness
checks as extras (*Quando houver tempo: verificar frescura*), all 14 cameras, pictures from 18:07 to 20:16. We do not know how Sensei counts its 9 tasks (store-wide, all
categories, per day), so we do not compare the two numbers. Next steps we have not built: cap each round, rank by how
soon the shelf empties, and merge an area's repeated pictures into one task that shows how long the problem has
lasted. We have not measured tasks per shift or how often a task flips between pictures.

### 21. Late in the day we let produce shelves run down on purpose. Won't "restock the low shelves" add waste?

**It would if staff followed it blindly, so the app has a closing-time mode.** The manager sets *Hora de fecho*
(default 21:00). In the last 2 hours before it, topping up "low" produce with a short or medium shelf life moves to
*Deixar até amanhã (perto do fecho)*, with the reason on screen; empty shelves and wrong products never wait, and
long-life produce stays in the list. In the demo build the pictures end at 20:16, so it is on: 25 of the 41 low
shelves wait until tomorrow. Honest limits: "now" is the time of the newest picture; the 2-hour window and the
shelf-life classes are our design choice (classes reviewed by Inês, question 27), and we have not measured the
effect on waste.

### 22. What stops the same alert coming back every picture?

**Today, little beyond honesty; that is a known gap.** Uncertain calls say *Confiança: Baixa: confirmar à vista*,
every card shows when the camera saw it (*Visto às 18:35*), and an age chip (*há 1 h 40 min*) when the picture is
older than the newest. *Marcar feito* is stored on that phone only. The detection side exists: `sensei watch`
emits "restocked" and "back to OK" events when the next picture shows the area filled, `--confirm 2` suppresses
one-picture flips, and the app's *Dia* view replays those events over the dataset day. Not built: closing the task
in *Fazer agora* from those events, and a button that silences an area until the planogram changes, for promotions
and planned swaps.

### 23. Why say 1 in 8 areas differ in the morning? Our team is still setting up then.

**Exactly: it is a set-up check, not a failure.** On one day and our AI-made key, about 1 area in 8 differed from the
plan in the first pictures (06h) and 1 in 65 by evening (19h); we cannot tell a set-up mistake from a planned change. That is what a morning check-sheet is for: the app prints one, with a tick
box per task. We do not know the store's opening hour, so we do not say "at opening".

## D. Questions other teams asked Sensei on Discord (judges may ask them too)

### 24. What about products that are not in the planogram?
Sensei's answer on Discord: they are **not planogram compliant**. That is exactly our rule: an area is compliant
only if it shows the planogram's product for that spot; anything else, including a product that is not in the
planogram at all, is "wrong product". Our answer key used the same rule (117 of 1,962 areas are not compliant,
`data/labels/teacher_labels_v2.json`).

### 25. How do you tell apart products that look the same (varieties, packs, different names)?
Sensei's answer on Discord: *"you have to train it"* - and that is what we do. The per-area memory compares each
picture with the same spot's labelled pictures from earlier in the day, so every spot learns its own normal look;
CLIP catches clear swaps (oranges in the banana crate). Honest limit: look-alike varieties are the hardest case,
and on a camera we have never labelled we miss most wrong products (slide 7). The scalable fix is training data
that the store already produces (for example what the scale or till recorded for that spot) - an idea, not built.

### 26. You trained on labels. Isn't the brief about learning without labels?
No human labelled anything. The core runs label-free from day 0 (the label-free model is shipped:
`SUBMIT_LABEL_FREE.bat`); to train it, as Sensei said teams have to, we had AI models annotate the train/test pictures
(never the validation set). That answer key costs minutes, not a labelling team, and works the same in a new store.

### 27. Who decided the freshness classes and the ethylene warnings? (Inês answers)
Inês, our team's biologist, reviewed the sourced reference for all 94 products (USDA Agriculture Handbook 66, FAO,
peer-reviewed postharvest papers) and confirmed every class; she designed the ethylene compatibility score: for two
neighbours, max(producer of A x sensitivity of B, producer of B x sensitivity of A), from 1 to 9, with three bands:
compatible (1-3), caution (4-6), avoid (7-9). The app's strong warnings are her "avoid" band (score 9, e.g. Galia
melon next to kiwi). It is a layout suggestion, not a measurement from the picture.

## Lightning round

- **Why not skip the areas that did not change?** We tested it: at hourly spacing it saves only 3.6% to 11.7% of the
  compute, because most label changes are borderline calls pixels barely show; no 5-minute figure (Q&A 6).
- **Camera moved?** Cameras are fixed; areas are drawn per camera. If one moves, its areas need redrawing.
- **Is the app tied to the internet?** No. It is a static page and opens from a file, a USB stick or a phone. In
  production the tasks would go into the alerts your staff already get; the page is the reference UI.
- **Languages?** Portuguese by default, English one tap away; product names come from your catalogue.
- **Privacy?** The scores use only the planogram areas; the optional box detector sees the whole picture and keeps
  only boxes inside the areas, dropping those it labels as hands or baskets. We never identify people. The staff app
  shows the frame, downscaled.
- **Why the name "Fresh."?** Fresh produce, fresh eyes on the shelf (your challenge title), and a full stop: the shelf, sorted. Tagline: *See every shelf. Fix what matters first.*
- **What would you do with another week?** Calibrate confidence (check that "Alta" is right more often than
  "Média"), hand-count 20 to 30 areas to check the unit counts, close tasks from the area events, and run on
  a second store.
- **Can you rebuild it? Is it reproducible?** Yes for the answers: `tools/reproduce_check.py` rebuilds the model
  from the public repo, the public AI labels and the dataset; in 7 rebuilds (2 recomputing every feature, about 5
  minutes each) the predictions were byte-identical to our rehearsal (0 of 152 areas changed). The model files match
  to float32 precision: multithreaded k-means once settled on a slightly different solution (same answers); with
  single-threaded math two rebuilds are bit-identical (`results/reproduce.md`). The dataset itself is not in the
  public repo, because it is your store footage.
- **What does a day look like?** The *Dia* view replays the 181 dataset pictures with an event log (after the
  pitch, `demo_script.md`). Same pictures the model was calibrated on: the experience, not accuracy.
- **"SUBMISSION FORMAT CHECK"?** Our own check that the output file has the brief's format; not a Sensei
  certification.
- **Who labelled the key?** AI models (Claude Opus 5.5 and Sonnet 5.5 votes, Opus adjudication), three votes per area
  (two on 36 areas); no human labelling, not the store.
- **Is the projection the score you expect?** It is our estimate, 355 to 430, on an AI-made key with the upper end
  assuming late pictures; the hidden set decides.
- **Did you beat the brief's 320?** We do not compare against it: it is a worked scoring example, not a benchmark.

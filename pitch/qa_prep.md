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

**Frames and the planogram in, area events out; this is a design, the connector is not built.** Today it reads
ceiling frames and `planogram.json` from disk and writes your annotation format (compliant, stock level, stock value
for every area), plus a static staff page we use as a reference UI. The design: read frames from your data API, run as
one CPU container on the on-prem servers you already have (about a sixth of a core per 14-camera section), and emit
area events (area_id, state, confidence, since) into the replenishment alerts your staff already get. No GPU, no
internet, no paid API. We have not built that connector yet.

### 3. What does it take to switch it on in a new store?

**One day of that store's own pictures and its planogram; no labels.** Day 0: the label-free core fits itself to the
store's unlabelled pictures. For one day here (181 frames) that is about 12 CPU-minutes of features plus an 11.5-second
fit, about a cent at cloud prices (our arithmetic); it then scores about 1.18 points per area over the day. Day 1,
optional: an AI labeller marks the store's pictures once and two small heads are refitted; no person labels anything.
At API list price that is about $2.5 to $7.7 per store-day (181 pictures, one to three Claude Sonnet 5.5 votes each),
our estimate. Late in the day the calibrated heads score 1.41 to 1.48 against the label-free 0.88 to 0.99, so day 1 is
where the late-day accuracy comes from. We have not timed this on a second store, because we have only one.

### 4. Would it scale to a fleet: hundreds of stores, thousands of cameras?

**On cost, yes; on accuracy, we need a second store to prove it.** At one picture per camera every 5 minutes, 14 hours
a day, it is about $0.24 per camera per month, about $235 a month for 1,000 cameras. What grows with a fleet is
usually labelling, and ours needs none: a new store is about a cent of CPU to switch on. Each picture is independent,
so more stores means more cores running the same command. Our proxy for a new camera is holding a whole camera out of
calibration: 1.23 points per area over the day, against 1.18 for the label-free core, and a new store is our ask. (If
asked about all of Leiria: 1,676 cameras, as Sensei reported at launch, at this cadence would be about $395 a month, an
upper bound, since most of those cameras do not look at produce.)

### 5. Why not just ask a vision-language model about every picture?

**Cost, and you asked about cost.** With the same two pictures our AI labellers saw (about 4,600 input and 490 output
tokens), Claude Sonnet 5.5 costs about $0.014 per image, about 300 times ours; Opus 5.5 about 600 times; Haiku 5.5
about 15 times, accuracy untested. That is a cost ratio, not an accuracy comparison. We used such a model
once, as a teacher to label a sample, and ship small open models as the student.

### 6. What exactly does it cost per image?

**About $0.00005 per image, measured.** One CPU core spends about 3.8 CPU-seconds on a frame (all ~11 areas; 14
frames, median of three back-to-back runs, 3.7 to 3.8; `tools/benchmark_cost.py`), peak RAM
1.2 GB, no GPU. At on-demand cloud prices (AWS c7i.large, $0.0892/h for 2 vCPU, so ~$0.045 per vCPU-hour) that is
~$0.000047 per image, about 5 cents per thousand. A 14-camera section photographed every 5 minutes for 14 hours is
2,352 images a day: ~$0.11 a day, ~$3 a month, a sixth of one core, or nothing extra on a machine the store already
runs. How we got there: running CLIP and DINOv2 in bf16 cut the CPU time by about a quarter against full precision (5.2 to 3.8 CPU-s on the same 14 frames)
with scores inside the noise of the clustering seed; int8 lost score and the smaller CLIP B/32 lost identification accuracy,
so both were rejected, and bigger models (CLIP-L, SigLIP, DINOv2-base) did not score better. Using 16 threads is faster (1.4 s
per image) but burns 18 CPU-seconds (an earlier full-precision measurement), so for cost we run one core per stream.
The optional product boxes (OWLv2) cost ~16 CPU-seconds more (~$0.0002) and only feed the staff app, not the score.

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
propose: at least 95% of empty shelves caught, at most 1 wasted walk in 10, and a first round short enough for one
person per shift. With your scale data we would also test the design on slide 11: kilos weighed per product per hour
against the drop in shelf fill, as free calibration and as a check on sales speed. None of that is tested yet.

### 8. Is planogram compliance even worth monitoring?

**Where compliance is high, the effect on out-of-stocks is modest; the value is where it is low.** In the one solid
study (one US retailer, four non-fresh categories), compliance was already above 90% and a 10-point change moved
out-of-stocks by about one point. In this produce section, about 1 area in 8 holds another product than planned in
the first pictures of the day, 1 in 65 by evening, and a wrong product also means a wrong price on the
shelf. So we flag only clear cases and put them first.

## B. Questions about the method and the numbers

### 9. Did you use labels?

**The pipeline does not need any.** It learns the store's look from unlabelled pictures: patch clusters for stock,
CLIP zero-shot for the product. To measure it, and to calibrate two small heads, we built an answer key with
independent AI labellers; no person labelled anything. The key has 1,962 areas over all 181 frames, three votes
per area: on the 11 cameras voted most recently (1,569 areas) the votes were unanimous for 84% and 34 disputes were
adjudicated; three cameras (393 areas) come from the earlier round, where 36 areas of camera 6373 got only two
votes (six of them split). The original 756-area key is kept as a
second test so older numbers stay comparable. A second AI, Gemini, matched all 24 wrong-product calls it re-checked. We never had the hidden
validation set.

### 10. How do you know the score will hold on the hidden set?

**We do not know; we estimate, and we show the weak number too.** Calibrated scores are on labels the heads were not
fitted on: 1.23 points per area with a whole camera held out over the day (all 1,962 areas), 1.41 on the last two
frames of each camera, 1.48 on the last frame. Label-free core: 1.18, 0.99 and 0.88. The label-free core uses no labels
at all, but it was fitted on unlabelled pictures from all 14 cameras, so we never say it saw no camera. The hidden set
is the same 14 cameras; if its pictures are late in the day, as the brief's one example file name (20:24) suggests,
1.41 to 1.48 x 289 is about 410 to 430 of 578; if they span the day, about 355 (1.23 x 289). The key is AI-labelled,
not the store's truth. If asked about the old 1.25: that was the first 756 areas with the previous model; the final
model scores 1.17 on that part (dominated by three cameras with 12 to 13 labelled frames each), 1.23 on all 1,962, and
the late rows, which are what the hidden set resembles, improved on both keys (on the 756 part 1.35 and 1.43, against
1.30 and 1.39 before; about 390 to 410 points). Sanity check: always answering "compliant" and "full" scores 0.76 per
area over the whole key but only 0.46 and 0.18 late in the day, because shelves empty.

### 11. What are the weak spots?

**Four, all measured, and on slide 8.** (1) Wrong product on a camera held out of calibration: it finds 31 of 117
cases, about a quarter, against 6 of 8 on late frames and 4 of 4 on the last frame (those folds hold very few wrong
products); it is precise (2 false alarms in 1,845 correct areas) but not complete. (2) Wasted walks: about 1 restock
task in 10 on late frames points at a shelf our key calls full (9 of 91), about 1 in 4 with a camera held out (148 of
539). (3) Half shelves shown as full: about 4 in 10 (28 of 71 late, 130 of 340 camera held out); our own labellers
disagreed most there: on the 11 voted cameras the three votes agreed on 58% of the areas the key calls half, against
88% for empty and 92% for full. (4) One store, one day.

### 12. Do you lean low on stock?

**The decision rule does; the remaining errors do not, and we say so.** Answering too high costs 3 points, too low 2.
Take an area that is half or full with equal chance: "half" has expected score 0.5 x 1 + 0.5 x (-2) = -0.5, "full"
has 0.5 x 1 + 0.5 x (-3) = -1.0, so the rule answers "half". We pick the answer with the best expected score for every
area, and we always answer. But on late frames the calibrated model is still too high 35 times and too low 11:
the misses are confident half-read-as-full calls, so the fix is in seeing, not in the threshold.

### 13. Why not train an object detector and count?

**Nobody can label boxes for loose, piled fruit at fleet scale, and the score is per area.** Counting bananas in a pile
is hard even for people, as your brief says. Your brief allows a fill level, and a fill level is more robust than a
count of overlapping fruit. We still show boxes from the free open-vocabulary detector OWLv2, because they help staff
trust the answer; they feed the "about N visible units" estimate, not the scored output.

### 14. What about hands, shoppers, baskets (occlusion)?

**We look only at what is visible, and we do not raise alarms we cannot support.** Every area crop carries a mask of
the visible pixels, and fill uses visible patches only. An area that is empty, occluded or barely visible counts as
compliant, because nothing wrong is shown. Hands and baskets are never drawn as products. We have not measured how
much a large occluder degrades the stock estimate.

### 15. What happens when the planogram changes?

**Edit the planogram file; the product side follows.** Catalogue names become CLIP prompts, so a new product needs no
new training images. The stock side looks for "container versus product", which does not depend on the product;
re-running the label-free fit refreshes it. We compare the shelf against the planogram; we never assume the planogram
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

**Only a first proxy today, and a design for more.** The app lists slow movers ("barely moved all day, check they are
still fresh"); we have not validated it against waste records. The design on slide 11: where fill drops with no
matching weighed sale, that is culling or shrink, a waste signal. Untested. Context, with its scope: in Austria's
mandatory retailer reporting, fruit and vegetables were about 45% of the food large retailers discarded (Q4 2023), and
MC has publicly committed to halve food waste by 2028 against 2020. The brief's stock scale stops at "full", so
overstock cannot be scored; our waste levers are slow movers and not over-restocking (question 21).

### 19. You have scales and weight sensors. Isn't that enough?

**They answer different questions, and together they are stronger.** Your store weighs every kilo of loose produce it
sells; a ceiling camera says which product is in which crate and how full it looks. Our pilot design uses the first to
teach the second: kilos sold per product per hour against the drop in shelf fill calibrates each store with no AI
labeller and checks our sales-speed estimate. We have not seen your sensor or sales data, so we have not tested that.

## C. Questions a store or operations manager will ask

### 20. The app shows 79 tasks. Your platform generates about 9 replenishment tasks a day. Isn't that alert overload?

**Staff see 25 first, and those 79 are one evening snapshot of the whole section.** The app groups the list: *Primeiro*
(wrong product and empty, 25 in that screenshot), *Depois* (running low, 41) and 13 freshness checks in a last group of
their own, all 14 cameras, pictures from 18:07 to 20:16. We do not know how Sensei counts its 9 tasks (store-wide, all
categories, per day), so we do not compare the two numbers. Next steps we have not built: cap each round, rank by how
soon the shelf empties, and merge an area's repeated pictures into one task that shows how long the problem has
lasted. We have not measured tasks per shift or how often a task flips between pictures.

### 21. Late in the day we let produce shelves run down on purpose. Won't "restock the low shelves" add waste?

**It would if staff followed it blindly, so the next step is a closing-time mode.** After a store's own cut-off, the
list would show only empty shelves and wrong products, and carry the low ones to the next morning's list. It is on
slide 11 as "next", not built. Today "low" already sits in the second round (*Depois*), after empty and wrong.

### 22. What stops the same alert coming back every picture?

**Today, little beyond honesty; that is a known gap.** Uncertain calls say *Incerto: confirmar à vista*, and every
task shows its picture's age. *Marcar feito* is stored on that phone only. Next (not built): a task closes itself when
the next picture shows the area filled, and *Está certo assim* silences an area until the planogram changes, for
promotions and planned swaps.

### 23. Why say 1 in 8 areas differ in the morning? Our team is still setting up then.

**Exactly: it is a set-up check, not a failure.** About 1 area in 8 differs from the plan in the first pictures (06h)
and 1 in 65 by evening (19h). That is what a morning check-sheet is for: the app prints one, with a tick
box per task. We do not know the store's opening hour, so we do not say "at opening".

## Lightning round

- **Why not skip the areas that did not change?** We tested it: at hourly spacing it saves only 3.6% to 11.7% of the
  compute, because most label changes are borderline calls pixels barely show; no 5-minute figure (Q&A 6).
- **Camera moved?** Cameras are fixed; areas are drawn per camera. If one moves, its areas need redrawing.
- **Is the app tied to the internet?** No. It is a static page and opens from a file, a USB stick or a phone. In
  production the tasks would go into the alerts your staff already get; the page is the reference UI.
- **Languages?** Portuguese by default, English one tap away; product names come from your catalogue.
- **Privacy?** We analyse only the planogram areas of each frame; we never identify people, and hands are dropped
  from the boxes.
- **Why the name Fresh Eyes?** It is your challenge title. The staff app itself is called *Controlo de prateleiras*.
- **What would you do with another week?** Calibrate confidence (check that "Certo" is right more often than
  "Provável"), hand-count 20 to 30 areas to check the unit counts, build the closing-time mode and
  self-closing tasks, and run on a second store.
- **"SUBMISSION FORMAT CHECK"?** Our own check that the output file has the brief's format; not a Sensei
  certification.
- **Who labelled the key?** Independent AI labellers, three votes per area (two on 36 areas); not people, not the store.
- **Is the projection the score you expect?** It is our best estimate; the hidden set decides.

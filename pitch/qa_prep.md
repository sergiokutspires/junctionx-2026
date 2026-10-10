# Judge Q&A prep

Rules for answering: short first sentence, then one reason, then stop. Say "we have not measured
that" instead of guessing. Numbers allowed are the ones in `pitch.md`; nothing else.

---

### 1. Did you use labels?

**The pipeline does not need any.** It learns the store's look from unlabelled pictures: patch
clusters for stock, CLIP zero-shot for the product. To *measure* it, and to lightly calibrate it, we
built a 1,240-area answer key with independent AI labellers (3 votes per area on 3 cameras, 94% unanimous; a second AI, Gemini, agreed with 100% of the wrong-product calls it re-checked). Small
heads on top of the same features are fitted on that key, and the submission uses them. Without the
heads the pipeline still runs, but it scores lower on our key. We never had the hidden validation set.

### 2. How do you know the score will hold on the hidden set?

**We do not know; we estimate, and we tried hard not to flatter ourselves.** Every number we quote
is on frames the model was not fitted on: 1.30 points per area on the last two frames of each camera (the hidden frames are
later in the day than every labelled one), 1.40 on the last frame, 1.25 when a whole camera is held
out. Times 289 areas that is about 360 to 400 of 578. Two caveats we say out loud: the key is
AI-labelled, not the store's truth, and our first unsupervised model's stock thresholds were tuned
on the same labels, so we ignore its in-sample score. Sanity check: the always-compliant + always-full baseline scores 0.70 per area over the whole key,
but only 0.36 on the last two frames and 0.06 on the last frame, because shelves empty late in the day.

### 3. Why not train an object detector?

**Nobody can label boxes for loose, piled fruit at store scale, and the task is not about boxes.**
Counting bananas in a pile is subjective even for people, and the brief says nobody can label every
image on thousands of cameras. The score is per area: right product, and empty / half / full. A fill
level is more robust than a count of overlapping fruit. We still show boxes, from the free
open-vocabulary detector OWLv2, because they help staff trust the answer; they are a UI feature,
not the scored output.

### 4. What about hands, shoppers, baskets (occlusion)?

**We look only at what is visible, and we do not raise alarms we cannot support.** Every area crop
carries a mask of the visible pixels, and fill is computed on the visible patches only. An area that
is empty, occluded or barely visible counts as compliant, because nothing wrong is shown. Hands and
baskets are never drawn as products. The honest limit: a large occluder over most of an area makes
the stock estimate for that picture rougher, and we have not measured by how much.

### 5. What happens when the planogram changes?

**Edit the planogram file; the product side follows.** Product names from the catalogue become CLIP
prompts, so a new product needs no new training images. The stock side looks for "container versus
product", which does not depend on which product it is; re-running the label-free fit refreshes it.
We also do not trust the planogram as a description of the shelf (it is broken even at opening, see
camera 6215), only as the thing to compare against.

### 6. How fast is it, and what does it cost?

**About 26 seconds for 14 frames on a laptop CPU (about 1 minute with detection boxes), and no running cost.** All models are free open weights
(CLIP, DINOv2, OWLv2); there are no paid APIs and no keys. A free Colab GPU speeds up the first
feature extraction. The optional detection boxes are the slow part, about 8 seconds a frame on CPU,
and only for the frames the app shows.

### 7. Would it scale to 100 stores?

**Yes in design, with one honest condition.** Nothing needs labelling to switch a store on, no new
hardware is needed, and predicting works picture by picture, so more stores means more machines
running the same command; the dashboard is a static page per store. The condition: our calibration
heads were fitted on this store. The leave-one-camera-out result (1.25 points per area) shows they
transfer to a camera they have not seen; for a very different store we would re-check on a small
labelled sample before trusting the stock levels. We have not measured another store.

### 8. What are the failure modes?

**Half versus full is the hard boundary, and variety-level product confusion.** "Half" is
subjective, and our labellers disagreed most there: in the first labelling round (393 areas) all
three agreed on 84% of the "half" areas, against about 94% to 96% for "empty" and "full".
CLIP is strong at base-fruit level (banana versus orange) and weak between varieties (Gala versus
Fuji), so we flag a wrong product only when the evidence is clear. Unusual containers can shift the
fill estimate, which is what the optional calibration is for. When we are wrong on stock we want to
be wrong on the cheaper side.

### 9. Why do you lean low on stock?

**Because the scoring is asymmetric.** Answering too high costs 3 points (the shelf runs empty
unseen), too low costs 2. Take an area where we think it is half or full with equal chance. Saying
"half" has expected score 0.5 x 1 + 0.5 x (-2) = -0.5; saying "full" has 0.5 x 1 + 0.5 x (-3) =
-1.0. So we answer "half". For every area we pick the answer with the best expected score, using the
challenge's own rules, and we always answer: a missing area would cost -2 and -3.

### 10. Why only base-fruit level for compliance? Isn't that cheating the planogram?

**It matches what staff can act on, and it avoids false alarms.** A false alarm sends staff to a
shelf with nothing to arrange, which costs 2 points and, in a real store, trust. Banana versus orange
errors are the ones that confuse customers and prices; telling two apple varieties apart from a
ceiling camera is something we would only claim with strong evidence. So we split the two: base
fruit decides, variety needs a clear margin.

---

## Lightning round

- **Camera moved?** Cameras are fixed; the planogram areas are drawn per camera. If one moves, its
  areas need redrawing.
- **Is the app tied to the internet?** No. It is a static page and opens from a file or a USB stick.
- **Languages?** English and Portuguese toggle; product names come from the catalogue.
- **What would you do with another week?** Forecast restocking from the per-area timeline (the
  "empty in about N minutes" warning is the seed), and label a small sample from a second store.
- **Who labelled the key?** Independent AI labellers, three votes per area; not people, not the
  store.

# Junction submission text: Fresh Eyes

Ready to paste into the Junction project form. Every number below comes from a file in the repository
(`results/`, `data/labels/`, `pitch/pitch.md`, "Numbers you may say"). If a form field has a length limit, use the
short versions first. Do not paste anything that is not in this file without checking it against `pitch/pitch.md`.

**Before you paste:** push the latest files to GitHub first (the links below point at it), and check the form for
required fields this page does not cover (demo video, slides, track or challenge name). Do not upload any store
picture: they are Sensei's data, and `pitch/slides_standalone.html` and the staff-app screenshots contain them.

---

## Fields

| Field | Text |
|---|---|
| Project name | **Fresh Eyes** |
| Team | **QuantumLotus**: Sérgio Kuts Pires, Inês Matias Medeiros |
| Challenge | Sensei: "Fresh eyes on fresh produce" |
| Tagline (short) | Your ceiling cameras, turned into a produce restock list. |
| GitHub | https://github.com/sergiokutspires/junctionx-2026 |

## One-liner

Fresh Eyes turns ceiling-camera pictures into a staff to-do list for the produce shelf: restock, swap back, or leave alone.

## Description (about 150 words)

Fresh Eyes reads the fruit and vegetable shelf from the ceiling cameras Sensei already has. For every planogram
area in every picture it answers the brief's questions: is the right product there, and is the area empty, half or
full? A static staff app turns the answers into a Portuguese phone to-do list: Repor (restock), Trocar (swap a wrong
product), Deixar (leave alone), each with the time of the picture and how sure the system is. It runs on one CPU
core with free open models (CLIP and DINOv2): no GPU, no paid API, about five cents per 1,000 images. The core
needs no labels; an optional answer key made by AI models lifts late-day accuracy. Our scores are measured on
that AI-made key, not on Sensei's hidden annotations. The same pictures also feed a one-day prototype of early
warnings before a shelf runs empty.

## How it works

1. **Cut out every area.** Each planogram area (a perspective four-sided zone, sometimes partly outside the
   picture) becomes a 224x224 crop with a mask of the visible part.
2. **Stock, with no labels.** DINOv2-small patch features are clustered; clusters that appear under every
   product are crate or tray ("surface"), the rest are produce. The product share of the area, ranked against the
   whole day, gives empty, half or full.
3. **Product, with no labels.** CLIP B/16 compares the crop with the store's catalogue (Portuguese names
   translated to English) and flags a wrong product only when the evidence is clear.
4. **Optional calibration.** One small stock head plus a per-area memory of AI-made labels from earlier the same
   day, fitted on an answer key of 1,962 areas (181 frames, 14 cameras, three AI votes per area, two for 36 areas). Product
   recognition stays zero-shot.
5. **Decide and deliver.** The answer with the best expected score under the challenge's own rules (it leans
   towards "less stock", because "too high" costs -3 and "too low" -2). Every area is always answered; the
   `predictions.json` is re-read and checked, and an offline staff app is built from it.

## Results (measured, and what they do not show)

Held-out points per area (maximum 2), against our own AI-made answer key. Each test refits the calibration
without the held-out cameras or frames.

| | Unseen cameras (1,962 areas) | Last two frames (304) | Last frame (152) |
|---|---:|---:|---:|
| **Fresh Eyes, calibrated** (the submission model) | **1.23** | **1.41** | **1.48** |
| Fresh Eyes, no labels at all | 1.18 | 0.99 | 0.88 |
| Baseline: always "compliant" and "full" | 0.76 | 0.46 | 0.18 |

Plain-text version: calibrated 1.23 / 1.41 / 1.48; no labels 1.18 / 0.99 / 0.88; always-full baseline
0.76 / 0.46 / 0.18 (unseen cameras / last two frames / last frame).

- **What the staff would see (unseen cameras).** 181 of the 182 empty areas reach the to-do list; 2 false
  wrong-product alarms in 1,845 correct areas.
- **Weak spots.** On a camera the model has never seen it finds only 31 of 117 wrong-product areas, and stock level
  is right on 82 to 86% of areas (half versus full is the hard call).
- **Estimate for Sensei's hidden set (289 areas, maximum 578):** about 355 to 430 points calibrated and about
  255 to 285 with no labels. These are multiplications of the rows above, not measurements. The upper end assumes
  the hidden pictures are late in the day, which we infer from one example file name in the brief and have not
  confirmed. The 320 in the brief is a worked scoring example, not a benchmark.
- **Why to be careful.** The answer key is AI-made (a second AI family agreed with it on 81% of stock levels), its
  thresholds were chosen while looking at it, and the late-frame rows hold only 152 and 304 areas with no confidence
  intervals. We have not seen Sensei's annotations.
- **Evidence:** `results/` (score and cost files), `docs/LABELLING_GUIDE.md` (how the key was made),
  `docs/HOW_IT_WORKS.md` (method, limits, commands).

## Cost

- **About 3.8 CPU-seconds per image on one core** (3.765, median of three runs; no GPU), which is
  **about $0.00005 per image, or 5 cents per 1,000 images**, at $0.0446 per vCPU-hour (AWS c7i.large, on-demand).
- **About 300 times cheaper** than asking Claude Sonnet 5.5 about each image with the same two pictures our
  labellers saw (about $0.014 per image). This is a cost ratio at list prices, not an accuracy comparison.
- A 14-camera produce section, one picture per camera every 5 minutes for 14 hours a day, is about 70,560 images a
  month: about $3 a month.
- Caveats: measured on one core of an AMD Ryzen AI 7 350 laptop that runs bf16 natively (without it expect about
  5.2 CPU-seconds); a cloud vCPU may be slower. The optional product boxes in the staff app add 15.7 CPU-seconds
  per image.

## Tech stack

- **Models (free, open, run locally):** CLIP ViT-B/16 (`openai/clip-vit-base-patch16`), DINOv2-small
  (`facebook/dinov2-small`), OWLv2 base for optional product boxes (`google/owlv2-base-patch16-ensemble`).
- **Python:** PyTorch (CPU, bf16), Hugging Face Transformers, scikit-learn, NumPy, OpenCV, Pillow.
- **Staff app:** one static page in plain HTML, CSS and JavaScript (no framework, no server, no internet), in
  Portuguese with an English toggle, works on a phone.
- **Quality:** pytest (187 tests), ruff, a format check on every `predictions.json`, SHA-256 fingerprints of the
  shipped models (`results/model_manifest.json`).
- **Answer key and tooling:** AI labellers (Claude Opus 5.5 and Claude Sonnet 5.5, three votes per area,
  disagreements settled by Opus 5.5; Gemini Flash as an independent check). Windows launcher `SUBMIT.bat`,
  free Google Colab notebook.
- **Built with** AI coding assistance (Claude Code).

## What's next

1. **Score on Sensei's validation annotations** as soon as they are available, and replace our AI-key estimates
   with the real figure.
2. **A four-week shadow pilot:** one silent week at Leiria against Sensei's restock logs, then a second store. This
   is the test our numbers cannot give: a second store, and real restock outcomes. The pass criteria we propose
   (at least 95% of empty shelves caught, at most 1 wasted restock walk in 10) are targets, not results.
3. **Fix the weak spots:** wrong products on a new camera, and half versus full for large fruit in deep crates.
4. **Check the counts:** the "about N visible units" estimates have never been compared with a hand count.
5. **Plug into Sensei's stack** as area events (area, state, confidence, since) fed by the frames and alerts Sensei
   already has. This is a design; the connector is not built.
6. **From one day to a store:** forecasting, sales speed and the freshness watch are a one-day prototype; they need
   weeks of data and Sensei's sales and waste records to be validated.

## Limits we state up front

- The answer key is AI-made; all scores are measured against it, not against Sensei's hidden annotations.
- The calibrated late-day scores depend on same-day AI labels and on an assumption about when the hidden pictures
  were taken. With no labels: 0.88 to 1.18 points per area.
- "Empty counts as compliant" is our reading of the brief; the brief does not say.
- One store, one day. The dataset is Sensei's and is not in the repository; no store picture is published.

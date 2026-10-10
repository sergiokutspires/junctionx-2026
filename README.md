# Sensei shelf monitor

JunctionX Lisbon 2026, Sensei challenge ("Fresh eyes on fresh produce"). From ceiling-camera pictures of a
supermarket fruit and vegetable section and its planogram, it answers for **every planogram area of every
image**: is the product on display the one the planogram expects (`planogram_compliant`), and how much is
there (`stock_level` empty / half / full, `stock_value` 0 / 0.5 / 1). It also builds a static staff app: a
prioritised "Do now" list, a gondola view with product boxes and visible-unit counts, and an Insights tab
(running out soon, sales speed, planogram adherence). The core pipeline is **unsupervised**: it needs no
labels to fit, and everything is free and local (Hugging Face weights, CPU is enough, CUDA is used if present,
no paid APIs). A 1,240-area answer key written by independent AI labellers is used to **measure** it and to
lightly **calibrate** two small heads on top (see Results). Held out, it scores 1.25 to 1.40 points per area
(maximum 2); the hidden validation set is the real judge.

## Validation day

When the organisers hand over the hidden images (a folder, a `.zip`, nested or flat), run **one** command:

```powershell
SUBMIT.bat "D:\path\to\validation.zip"      # or double-click it, or drag the folder / zip / image files onto it
.venv\Scripts\python -m sensei submit --images <folder or .zip> [--model models/real_v1_cal] [--out submission] [--no-detect]
```

It unpacks zips (junk like `__MACOSX` skipped), predicts every area of every image, re-reads the written JSON and
checks it independently (all areas of each camera exactly once, valid `planogram_compliant` / `stock_level` /
`stock_value`, every image answered, no mass fallbacks), then builds the staff app with local OWLv2 boxes
(`--no-detect` skips them; a detection failure never blocks the submission).

- Look for `SENSEI SUBMISSION CHECK: PASSED` and **`HAND IN THIS FILE: ...\submission\predictions.json`**;
  the staff app is `submission\dashboard\index.html`. Exit code 0 = passed, 1 = file written but invalid
  (read the `ERROR` lines, do not hand it in), 2 = no usable input (nothing written, old results removed).
- Expect 26 images / 289 areas; a different count only prints a warning. Needs no internet when the
  Hugging Face weights are cached (they are on this laptop). Rehearsal: `SUBMIT.bat data\val_sim`.
- The output folder ignores itself in git (public repo: never commit store images or answers).

## Results

Scored with the challenge rules (`scoring.py`): identification +1 right / -2 wrong, stock +1 right / -2 too low /
-3 too high, so the maximum is **2 points per area**.

| Held-out test | Areas | Points per area (max 2) |
|---|---:|---:|
| Unseen cameras (leave one camera out) | 756 | **1.25** |
| Last two labelled frames of every camera | 304 | **1.30** |
| Last labelled frame of every camera | 152 | **1.40** |
| Baseline: always "compliant" and "full" | 756 | 0.70 |

### Cost per image (Sensei's resource-efficiency criterion)

Measured with `tools/benchmark_cost.py` (no feature cache; model loading excluded, ~6 s once per process):

| Setup | Wall time per image | CPU-seconds per image | Peak RAM |
|---|---:|---:|---:|
| 1 CPU core (`SENSEI_THREADS=1`), all ~11 areas of a frame | 5.5-7.1 s | **5.6-7.0** | 1.1 GB |
| 16 threads (fast, less efficient) | 1.4 s | 18.2 | |
| Optional OWLv2 product boxes (staff app only, 1 core) | +15.9 s | +15.5 | |

At ~$0.045 per vCPU-hour (AWS c7i.large on-demand, $0.0892/h for 2 vCPU, us-east-1) that is **~$0.00009 per
image analysed** (~$0.09 per 1,000), or ~$6 a month for a 14-camera section at one picture per camera every
5 minutes for 14 hours a day (a third of one core). No GPU and no paid API are needed. Bigger models (CLIP-L,
SigLIP, DINOv2-base) were tested and did not score better, so the small ones ship.

How to read it, and what it is **not**:

- **The answer key is AI-labelled, not the store's truth.** 1,240 areas over 115 frames of the 14 cameras
  (`data/labels/teacher_labels*.json`) labelled by independent AI labellers (three votes per area on 3 cameras, 94%
  unanimous; one vote elsewhere); 72 of the 1,240 areas show a wrong product. The scores above are measured on the
  original 756-area part of the key so they stay comparable; heads are trained on the rest of each fold. It ranks models and calibrates the heads; it cannot replace the hidden
  annotations, so every number here is an estimate.
- **The core pipeline is unsupervised.** Patch clustering, product recognition and the decision rule never see a
  label at fit time. The labels are used (a) to measure, and (b) to fit two small heads (stock, compliance) on
  top of the same features, refitted without the test cameras or frames in each of the three scored rows. The unsupervised
  part's defaults (thresholds, priors) were chosen while looking at this same key, so the rows are optimistic to
  that extent.
- **Late frames matter most.** The hidden frames are later in the day than every labelled one, so the "last
  frames" rows are the closest rehearsal. Times the 289 hidden areas that is roughly 360 to 400 of 578 points
  (the brief's worked example scores 320).
- **The baseline is the generous figure.** On the last two frames and on the last frame, answering "compliant" and
  "full" everywhere scores only 0.36 and 0.06, because shelves empty out during the day.
- On the unseen-camera and last-two-frames tests identification is right on 98% and 99% of areas and stock
  level on 81% and 82%: stock level is the weaker half.

The shipped model is `models/real_v1_cal` (unsupervised model plus heads fitted on all 1,240 labelled areas). Choose
models only on the late-frame fold of `calibrate` (the `[time]` block of `models/<m>/calibration_cv.json`). Per-camera
numbers are in that file.

## How it works

```
 ceiling frame + planogram.json
            |
            v
 warp every planogram area (perspective quad -> 224x224 crop + visibility mask)
            |
            +--> DINOv2 patch features -> clusters, named by CLIP as "surface"
            |    (crates, trays: same under every product) or "product"
            |    -> fill = share of product patches -> p(empty / half / full)
            |
            +--> CLIP zero-shot at base-product level (banana vs orange vs apple)
            |    -> p(compliant)
            v
 cost-aware decision from the scoring rules (best expected score, leans low)
            |
            v
 predictions.json: every area of every image  <-- the submission
            |
            +--> OWLv2 open-vocabulary detections -> product boxes + visible-unit counts
            v
 staff dashboard (static page): Do now | Gondolas | Products | Insights
```

1. **Crops.** Each planogram quad (a perspective trapezoid, sometimes partly outside the frame) is warped to a
   224x224 crop, shrunk slightly to avoid neighbours, with a mask of the visible part.
2. **Stock (fill).** DINOv2 patch features are clustered. Crates, trays and boxes look the same under every
   product, so clusters spread over many products are "surface" and product-specific clusters are "product"
   (CLIP prompts help name them). Fill is the share of visible patches that are product, normalised per area over
   the day; soft ordered thresholds in rank space give p(empty), p(half), p(full).
3. **Product recognition (compliance).** CLIP zero-shot. Portuguese product names are translated to English
   ("MACA GALA KG" becomes "gala apple") and turned into prompts such as "a photo of a pile of gala apple in a
   supermarket". A crop is scored against the whole catalogue, mainly at the base-fruit level, with image
   prototypes as supporting evidence. The planogram is often not followed in the real data, so an area's own
   history is not trusted as a reference. Variety-level confusions (Gala vs Fuji) need strong evidence. Empty,
   occluded or barely visible crops count as compliant, because nothing wrong is shown.
4. **Cost-aware decisions.** The answer with the best *expected* score under the scoring rules: compliance
   threshold 0.5, stock via `scoring.best_stock` (leans low, because too high costs -3 and too low costs -2).
   Every area is always answered, because a missing area costs -2 and -3.
5. **Optional calibration.** A few self-labelled crops (`label`, then `calibrate`) fit cost-sensitive heads on top
   of the same features, with a cross-validated challenge score. Without labels the pipeline is unchanged.
   Time-neighbour smoothing is off by default (`smoothing_weight = 0`); the per-area time series only feeds the
   dashboard timeline, the "empty in ~N min" forecast and the Insights tab.
6. **Boxes and counts.** OWLv2 (free, local) finds products in each frame. Boxes with score of at least 0.28 are
   drawn; for counting, boxes with score of at least 0.20 whose centre is inside an area are merged (IoU 0.5),
   hands, baskets, shelf-sized boxes and specks are dropped, and in areas the stock model calls empty only boxes
   of at least 0.35 count. The app shows "about N visible units" (visible packs for packaged products) per
   area and per product, always labelled as an estimate.
7. **Insights tab** (all computed from the day's fill timeline):
   - *Running out soon*: low or wrong-product areas forecast to be empty within 2 hours, soonest first (the same
     rule as the "Do now" forecast, so the two never disagree).
   - *Sales speed*: per product, the average share of a shelf lost per hour; sharp rises count as restocks and are
     listed, tiny drops as noise; plus a store-wide bar chart by hour.
   - *Planogram adherence*: share of compliant areas per gondola, gondolas with a wrong product first.
   - Peak-hour highlights appear only when a window is clearly above the product's daily average.

A `lite` backend (handcrafted colour features only, no torch) exists for tests and quick checks.

## Run it

### Windows setup (CPU is enough)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest tests -q                      # lite backend, 154 tests, under a minute
```

The deep backend downloads `openai/clip-vit-base-patch16`, `facebook/dinov2-small` and (for boxes)
`google/owlv2-base-patch16-ensemble` on first use (free, cached afterwards). On Linux or macOS use
`.venv/bin/python` instead of `.venv\Scripts\python`.

**Data and models are not in this repository, on purpose** (the dataset is Sensei's store footage; see
`.gitignore`). Put the dataset in `data/raw/planogram.json` and `data/raw/images/<camera_id>/<unix_ts>.jpg`
(train and test images mixed in one folder, so every image is used to fit), then build the model:

```powershell
# the submission model: unsupervised fit on every image + calibration heads from the answer key
.venv\Scripts\python -m sensei fit --data data/raw/images --planogram data/raw/planogram.json `
    --model models/real_v1_cal --labels data/labels/teacher_labels.json
# without --labels you get the pure unsupervised model
```

Then use `SUBMIT.bat` (see Validation day). Other one-liners:

```powershell
# fit on the dataset, predict, build the dashboard in one go (model goes to outputs\model)
.venv\Scripts\python -m sensei run --data data/raw/images --planogram data/raw/planogram.json `
    --images data/raw/images --out outputs
# local challenge score when you hold annotations in the same format
.venv\Scripts\python -m sensei score annotations.json predictions.json
```

### Free Google Colab

Open `colab/sensei_colab.ipynb` in Colab and choose **Runtime > Change runtime type > T4 GPU**. Put these in
`MyDrive/sensei/`: `junctionx-sensei.zip` (make it with `python colab/make_zip.py`, which uses forward-slash paths
and leaves out `.venv`, `cache`, `outputs`; do not use PowerShell `Compress-Archive`), `Frutas e Legumes (train &
test).zip`, `planogram.json`, and optionally `validation.zip`. Run the cells top to bottom: they mount Drive, unpack
everything into `data/raw/images/<cam>/<ts>.jpg`, install `requirements.txt`, run `python -m sensei run --labels
data/labels/teacher_labels*.json` (the same recipe as `models/real_v1_cal`), predict on the validation folder when
given, and zip `outputs/` back to Drive. No paid tier and no keys; a GPU only speeds up the first feature extraction.
`colab/sensei_bigfeatures.ipynb` computes large-model features and OWLv2 detections for every frame on a free T4
(about 10 minutes) and downloads `sensei_colab_features.zip`; keep that zip in `cache/colab/` and pass it as
`--detections` below.

### Command line

All commands are `python -m sensei <command>`:

| Command | Purpose |
|---|---|
| `submit --images <folder\|.zip\|files> [--model models/real_v1_cal] [--out submission] [--no-detect] [--detections <zip\|json>]` | validation day: unpack, predict, check, build the staff app |
| `synth --out data_synth [--cameras 4 --images 40]` | write a synthetic dataset for tests and demos |
| `fit --data <root> --planogram <planogram.json> --model models/m1 [--backend lite\|deep] [--max-images-per-camera N] [--labels ...]` | learn everything from the unlabelled images |
| `predict --model models/m1 --images <dir> --out predictions.json [--details details.json]` | answer every area of every image in `<dir>` |
| `score annotations.json predictions.json` | local challenge score against truth |
| `dashboard --details details.json --data <root> --out dashboard/ [--detections <zip\|json>] [--detect]` | build the static staff dashboard |
| `label --model models/m1 --data <root> --out labeling/ [--n 150]` | export contact sheets and a labelling page (optional) |
| `calibrate --model models/m1 --labels labels.json` | fit heads from labels and report a cross-validated score (optional) |
| `run --data <root> --planogram ... --images <dir> --out outputs/` | fit, predict and build the dashboard in one go |

`-q` (warnings only) works before or after the sub-command. `fit` and `run` also accept `--labels labels.json [...]`
(annotation format) to fit the calibration heads right after fitting; `predict` then uses `<model>/heads/`
automatically. Tunables (crop size, inset, number of patch clusters, priors, device, CLIP and DINO model names)
live in `sensei/config.py`.

### Predict by hand and open the dashboard

`submit` does all of this; the manual steps are:

```powershell
.venv\Scripts\python -m sensei predict --model models/real_v1_cal --images data/val `
    --out predictions.json --details details_val.json
.venv\Scripts\python -m sensei dashboard --details details_val.json --data data/val --out dashboard `
    --detections cache/colab/sensei_colab_features.zip
start dashboard\index.html
```

- Images: preferably `data/val/<camera_id>/<unix_ts>.jpg`; `<camera_id>_<ts>.jpg` and a flat folder of `<ts>.jpg`
  also work (the camera is then recognised from the picture, since the ceiling views are static). `predict` exits
  with code 2 and writes nothing if no image matches a camera. Keys in `predictions.json` are `<unix_ts>.jpg`
  (the annotation format), plus the on-disk name when it differs.
- `predictions.json` is `{camera_id: {image_name: {area_id: {"planogram_compliant": true, "stock_level": "half",
  "stock_value": 0.5}}}}` with every planogram area of every image (unreadable images get a safe fallback answer
  instead of a crash). With heads, frames later than a camera's last labelled frame get the late-day stock prior,
  and areas whose latest labelled frame was a wrong product stay flagged while the crop still looks the same.
- The dashboard is a static page: no server, no build step, no network, so it also opens from a USB stick or a
  phone. Counters (Empty / Low / Wrong product / OK), a "Do now" list (wrong product and empty first, then low),
  a gondola view with coloured area polygons and a fill sparkline, a per-product view, the Insights tab, an EN/PT
  toggle, light and dark mode, from 375 px wide. `--data` must be the folder holding the images in `details.json`.
- **Boxes and counts** need detections: `--detections` takes the cached `owl_detections.json` (inside the Colab
  features zip, or that json), or `--detect` runs OWLv2 locally on the shown frames that have none (a few seconds
  per frame on CPU; about 4 s measured for the 14-camera dry run). Without either, the **Show detections** button
  and the visible-unit counts do not exist. Only the latest frame of each camera is shown, so only those frames
  need boxes. `DET_*` and `COUNT_*` constants in `sensei/dashboard.py` hold the thresholds. A link such as
  `index.html#/gondola/6491/6491_1/det` opens a gondola with the boxes already on; `index.html#/insights` opens
  the Insights tab.

Synthetic data for tests and demos: `python -m sensei synth --out data_synth` writes `planogram.json`,
`images/<cam>/<ts>.jpg`, `val/<cam>/<ts>.jpg`, `annotations.json` (truth for `val`) and `annotations_train.json`.
Fit on `data_synth/images` and predict on `data_synth/val`; do not fit on `data_synth` itself.

## Repository layout

```
README.md  SPEC.md  requirements.txt
SUBMIT.bat                    validation day: double-click, or drop a folder / zip / images on it
scoring.py, test_scoring.py   local scorer and decision rules (do not change the maths)
sensei/                       the package
  config.py data.py products.py features.py stock.py compliance.py temporal.py
  pipeline.py calibrate.py dashboard.py submit.py synth.py __main__.py
ui/                           static dashboard assets (index.html, app.js, style.css) copied by dashboard.py
colab/                        free Colab notebooks (sensei_colab.ipynb, sensei_bigfeatures.ipynb) and make_zip.py
tests/                        pytest suite (lite backend; the deep smoke test is marked slow)
data/labels/                  the AI-labelled answer key (annotation format, no images)
labeler/, tools/              labelling page and the scripts that rendered sheets for the AI labellers
pitch/                        3-minute pitch: slides.html, pitch.md, demo_script.md, qa_prep.md, build scripts
docs/brief.txt                text of the challenge brief
SPEC.md                       build contract: module signatures, file formats, real-data facts

not in the repo (git-ignored): data/raw (the dataset), data/val_sim, models/, cache/, outputs/, experiments/,
backups/, every .jpg/.png/.zip, pitch/assets pictures and pitch/slides_standalone.html
```

The deck in `pitch/` shows store frames and dashboard screenshots from a local `pitch/assets/` folder that is not
published; the deck source is.

## Limitations

- **Half versus full is the hard call**, especially for large fruit in deep crates, where a top-down view cannot see
  how deep the pile is. Stock level is right on about 80% of held-out areas, identification on 97 to 99%.
- **Counts are visible-unit estimates**, not inventory: boxes only see what is on top, piles hide items, and for
  produce that comes in bunches one "unit" can be a bunch (bananas). The app says "estimate" wherever it shows one.
- **One day of data** from one store: the sales-speed, peak-hour and "running out soon" figures come from a single
  day's timeline of fill estimates and are a prototype of forecasting, not a scored feature.
- **The answer key is AI-labelled** (not the store's truth) and was also used to choose defaults; expect the hidden
  set to differ from the held-out numbers above.
- Zero-shot recognition is strong at the base-fruit level and weak between varieties, so the system only flags a
  wrong product when the evidence is clear. Portuguese-to-English translation is dictionary based; unknown words
  are kept as variety words.
- Stock depends on how crates and products look; unusual containers can shift the fill estimate, which is what the
  optional calibration step is for.
- Store images, models and outputs are deliberately not published, so a fresh clone needs the dataset and a fit
  (above) before it can predict.

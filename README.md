# Sensei shelf monitor

JunctionX Lisbon 2026, Sensei challenge. From ceiling-camera images of a supermarket fruit and
vegetable section, it answers for **every planogram area of every image**:

- `planogram_compliant`: is the product on display the one the planogram expects?
- `stock_level`: `empty`, `half` or `full` (`stock_value` 0, 0.5, 1).

It also builds a static dashboard that tells a store employee in seconds what to restock first,
what to move back and what to leave. Everything is free and local: Hugging Face weights, CPU
works, CUDA is used if present (for example on free Google Colab). No labels and no paid APIs are
needed.

## Method (label-free)

1. **Crops.** Each planogram quad (a perspective trapezoid, sometimes partly outside the frame) is
   warped to a 224x224 crop, shrunk slightly to avoid neighbours, with a mask of the visible part.
2. **Product recognition (compliance).** CLIP zero-shot. Portuguese product names are translated
   to English ("MACA GALA KG" becomes "gala apple") and turned into prompts such as "a photo of a
   pile of gala apple in a supermarket". A crop is scored against the whole catalogue, mainly at the
   base-fruit level (banana vs orange vs apple), with image prototypes as supporting evidence. The
   planogram is often not followed in the real data, so an area's own history is not trusted as a
   reference. Variety-level confusions (Gala vs Fuji) need strong evidence. Empty, occluded or
   barely visible crops count as compliant, because nothing wrong is shown.
3. **Stock (fill).** DINOv2 patch features are clustered. Crates, trays and boxes look the same under
   every product, so clusters spread over many products are "surface" and product-specific clusters
   are "product". Fill is the share of visible patches that are product, normalised per area over the
   day, then a 3-component ordered Gaussian mixture gives p(empty), p(half), p(full).
4. **Cost-aware decisions.** The answer with the best *expected* score under the scoring rules:
   compliance threshold 0.5, stock via `scoring.best_stock` (leans low, because too high costs -3 and
   too low costs -2). Every area is always answered, because a missing area costs -2 and -3.
5. **Optional calibration.** A few self-labelled crops (`label`, then `calibrate`) fit cost-sensitive
   heads on top of the same features, with a cross-validated challenge score. Without labels the
   pipeline is unchanged. Time-neighbour smoothing is off by default (`smoothing_weight = 0`); the
   per-area time series only feeds the dashboard timeline and the "empty in ~N min" forecast.

A `lite` backend (handcrafted colour features only, no torch) exists for tests and quick checks.

## Scoring (local copy in `scoring.py`)

Per area: identification +1 right / -2 wrong; stock +1 right / -2 too low / -3 too high. Maximum
2 points per area. A missing area scores -2 and -3.

## Quickstart on Windows

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest tests -q                      # lite backend, a few minutes at most
```

Real data goes in `data/raw/planogram.json` and `data/raw/images/<camera_id>/<unix_ts>.jpg`
(train and test images are mixed in one folder, so every image is used to fit).

```powershell
# one command: fit on the dataset, predict, build the dashboard
.venv\Scripts\python -m sensei run --data data/raw/images --planogram data/raw/planogram.json `
    --images data/raw/images --out outputs

# or step by step
.venv\Scripts\python -m sensei fit --data data/raw/images --planogram data/raw/planogram.json --model models/m1
.venv\Scripts\python -m sensei predict --model models/m1 --images data/raw/images `
    --out predictions.json --details details.json
```

The deep backend downloads `openai/clip-vit-base-patch16` and `facebook/dinov2-small` on first use
(free, cached afterwards). Add `--backend lite` to `fit` to skip torch entirely.

On Linux or macOS use `.venv/bin/python` instead of `.venv\Scripts\python`.

## Quickstart on Google Colab (free)

Open `colab/sensei_colab.ipynb` in Colab and choose **Runtime > Change runtime type > T4 GPU**. Put
these in `MyDrive/sensei/`: `junctionx-sensei.zip` (make it with `python colab/make_zip.py`, which
uses forward-slash paths and leaves out `.venv`, `cache`, `outputs`; do not use PowerShell
`Compress-Archive`), `Frutas e Legumes (train & test).zip`, `planogram.json`, and optionally
`validation.zip`. Run the cells top to bottom: they mount Drive, unpack everything into
`data/raw/images/<cam>/<ts>.jpg`, install `requirements.txt`, run `python -m sensei run --labels
data/labels/teacher_labels*.json` (so Colab builds the same calibrated model as `models/real_v1_cal`),
predict on the validation folder when given, and zip `outputs/` back to Drive. No paid tier and no
keys are needed; a GPU only speeds up the first feature extraction.

## Command line

All commands are `python -m sensei <command>`:

| Command | Purpose |
|---|---|
| `synth --out data_synth [--cameras 4 --images 40]` | write a synthetic dataset for tests and demos |
| `fit --data <root> --planogram <planogram.json> --model models/m1 [--backend lite\|deep] [--max-images-per-camera N]` | learn everything from the unlabelled images |
| `predict --model models/m1 --images <dir> --out predictions.json [--details details.json]` | answer every area of every image in `<dir>` |
| `score annotations.json predictions.json` | local challenge score against truth |
| `dashboard --details details.json --data <root> --out dashboard/` | build the static staff dashboard |
| `label --model models/m1 --data <root> --out labeling/ [--n 150]` | export contact sheets and a labelling page (optional) |
| `calibrate --model models/m1 --labels labels.json` | fit heads from labels and report a cross-validated score (optional) |
| `run --data <root> --planogram ... --images <dir> --out outputs/` | fit, predict and build the dashboard in one go |

`-q` (warnings only) works before or after the sub-command. `fit` and `run` also accept `--labels labels.json [...]` (annotation format, e.g. the teacher labels) to fit the
calibration heads right after fitting; `predict` then uses `<model>/heads/` automatically. `run` stores the model in `<out>/model`.

Tunables (crop size, inset, number of patch clusters, priors, device, CLIP and DINO model names) live
in `sensei/config.py`. A larger free CLIP such as `openai/clip-vit-large-patch14` can be selected there.

## Run on the hidden validation set and make the submission

**Submit with `models/real_v1_cal`** (the unsupervised model plus heads fitted on all teacher labels).
Choose models only on the late-frame fold of `calibrate` (the `[time]` block of
`models/<m>/calibration_cv.json`): the hidden frames are later in the day than every labelled one.
There the calibrated model scores about 1.19 points per area against 0.97 for the unsupervised
`models/real_v1`; the 899/1512 of `real_v1` against the teacher labels is in-sample (its stock
thresholds were tuned on those labels) and must not be used to pick models.

1. Put the validation images in one folder, preferably `data/val/<camera_id>/<unix_ts>.jpg`.
   `<camera_id>_<ts>.jpg` also works, and so does a flat folder of `<ts>.jpg`: the camera is then
   recognised from the picture (static ceiling views). Keys in `predictions.json` are
   `<unix_ts>.jpg` (the annotation format), plus the on-disk name when it differs (e.g. `.JPG`).
2. Predict (the command exits with code 2 and writes nothing if no image matches a camera):

   ```powershell
   .venv\Scripts\python -m sensei predict --model models/real_v1_cal --images data/val `
       --out predictions.json --details details_val.json
   .venv\Scripts\python -m sensei dashboard --details details_val.json --data data/val --out dashboard_val
   ```

   It prints the number of images, cameras, areas (and the expected count), skipped files and
   whether heads were used. With heads, frames later than a camera's last labelled frame get the
   late-day stock prior, and areas whose latest labelled frame was a wrong product stay flagged
   while the crop still looks the same.

3. `predictions.json` is the submission. Its format is
   `{camera_id: {image_name: {area_id: {"planogram_compliant": true, "stock_level": "half", "stock_value": 0.5}}}}`
   and it contains every planogram area of every image (cameras missing from the planogram are
   skipped with a warning, and unreadable images get a safe fallback answer instead of a crash).
4. If you have truth in the same format: `python -m sensei score annotations.json predictions.json`.

## Open the dashboard

```powershell
.venv\Scripts\python -m sensei dashboard --details details_val.json --data data/val --out dashboard
start dashboard\index.html
```

It is a static page: no server, no build step, no network, so it also opens from a USB stick or a
phone. It shows counters (Empty / Low / Wrong product / OK), a "Do now" list ordered by priority
(wrong product and empty first, then low), a gondola view with coloured area polygons and a fill
sparkline, a per-product view, an EN/PT toggle, and works from 375 px wide in light and dark mode.
`--data` must be the folder that holds the images listed in `details.json`.

## Synthetic data

`python -m sensei synth --out data_synth` writes `planogram.json`, `images/<cam>/<ts>.jpg` (a
synthetic day), `val/<cam>/<ts>.jpg` (later frames), `annotations.json` (truth for `val`) and
`annotations_train.json` (truth for `images`). Fit on `data_synth/images` and predict on
`data_synth/val`; do not fit on `data_synth` itself, because the `val` folder would switch on the
train/test/val split filter and hide the unlabelled `images` folder.

## Folder layout

```
scoring.py, test_scoring.py   local scorer and decision rules (do not change the maths)
SPEC.md                       build contract: module signatures, file formats, real-data facts
requirements.txt
sensei/                       the package
  config.py data.py products.py features.py stock.py compliance.py temporal.py
  pipeline.py calibrate.py dashboard.py synth.py __main__.py
ui/                           static dashboard assets copied by dashboard.py
colab/sensei_colab.ipynb      free Colab runner (colab/make_zip.py builds its project zip)
tests/                        pytest suite (lite backend; the deep smoke test is marked slow)
data/raw/                     planogram.json and images/<camera_id>/<unix_ts>.jpg (read-only)
data/labels/                  optional labels in the annotations.json format
models/ cache/ outputs/       fitted models, feature cache, run results (not shipped)
docs/brief.txt                text of the challenge brief
```

## Known limitations

- Zero-shot recognition is strong at the base-fruit level and weak between varieties, so the system
  only flags a wrong product when the evidence is clear.
- Portuguese-to-English translation is dictionary based; unknown words are kept as variety words.
- Stock depends on how crates and products look; unusual containers can shift the fill estimate,
  which is what the optional calibration step is for.

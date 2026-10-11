# Reproducing the submission model

Question: can someone with this public repository and Sensei's dataset rebuild `models/real_v3_cal` and get
the same answers? Answer, checked on 2026-10-11: **yes. The rebuilt model's predictions on `data/val_sim` are
byte-identical to `outputs/rehearsal_0850/predictions.json`** (152 of 152 areas), with or without the
on-disk feature cache.

## Inputs

| Input | Where | In the public repo? |
|---|---|---|
| Code | `sensei/`, `scoring.py`, `requirements.txt` | yes |
| Config | `models/real_v3_cal/config.json` (the `Config()` defaults: deep backend, seed 0, `clip-vit-base-patch16`, `dinov2-small`, bf16) | the defaults are in `sensei/config.py` |
| Labels | `data/labels/teacher_labels_v2.json` | yes |
| Images + planogram | `data/raw/images/<cam>/<ts>.jpg` (181 frames), `data/raw/planogram.json` | no (Sensei's store footage) |
| Weights | `openai/clip-vit-base-patch16`, `facebook/dinov2-small` (free, Hugging Face) | downloaded on first use |

## Commands

The documented build (README, "From a fresh clone", step 3):

```powershell
.venv\Scripts\python -m sensei fit --data data/raw/images --planogram data/raw/planogram.json `
    --model models/<new> --labels data/labels/teacher_labels_v2.json
```

The check does exactly that into `models/repro_check` (never touching the frozen models), predicts
`data/val_sim` and compares:

```powershell
.venv\Scripts\python tools/reproduce_check.py                    # reuses cache/ features: ~50 s
.venv\Scripts\python tools/reproduce_check.py --fresh-features `
    --out models/repro_check_fresh                               # recomputes every CLIP/DINOv2 feature: ~5 min
```

Exit code 0 = identical predictions. It prints the per-file comparison with `results/model_manifest.json` and,
if the predictions differ, every changed area (`camera/image/area: old -> new`).

## Results (laptop CPU, Windows 11, Python 3.14.7, numpy 2.5.3, torch 2.14.1+cpu, transformers 5.19.0, scikit-learn 1.9.1)

| Run | fit | calibrate (+ CV) | predict val_sim | total | predictions |
|---|---|---|---|---|---|
| feature cache reused | 21 s | 25 s | 0.2 s | 46 s | **identical** (0 / 152 areas changed) |
| `--fresh-features` (empty cache), run 1 | 243 s | 26 s | 17 s | 286 s | **identical** (0 / 152 areas changed) |
| `--fresh-features` (empty cache), run 2 | 230 s | 29 s | 16 s | 274 s | **identical** (0 / 152 areas changed) |
| cache, single-threaded (x2), `--no-cv` | | | 0.2 s | 23 s, 26 s | **identical** (0 / 152 areas changed) |

Seven rebuilds in total (2 with fresh features, 3 from the cache, 2 single-threaded), **all seven gave
predictions byte-identical to the rehearsal**. The model *files*, however, are not always bit-identical, and
the reason is known:

* **Always identical:** `config.json`, `planogram.json`, `compliance.json/.npz`, `cam_thumbs.npz`, the
  CLIP/DINOv2 feature arrays in `fit_feats.npz` (every float, also when recomputed from the images), and
  `model.json` apart from the wall-clock `fit_seconds`.
* **Cause of the differences: the multithreaded k-means of the stock model's patch coder**
  (`sensei/stock.py`, `PatchCoder`: randomized PCA + `KMeans(n_init=3, random_state=seed)` on DINOv2
  patch tokens). The seeds are fixed, but the threaded BLAS/OpenMP sums run in a different order each time,
  so the 24 x 48 cluster centres move in the last float32 bit (seen as at most 6e-8 in 4 of 5 multithreaded
  runs: only `stock.npz` differs, heads, series and the published `calibration_cv.json` are identical).
  In 1 of the 5 multithreaded runs (the second `--fresh-features` run) that tiny difference tipped k-means
  into a slightly different solution: 40 of the stored patch codes changed, and with them the stock
  reference fills (up to 0.016), `series.json`, the heads (coefficients up to 0.01) and the held-out CV
  (`time` scheme 429 -> 426 points). The answers on `data/val_sim` were still identical.
* **Proof:** with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1` two rebuilds are
  bit-identical to each other in every file (deterministic), but they are a different k-means solution from
  the shipped model, which was fitted multithreaded. Their predictions are again byte-identical.
* `fit_feats.npz` also stores each crop's image path as given on the command line; the tool passes the
  relative paths the README uses (stored with backslashes on Windows; on Linux/macOS the separator
  differs, so that file's hash differs there even when every number matches).

So: the submitted answers are reproducible from the public repo + the dataset; the model files are
reproducible to float32 precision, except that threaded k-means occasionally converges to a nearby
solution. For bit-exact rebuilds, set the three thread variables above to 1 (deterministic, about the same
speed here because the k-means is a few seconds) and compare two such runs with each other.

## What would break it

* Different library versions (torch / transformers kernels, numpy BLAS) can move features in the last bits;
  answers near a decision threshold could then flip. Pin with `requirements.txt` and compare with this tool.
* A GPU (CUDA) run computes the features with other kernels; the check above is CPU only.
* Other images or another planogram give another model, by design (the model is fitted to the store's own
  cameras).

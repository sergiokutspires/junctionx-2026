# Sensei shelf monitor: build spec (shared contract for all modules)

Challenge brief: `C:\Users\alifa\Documents\JunctionX 2026\Sensei - JunctionX Lisbon 2026.pdf`
(text extract: `docs/brief.txt`). Read it once if you need context; this spec is the contract.

## 1. What we must produce

For every image of a camera, for **every planogram area of that camera** (never skip one: a missing
area costs -2 and -3), output:

```json
{"<camera_id>": {"<image_name>": {"<area_id>": {"planogram_compliant": true,
                                               "stock_level": "half", "stock_value": 0.5}}}}
```

- `image_name` is the file name exactly as on disk (e.g. `1751052241.jpg`; stem = unix timestamp).
- `stock_level` in {"empty","half","full"} with `stock_value` 0 / 0.5 / 1.
- Scoring per area (see `scoring.py`, already written and tested; DO NOT change its maths):
  identification right +1 / wrong -2; stock right +1 / too low -2 / too high -3.
- Therefore: always answer; compliance threshold 0.5 on p(compliant); stock chosen with
  `scoring.best_stock(p_empty, p_half, p_full)` (expected-score optimal, leans low).
- No labels exist for train/test. The method must be unsupervised / zero-shot. An OPTIONAL
  calibration file of a few self-labelled crops may refine thresholds (section 6), but the
  default path must work with zero labels.
- No paid services. Free local models only (Hugging Face weights, CPU OK; CUDA used if present,
  e.g. free Google Colab).

## 2. Data format (from the brief)

`planogram.json`:
```json
{"Frutas e Legumes": {"cameras": {"6215": {"products": [
  {"area_id": "6215_2", "product_id": "11908", "product_name": "BANANA CAT I CNT KG",
   "image_coordinates": {"top_left": [299,350], "top_right": [464,347],
                         "bottom_right": [479,438], "bottom_left": [331,438]}}]}}}}
```
- 14 cameras, 152 areas. Quads are not rectangles (perspective). Coordinates can be negative or
  beyond the image (area partly outside the frame) -> must be handled (visible mask).
- Same product can be in several areas (count per area, aggregate per product in the UI).
- Names are Portuguese. Ending in `KG` = loose (unit = one fruit). With a weight (`500 G`,
  `EMB. 3KG`) = packaged (unit = one package).
- Images: train / test (no labels, shared) and val (hidden, 26 images, 1-2 per camera, run by us
  on request). One full day of operation. Exact folder layout is UNKNOWN until the dataset
  arrives: support both `<root>/<split>/<camera_id>/<ts>.jpg` and flat
  `<root>/<split>/<camera_id>_<ts>.jpg` / `<root>/<split>/<ts>.jpg` inside a camera folder, any
  depth. Camera id = the nearest path component (dir name) equal to a known camera id, else a
  filename prefix `<cam>_` / `<cam>-`. Split = nearest path component in
  {train, test, val, validation} (validation -> "val"), else "unknown".
- The section key ("Frutas e Legumes") must not be hard-coded; iterate over all sections.

## 2b. FACTS FROM THE REAL DATASET (supersede any assumption above)

- Location: `data/raw/planogram.json` and `data/raw/images/<camera_id>/<unix_ts>.jpg`
  (181 images, 12-14 per camera, 1280x720 JPEG, ~hourly from 1751001155 (06:12 Lisbon) to
  ~1751049846 (19:24)). There are NO train/test sub-folders: train and test are mixed, so every
  image has split "unknown" and `fit` must use all of them. Validation images (hidden, 26) will
  be given to us later in the same `<camera>/<ts>.jpg` layout; the brief's example
  `1751052241.jpg` is LATER than every image we have, so time-neighbour smoothing is weak:
  keep `smoothing_weight` default 0.0 (feature kept for the UI timeline/forecast only).
- 152 areas, 94 distinct products: most products occur in ONE area only, so product
  prototypes are mostly per-area. 5 areas extend outside the frame.
- Product names contain accents (MAÇÃ, LIMÃO, FEIJÃO, CORAÇÃO, ABÓBORA, AVIÃO) and odd
  codes (CAT I, CNT, IGP, IG, R0, A/AA, CAL. 73/85, ZER0%D, S/ GRAINHA, P/ SEMENTES, EMB:.).
  Read the JSON as UTF-8.
- What the scenes look like (verified by eye on several cameras):
  * Containers/surfaces are shared across the whole store: teal/green plastic crates (very
    common), grey metal trays, cardboard boxes, white foam / egg-crate liners, black curved
    banana display. An EMPTY area shows mostly this surface.
  * Products: loose piles (bananas, oranges, apples, tomatoes, mangos, melons, pineapples),
    net bags (oranges, onions), plastic bags/packs (potatoes 3 KG, cherry tomatoes, cherries,
    grapes, kiwis 500 G).
  * THE PLANOGRAM IS OFTEN NOT FOLLOWED, even at the start of the day. Example: camera 6215 at
    06:12, banana areas 3 and 5 hold oranges; at 19:00 citrus areas 7 and 9 hold bananas. So
    an area's own history is NOT a trustworthy reference for "the expected product".
    Compliance must rest on zero-shot product recognition (CLIP text prompts over the whole
    catalog, primarily at the base-fruit level: banana vs orange vs apple vs tomato ...),
    with image prototypes only as supporting evidence. Variety-level confusions (Gala vs Fuji,
    tomato types) are hard: require strong evidence before declaring non-compliance.
  * Morning frames show many empty crates before restocking; stock changes a lot over hours.
  * An empty area counts as compliant (nothing wrong is shown).
- Scale is tiny: ~181 x ~11 = ~2,000 crops in total. Fit can use ALL images
  (`max_images_per_camera` irrelevant), and DINOv2 patch maps for all crops fit in RAM after
  PCA (2000 x 256 x 48 floats). Everything runs on CPU in minutes; CUDA optional.
- A larger CLIP (e.g. `openai/clip-vit-large-patch14`, free) may be selected via config if it
  improves zero-shot; B/16 stays the default and is the one cached.

## 2c. Teacher labels / calibration (planned next step, keep the hooks)

We will later create pseudo-labels for many fit-time crops (empty/half/full + compliant) in
EXACTLY the annotations.json format (`{cam: {image_name: {area_id: {...}}}}`) so `scoring.py`
can score predictions against them. `calibrate` must then (a) fit cost-sensitive heads
(e.g. multinomial logistic regression on [fill features, CLIP, DINO cls]) for stock and
compliance, (b) report a cross-validated challenge score (group by camera AND by time), and
(c) store the heads in the model dir so `predict` uses them automatically when present.
`label` must export contact sheets for review: `labeling/sheets/sheet_###.jpg` grids of
~12 crops (each tile = the warped crop + a short context strip of the original frame region,
with a big tile id, area id and the expected product name in English and Portuguese) plus
`labeling/manifest.json` mapping tile id -> (camera, image_name, area_id).

## 3. Package layout (Python >= 3.10 compatible syntax; must also run on Colab)

```
junctionx-sensei/
  scoring.py            # EXISTS. local scorer + best_stock/best_compliance/make_entry
  test_scoring.py       # EXISTS.
  SPEC.md               # this file
  requirements.txt
  README.md
  sensei/
    __init__.py
    __main__.py         # CLI (python -m sensei ...)
    config.py           # Config dataclass: all tunables + defaults, load/save json
    data.py             # planogram + image discovery + perspective warp
    products.py         # PT->EN translation, catalog, CLIP prompts, loose/packaged
    synth.py            # synthetic dataset generator for tests/demo
    features.py         # model wrappers (CLIP, DINOv2, handcrafted) + batching
    stock.py            # fill estimation + level posterior
    compliance.py       # product identification -> p(compliant), likely product
    temporal.py         # per-area time series, neighbour smoothing, depletion forecast
    pipeline.py         # fit() on train/test, predict() on any images, save/load model
    calibrate.py        # optional: labelling sheet export + threshold fit from labels
    dashboard.py        # builds the static staff dashboard from details.json
  ui/                   # static assets copied by dashboard.py (index.html, app.js, style.css)
  labeler/              # static labelling page (labeler.html) used by calibrate.py
  colab/sensei_colab.ipynb
  tests/                # pytest; must pass on CPU in < 5 min with backend=lite
  docs/brief.txt
```

Environment: `.venv` in the project root already has numpy, pillow, opencv-python-headless,
scikit-learn, torch (CPU), transformers, safetensors, pytest, and the cached weights
`openai/clip-vit-base-patch16` + `facebook/dinov2-small`. Run things with
`.venv/Scripts/python` (Windows). Do NOT pip install other packages; do NOT use paid APIs.

## 4. Module contracts (names/signatures are binding)

### sensei/config.py
```python
@dataclass
class Config:
    backend: str = "deep"            # "deep" (CLIP+DINOv2) | "lite" (handcrafted only, fast, no torch)
    device: str = "auto"             # auto -> cuda if available else cpu
    crop_size: int = 224
    inset: float = 0.06              # shrink each quad towards its centre before warping (avoid neighbours)
    max_images_per_camera: int = 150 # subsample train/test for fit (evenly over time)
    batch_size: int = 32
    clip_model: str = "openai/clip-vit-base-patch16"
    dino_model: str = "facebook/dinov2-small"
    # stock
    n_patch_clusters: int = 24
    pca_dims: int = 48
    level_prior: tuple = (0.15, 0.35, 0.50)   # empty, half, full (used when GMM degenerate)
    # compliance
    compliance_prior: float = 0.93
    # temporal
    smoothing_window_s: int = 300
    smoothing_weight: float = 0.0   # weight of time neighbours vs the frame itself (0 = off, see 2b)
    seed: int = 0
    def to_json(self, path); @classmethod def from_json(cls, path)
```

### sensei/data.py
```python
@dataclass(frozen=True)
class Area:
    area_id: str; camera_id: str; product_id: str; product_name: str; section: str
    quad: np.ndarray        # (4,2) float32 [TL, TR, BR, BL] image px, may lie outside image
@dataclass(frozen=True)
class ImageRecord:
    path: Path; camera_id: str; image_name: str; timestamp: int; split: str  # timestamp -1 if stem not numeric

def load_planogram(path) -> dict[str, list[Area]]          # camera_id -> areas in file order
def discover_images(root, camera_ids, splits=None) -> list[ImageRecord]  # sorted by (camera, timestamp, name)
def subsample_even(records, k) -> list[ImageRecord]        # per camera, evenly spaced in time, keeps first & last
def load_image(path) -> np.ndarray                          # RGB uint8 HxWx3 (cv2 imdecode so unicode paths work)
def inset_quad(quad, frac) -> np.ndarray                    # shrink towards centroid
def warp_area(image, quad, size=224, inset=0.0) -> tuple[np.ndarray, np.ndarray]
    # (crop uint8 (size,size,3), visible bool (size,size)); pixels outside the image -> 0 and visible False
def visible_fraction(quad, image_shape) -> float            # share of the quad inside the frame
```

### sensei/products.py
```python
def parse_name(name: str) -> dict
    # {"raw","english","base","variety","loose": bool,"packaged": bool,"organic": bool}
    # english: best-effort translation, e.g. "BANANA CAT I CNT KG" -> "banana";
    # "TOMATE CHERRY EMB. 250 G" -> "cherry tomato"; "MACA GALA KG" -> "gala apple"
    # Must handle accents present or stripped (MAÇÃ / MACA), uppercase, codes like CAT I, CNT, KG, EMB., UN, BIO.
def prompts_for(name: str) -> list[str]
    # CLIP prompts, loose: "a photo of a pile of {english} in a supermarket", "loose {english} at a grocery store", ...
    # packaged: "packages of {english} on a supermarket shelf", ...
EMPTY_PROMPTS: list[str]   # "an empty supermarket display crate", "an empty shelf", ...
OCCLUSION_PROMPTS: list[str] # "a hand reaching into a shelf", "a shopper's arm", ...
@dataclass
class Catalog:
    products: dict[str, dict]        # product_id -> parse_name(...) + {"areas": [area_ids], "name": raw}
    @classmethod
    def from_planogram(cls, areas_by_cam) -> "Catalog"
```
Translation dictionary should cover ~150 Portuguese produce words + varieties + colours.

### sensei/features.py
```python
@dataclass
class CropFeatures:              # columnar, one row per (image, area)
    keys: list[tuple[str, str, str]]   # (camera_id, image_name, area_id)
    timestamps: np.ndarray       # (N,) int64
    visible: np.ndarray          # (N,) float32 visible fraction of the warped crop
    hand: np.ndarray             # (N, H) float32 handcrafted descriptor (always present)
    clip: np.ndarray | None      # (N, Dc) float32 L2-normalised (deep backend)
    dino_cls: np.ndarray | None  # (N, Dd) float32 L2-normalised
    patch_codes: np.ndarray | None # (N, G*G) int16 patch cluster ids, filled by stock model (-1 = not visible)
    def subset(self, idx) -> "CropFeatures"; def save(path); @classmethod def load(path)

def handcrafted(crop, visible) -> np.ndarray   # HSV histogram (e.g. 8x4x4 normalised) + sat/val stats + edge density + "colourfulness"
class Extractor:
    def __init__(self, cfg: Config)
    def clip_image(self, crops: list[np.ndarray]) -> np.ndarray      # (N,Dc) L2
    def clip_text(self, texts: list[str]) -> np.ndarray               # (T,Dc) L2
    def dino(self, crops) -> tuple[np.ndarray, np.ndarray]            # (cls (N,Dd) L2, patches (N,G,G,Dd) L2 per patch), G=16 at 224
    logit_scale: float
# Extractor must lazy-import torch/transformers so backend="lite" works without them.
# Preprocessing done manually in numpy/torch (resize already 224; CLIP mean/std; DINO ImageNet mean/std).
# torch.set_num_threads(os.cpu_count()) on CPU; inference_mode; batches of cfg.batch_size.
```
Memory rule: never keep all DINO patch maps of the train set in RAM. Patches are consumed
batch-by-batch: `stock.PatchCoder` turns them into cluster codes (`patch_codes`).

### sensei/stock.py
Idea (unsupervised): crates/shelves look the same under every product, products do not.
1. `PatchCoder.fit(patch_sample (M,Dd), product_ids_of_each_patch (M,), visible (M,))`:
   PCA -> `pca_dims`, KMeans (`n_patch_clusters`). For each cluster compute the entropy of its
   distribution over product ids (normalised by log(#products)) and its spread over areas.
   Product-specific clusters (low entropy) = "product"; clusters spread over all products
   (high entropy) = "surface/background/occluder". Store a per-cluster productness weight in
   [0,1] (soft, e.g. sigmoid on (entropy threshold - entropy)).
   `PatchCoder.encode(patches (N,G,G,Dd)) -> codes (N,G*G) int16`.
2. `fill_raw(codes, visible_patch_mask) -> (N,)`: mean productness over visible patches.
   Lite backend: `fill_raw_lite(hand)` from colourfulness / saturation vs. a per-area background
   estimate (documented heuristic).
3. Per-area normalisation (`StockModel.fit_area_stats(area_ids, fill_raw)`): robust low/high
   percentiles of fill_raw per area over the day -> relative fill in [0,1]; blend with absolute
   fill (areas that never empty must not be stretched to look empty: use the global
   distribution as a floor, i.e. lo = min(area_p5, global_p5)).
4. Level posterior: fit a 3-component ordered 1-D GMM on all fills (train+test) ->
   `p_levels(fill) -> (N,3)` (empty, half, full); fall back to `cfg.level_prior` + fixed centres if
   degenerate. Optional calibration (section 6) replaces it with fitted ordinal thresholds.
5. Optional CLIP zero-shot evidence: similarity to EMPTY_PROMPTS vs product prompts -> blended
   into the posterior with a small weight.
```python
class StockModel:
    def fit(self, feats: CropFeatures, area_product: dict[str,str], cfg) -> None
    def predict_proba(self, feats: CropFeatures) -> np.ndarray      # (N,3) rows sum to 1
    def fill(self, feats: CropFeatures) -> np.ndarray                # (N,) relative fill in [0,1] (for UI)
    def state_dict(self) -> dict; @classmethod def from_state(cls, d)
```
Final level = `scoring.best_stock(*p)` per row (pipeline does this).

### sensei/compliance.py
Idea (unsupervised): the planogram is valid at the start of the day and most areas are compliant
most of the time, so each area's own typical appearance (when stocked) is its reference.
- Area prototypes: mean CLIP (or `hand` in lite) embedding of the area's crops with fill above
  median, weighting earlier timestamps higher. Product prototypes: mean over the product's areas.
- Zero-shot text scores: CLIP similarity of the crop to every catalog product's prompts.
- For a crop with enough fill: evidence that it shows product q != expected p =
  (sim to proto(q) - sim to proto(p)) and (text(q) - text(p)); convert to a log-likelihood
  ratio, combine with `compliance_prior` -> p_compliant. Similar-looking products (same base
  fruit, different variety) need stronger evidence. Empty / mostly-occluded / barely-visible crops
  -> p_compliant = prior (nothing wrong is shown).
```python
class ComplianceModel:
    def fit(self, feats, area_product: dict[str,str], catalog, text_emb: dict[str,np.ndarray] | None, fill: np.ndarray, cfg)
    def predict(self, feats, fill: np.ndarray) -> tuple[np.ndarray, list[str|None]]
        # (p_compliant (N,), likely product_id when p_compliant < 0.5 else None)
    def state_dict(self); @classmethod def from_state(cls, d)
```

### sensei/temporal.py
```python
class AreaSeries:   # per area: sorted (timestamp, fill, p_levels) from fit-time images
    def add(...); def neighbours(area_id, ts, window_s) -> rows
def smooth(fill_now, p_now, neighbour_rows, cfg) -> (fill, p)  # weighted blend, weight decays with |dt|
def forecast_empty(series_rows, now_ts) -> float | None   # seconds until fill hits ~0 from a robust slope; None if not depleting
```

### sensei/pipeline.py
```python
class SenseiModel:  # everything learned at fit time; save()/load() to a directory (json + npz, no pickle of torch)
def fit(data_root, planogram_path, out_dir, cfg, splits=("train","test")) -> SenseiModel
def predict(model, image_records, cfg) -> tuple[dict, list[dict]]
    # (predictions in the submission format, details rows for the UI:
    #  {camera_id,image_name,area_id,product_id,product_name,english,timestamp,
    #   stock_level,stock_value,fill,p_levels,planogram_compliant,p_compliant,likely_product_id,
    #   likely_product_name,visible,forecast_empty_s})
```
Guarantees: every planogram area of each image's camera appears exactly once; images whose
camera is not in the planogram are skipped with a warning; corrupt images -> fallback answer
(compliant=True, stock from that area's time-series median or `level_prior` via best_stock), never a crash.

### sensei/__main__.py (CLI)
```
python -m sensei synth   --out data_synth [--cameras 4 --images 40]
python -m sensei fit     --data <root> --planogram <planogram.json> --model models/m1 [--backend lite|deep] [--max-images-per-camera N]
python -m sensei predict --model models/m1 --images <dir> --out predictions.json [--details details.json]
python -m sensei score   annotations.json predictions.json
python -m sensei dashboard --details details.json --data <root> --out dashboard/   # then open dashboard/index.html
python -m sensei label   --model models/m1 --data <root> --out labeling/ [--n 150]   # optional calibration sheet
python -m sensei calibrate --model models/m1 --labels labels.json                   # optional
python -m sensei run     --data <root> --planogram ... --images <val dir> --out outputs/   # fit+predict+dashboard
```

### Contract addendum (binding; refines section 4)
- `CropFeatures` also has `patch_visible: np.ndarray | None  # (N, G*G) bool` (a patch is
  visible if >= 50% of its pixels are inside the frame) and `image_paths: list[str]` (N).
- `features.iter_crops(records, areas_by_cam, cfg)` yields
  `(key, timestamp, crop_uint8, visible_mask, visible_fraction, image_path)` per (image, area);
  a corrupt image yields nothing for that image (logged), never raises.
- `features.compute_features(records, areas_by_cam, cfg, extractor=None, return_patches=True,
  cache_dir="cache") -> tuple[CropFeatures, np.ndarray | None]`; patches are float16
  `(N, G, G, Dd)` (fine at this dataset's scale); disk cache keyed by a hash of image
  paths + sizes + mtimes + the feature-relevant cfg fields; `backend="lite"` -> clip/dino/patches None.
- `features.product_text_embeddings(extractor, catalog) -> dict[product_id, (Dc,) L2 vector]`
  (mean of `products.prompts_for(name)` embeddings, re-normalised) and
  `features.prompt_set_embedding(extractor, prompts) -> (Dc,)`.
- Real-data feature cache for development: `cache/real/feats.npz` (CropFeatures.save) and
  `cache/real/patches.npy` (float16) for ALL real images, written by the features agent.
- `details.json` (written by `predict --details`, read by `dashboard`):
```json
{"section": "Frutas e Legumes", "generated_at": 1751052241, "backend": "deep",
 "rows": [{"camera_id": "6215", "image_name": "1751052241.jpg", "area_id": "6215_2",
           "product_id": "11908", "product_name": "BANANA CAT I CNT KG", "english": "banana",
           "loose": true, "timestamp": 1751052241, "stock_level": "half", "stock_value": 0.5,
           "fill": 0.43, "p_levels": [0.1, 0.6, 0.3], "planogram_compliant": true,
           "p_compliant": 0.97, "likely_product_id": null, "likely_product_name": null,
           "likely_english": null, "visible": 1.0, "forecast_empty_s": 5400,
           "quad": [[299,350],[464,347],[479,438],[331,438]], "image_path": "..."}],
 "timeline": {"6215_2": [[1751001268, 0.91, "full"], [1751005412, 0.80, "full"]]}}
```
- Calibration heads (`calibrate.py`): `fit_heads(feats, fill, labels, cfg) -> Heads`;
  `Heads.stock_proba(feats, fill) -> (N,3)`; `Heads.compliance_proba(feats, fill) -> (N,)`;
  `Heads.save(dir)` / `Heads.load(dir)` (json + npz); `cross_validate(feats, fill, labels, cfg)
  -> dict` with the challenge score computed by `scoring.score` on held-out folds;
  `export_sheets(feats_or_keys, data_root, areas_by_cam, out_dir, cfg, n=None)`.
  `pipeline.predict` uses `<model_dir>/heads/` automatically if present. Heads version 2 may carry a
  per-area memory (`HeadParams.memory`): the labelled crops' embeddings and labels (`mem_*` arrays in
  heads.npz) and a `memstock` head used for crops whose area has earlier labelled crops
  (`memory_features`, causal in time); version-1 heads load unchanged.

## 5. Staff dashboard (UI/UX breaks ties: make it excellent)

Static site, no server, no build step, opens from `file://`: `index.html` + `app.js` +
`style.css` + `data.js` (`window.SHELF_DATA = {...}`) + `img/` (downscaled camera frames,
<= 1280 px wide, JPEG q80, plus per-area crops). Persona: a store employee starting a shift on a
phone or tablet who must see in seconds what to restock first, what to move back, what to leave.
- Top: section + snapshot time + counters (Empty / Low / Wrong product / OK), large and coloured.
- "Do now" list ordered by priority: wrong product and empty first, then low (half); each
  card: product name (EN big, PT small), location (camera / area), crop thumbnail, action verb
  ("Restock", "Move back: expected X, seen Y", "Top up soon"), confidence hint.
- Gondola view: camera frame with area polygons coloured by status, tap an area for details and
  the fill sparkline over the day with "empty in ~N min" forecast when available.
- Product view: per product, aggregated over its areas.
- Colour + icon + text (colour-blind safe), large touch targets, works at 375 px width, light and
  dark mode, keyboard accessible, no external network requests (all assets local).
- Language toggle EN / PT for UI strings.

## 6. Optional calibration
`label` exports a stratified sample of fit-time crops (by current fill estimate) to
`labeling/` with `labeler.html` (keyboard: 1 empty, 2 half, 3 full, W wrong product, arrows;
exports labels.json via download). `calibrate` fits ordinal thresholds on fill (and compliance
LLR offset) by maximising the challenge score (via scoring.py logic) with cross-validation,
reports the estimated score, and stores the calibration in the model dir. Without labels the
pipeline is unchanged.

## 7. Quality bar
- `tests/` pytest suite green with backend=lite; one deep-backend smoke test marked `slow`.
- End-to-end on synthetic data (`synth` -> `fit` -> `predict` -> `score`) produces a valid
  submission covering all annotated areas and a positive score.
- No crash on: negative coords, quads fully outside the frame, grayscale/PNG images, a camera with
  zero images, an area whose product appears nowhere else, unicode paths.

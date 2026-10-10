# %% [markdown]
# # Sensei: big-model features on a free Colab GPU
#
# Computes, for every (frame, planogram area) crop: **CLIP ViT-L/14**, **SigLIP so400m** and
# **DINOv2-base** embeddings, plus **OWLv2** open-vocabulary fruit/vegetable detections per frame.
# Free tier only; no API keys.
#
# 1. **Runtime → Change runtime type → T4 GPU → Save.**
# 2. **Runtime → Run all.**
# 3. When the upload button appears (cell 3), select **both** files from the dataset folder:
#    `Frutas e Legumes (train & test).zip` and `planogram.json`.
#    (For the hidden validation set later: upload the validation zip + planogram.json instead.)
# 4. At the end the browser downloads **`sensei_colab_features.zip`**. Put it in
#    `junctionx-sensei/cache/colab/` on the laptop (don't unzip; the pipeline reads it).
#
# Runtime on a T4: about 10 minutes, mostly model downloads.

# %%
!nvidia-smi -L || echo "NO GPU - use Runtime > Change runtime type > T4 GPU (it still works on CPU, just slowly)"

# %%
import glob, json, os, shutil, zipfile
from google.colab import files

UP = "/content/up"
os.makedirs(UP, exist_ok=True)
os.chdir(UP)
if not glob.glob(f"{UP}/*.zip"):
    print("Select BOTH files: the images zip and planogram.json")
    files.upload()  # saved into /content/up
print(os.listdir(UP))

# %%
RAW = "/content/data/raw/images"
shutil.rmtree(RAW, ignore_errors=True)
os.makedirs(RAW)
n = 0
for z in glob.glob(f"{UP}/*.zip"):
    with zipfile.ZipFile(z) as zf:
        for m in zf.namelist():
            base = os.path.basename(m)
            if "__MACOSX" in m or base.startswith(".") or not base.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            cam = m.rstrip("/").split("/")[-2]
            os.makedirs(f"{RAW}/{cam}", exist_ok=True)
            with zf.open(m) as src, open(f"{RAW}/{cam}/{base}", "wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
plan_path = next(p for p in glob.glob(f"{UP}/*.json") if '"cameras"' in open(p, encoding="utf-8").read())
print(n, "images in", len(os.listdir(RAW)), "camera folders; planogram:", plan_path)

# %%
import numpy as np, cv2, torch

CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")
plan = json.load(open(plan_path, encoding="utf-8"))
areas = {}
for section in plan.values():
    for cam, c in section["cameras"].items():
        areas[cam] = [(a["area_id"], np.array([a["image_coordinates"][k] for k in CORNERS], np.float32))
                      for a in c["products"]]

SIZE, INSET = 384, 0.06
DST = np.array([[0, 0], [SIZE - 1, 0], [SIZE - 1, SIZE - 1], [0, SIZE - 1]], np.float32)

def warp(img, quad):
    c = quad.mean(0)
    q = (c + (quad - c) * (1 - INSET)).astype(np.float32)
    M = cv2.getPerspectiveTransform(q, DST)
    crop = cv2.warpPerspective(img, M, (SIZE, SIZE), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    vis = cv2.warpPerspective(np.ones(img.shape[:2], np.uint8), M, (SIZE, SIZE), flags=cv2.INTER_NEAREST)
    return crop, float(vis.mean())

keys, crops, visible, frames = [], [], [], []
for cam in sorted(os.listdir(RAW)):
    if cam not in areas:
        print("skip camera not in planogram:", cam); continue
    for path in sorted(glob.glob(f"{RAW}/{cam}/*")):
        img = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print("unreadable:", path); continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        frames.append((cam, os.path.basename(path), img))
        for area_id, quad in areas[cam]:
            crop, v = warp(img, quad)
            keys.append(f"{cam}|{os.path.basename(path)}|{area_id}")
            crops.append(crop)
            visible.append(v)
print(len(frames), "frames,", len(keys), "area crops")

# %%
from transformers import AutoModel, AutoProcessor, CLIPModel, CLIPProcessor

dev = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if dev == "cuda" else torch.float32

def l2(x):
    return x / np.linalg.norm(x, axis=-1, keepdims=True).clip(1e-8)

def as_tensor(out):
    """transformers >= 5 returns a ModelOutput from get_*_features; the projection is pooler_output."""
    return out if isinstance(out, torch.Tensor) else out.pooler_output

@torch.inference_mode()
def embed_images(model, proc, fn, bs=32):
    out = []
    for i in range(0, len(crops), bs):
        inp = proc(images=crops[i:i + bs], return_tensors="pt")
        out.append(as_tensor(fn(pixel_values=inp["pixel_values"].to(dev, dtype))).float().cpu().numpy())
    return l2(np.concatenate(out))

# Generic English produce vocabulary (store catalogue bases) for zero-shot text embeddings.
PRODUCE = ["bananas", "oranges", "net bags of oranges", "lemons", "limes", "clementines", "apples", "green apples",
           "red apples", "yellow apples", "pears", "kiwis", "packs of kiwis", "melons", "watermelons", "cantaloupes",
           "mangoes", "pineapples", "papayas", "passion fruits", "dragon fruits", "guavas", "white grapes",
           "red grapes", "packs of cherries", "packs of strawberries", "apricots", "peaches", "flat peaches",
           "nectarines", "tomatoes", "tomatoes on the vine", "packs of cherry tomatoes", "oxheart tomatoes",
           "plum tomatoes", "potatoes", "bags of potatoes", "red potatoes", "sweet potatoes", "onions",
           "red onions", "bags of onions", "garlic", "packs of garlic", "pumpkins", "ginger", "bagged lettuce",
           "avocados", "green peppers", "red peppers", "cabbages", "red cabbages", "broccoli", "cauliflowers",
           "kale", "zucchini", "eggplants", "chayotes", "green beans", "cucumbers", "shallots"]
TEMPLATES = ["a photo of {} in a supermarket display", "a crate full of {}", "a few {} in a mostly empty crate"]
EMPTY = ["an empty plastic crate in a supermarket", "an empty teal plastic crate", "an empty grey metal tray",
         "an empty cardboard box", "an empty black plastic display", "an empty shelf"]
TEXTS = [t.format(p) for p in PRODUCE for t in TEMPLATES] + EMPTY
TEXT_NAMES = [f"{p}|{t}" for p in PRODUCE for t in TEMPLATES] + [f"EMPTY|{e}" for e in EMPTY]

feats = {"keys": np.array(keys), "visible": np.array(visible, np.float32), "text_names": np.array(TEXT_NAMES)}

# CLIP ViT-L/14
m = CLIPModel.from_pretrained("openai/clip-vit-large-patch14", torch_dtype=dtype).to(dev).eval()
p = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
feats["clip_l14"] = embed_images(m, p, m.get_image_features)
with torch.inference_mode():
    t = p(text=TEXTS, return_tensors="pt", padding=True).to(dev)
    feats["clip_l14_text"] = l2(as_tensor(m.get_text_features(**t)).float().cpu().numpy())
feats["clip_l14_logit_scale"] = np.float32(m.logit_scale.exp().item())
del m; torch.cuda.empty_cache()
print("clip_l14", feats["clip_l14"].shape)

# SigLIP so400m (384 px)
m = AutoModel.from_pretrained("google/siglip-so400m-patch14-384", torch_dtype=dtype).to(dev).eval()
p = AutoProcessor.from_pretrained("google/siglip-so400m-patch14-384")
feats["siglip"] = embed_images(m, p, m.get_image_features)
with torch.inference_mode():
    t = p(text=TEXTS, return_tensors="pt", padding="max_length").to(dev)
    feats["siglip_text"] = l2(as_tensor(m.get_text_features(input_ids=t["input_ids"])).float().cpu().numpy())
feats["siglip_logit_scale"] = np.float32(m.logit_scale.exp().item())
feats["siglip_logit_bias"] = np.float32(m.logit_bias.item())
del m; torch.cuda.empty_cache()
print("siglip", feats["siglip"].shape)

# DINOv2-base: CLS + mean patch token
m = AutoModel.from_pretrained("facebook/dinov2-base", torch_dtype=dtype).to(dev).eval()
p = AutoProcessor.from_pretrained("facebook/dinov2-base")
cls, mean = [], []
with torch.inference_mode():
    for i in range(0, len(crops), 32):
        inp = p(images=crops[i:i + 32], return_tensors="pt")
        h = m(pixel_values=inp["pixel_values"].to(dev, dtype)).last_hidden_state.float().cpu().numpy()
        cls.append(h[:, 0]); mean.append(h[:, 1:].mean(1))
feats["dino_base_cls"], feats["dino_base_mean"] = l2(np.concatenate(cls)), l2(np.concatenate(mean))
del m; torch.cuda.empty_cache()
print("dinov2-base", feats["dino_base_cls"].shape)

# %%
from transformers import Owlv2ForObjectDetection, Owlv2Processor

QUERIES = PRODUCE + ["a plastic package of fruit", "a net bag", "a person's hand", "a shopping basket"]
m = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble", torch_dtype=dtype).to(dev).eval()
p = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble")
detections = {}
with torch.inference_mode():
    for k, (cam, name, img) in enumerate(frames):
        inp = p(text=[QUERIES], images=img, return_tensors="pt").to(dev)
        inp["pixel_values"] = inp["pixel_values"].to(dtype)
        out = m(**inp)
        side = max(img.shape[:2])  # OWLv2 pads to a square: scale boxes by the padded side
        post = getattr(p, "post_process_grounded_object_detection", None) or p.post_process_object_detection
        res = post(out, threshold=0.12, target_sizes=torch.tensor([[side, side]]))[0]
        boxes = res["boxes"].float().cpu().numpy().round(1)
        detections[f"{cam}|{name}"] = [[*b.tolist(), QUERIES[int(l)], round(float(s), 3)]
                                       for b, l, s in zip(boxes, res["labels"], res["scores"])]
        if k % 20 == 0:
            print(k, "/", len(frames), cam, name, len(detections[f"{cam}|{name}"]), "boxes")
del m; torch.cuda.empty_cache()

# %%
OUT = "/content/out"
os.makedirs(OUT, exist_ok=True)
np.savez_compressed(f"{OUT}/colab_features.npz", **feats)
json.dump({"queries": QUERIES, "detections": detections}, open(f"{OUT}/owl_detections.json", "w"))
json.dump({"crop_size": SIZE, "inset": INSET, "n_crops": len(keys), "n_frames": len(frames),
           "models": ["openai/clip-vit-large-patch14", "google/siglip-so400m-patch14-384",
                      "facebook/dinov2-base", "google/owlv2-base-patch16-ensemble"]},
          open(f"{OUT}/meta.json", "w"), indent=1)
shutil.make_archive("/content/sensei_colab_features", "zip", OUT)
print({f: os.path.getsize(f"{OUT}/{f}") // 1024 for f in os.listdir(OUT)}, "KB")
files.download("/content/sensei_colab_features.zip")

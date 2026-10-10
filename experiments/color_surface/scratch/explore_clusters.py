import sys, time
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cs_lib as L
from extract import extract
from sklearn.cluster import MiniBatchKMeans

K = int(sys.argv[1]) if len(sys.argv) > 1 else 40
d = extract()
crops, vis, aids, cams = d["crops"], d["vis"], d["aids"], d["cams"]
N = len(crops)
rng = np.random.default_rng(0)
t0 = time.time()
samp = []
for i in range(N):
    f = L.pixel_features(crops[i])
    idx = np.flatnonzero(vis[i].ravel())
    if len(idx) == 0: continue
    pick = rng.choice(idx, size=min(256, len(idx)), replace=False)
    samp.append(f.reshape(-1, 4)[pick])
samp = np.concatenate(samp)
print("samples", samp.shape, time.time() - t0)
km = MiniBatchKMeans(K, random_state=0, batch_size=4096, n_init=3, max_iter=200).fit(samp)
C = km.cluster_centers_
print("kmeans", time.time() - t0)
labels = np.empty((N, L.S, L.S), np.uint8)
frac = np.zeros((N, K), np.float32)
for i in range(N):
    f = L.pixel_features(crops[i]).reshape(-1, 4)
    dd = (f ** 2).sum(1)[:, None] - 2 * f @ C.T + (C ** 2).sum(1)[None]
    lab = dd.argmin(1).astype(np.uint8)
    labels[i] = lab.reshape(L.S, L.S)
    v = vis[i].ravel()
    if v.sum():
        frac[i] = np.bincount(lab[v], minlength=K) / v.sum()
print("assign", time.time() - t0)
np.savez(L.HERE / "cache" / f"explore_k{K}.npz", C=C, labels=labels, frac=frac)

areas = L.load_planogram()
base = {a["area_id"]: L.base_of(a["product_name"]) for cam in areas for a in areas[cam]}
ua = sorted(set(aids))
A = np.stack([frac[aids == a].mean(0) for a in ua])  # area x K
Amax = np.stack([frac[aids == a].max(0) for a in ua])
bases = sorted(set(base.values()))
B = np.stack([A[[base[a] == b for a in ua]].mean(0) for b in bases])  # base x K
camlist = sorted(set(cams))
Cm = np.stack([frac[cams == c].mean(0) for c in camlist])
mass = frac.mean(0)
Pb = B / B.sum(0, keepdims=True)
Hb = -(Pb * np.log(Pb + 1e-12)).sum(0) / np.log(len(bases))
Pa = A / A.sum(0, keepdims=True)
Ha = -(Pa * np.log(Pa + 1e-12)).sum(0) / np.log(len(ua))
Pc = Cm / Cm.sum(0, keepdims=True)
Hc = -(Pc * np.log(Pc + 1e-12)).sum(0) / np.log(len(camlist))
order = np.argsort(-Hb)
# swatches
tiles = []
for c in order:
    tile = np.zeros((60, 600, 3), np.uint8)
    ys, xs, ns = [], [], []
    ii = np.argwhere(labels == c)
    if len(ii):
        sel = ii[rng.choice(len(ii), size=min(10, len(ii)), replace=False)]
        for j, (n, y, x) in enumerate(sel):
            y0, x0 = np.clip(y - 10, 0, L.S - 20), np.clip(x - 10, 0, L.S - 20)
            p = crops[n, y0:y0 + 20, x0:x0 + 20]
            p = cv2.resize(p, (40, 40), interpolation=cv2.INTER_NEAREST)
            tile[10:50, 5 + j * 42: 45 + j * 42] = p
    topb = np.argsort(-Pb[:, c])[:3]
    txt = f"c{c} m{mass[c]*100:.1f}% Hb{Hb[c]:.2f} Ha{Ha[c]:.2f} Hc{Hc[c]:.2f} " + ",".join(f"{bases[b][:6]}{Pb[b,c]:.2f}" for b in topb)
    tile2 = np.zeros((60, 1000, 3), np.uint8); tile2[:, :600] = tile
    cv2.putText(tile2, txt[:60], (430, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    cv2.putText(tile2, txt[60:], (430, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    tiles.append(tile2)
sheet = np.vstack(tiles)
cv2.imwrite(str(L.HERE / "scratch" / f"clusters_k{K}_a.jpg"), sheet[: len(sheet) // 2])
cv2.imwrite(str(L.HERE / "scratch" / f"clusters_k{K}_b.jpg"), sheet[len(sheet) // 2:])
for c in order:
    print(c, f"m={mass[c]:.3f} Hb={Hb[c]:.2f} Ha={Ha[c]:.2f} Hc={Hc[c]:.2f} C={np.round(C[c],1)}")

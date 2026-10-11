# results/: the evidence behind the README

Small, metric-only files (no images, no store data) copied from the team's local `models/`, `outputs/` and
`experiments/` folders, which are not published. Every number in the [README](../README.md) and
[docs/HOW_IT_WORKS.md](../docs/HOW_IT_WORKS.md) comes from one of these files or from the AI answer key in
[`data/labels/`](../data/labels/).

The commands need the dataset in `data/raw/` and the fitted models in `models/` (see the README, "Run it");
none of them reads the hidden validation set.

## Accuracy

| File | What it holds | Regenerate with |
|---|---|---|
| `calibration_cv_real_v3_cal.json` | Cross-validated score of the submission model `models/real_v3_cal` on the AI key: schemes `camera` (leave one camera out, 1,962 areas), `time` (last two labelled frames of every camera, 304 areas) and `time1` (last frame, 152 areas). Methods: `heads` (submission), `heads_nomem` (no same-day memory), `baseline` (label-free outputs of the same model), `all_full` (always compliant + full), plus per-camera rows. Copy of `models/real_v3_cal/calibration_cv.json`. | `python -m sensei calibrate --model models/real_v3_cal --labels data/labels/teacher_labels_v2.json` |
| `heldout.py` | The held-out script behind the README results table (copy of `experiments/final_integration/heldout.py`, paths only changed). Refits the heads per fold for four recipes: `v1cal` (previous submission), `v3cal` (submission), `v1mem`, `v3nomem`. | `python results/heldout.py [recipes]` |
| `heldout_v1cal_v3cal_v1mem_v3nomem.json` | Its output for all four recipes, on the full key (`|v2`) and the original 756-area key (`|756`). | `python results/heldout.py` |
| `heldout_v3cal.json` | The same script re-run for the submission recipe only on 2026-10-11, from this folder: 1.233 / 1.411 / 1.480, identical to the file above. | `python results/heldout.py v3cal` |
| `labelfree.py` | Scores a model's label-free outputs (no heads) on the same test sets. | `python results/labelfree.py models/real_v3_cal models/real_v1` |
| `labelfree_real_v3_cal.json` | Label-free core of the submission model: 1.183 / 0.990 / 0.882 (equals `baseline` above). | as above |
| `labelfree_real_v1.json` | Label-free fallback model `models/real_v1`: 1.210 / 1.007 / 0.980. | as above |
| `final_numbers_real_v3_cal.json` | The same held-out folds in staff terms (copy of `pitch/research/evidence/final_numbers_real_v3_cal.json`): confusion matrices, wrong-product hits and false alarms (31 of 117 found, 2 false alarms on unseen cameras), empties reaching the to-do list, restock tasks on full shelves, for `heads`, `unsup` (label-free) and `always_compliant_full`. | `python pitch/research/evidence/final_numbers_v3.py <out.json>` (imports `experiments/final_integration/heldout.py`, not published) |

## Cost (`benchmark/`)

All measured on one laptop, an AMD Ryzen AI 7 350 (native bf16), 14 frames / 152 areas, no feature cache. Each
file records the model, precision, threads, wall and CPU seconds per image and peak RAM.

| File | What it holds | Regenerate with |
|---|---|---|
| `cost_1t_real_v3_cal_b2b_run1.json`, `_run2`, `_run3` | Submission model, 1 core, three back-to-back runs: 3.765 / 3.837 / 3.661 CPU-s per image | `SENSEI_THREADS=1 python tools/benchmark_cost.py --model models/real_v3_cal` |
| `cost_1t_real_v3_cal.json` | The median run (3.765), the figure used for the price | as above |
| `cost_1t_real_v3_cal_first.json` | An earlier single run (3.59) | as above |
| `cost_1t_real_v3_cal_detect.json` | Submission model plus OWLv2 boxes: 4.53 CPU-s for the prediction part in this run, +15.7 s for boxes | `... --detect` |
| `cost_1t_real_v2.json`, `cost_1t_real_v2_detect.json` | `models/real_v2` (bf16, heads, no memory): 3.43 | `... --model models/real_v2` |
| `cost_1t.json` | Previous submission `models/real_v1_cal` (fp32): 5.16 | `... --model models/real_v1_cal` |
| `cost_16t.json` | 16 threads, earlier fp32 measurement: 1.37 s wall, 18.2 CPU-s; OWLv2 3.1 s wall | `SENSEI_THREADS=16 ...` |
| `cost_1t_bf16.json`, `cost_1t_b32*.json`, `cost_1t_*int8*.json` | Precision and model-size experiments (cost only; no accuracy result was saved for them; `sensei/config.py` notes why int8 was not used) | `tools/benchmark_cost.py` with the matching options |
| `llm_cost_compare.json` | Our cost per image ($0.0000467) against one Claude call per image with the labellers' two pictures (Sonnet 5.5 $0.0141, Opus 5.5 $0.0282, Haiku 5.5 $0.0007) | `python tools/llm_cost_compare.py` |
| `change_gate.json` | Study of skipping areas whose pixels did not change between consecutive frames (AUC 0.888; 3.8% skipped for 1 of 281 changes missed). Not shipped. | `python tools/change_gate.py` |

Not included: `pitch/research/evidence/results_final.txt`, which predates the final answer key (02:00 vs 02:06)
and is superseded by the files above.

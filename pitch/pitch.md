# Sensei shelf monitor: 3-minute pitch

Deck: `pitch/slides.html` (arrow keys to move, F for fullscreen). One slide per block below. Target
pace is about 155 words a minute, which ends at about 2:55, leaving a few seconds spare; the whole script is about 450 words. Fill in the team name and
names on slide 9 before presenting (the yellow boxes).

If you run long, cut the sentences marked *(cut if short)*. If you run short, add the 6215 story
from slide 3 to the demo.

---

## 1. Title (0:00 - 0:13)

Hello, we are **[team name]**, and this is the **Sensei shelf monitor**. In one line: it tells store
staff which shelf to fix first, from ceiling-camera pictures alone. No labels, and no new hardware.

## 2. The problem (0:13 - 0:35)

Fruit and veg goes wrong fast. An **empty gondola** is lost sales. An **overstocked** one is waste.
The **wrong product in the wrong place** confuses customers and gives wrong prices. Staff walk the
store to check, and nobody can label thousands of cameras. So the system must learn to see the shelf
without being told what is right.

## 3. What we found (0:35 - 1:01)

This is camera 6215 at 6:14 in the morning, before the store is busy. Areas 3 and 5 are planned
for banana and hold oranges; the banana trays beside them are empty. In our labelled sample, 42 of
756 areas show the wrong product. So the planogram is the question, not the answer. And empty trays
look the same under every product: the container repeats, the product changes.

## 4. How it works (1:01 - 1:30)

We warp each planogram area to a square crop. For **stock**, we cluster DINOv2 patches: clusters
found under every product are surface, clusters tied to a few fruits are product, and CLIP names
them. Fill is the share of product. For **compliance**, CLIP recognises the product at base-fruit
level: banana versus orange versus apple. Then we decide for the score: too high costs three points,
too low costs two, so we lean low when unsure. *(cut if short: OWLv2 draws the product boxes you
will see in the app.)*

## 5. Honest calibration (1:30 - 2:06)

The pipeline needs no labels, but we needed a ruler. So we built a **756-area answer key** with
independent AI labellers: three votes per area, 94% unanimous. We used it to measure, and to
calibrate small heads on top. On held-out late frames we score **1.19 points per area**, 1.41 on the
last frame, against **0.70** for always answering "compliant" and "full". On the hidden set that
projects to **about 345 to 400 out of 578**; the brief's example is 320. The key is AI-labelled, so
it is an estimate: the hidden set decides.

## 6. The staff app (2:06 - 2:21)

The **Do now** list puts wrong product and empty first, then low. Tap an area for the photo, the
outlined shelf and one clear action, like "move it back". It works on a phone, in English or
Portuguese. *(Live demo here if you have the time; see `demo_script.md`.)*

## 7. Runs anywhere (2:21 - 2:37)

It runs anywhere. Free models, no keys: **35 seconds for 14 frames on a laptop CPU**, or a free
Colab GPU. One command. In a new store you point it at the camera pictures and switch it on the same
day.

## 8. Next steps (2:37 - 2:47)

The same pictures can give **restock forecasting**, less waste, planogram audits with no manual
walk, layout analytics, and later other loose products like bakery and flowers.

## 9. Thank you (2:47 - 2:54)

Thank you. No labels, no new hardware, and staff know what to do first. We would love your
questions.

---

## Numbers you may say (all from our own measurements)

| Claim | Number | Where it comes from |
|---|---|---|
| Answer key | 756 areas, 3 votes, 94% unanimous | `data/labels/teacher_labels.json` |
| Wrong product in the key | 42 of 756 areas | count of `planogram_compliant: false` in that file |
| Held-out, late frames | 1.19 points per area (max 2) | `calibrate` late-frame fold |
| Held-out, last frame | 1.41 points per area | same |
| Held-out, whole camera unseen | 1.15 points per area | leave-one-camera-out, 1.147 |
| Baseline | 0.70 points per area | always "compliant" and "full" |
| Hidden set | 289 areas, max 578, brief example 320 | the brief |
| Projection | about 345 to 400 | roughly 1.19 and 1.41 times 289 |
| Speed | 35 s for 14 frames, laptop CPU | measured dry run |

Do not say any other number out loud. If asked something we have not measured, say so.

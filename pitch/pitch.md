# Sensei shelf monitor: 3-minute pitch

Deck: `pitch/slides.html` (arrow keys to move, F for fullscreen, number keys jump, 0 = last slide). One slide per
block below, 10 slides. Target pace is about 155 words a minute: reading everything (about 450 words) ends at
about 2:54, and cutting the marked sentences brings it to about 2:45. Fill in the team name and names on slide 10 before
presenting (the yellow boxes).

If you run long, cut the sentences marked *(cut if short)*. If you run short, add the 6215 story from slide 3
to the demo.

---

## 1. Title (0:00 - 0:12)

Hello, we are **[team name]**, and this is the **Sensei shelf monitor**. It tells store staff which shelf
to fix first, from ceiling-camera pictures alone. No labels, no new hardware.

## 2. The problem (0:12 - 0:30)

Fresh produce goes wrong fast. An **empty gondola** is lost sales, an **overstocked** one is waste, and the
**wrong product** in the wrong place means wrong prices. Nobody can label thousands of cameras, so the system
must learn to see the shelf without being told what is right.

## 3. What we found (0:30 - 0:52)

This is camera 6215 at 6:14 in the morning. Areas 3 and 5 are planned for banana and hold oranges; the banana
trays beside them are empty. In our labelled sample, 72 of 1,240 areas show the wrong product, so the planogram
is the question, not the answer. *(cut if short: And empty trays look the same under every product.)*

## 4. How it works (0:52 - 1:20)

We warp each planogram area to a square crop. For **stock**, we cluster DINOv2 patches: clusters found under
every product are surface, clusters tied to a few fruits are product, and CLIP names them. Fill is the share of
product. For **compliance**, CLIP recognises the base fruit. Then we decide for the score: too high costs three
points, too low two, so we lean low when unsure. *(cut if short: OWLv2 boxes feed the counts.)*

## 5. Honest calibration (1:20 - 1:56)

The pipeline needs no labels, but we needed a ruler: a **1,240-area answer key** from independent AI labellers
(a second AI, Gemini, agreed with every wrong-product call it checked). We use it to measure, and to calibrate small heads on top. Held out, we score **1.25
points per area** on cameras it never saw, **1.30** on late frames, **1.40** on the last frame, against
**0.70** for always answering compliant and full. On the hidden set that projects to **about 360 to 400 out
of 578**. The key is AI-labelled, so it is an estimate: the hidden set decides.

## 6. The staff app (1:56 - 2:09)

The **Do now** list puts wrong product and empty first. Tap an area for the photo, the outlined shelf, one
clear action and an estimate of the visible units. Phone or desktop, English or Portuguese. *(Live demo here if
you have the time; see `demo_script.md`.)*

## 7. Counts and Insights (2:09 - 2:26)

The same pictures give the manager's view. **Running out soon**: shelves forecast to be empty within two
hours. **Sales speed**: how fast each product sells, with restocks spotted. **Planogram adherence**: which
gondolas hold the wrong product. All estimates, from one day of pictures.

## 8. Cost per image (2:26 - 2:42)

You asked about cost. We measured it: about **7 CPU-seconds per image** on one core, no GPU, 1.1 GB of RAM.
At on-demand cloud prices that is about **$0.00009 per image**, roughly 9 cents per thousand, or about
**$6 a month** for this 14-camera section at one picture every five minutes. We chose the small models on
purpose: the big ones did not score better. And it is one command: pictures in, checked file out.

## 9. Next steps (2:42 - 2:48)

Next: waste tracking, layout analytics, and other loose products like bakery and flowers.

## 10. Thank you (2:48 - 2:54)

Thank you. No labels, no new hardware, and staff know what to do first. Questions welcome.

---

## Numbers you may say (all from our own measurements)

| Claim | Number | Where it comes from |
|---|---|---|
| Answer key | 1,240 areas over 115 frames (3 votes on 3 cameras, 94% unanimous) | `data/labels/teacher_labels*.json` |
| Wrong product in the key | 72 of 1,240 areas | count of `planogram_compliant: false` in that file |
| Held-out, cameras unseen | 1.25 points per area (max 2) | leave-one-camera-out, `models/real_v1_cal/calibration_cv.json` |
| Held-out, late frames | 1.30 points per area | last two labelled frames of every camera, same file |
| Held-out, last frame | 1.40 points per area | last labelled frame of every camera (152 areas, 1.395) |
| Baseline | 0.70 points per area | always "compliant" and "full", all 756 areas; it scores 0.36 and 0.06 on the last two frames and the last frame |
| Hidden set | 289 areas, max 578, brief example 320 | the brief |
| Projection | about 360 to 400 | roughly 1.25 to 1.40 times 289, rounded |
| Speed | 26 s for 14 frames (152 areas) on a laptop CPU; product boxes add about a minute (about 4 s per camera) | measured `submit` dry runs |
| Cost per image | ~7 CPU-seconds on 1 core (5.6-7.1 measured), 1.1 GB RAM, no GPU; x $0.045/vCPU-hour = ~$0.00009 per image (~$0.09 per 1,000) | `tools/benchmark_cost.py`; AWS c7i.large on-demand $0.0892/h for 2 vCPU (us-east-1) |
| Per store | 14 cameras x 1 picture / 5 min x 14 h = 2,352 images/day = ~4.6 CPU-hours = ~$0.20/day, ~$6/month (a third of one core) | arithmetic on the line above |
| Optional boxes | +~15.5 CPU-s per image (~$0.0002) | same benchmark, `--detect` |
| Expected hidden input | 26 images, 289 areas | the brief; `submit` only warns on a different count |

Insights and counts on the dry-run pictures (do not quote the figures as findings: they are model estimates
from one day, shown on screen as such): "Running out soon" lists areas forecast empty within 2 hours; a count
reads "about N visible units", and for bunches such as bananas a unit is a bunch.

Do not say any other number out loud. If asked something we have not measured, say so.

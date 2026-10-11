# Morning summary: Sunday 11 October 2026

For Sérgio and Inês. Deadline **13:00**. Written by Claude at about 09:15. Your own to-do list is
[`TODO_FOR_TEAM.md`](TODO_FOR_TEAM.md); this page says where things stand.

## The short version

**The project is ready to submit.** The model, the staff app, the README, the documents and the pitch are all
finished and checked. Everything left is for humans: push to GitHub, fill in the form, rehearse, back up.

- **Checked at 09:08 by the verification step, and re-run by me at about 09:12:** 184 fast tests pass (187 with the
  slow ones), `test_scoring.py` still reproduces the brief's 320 of 578, the code linter is clean, and the model
  files match their fingerprints (`tools/model_manifest.py --check` says "models match the manifest").
- **A dry run of the real hand-in works:** `SUBMIT.bat` on 14 test pictures printed `SUBMISSION FORMAT CHECK:
  PASSED` and `HAND IN THIS FILE`, exit code 0. The label-free fallback ran too.
- **Not pushed yet.** GitHub still shows the 08:50 commit. The new README, `docs/`, `results/` and the pitch files
  are only on this laptop. See step 1 of the plan below.

## Numbers to memorise

All "points per area" are out of 2, measured on **our own AI-made answer key**, with the tested cameras or frames held
out. Say "on our own answer key" every time.

| What | Number |
|---|---|
| Score, whole day, cameras the model never saw | **1.23** |
| Score, last two pictures of each camera / last picture | **1.41 / 1.48** |
| Score with no labels at all | 1.18 / 0.99 / 0.88 |
| Dumb baseline ("always compliant, always full") | 0.76 / 0.46 / 0.18 |
| Our estimate for Sensei's hidden set (578 points) | **355 to 430**; with no labels about 255 to 285 |
| Cost | **3.8 CPU-seconds per image, one core, no GPU = about 5 cents per 1,000 images** |
| Versus asking Claude Sonnet 5.5 per image | about **300 times cheaper** |
| One 14-camera produce section | about **$3 a month** |
| Empty shelves that reach the to-do list | **181 of 182** (99%), cameras held out |
| False wrong-product alarms | **2 in 1,845** correct areas |
| The honest weak spot | on a new camera it finds only **31 of 117** wrong products ("about one in four") |
| The answer key | 1,962 areas, 181 pictures, 14 cameras, 3 AI votes each, no human labelling |

**Never say:** "we beat 320" (it is the brief's worked example, not a benchmark); "no labelling effort" about the
1.41 score (day 0 needs no labels; day 1 uses the AI-made key); "four cents" (it is five). If you are asked something
that is not in `pitch/pitch.md` ("Numbers you may say"), say "we have not measured that".

## The line

> **"The plan says where things go. The camera sees what is there."**

Inês says it at about 0:15 and again as the last sentence. The talk opens on the 06:14 picture of camera 6215: four
empty banana trays and two banana crates holding oranges.

## What changed overnight

- **The answer key and final model.** All 1,962 areas of all 181 pictures now have 3 AI votes (84% unanimous on
  the 11 cameras voted last; 34 disputes settled by a fourth AI pass). The submission model is `models/real_v3_cal`.
  It is faster too (bf16: about a third less CPU time).
- **Code tidy-up.** Docstrings, command-line help and lint fixes. A before-and-after run gave **byte-identical
  predictions**, so nothing about the answers changed.
- **README rewritten** as a "start here" page, plus two new pages: `docs/HOW_IT_WORKS.md` (method, limits, commands)
  and `docs/LABELLING_GUIDE.md` (how the answer key was made, and what it is not).
- **`results/` folder (new):** the small score and cost files behind every number, with the scripts, so that every
  claim links to a file on GitHub. Ran `results/heldout.py` again: it reproduces 1.233 / 1.411 / 1.480 exactly.
- **Pitch rebuilt:** 10 slides plus 5 appendix slides for Q&A, a new 3-minute script (390 words, about 2:47; 367
  without the two optional lines, about 2:37), a 90-second demo script, and Q&A answers. The staff-app screenshots were
  retaken from the current app and all quoted labels match it (**Repor, Trocar, Deixar**).
- **Honesty fixes after five reviewers read everything cold (95 findings, 10 serious):** the "320" comparison was
  removed; "no labelling effort" and "switched on the same day" were removed; "four cents" became five cents; the
  claim that the hidden pictures are late in the day is now stated as an **assumption**; the label-free scores were
  added next to the calibrated ones; one slide claim that was never verified was dropped.
- **Safety net added:** `SUBMIT_LABEL_FREE.bat` (the no-labels fallback) and `results/model_manifest.json`
  (fingerprints of the model files, so you can prove nothing changed after 13:00:
  `.venv\Scripts\python tools\model_manifest.py --check`).

## Things to know before a judge asks

- **The scores are against our AI key, not Sensei's annotations.** On the 192 areas a second AI family (Gemini
  Flash) re-labelled, it agrees with the key on 81% of stock levels and on every wrong-product call.
- **The best numbers (1.41 to 1.48) need labels from the same day.** Without them: 0.88 to 1.18.
- **"The hidden pictures are late in the day" is our guess**, from one example file name in the brief (20:24; our
  latest picture is 20:16). If they are from mid-day, the 1.23 is the better guide, about 355 points.
- **Restock walks:** on cameras held out, about 1 restock task in 4 points at a shelf the key calls full (148 of 539);
  on late pictures about 1 in 10. Half versus full is the hard call.
- **Freshness counts:** newer app builds show 17 freshness checks; `pitch.md` says 13 (from the 08:48 build). The
  number is not spoken in the pitch; if asked, read it off the screen.

## Known small problems (the pitch avoids all of them)

- Product names in the **Análise** tab's "A acabar em breve" list break mid-word on a very narrow window (about 400 px).
  Demo the Análise tab in a wider window, or on a phone held sideways.
- A gondola panel can show "≈ N unidades visíveis" beside **Vazio**. Do not point at counts in the demo.
- **Slide 1** says four banana trays are empty. True, but the key also has a fifth empty (Madeira bananas, area 1).
  Fine to leave; say "at least four" if you want to be exact.
- The slides in the GitHub repository show no pictures (pictures are kept out on purpose). Present from
  `pitch/slides_standalone.html` on the laptop, never from GitHub.
- Not done: a "historical" banner on `SPEC.md`, a LICENSE file (you choose), and damaged characters in
  `docs/brief.txt` (our copy of the brief). Ask Claude if you want the first and last fixed.

## Validation day (when the pictures arrive)

Per Sensei's answer, noted in the to-do list at 09:05: the validation pictures arrive **after** the 13:00 submission,
from the same cameras. So at 13:00 you hand in code and description; the predictions file comes later.
**Do not edit anything in `models/`, and keep this laptop on, plugged in and awake.**

1. Put the pictures in one folder (or keep the `.zip`).
2. **Drag the folder or the zip onto `SUBMIT.bat`** in the project folder. In our rehearsal, 14 pictures took
   about 90 seconds including the staff app, so allow a few minutes for 26. Expect 26 pictures / 289 areas in the
   report; a warning about other numbers means check that every picture was handed over.
3. Wait for `SUBMISSION FORMAT CHECK: PASSED` and `HAND IN THIS FILE: ...\submission\predictions.json`. **Hand in
   that file.** The staff app for the same pictures is `submission\dashboard\index.html`.
4. If it says **`FAILED - DO NOT HAND IN YET`**, or the window closes with an error: do not hand anything in; tell
   Claude straight away and paste the message.
5. **No-labels fallback**, only if Sensei says AI-made annotations are not allowed: drag the same folder onto
   **`SUBMIT_LABEL_FREE.bat`** instead. It uses the label-free model `models/real_v1` and writes to
   `submission_label_free\` (the staff app is `submission_label_free\dashboard\index.html`). By hand:
   `.venv\Scripts\python -m sensei submit --model models/real_v1 --out submission_label_free --images <folder>`.
   Without `--out` it would overwrite the `submission\` folder. The fallback scores 1.21 / 1.01 / 0.98 on our
   tests; the pitch would then quote those instead.
6. After a run, never delete `submission\`; copy the printed file to a USB stick.

## Time plan to 13:00

| Time | What | Who |
|---|---|---|
| 09:45 | Read this page and `TODO_FOR_TEAM.md`. Read `docs/submission_text.md`. Approve the numbers (the "NEW or DERIVED" rows of `pitch/pitch.md`) | both |
| 10:00 | **Push to GitHub** (tell Claude in the main chat to commit and push everything since 08:50), then open the repository page: README renders, both diagrams show, `results/` is there, no pictures | Sérgio |
| 10:15 | **USB backup** of the whole `junctionx-sensei` folder (keep the stick private: `gemini_key.txt` is inside). Run `SUBMIT.bat data\val_sim` once yourself so the first time is not on validation day | Sérgio |
| 10:30 | **Fill in the Junction form** from `docs/submission_text.md`; save it as a draft. Check Junction/Discord for how the validation pictures arrive and what to hand in | Sérgio |
| 10:30 | Inês: review `docs/produce_biology_reference.csv`; test the app on your phone and tell Claude any wording that is wrong in Portuguese | Inês |
| 11:00 | **Rehearsal 1 and 2 out loud, with a timer.** Inês: slides 1 to 4 and 10. Sérgio: slides 5 to 9. Target 2:40 to 2:50, hard stop 3:00. Cut the optional lines if over 2:40 | both |
| 11:40 | **Rehearsal 3**, then the 90-second demo once (`pitch/demo_script.md`). Ask a mentor for a look when one is free | both |
| 12:00 | One tough-judge round with Gemini Live (paste `pitch/qa_prep.md`). Test `pitch/slides_standalone.html` on the presentation screen (open, press F) | both |
| 12:30 | **Submit the form** (do not wait for 12:55). Check the GitHub link opens from a logged-out browser | Sérgio |
| 12:40 | Final USB copy. Close nothing, shut nothing down | Sérgio |
| 13:00 | Deadline. Then keep the laptop awake for the validation pictures | |

## Why "sensei judge clarity" ran so long

It is an eight-step job (audit by five reviewers, code tidy-up, README and docs, pitch, coaching, polish, verify,
this summary), started at 02:33; the steps run one after another. The file times show that **nothing in the
project or the scratch folder was written between 04:38 and 08:39**. Windows logs no sleep that night, so the
job did not stop because the laptop slept. The tidy-up step (its "before" snapshot is stamped 04:37, its first edits
08:42) sat waiting; a blocked command or a waiting prompt are the likely causes, and the logs do not say which. After
it moved again at 08:39, all the remaining steps finished in about 30 minutes. If it happens again, check the Claude
app for a waiting prompt first. (An earlier note blamed slow work such as test runs; the file times do not support that.)

## Where things are

| What | Where |
|---|---|
| Start-here page | `README.md` |
| Method, limits, commands | `docs/HOW_IT_WORKS.md` |
| How the answer key was made | `docs/LABELLING_GUIDE.md` |
| Junction form text | `docs/submission_text.md` |
| Evidence for every number | `results/README.md` |
| Pitch script, numbers table | `pitch/pitch.md` |
| Slides (use this one on the laptop) | `pitch/slides_standalone.html` |
| Demo script / Q&A | `pitch/demo_script.md`, `pitch/qa_prep.md` |
| Validation day | `SUBMIT.bat` (main), `SUBMIT_LABEL_FREE.bat` (fallback) |
| Staff app on the dataset day | `outputs\rehearsal_0850\dashboard\index.html` |


## Sensei's answers on Discord (09:05)
- **Validation images come AFTER the 13:00 submission, from the same cameras.** Code and models are frozen at the
  submission commit (fingerprint: `results/model_manifest.json`). When the images arrive: drag the folder/zip onto
  **`SUBMIT.bat`** and hand in the file it prints. Keep this laptop working and don't touch `models/`.
- **"You have to train it"** (asked about look-alike products) - training is expected, so the trained model
  (`SUBMIT.bat`) is the one to use. `SUBMIT_LABEL_FREE.bat` is an emergency fallback only.
- **Products not in the planogram = not compliant** - already our rule (Q&A #24-26 in `pitch/qa_prep.md`).

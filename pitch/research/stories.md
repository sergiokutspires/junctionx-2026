# Real moments of the day (for the pitch)

Built 2026-10-11 from the raw frames of the 14 cameras (about one picture per camera per hour, Lisbon time = UTC+1) and
the AI answer key. Pictures: `pitch/assets/story_*.jpg` (1600 px wide, git-ignored because they show the store).
Rebuild: `.venv/Scripts/python pitch/assets/make_stories.py` (`--check` only re-verifies every time and status quoted
below against `data/labels/teacher_labels_v2.json`; the script stops if the key disagrees).

How to read the status words: they come from the **AI answer key** (`teacher_labels_v2.json`), three independent
labellers per area (`votes_round1.json` for cameras 6215/6371/6373, `votes_v2.json` for the rest). They are not the store's
truth: say "independent AI labellers agree", never "ground truth". Every panel used in the three main pictures is
3 of 3 on the checked field (stock level, or compliance for the wrong-product ones); the tomato picture has one 2 of 3.
Nothing in the pictures is model output. Every picture says so in its footer.

| File | Story | Camera / area | Use |
|---|---|---|---|
| `story_emptying.jpg` | bananas full, then bare | 6215 / 6 | main |
| `story_wrong_product.jpg` | oranges in the banana crates | 6215 / 3 and 5 | main |
| `story_restock.jpg` | bare, refilled, bare again | 6215 / 4 | main |
| `story_emptying_tomato.jpg` | full, half, nearly bare (early warning) | 6443 / 11 | alternative, or for the "running out soon" slide |
| `story_restock_morning.jpg` | whole gondola bare to stocked, trolley in view | 6491 / all 10 | extra |
| `story_wrong_product_6468.jpg` | second wrong-product case, other camera | 6468 / 12 | extra, "not one lucky camera" |

---

## 1. EMPTYING: bananas, camera 6215, area 6

- Product: BANANA CAT I CNT KG. Bananas are 10 of the 152 planogram areas (third by product family, after potatoes 19 and
  tomatoes 12); BANANA CAT I alone is on 6 areas, tied with BATATA BRANCA 3KG for the most of any product. That is shelf
  space, not sales: do not say "best seller".
- Times (key, all 3 of 3): 08:33 full, 09:34, 10:40, 11:49, 12:59, 14:08 full (six full pictures in a row), then
  15:14 **empty**, 16:20, 17:24, 18:35 **empty** (four empty pictures in a row, 3 h 21 min from the first to the last,
  never refilled before the last picture of the day). The picture shows 08:33, 12:59, 15:14, 18:35. 14:08 is only quoted
  in the caption: the key says full, but the area is only partly covered, so it is not in the strip.
- Headline on the picture: **Full at 12:59, bare by 15:14**
- Caption: *Bananas, area 6: stocked at 14:08, bare at 15:14, and still bare at the last picture (18:35).*
- Presenter line: "Same banana area: full at 12:59, bare at 15:14 and still bare at 18:35, so the app can raise it in the first picture
  it is empty, not the fourth."
- System cross-check (label-free core, `models/real_v1/series.json`, no label used to fit; real_v2 and real_v3_cal give the
  same shape): shelf fill 1.00 at 14:08, 0.09 at 15:14, 0.00 at 18:35. Say it as "our fill reading drops from full to
  nothing on the same pictures", not as a score.

## 2. WRONG PRODUCT: oranges in the banana crates, camera 6215, areas 3 and 5

- Plan (start of day): BANANA CAT I in both areas. Camera: loose oranges in teal crates (the labellers' own words, all 3).
- Times (key, all 3 of 3, both areas): 06:14 **wrong**, 07:23 **wrong**, 08:33 compliant (bananas), and compliant at every
  later picture. So: wrong at both opening pictures, corrected somewhere in the 70 minutes between 07:23 and 08:33.
- Headline: **06:14: oranges in the banana crates**
- Caption: *Wrong at 06:14 and still at 07:23, corrected by 08:33: the camera sees the mismatch and the fix.*
- Presenter line: "At 06:14 the plan says bananas and the camera sees oranges; by 08:33 someone has put bananas in, and the app
  puts that on the move-back list the moment it appears."
- System cross-check (label-free core `models/real_v1`, no heads, run on the raw frames on 2026-10-11): it flags both areas at both
  opening pictures and clears them at 08:33. Probability that the area holds the planned product: area 3 0.25 (06:14), 0.30 (07:23),
  0.996 (08:33); area 5 0.15, 0.14, 1.00. It also names the intruder: "algarve orange". It flags areas 7 and 9 from 08:33 on as
  well, like the key. On all 614 area-pictures of cameras 6215, 6443, 6468 and 6491 it raised 0 false wrong-product alarms and
  flagged 31 of the 42 the key marks wrong. Not held out (the core is label-free, but its defaults were chosen while looking at this
  key), so say "our core sees it too", not an accuracy number.
- **Caveat, read before pointing at the lower row.** The picture crops out areas 7 and 9 (planned: oranges). From 08:33 to
  the last picture (18:35) those two crates hold bananas, and the key marks them wrong in all ten pictures, 3 of 3. It may
  simply be that the store changed the plan during the morning (`planogram.json` is the start-of-day plan). Do not present it as a
  store mistake; if someone points at the 08:33 row, say the app checks against whichever plan the store gives it.

## 3. RESTOCK: bananas, camera 6215, area 4

- Product: BANANA CAT I CNT KG (same island as story 1).
- Times (key, all 3 of 3): 12:59 half, 14:08 **empty**, 15:14 **full**, 16:20 half, 17:24 **empty** (one bunch left in the
  area, labellers medium or low confidence on that one), 18:35 empty. The picture shows 12:59, 14:08, 15:14, 17:24.
- Headline: **Empty at 14:08, refilled by 15:14**
- Caption: *Area 4 was bare at 14:08, refilled within 66 minutes, and down to one bunch by 17:24.*
- "66 minutes" is the gap between two pictures, not a measured restock time: say "between two pictures".
- Presenter line: "Bare at 14:08, full at 15:14, nearly bare again at 17:24: with a picture every hour the timeline shows how long a
  gap lasts and how long a refill holds."
- System cross-check (label-free fill): 0.69 at 12:59, 0.09 at 14:08, 1.00 at 15:14, 0.10 at 17:24.

## 4. Alternative emptying: plum tomatoes, camera 6443, area 11 (the "running out soon" picture)

- Product: TOMATE CHUCHA CNT KG (plum tomatoes). Times (key): full 06:14 to 10:33 (five pictures), **half 11:38**, **empty
  12:39**, and empty at every picture after, to 18:07 (5 h 28 min, never refilled). The picture shows 10:33, 11:38, 12:39, 18:07.
  Agreement: 3 of 3 everywhere except 12:39 (2 say empty, 1 says half; about eight tomatoes are left at the bottom).
- Headline: **Full at 10:33, nearly bare by 12:39**
- Caption: *Tomatoes, area 11: full at 10:33, half at 11:38, almost nothing at 12:39, and no refill by 18:07.*
- Presenter line: "Tomatoes are half full at 11:38 and nearly gone an hour later; that half-full picture is where the app says
  'running out soon'."
- System cross-check (label-free fill): 0.94, 0.38, 0.04, 0.03 for real_v1 (0.64, 0.17, 0.00, 0.01 for real_v2/v3: the
  scale moves between model versions, the fall does not). Do not quote the fill numbers on stage.
- Why it is the alternative, not the main one: the bananas end on a truly bare area at 15:14 and 18:35, the tomatoes end on
  a handful, which the key calls empty but a sceptic may not.

## 5. Extra: a whole gondola restocked, camera 6491

- Plan: nectarines, peaches, apricots (ALPERCE, PESSEGO, NECTARINA), 10 areas. Times (key): 06:14 all 10 **empty** (bare
  crates and shelves), 07:26 7 full / 1 half / 2 empty with a **restock trolley and crate in the picture**, 08:40 all 10 **full**.
- Headline: **Bare at 06:14, stocked by 08:40**
- Caption: *A whole gondola from bare crates to full: the camera catches the restock under way, not just the result.*
- Presenter line: "Same gondola at 06:14, 07:26 and 08:40: bare, then the restock trolley in the picture with seven areas done, then
  all ten full."
- This is the clearest picture in the data of restock work in progress (staff trolley and crate visible). It is routine opening restock, not a sell-out, so use it
  for "the camera sees the restock", not for "lost sales".

## 6. Extra: wrong product on a second camera, 6468 area 12

- Plan: BANANA PAO CNT KG (cooking banana). Camera: dark purple passion fruit (all 3 labellers). Times (key, 3 of 3):
  06:12, 07:29, 08:37 **wrong**; 09:38 compliant (green cooking bananas), and compliant after. The neighbouring areas show
  the same slot shuffle at opening: areas 7, 8, 11, 13 and 14 are also marked wrong until 08:37 (area 14 is 2 of 3 at 06:12).
- Headline: **06:12: passion fruit in the banana slot**
- Caption: *A second camera, the same pattern: wrong at opening, corrected by 09:38.*
- Presenter line: "It is not one lucky camera: on 6468 passion fruit sat in the banana slot until 08:37 and was corrected by 09:38."
- System cross-check (same run): probability of the planned product 0.44 (06:12), 0.30 (07:29), 0.43 (08:37), 0.998 (09:38); it names
  "purple passion fruit".

---

## What was searched and why these

Searched every area in every picture of the key (181 frames, 14 cameras, 1,962 area-pictures).
Ranked by: a full picture followed by an empty one, vote agreement, how clear the bare surface is to a stranger, how
big the product's presence is. Rejected, so nobody wastes time on them: **6371 area 3 (melon)**: empty 11:49 to 14:58 then
restocked, a great timeline, but at 06:12 the crate holds netted melons that do not look like the planned
"melao verde", so a sharp audience would question the product; **6376 areas 3 to 5 (kiwi)**: the labellers split 2 to 1 on whether the product is wrong;
**6594 area 6 (onions)**: wrong only because the onions are in net bags instead of loose, too subtle for a slide;
**6462 area 1 (strawberries)**: popular and emptying, but the crate changes (metal tray, cardboard, teal crate) and it
reads worse than bananas; **6215 areas 2 and 8**: the "empty" pictures still have a banana or two in the area.

## Busy moment with shoppers

**There is no busy moment in this data.** The cameras give one still per hour per camera, and shoppers are almost never in
the frame. Checked two ways: by eye on a contact sheet of every picture of every camera, and with the local OWLv2 detector
(`a person`, `a human hand`, threshold 0.15) over all 181 frames: zero person detections (the four "hand" hits are one
fixed object on camera 6781). The only human traces are head fragments at the frame edge (6781 at 09:45, 6385 at 12:40) and
staff or shopper carts: restock trolley on 6491 at 07:26, a crate cart on 6215 at 07:23, a pallet of pineapples on 6215 at 08:33,
carts on 6781 07:30 to 09:45, a shopper's trolley on 6383 at 19:28. The best real "people at work" picture is story 5 (the 6491
restock). Do not claim the system copes with crowds: nothing here tests it.

## Things not to say

- Not "sold out", "lost sales" or "customers could not buy": we see the shelf, not the shoppers, and the area next to
  an empty one often holds the same product.
- Not "staff refilled at 14:30": the data only says between two pictures.
- Not "our model scored these": the pictures show the answer key; the system cross-check lines are in this file only.

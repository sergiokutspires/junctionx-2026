# 90-second live demo: the staff dashboard

Goal: show that a member of staff knows what to do in seconds, and that the same pictures also say what is
coming. Say the sentence in quotes, do the action beside it. The dashboard is one static page, so no server,
no network and no login.

Two versions:

- **Full demo (about 90 seconds)**, table below. Use it in Q&A or after the 3-minute pitch.
- **Short demo (about 40 seconds)** inside the pitch, replacing the talking on slides 6 and 7: beats 0:00, 0:10,
  0:32 and 1:04 of the table (counters, first card with its count, wrong-product card, Insights).

## Before you go on stage (2 minutes, do it once)

1. Open `outputs/real_v1_cal/dashboard/index.html` in the browser (double-click, or
   `start outputs\real_v1_cal\dashboard\index.html`). Full-screen it (F11) and zoom with Ctrl and +
   until the cards read from the back of the room.
2. Check three things: the **Do now** list loads, the gondola view has a **Show detections** button, the
   tab bar has an **Insights** tab, and cards show an "about N visible units" line. If any is missing, rebuild with
   the cached boxes (no network and no model run needed, about a minute at most):

   ```powershell
   .venv\Scripts\python -m sensei dashboard --details outputs/real_v1_cal/details.json `
       --data data/raw/images --out outputs/real_v1_cal/dashboard `
       --detections cache/colab/sensei_colab_features.zip
   ```

   (The `submission\dashboard` folder that `SUBMIT.bat` builds has the same features once it has run; use it
   instead when you have just processed the validation images.)
3. Open four tabs of the same folder: tab 1 on `index.html` (Do now), tab 2 on the shortcut
   `index.html#/gondola/6215/6215_7/det` (gondola 6215, the wrong-product area, boxes already on), tab 3 on
   `index.html#/products` (counts per product), tab 4 on `index.html#/insights`.
4. Put the phone-sized view ready: either your phone with the folder copied over, or a narrow browser
   window (375 px wide).
5. Keep `pitch/assets/dash_desktop.png`, `dash_gondola.png`, `dash_counts.png` and `dash_insights.png` open in
   an image viewer as the fallback (see the end).

The counters on the first screen are read off the screen, not memorised. In the build we
checked they were 24 empty, 45 low, 1 wrong product and 82 OK (152 areas, the late-day pictures);
say whatever the screen says. Do the same for every count and every Insights line: read it, do not recite it.

## The script

| Time | Do | Say |
|---|---|---|
| 0:00 | Tab 1, top of the page. Point at the four counters. | "A shift starts. Staff open the app and see four numbers: empty, low, wrong product, OK. Nothing to read, nothing to configure." |
| 0:10 | Scroll slowly down the **Do now** list. Stop on the first card (camera 6215, banana, empty). Point at the "visible units" line. | "Below is the to-do list, in the order that matters: wrong product and empty first, then low. Each card says what to do in plain words: Restock, shelf is empty. There is the photo, the outlined area, how sure we are, and an estimate of how many units we can see." |
| 0:26 | Tick **Mark done** on that card. Watch the progress bar move. | "Staff tick it off and the list shrinks." |
| 0:32 | Click **Show on gondola** on any card, then switch to tab 2 (gondola 6215, area 7 selected, boxes on). Read the card on the right aloud. | "One tap takes you to the gondola, with every area coloured by its status. This area is planned for Algarve orange, and the app says: it looks like banana, move it back. That is the wrong-product case the planogram check exists for." |
| 0:46 | Hover a box (for example "Bananas, 52%"), then click **Show detections** off and on. | "Behind this button are the boxes from a free open-vocabulary detector. Off by default so staff see a clean picture; on when they want to check our reasoning. The same boxes give the unit counts." |
| 0:56 | Switch to tab 3 (**Products**). Point at the Banana card: the "visible units in N areas (estimate)" line. | "Added up per product: about this many visible units. It says estimate on purpose: a banana unit is a bunch, and a pile hides what is underneath." |
| 1:04 | Switch to tab 4 (**Insights**). Point at **Running out soon** and read the first row aloud, then scroll to **Sales speed** and **Planogram adherence**. | "And the manager's view, from the same pictures. Running out soon: shelves forecast to be empty within two hours, soonest first. Sales speed: how fast each product sells, with restocks spotted. Planogram adherence: which gondolas hold the wrong product." |
| 1:20 | Press the **PT** button once, then back to **EN**. | "English or Portuguese, and the same page works on a phone." |
| 1:26 | Stop. Back to the slides (or the Q&A). | "That is the whole loop: see, decide, act, and see what is coming." |

## If it goes wrong

| Problem | Do this |
|---|---|
| The page does not open | Open `pitch/assets/dash_desktop.png` (the Do now view), then `dash_gondola.png` (area 7 with boxes), `dash_counts.png` and `dash_insights.png`. Same script, say "this is the live page, captured earlier". |
| No **Show detections** button, no visible units, or no **Insights** tab | Do not apologise. Skip the boxes and counts sentences, use the 0:32 line, and say the boxes are an optional extra. Fix with the rebuild command above after the talk. |
| The shortcut link opens the wrong place | Click **Gondolas**, choose camera 6215 and click area 7; **Products** and **Insights** are in the tab bar. |
| Counters, counts or Insights lines look different from this script | Read what is on screen. The page may have been rebuilt on the hidden validation pictures, which is fine. |
| A card is slow or an image is missing | Move on to the next card; every card follows the same pattern. |
| Projector is low resolution | Ctrl and + to zoom the browser; the layout is built for 375 px phones, so it copes. |
| Running out of time | Use the short demo: the **Do now** list (0:10), the wrong-product card (0:32) and **Insights** (1:04). Drop 0:26, 0:56 and 1:20 first. |
| Laptop dies | Use the phone: copy the whole `dashboard` folder over, open `index.html`, and run the same script on the phone screen. |

## What not to claim in the demo

- The pictures are from the training day (the late frames of 27 June), not the hidden validation
  set, unless you rebuilt on it. Say "pictures from the dataset day".
- Counts are estimates of visible units (the app says so), not inventory. For bunches such as bananas a
  unit is a bunch.
- The timeline, "Empty in about N minutes", Running out soon, Sales speed and the peak-hour lines are model
  estimates from one day of pictures: a prototype of forecasting and analytics, not scored features. Do not
  quote a number from them as a finding.
- Marks on the story slides were added by eye; marks in the app come from the model.

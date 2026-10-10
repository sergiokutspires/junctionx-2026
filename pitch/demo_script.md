# 90-second live demo: the staff dashboard

Goal: show that a member of staff knows what to do in seconds. Say the sentence in quotes, do the
action beside it. The dashboard is one static page, so no server, no network and no login.

## Before you go on stage (2 minutes, do it once)

1. Open `outputs/real_v1_cal/dashboard/index.html` in the browser (double-click, or
   `start outputs\real_v1_cal\dashboard\index.html`). Full-screen it (F11) and zoom with Ctrl and +
   until the cards read from the back of the room.
2. Check that the **Do now** list loads and that the gondola view has a **Show detections** button.
   If the button is missing, rebuild with the cached boxes (no network and no model run needed):

   ```powershell
   .venv\Scripts\python -m sensei dashboard --details outputs/real_v1_cal/details.json `
       --data data/raw/images --out outputs/real_v1_cal/dashboard `
       --detections cache/colab/sensei_colab_features.zip
   ```

3. Open two tabs: tab 1 on `index.html`, tab 2 on the shortcut
   `index.html#/gondola/6215/6215_7/det` (gondola 6215, the wrong-product area, boxes already on).
4. Put the phone-sized view ready: either your phone with the folder copied over, or a narrow browser
   window (375 px wide).
5. Keep `pitch/assets/dash_desktop.png` and `dash_gondola.png` open in an image viewer as the
   fallback (see the end).

The counters on the first screen are read off the screen, not memorised. In the build we
checked they were 24 empty, 45 low, 1 wrong product and 82 OK (152 areas, the late-day pictures);
say whatever the screen says.

## The script

| Time | Do | Say |
|---|---|---|
| 0:00 | Tab 1, top of the page. Point at the four counters. | "A shift starts. Staff open the app and see four numbers: empty, low, wrong product, OK. Nothing to read, nothing to configure." |
| 0:12 | Scroll slowly down the **Do now** list. Stop on the first card (camera 6215, banana, empty). | "Below is the to-do list, in the order that matters: wrong product and empty first, then low. Each card says what to do in plain words: Restock, shelf is empty. There is the photo, the outlined area, how sure we are, and when the picture was taken." |
| 0:30 | Tick **Mark done** on that card. Watch the progress bar move. | "Staff tick it off and the list shrinks." |
| 0:38 | Click **Show on gondola** on any card. | "One tap takes you to the gondola, with every area coloured by its status." |
| 0:46 | Switch to tab 2 (gondola 6215, area 7 selected, boxes on). Read the card on the right aloud. | "This area is planned for Algarve orange, and the app says: it looks like banana, move it back. That is the wrong-product case the planogram check exists for." |
| 1:00 | Hover a box (for example "Bananas, 52%"), then click **Show detections** off and on. | "Behind this button are the boxes from a free open-vocabulary detector. Off by default so staff see a clean picture; on when they want to check our reasoning." |
| 1:12 | Point at the **Stock during the day** line under the card. If a Low card with an "Empty in about N min" line is on screen, point at it instead. | "Every area has its whole day as a timeline, and for low shelves a warning of when it will be empty. That is the seed of restock forecasting." |
| 1:22 | Press the **PT** button once, then back to **EN**. | "English or Portuguese, and the same page works on a phone." |
| 1:28 | Stop. Back to the slides (or the Q&A). | "That is the whole loop: see, decide, act." |

## If it goes wrong

| Problem | Do this |
|---|---|
| The page does not open | Open `pitch/assets/dash_desktop.png` (the Do now view), then `dash_gondola.png` (area 7 with boxes). Same script, say "this is the live page, captured earlier". |
| No **Show detections** button | Do not apologise. Skip the boxes sentence, use the 0:46 line, and say the boxes are an optional extra. Fix with the rebuild command above after the talk. |
| The shortcut link opens the wrong place | Click **Gondolas**, choose camera 6215 and click area 7. |
| Counters look different from this script | Read what is on screen. The page may have been rebuilt on the hidden validation pictures, which is fine. |
| A card is slow or an image is missing | Move on to the next card; every card follows the same pattern. |
| Projector is low resolution | Ctrl and + to zoom the browser; the layout is built for 375 px phones, so it copes. |
| Running out of time | Drop the 0:30 and 1:22 beats. The two that matter are the **Do now** list (0:12) and the wrong-product card (0:46). |
| Laptop dies | Use the phone: copy the whole `dashboard` folder over, open `index.html`, and run the same script on the phone screen. |

## What not to claim in the demo

- The pictures are from the training day (the late frames of 27 June), not the hidden validation
  set, unless you rebuilt on it. Say "pictures from the dataset day".
- The timeline and the "empty in about N minutes" warning are a prototype of forecasting, not a
  scored feature.
- Marks on the story slides were added by eye; marks in the app come from the model.

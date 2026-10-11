# 90-second live demo: the staff app (Controlo de prateleiras)

Goal: show that a member of staff gets the brief's three answers in seconds, in Portuguese (what to restock first,
what to move back, what to leave alone), that the app says when it is unsure, and that the same pictures give the
manager a view of what is coming. Say the sentence in quotes (in English, for the jury), do the action beside it, and
point at the Portuguese label on screen. The app is one static page: no server, no network, no login.

Two versions:

- **Full demo (about 90 seconds)**, table below. Use it in Q&A or after the 3-minute pitch.
- **Short demo (about 40 seconds)**, only if the jury asks during the pitch: beats 0:00, 0:08, 0:22, 0:54 and 1:06.

## Before you go on stage (2 minutes, do it once)

1. The current demo page is `outputs/rehearsal_0850/dashboard/` (built 11 October, 08:48, from the current `ui/`
   files and the final model's answers, `real_v3_cal`). It opens in Portuguese by default, and every label in this
   script was read off that build. To rebuild into the older folder instead (no network and no model run, about a
   second):

   ```powershell
   .venv\Scripts\python -m sensei dashboard --details outputs/real_v3_cal/details.json `
       --data data/raw/images --out outputs/real_v3_cal/dashboard `
       --detections cache/colab/sensei_colab_features.zip
   ```

   (The `submission\dashboard` folder that `SUBMIT.bat` builds has the same features once it has run; use it instead
   when you have just processed the validation images.) If you skip the rebuild, or the browser remembers English,
   press **PT** once at the top right; the choice is remembered.
2. Open `outputs/rehearsal_0850/dashboard/index.html` (double-click, or `start outputs\rehearsal_0850\dashboard\index.html`).
   Full-screen it (F11) and zoom with Ctrl and + until the cards read from the back of the room.
3. Check: the title reads **Controlo de prateleiras**; the tab bar has **Fazer agora, Gôndolas, Produtos, Análise**; the
   gondola view has a **Mostrar deteções** button; the **Produtos** tab shows "≈ N unidades visíveis" (task cards
   show no counts); on **Fazer agora**, **Hora de fecho** (top right of the list) reads **21:00** and the grey note
   "Perto do fecho (21:00): os reforços de produtos perecíveis ficam para amanhã." is shown. The setting is
   remembered by the browser: if someone changed it while rehearsing, set it back to 21:00.
4. Open three tabs of the same folder: tab 1 on `index.html` (Fazer agora), tab 2 on
   `index.html#/gondola/6215/6215_7/det` (gondola 6215, the wrong-product area, boxes already on), tab 3 on
   `index.html#/insights` (Análise).
5. Phone view ready: your phone with the folder copied over, or a narrow browser window (375 px wide).
6. Fallback pictures open in an image viewer (see the end): `pitch/assets/pt_mobile.jpg`, `pt_card_restock.jpg`,
   `pt_card_move.jpg`, `pt_insights.jpg` (all four retaken from the current app on 11 October). The older
   `pt_card_low.jpg`, `pt_leave.jpg`, `pt_gondola.jpg` and `pt_products.jpg` show the previous wording; use them only
   as a last resort.

Read every number off the screen; do not memorise it. In the build we checked (11 October, 10:15, `real_v3_cal`, closing
time 21:00), all cameras showed 24 Vazio, 41 Baixo, 1 Produto errado and 86 OK (152 areas, pictures from 18:07 to 20:16),
"Fazer agora · 66 tarefas" (Primeiro 25, Depois 16, **Deixar até amanhã (perto do fecho) 25**; the 13 freshness checks
under "Quando houver tempo: verificar frescura" are extras), and camera 6215 alone showed "7 tarefas": 1 Produto
errado (zona 7), 5 Vazio, and zona 5 (Banana, Baixo, "Confiança: Baixa: confirmar à vista") under **Deixar até amanhã
(perto do fecho)**, then "Deixar: 3 zonas estão certas". The newest pictures are from 20:16, within 2 hours of the
21:00 closing time, so closing-time mode is on. (With Hora de fecho at 23:30 the list is the old one: Depois 41, and
zona 5 sits under "Depois: a ficar baixo".) Say whatever the screen says.

## The script

| Time | Do | Say |
|---|---|---|
| 0:00 | Tab 1, top of the page. Point at the four counters (**Vazio, Baixo, Produto errado, OK**), then at **Primeiro: produto errado e vazio** and its count. | "A shift starts. The app opens in Portuguese: empty, low, wrong product, OK. Wrong products and empty shelves come first; low shelves are the next round." |
| 0:08 | In the camera filter, choose **Câmara 6215**. | "Let's take one gondola, camera 6215." |
| 0:12 | Point at a **Vazio** card: **Banana, Repor: está vazio**, its photo, **Confiança: Alta** and **Visto às 18:35**. | "Your first answer: what to restock first. Repor: the banana tray is empty. The photo, how sure we are, and when the camera saw it." |
| 0:22 | Point at the **Produto errado** card (zona 7): **Trocar: aqui devia estar Citrinos do Algarve Laranja, mas está Banana.** and **Levar Banana para: Câmara 6215 · zonas 2, 3, 4**. Click **Ver na gôndola** (or switch to tab 2). | "Second answer: what to move back. This spot should hold Algarve oranges; it holds bananas. Trocar, and it says where the bananas go." |
| 0:36 | On the gondola view, hover a box, then click **Mostrar deteções** off and on. | "Behind this button are the boxes from a free open-vocabulary detector. Off by default, so staff see a clean picture; on when they want to check our reasoning." |
| 0:46 | Back to **Fazer agora**. Scroll to **Deixar até amanhã (perto do fecho)**, the **Baixo** card (zona 5, Banana) with **Confiança: Baixa: confirmar à vista**. Point at the grey reason line above it. | "When it is not sure, it says so: confirmar à vista, check by eye. And these pictures are from 20:16, close to closing, so this banana top-up waits until tomorrow: less fruit out overnight. Empty shelves and wrong products never wait." |
| 0:54 | Scroll to the bottom: **Deixar: 3 zonas estão certas**. | "Third answer: what to leave alone. Three areas look right; nobody walks there." |
| 1:00 | Tick **Marcar feito** on one card. Watch the progress bar. | "Done, and the list shrinks." |
| 1:06 | Switch to tab 3 (**Análise**). Point at **Destaques**, then **A acabar em breve**, then scroll to **Velocidade de vendas** and **Cumprimento do planograma**. | "And the manager's view, from the same pictures: shelves forecast to be empty within two hours, how fast each product sells, which camera views follow the plan, and a count of products that barely moved all day, to check they are still fresh. All marked as estimates." |
| 1:20 | Back to tab 1. Click the **print** icon (top right); show the preview, then cancel. | "And the morning sheet for the team lead: every task, a tick box each, on one page." |
| 1:28 | Stop. Back to the slides (or the Q&A). | "Repor, Trocar, Deixar, and see what is coming." |

## Optional: "replay the day" (about 20 seconds, only AFTER the pitch)

Use it in Q&A or when a judge asks "what happens over a day?" or "how would this feed our alerts?". It is a
separate build of the same app over all 181 pictures of the dataset day; it is not in the slides.

**Setup (once):** open a fourth tab on
`outputs/day_replay/dashboard/index.html#/day/1514/6376/6376_12` (rebuild commands: README, "What's new"). Check:
the clock reads **15:14**, the tab **Dia** is highlighted, camera **6376** is picked, area 12 is outlined orange,
and the top row of **O que aconteceu** reads "15:13 Câmara 6376 · zona 12 · Clementina: ficou vazia". Fallback
picture: `pitch/assets/dash_replay.png` (the same view).

| Time | Do | Say |
|---|---|---|
| 0:00 | Tab 4. Point at the orange area 12 on the picture, then at the top row of **O que aconteceu**. | "Same app, replaying the dataset day. At 15:13 the clementine crate went empty, and here is the picture." |
| 0:06 | Click **Reproduzir o dia**. Do nothing else: it plays to 20:30 in about 5 seconds and stops by itself. | "An hour a second: the counters, the picture and the list follow the day. The bars above the slider are the store's pulse." |
| 0:13 | Click the third bar from the left (07:30; its tooltip reads "07:30: 24 Vazio, 32 Baixo, 5 Produto errado"). Point at the log rows "07:29 … reposição detetada". | "The tall bars on the left are the shelves before the morning restock; every change is an event with a time, an area and a product, the kind of event your alerts carry. These are the pictures the model was calibrated on, so this shows the experience, not accuracy." |
| 0:20 | Stop. | |

Say the last sentence; the page shows the same caveat. Do not quote event counts from the replay as accuracy.

## If it goes wrong

| Problem | Do this |
|---|---|
| The page does not open | Show the fallback pictures in this order: `pt_mobile.jpg`, `pt_card_restock.jpg`, `pt_card_move.jpg`, `pt_insights.jpg`, or the deck's slides 3 and 4. Same script; say "this is the live page, captured earlier". |
| The page opens in English | Press **PT** once at the top right and carry on. |
| No **Mostrar deteções** button, no visible units, or no **Análise** tab | Do not apologise. Skip the boxes sentence and say the boxes are an optional extra. Fix with the rebuild command above after the talk. |
| The shortcut link opens the wrong place | Click **Gôndolas**, choose Câmara 6215 and click zona 7; **Análise** is in the tab bar. |
| Counters, cards or Análise lines differ from this script | Read what is on screen. The page may have been rebuilt on the hidden validation pictures, which is fine; then camera 6215 may show different cards, so use whichever cards show Repor, Trocar and Deixar. |
| A card is slow or an image is missing | Move on to the next card; every card follows the same pattern. |
| Projector is low resolution | Ctrl and + to zoom the browser; the layout is built for 375 px phones, so it copes. |
| Running out of time | Use the short demo: beats 0:00, 0:08, 0:22, 0:54 and 1:06. |
| Laptop dies | Use the phone: copy the whole `dashboard` folder over, open `index.html`, and run the same script on the phone screen. |

## What not to claim in the demo

- The pictures are from the dataset day (the late frames of 27 June), not the hidden validation set, unless you
  rebuilt on it. Say "pictures from the dataset day".
- Counts are estimates of visible units (the app says *estimativa*), not inventory. For bunches such as bananas a
  unit is a bunch.
- The timeline, "Vazio daqui a ~N min", A acabar em breve, Velocidade de vendas and the Destaques lines are model
  estimates from one day of pictures: a prototype of forecasting and analytics, not scored features. Do not quote a
  number from them as a finding.
- "Slow movers" is a prompt to check freshness, not a waste measurement.
- *Marcar feito* is saved on that device only, and tasks in *Fazer agora* do not close themselves yet; if asked, say
  both are next steps (see `qa_prep.md` question 22). The closing-time mode **is** built (beat 0:46); *Está certo
  assim* is not, so do not demo it.
- The closing-time rule (hold short and medium shelf-life top-ups in the last 2 hours) is a design choice from
  shelf-life classes; we have not measured its effect on waste. "Now" is the time of the newest picture, not the
  clock on the wall.
- The print sheet is grouped by camera, not by walking route. Do not call it a route.
- Marks on the story slides were added by eye; marks in the app come from the model.

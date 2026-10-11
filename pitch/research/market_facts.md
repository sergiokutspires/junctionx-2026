# Market facts for the Sensei pitch

Research done 2026-10-11. Purpose: credible, sourced figures about the business problem (fresh-produce waste, empty
shelves, staff time, planogram compliance, the value of real-time shelf monitoring) that we may say in front of
Sensei, who is both sponsor and jury.

How to read this file

- Every figure is kept exactly as its source states it, with its own scope (region, year, category, unit). Figures
  from different scopes are never added, averaged or merged. Where I did my own arithmetic it is labelled
  "our arithmetic" and kept out of the headline.
- Safety grade for quoting in a pitch:
  - **A** = quote with attribution. Official or peer-reviewed source, and the scope matches what you would say.
  - **B** = quote only with its scope spoken aloud (country, year, "one retailer", "survey", "US"). Real source, but
    old, narrow, an estimate, or confirmed only through a second-hand copy.
  - **C** = context for us, do not say on stage. Vendor claim, self-reported result, trade press, or not traced to
    a primary source.
  - **X** = do not use. Conflicting, untraceable, or misleading outside its scope.
- "Fetched" means I read the page or document itself. "Search summary only" means I did not open the primary document.
- The jury knows this domain. A narrow, correct number beats a big, loose one.

---

## 0. Shortlist: the facts I would actually use (each with the exact wording that keeps it true)

| # | Safe sentence | Scope kept in the sentence | Grade | Detail |
|---|---|---|---|---|
| 1 | "Eurostat estimates that retail and distribution in Portugal wasted about 21 kg of food per inhabitant in 2024, against about 10 kg for the EU average." | All food (edible and inedible), tonnes of fresh mass, Eurostat estimate for Portugal | B | W3 |
| 2 | "In Austria, where large retailers must report, fruit and vegetables were about 45% of the food retailers discarded in the last quarter of 2023." | Austria, Q4 2023, retailers that assigned product groups | B | P1 |
| 3 | "EU law now sets binding 2030 food-waste targets: minus 30% per capita, counted jointly across retail, food service and households, against a 2021-2023 average." | Directive (EU) 2025/1892; the 30% is a joint target, not a retail-only target | A | W5 |
| 4 | "Sonae MC has publicly committed to cut food waste by 50% by 2028 against 2020." | Company commitment, no progress figure published in what I found | B | W8 |
| 5 | "In the best-known out-of-stock study, about a quarter of empty-shelf events were products that were in the store but not on the shelf." | Gruen, Corsten and Bharadwaj 2002, fast-moving consumer goods, not fresh | B | O3 |
| 6 | "When a shopper meets an empty shelf, the retailer loses the sale about 40% of the time: 31% buy it elsewhere, 9% do not buy." | Average over 8 packaged categories, 2002 study | B | O2 |
| 7 | "In a McKinsey survey of 23,000 European shoppers, quality was the biggest factor in whether they would recommend a store's fresh-produce department." | Four European countries, 2018 | B | V6 |
| 8 | "Retail executives estimate that about a quarter of hourly store-associate hours go to stocking shelves." | Wharton 2022 survey, 60 executives in 10 countries, mostly grocery; estimates, not time studies | B | S1 |
| 9 | "Fixed shelf cameras are already being rolled out chain-wide by Walmart Canada to flag empty and low-stock shelves." | Fact of the rollout (2022); no result numbers were published | A | V3 |
| 10 | "Ceiling cameras suit produce, where there are no barcodes and no packaging, which is the case Sensei's own page names as the hard one." | Needs a read of the Sensei page before saying it | C | I3 |

Two honest warnings that make us look more credible if we volunteer them: (a) the best planogram-compliance study
(Gruen and Corsten) found only a small effect of compliance on out-of-stocks, because compliance was already
above 90% in the stores studied (G1); (b) I found no credible published out-of-stock rate for fresh produce
specifically (O8), so any produce-specific "lost sales" number would be invented.

---

## 1. Food waste in retail: EU and Portugal

### W1. EU food waste, 2024 data (latest vintage)
- **Figure:** 57.9 million tonnes of food waste in the EU in 2024, about 129 kg per inhabitant, edible and inedible
  parts included. Retail and other distribution of food: 8%, 10 kg per inhabitant. Households 53% (69 kg),
  manufacture of food and beverages 19% (25 kg), restaurants and food services 12% (15 kg), primary production 8%
  (10 kg).
- **Scope:** EU-27, reference year 2024, all food, tonnes of fresh mass. Bulgaria, Germany and Romania unavailable
  for 2024.
- **Source:** Eurostat news item "Food waste in the EU: 129 kg per person in 2024", 29 September 2026.
  https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20260929-1 (fetched). Statistics Explained:
  https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Food_waste_and_food_waste_prevention_-_estimates (fetched).
- **Safety: A.** Say "all food, including inedible parts". It is not a produce number. The Eurostat category
  "retail and other distribution of food" is coded G46_G47 (wholesale and retail trade of food), so it is not
  supermarkets alone (inferred from the code in the dataset).

### W2. EU food waste, 2023 data
- **Figure:** Latest vintage of the dataset: 57.5 million tonnes, 128 kg per inhabitant; retail and other
  distribution 4.5 million tonnes, 10 kg per inhabitant. The first 2023 release (16 October 2025) said 58.2 million
  tonnes, about 130 kg, retail 8% and 10 kg. The numbers were revised, so quote one vintage only.
- **Source:** Eurostat database `env_wasfw`, queried through the API, data updated 2026-09-28
  (https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/env_wasfw, fetched). First release:
  https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20251016-2 (search summary only).
- **Safety: A** for the latest vintage; do not mix it with the 58.2 million tonne figure.

### W3. Portugal retail and distribution food waste, Eurostat
- **Figure:** "Retail and other distribution of food", Portugal: 21 kg per inhabitant in 2022, 2023 and 2024;
  232,420 tonnes in 2023 and 235,933 tonnes in 2024. All flagged "e" (estimated). EU-27 in the same table: 10 kg in
  2022, 2023 and 2024.
- **Same table, 2023, kg per inhabitant, for context:** ES 9, FR 12, IT 10, DE 9, PL 13, EL 20, IE 16, DK 18,
  NL 6, AT 8, BE 9, SE 10.
- **Scope:** Food waste of all food (edible and inedible), tonnes of fresh mass, NACE G46_G47 as above.
- **Source:** Eurostat `env_wasfw`, data updated 2026-09-28 (fetched, values read from the JSON for unit KG_HAB and T).
- **Safety: B.** The Portuguese values are Eurostat estimates, so say "estimated". Do not say "Portuguese retail
  wastes twice as much as the EU": definitions and national reporting methods differ between countries. Saying
  "about 21 kg per inhabitant, roughly twice the EU average figure" is true as a statement about the published
  numbers, but let the audience draw the conclusion.
- **Cross-check (our arithmetic):** INE says commerce and distribution were 12% of Portugal's 2023 total of about
  1.93 million tonnes (see W4); 12% of 1.93 million tonnes is about 232,000 tonnes, which matches Eurostat's
  232,420 tonnes. Two sources agree on the size.

### W4. Portugal food waste by link of the chain, INE
- **Figure:** 2023 (provisional): about 1.93 million tonnes wasted, 182.7 kg per inhabitant (2020: 174.5; 2021: 180.6;
  2022: 184.0). Share by link: households 66.8%, commerce and distribution 12%, restaurants, hotels and similar
  11.5%, primary production 6.8%, industry 2.9%. The wire report says waste in commerce and distribution has risen
  every year since 2020, while households fell in 2023.
- **Scope:** Portugal, 2023, all food, INE series (data extracted July and September 2025).
- **Source:** Lusa via Agroportal, 16 September 2025 (fetched) https://www.agroportal.pt/?p=1197620. Per-capita series:
  CNCDA/GPP presentation "ENCDA 2025+" citing INE (fetched, text layer):
  https://www.gpp.pt/images/Destaques/Programas_e_Apoios/ENCDA2025/Apresenta%C3%A7%C3%A3o_ENCDA_2025_GPP.pdf
- **Safety: B.** INE is the official source but I read it through a news report and a chart-based slide. Do not mix
  INE's 182.7 kg total with Eurostat's own Portugal total (156 kg in the same year), because they aggregate
  differently; for retail only use the 12% / tonnes pair, which agrees with Eurostat (W3).

### W5. Binding EU targets from 2030
- **Figure:** Directive (EU) 2025/1892 amends the Waste Framework Directive. Member States must reduce food waste by
  2030 by 10% in processing and manufacturing, and by 30% per capita **jointly** across retail and consumption
  (restaurants, food services and households). Reference: annual average 2021-2023 (a Member State may use 2020 if
  it notifies). The Commission must review the targets by the end of 2027, including possible binding targets for
  2035. Published in the Official Journal 26 September 2025, in force 16 October 2025.
- **Source:** European Commission, food waste reduction targets page (fetched)
  https://food.ec.europa.eu/food-safety/food-waste/eu-food-waste-relevant-legislation/food-waste-reduction-targets_en;
  Linklaters summary for the dates (fetched)
  https://sustainablefutures.linklaters.com/post/102l7yl/eu-revised-waste-framework-directive-to-cater-for-food-and-textile-waste-publish;
  European Parliament topic page, updated 11 September 2025 (fetched)
  https://www.europarl.europa.eu/topics/en/article/20240318STO19401/food-waste-reduction-what-eu-actions-are-there.
  I could not open EUR-Lex itself (empty page).
- **Safety: A** for the existence and the numbers. **Do not say "retailers must cut 30%"**: the 30% is a joint
  national target, and the binding duty is on Member States, not on a single store.

### W6. EU "cost" of food waste
- **Figure:** About EUR 132 billion "in market value" of EU food waste, citing Commission staff working document
  SWD(2023) 421. The Commission and Parliament pages give no year. A news report on the July 2023 proposal adds
  EUR 9.3 billion a year of collection and treatment cost (search summary only).
- **Scope:** EU, all sectors and all food; not retail, not produce. The year is not stated on the pages I read.
- **Source:** https://food.ec.europa.eu/food-safety/food-waste_en (fetched); Parliament page above (fetched).
- **Safety: B** for 132 billion if you say "all sectors, market value"; **C** for 9.3 billion. I found no
  retail-only euro figure for the EU and none for Portugal (see section 9).

### W7. Global context (UNEP)
- **Figure:** 2022: 1.05 billion tonnes wasted worldwide; households 60% (631 million tonnes), food service 28%
  (290), retail 12% (131).
- **Source:** UNEP Food Waste Index Report 2024, https://www.unep.org/resources/publication/unep-food-waste-index-report-2024
  (search summaries of the key messages only; the report itself not opened).
- **Safety: B.** Global scope; of little use for a Portuguese jury.

### W8. Sonae MC (operator of Continente) commitment
- **Figure:** Commitment to cut food waste 50% by 2028 against a 2020 base year, "two years ahead of the EU legal
  target". 2024 donations: 8,800 tonnes of food, 1,099 institutions, about EUR 30 million in total donations (food
  alone valued above EUR 28 million), from 393 stores. I found no figure for progress against the 50%.
- **Source:** Agroportal, "Missao Continente salva mais de 8 milhoes de refeicoes em 2024", 20 February 2025 (fetched)
  https://www.agroportal.pt/?p=1150337. The article calls the company "Continente" and "MC".
- **Safety: B.** It is the retailer's own public statement. It is the best "your own goal" hook, but ask "how is
  progress measured today?" rather than claiming we know it. Do not call the retailer "Sensei's parent": I did not
  establish the corporate link, and the store page speaks of Sensei and MC Sonae as partners.

---

## 2. Fresh-produce waste inside stores

### P1. Austria: fruit and vegetables in reported retail waste
- **Figure:** Last quarter of 2023, mandatory quarterly reporting by large food retailers: fruit and vegetables were
  about 45% of discarded food (44.96% in one source), bakery goods 19%, fresh goods 12%. For donated food, fruit and
  vegetables were 30%, dairy and bakery 23% each. About 4,000 outlets reported.
- **Scope:** Austria, Q4 2023, retailers that assigned their waste to product groups (the reporting is partly
  voluntary at product-group level). Legal basis: amendment of the Austrian Waste Management Act.
- **Source:** Vienna.at (APA), 1 March 2024 (fetched) https://www.vienna.at/supermarkte-meldeten-lebensmittelabfalle-uber-16-200-tonnen-landeten-im-mull/8597791;
  EU CAP Network practice abstract (fetched) https://eu-cap-network.ec.europa.eu/projects/practice-abstracts/food-waste-austria-consumer-and-retail-level_en.
- **Safety: B.** The two sources agree on about 45% but differ on tonnage (more than 16,200 t vs about 14,460 t
  discarded), so quote the share, never the tonnes. I did not reach the ministry's own quarterly report. A Swedish
  paper (P3) cites a different Austrian study with fruit and vegetables at 53% of the monetary value of retail
  waste; I did not trace it, do not use it.

### P2. Sweden 2010-2011: fruit and vegetable department, six supermarkets
- **Figure:** Relative to mass delivered: pre-store waste (rejections) 3.0%, in-store recorded waste 1.0%,
  in-store unrecorded waste 0.3%, in-store total 1.3%; 4.3% in total as stated in the journal paper (search
  summary). Tomatoes, bananas and lettuce were the largest items by tonnes (thesis, search summary).
- **Scope:** Six supermarkets, Uppsala-Stockholm region, 2010-2011, percent of mass delivered (not of sales).
- **Source:** M. Eriksson, "Retail food wastage: a case study approach to quantities and causes", licentiate thesis,
  SLU, 2012 (fetched) https://research.slu.se/en/publications/507c424a-45d8-4958-86e3-b56c7ad7002b. Journal paper:
  Eriksson, Strid, Hansson (2012), Resources, Conservation and Recycling 68: 14-20.
- **Safety: B.** Old, small, Swedish. The useful point for us is that part of the in-store waste (0.3 points of the
  1.3) was unrecorded, i.e. not seen by the store's own records.

### P3. Sweden 2018: three ICA stores, fresh fruit and vegetables
- **Figure:** 68 tonnes of fresh fruit and vegetables wasted across three stores, an average waste quota of 1.9%.
  Seven products (apples, bananas, grapes, lettuce, pears, sweet peppers, tomatoes) were 47% of wasted mass and 49%
  of the economic cost. Cost of the waste: product value about 85%, waste handling about 6%, staff time about 9%.
  The authors estimated that doubling staff time spent on waste reduction would cut the waste by about 10%.
- **Scope:** Three franchised ICA stores in mid-Sweden; the paper's own definition of "waste quota" should be read in
  the paper before quoting it as a share of anything.
- **Source:** L. Mattsson, H. Williams, J. Berghel (2018), Resources, Conservation and Recycling, as reported by
  FoodNavigator, 16 February 2018 (fetched) https://www.foodnavigator.com/Article/2018/02/16/Hotspot-food-groups-make-up-nearly-50-of-waste-retail-costs-study-finds.
  The paper itself was not opened.
- **Safety: B.** Good for "bananas and lettuce are hotspots" and "85% of the cost is the product itself". Three
  stores only.

### P4. United States: supermarket shrink of fresh fruit and vegetables
- **Figure:** Average supermarket shrink of 12.6% for 24 fresh fruits and 11.6% for 31 fresh vegetables. Bananas 4.1%
  (the lowest fruit), papayas 43.1% (the highest fruit). Shrink = pounds received by about 2,900 supermarkets compared
  with pounds bought by consumers.
- **Scope:** US, data 2011-12, by weight, edible-weight loss between receipt and sale (includes trimming and moisture
  loss), not a percentage of sales.
- **Source:** USDA Economic Research Service, "Updated Supermarket Shrink Estimates for Fresh Foods and Their
  Implications for ERS Loss-Adjusted Food Availability Data" (J. Buzby and J. Bentley, report 21 June 2016), chart of
  note dated 23 June 2016 (fetched) https://www.ers.usda.gov/data-products/charts-of-note/79033.
- **Safety: B.** Only quote as "US, 2011-12, by weight". Bananas at 4.1% is a safe, relevant detail (bananas are our
  best-covered product).

### P5. Lithuania: fruit and vegetables in retail waste
- **Figure:** Fruit and vegetables 63% of retail food waste; retail food waste 36.4 thousand tonnes, 13.0 kg per capita.
- **Source:** "Food waste in the retail sector: a survey-based evidence from Central and Eastern Europe"
  (search summary only) https://www.lituanistika.lt/content/104439.
- **Safety: C.** Survey-based, not opened.

---

## 3. Out-of-stocks and lost sales

### O1. The reference out-of-stock study
- **Figure:** Average out-of-stock rate of 8.3% (the report also says "8 percent"); retailers lose about 4% of annual
  sales to out-of-stocks; about 75% of the cause is retail store practices rather than upstream supply (the report's
  Figure 3 splits it as store ordering and forecasting 47%, "in the store, not on the shelves" 25%, upstream 28%, so
  store-related = 72% by that figure; both 72% and 75% appear in the report).
- **Scope:** Developed countries worldwide, 2002 study, fast-moving consumer goods across 8 categories; **fresh
  produce is not broken out**.
- **Source:** T. Gruen and D. Corsten, "A Comprehensive Guide to Retail Out-of-Stock Reduction in the Fast-Moving
  Consumer Goods Industry" (GMA, FMI, NACDS; funded by P&G; copyright 2007, cited in the text as 2008), restating
  Gruen, Corsten and Bharadwaj (2002) (fetched as PDF) https://www.nacds.org/pdfs/membership/out_of_stock.pdf.
- **Safety: B.** Always say "2002, packaged goods". Regional figures I saw second-hand disagree: Europe 8.6% (search
  summary) versus 7.1% for the ECR Europe/Roland Berger study (German trade article). Use only the global 8.3%.

### O2. What shoppers do when the shelf is empty
- **Figure:** Average across 8 categories: buy a different brand 26%, same brand (other size or variant) 19%, buy the
  item at another store 31%, delay the purchase 15%, do not purchase 9%. The report states the cost to retailers as 40%
  of intended sales (31% + 9% in the chart).
- **Scope:** Worldwide average, 2002 study, 8 packaged categories.
- **Source:** same Gruen and Corsten report, Figure 4 (fetched).
- **Safety: B.** The "40%" is the report's own statement for retailers. Fresh produce, with easy substitutes, may behave
  differently; say so if challenged.

### O3. Shelf out-of-stocks: in the store, not on the shelf
- **Figure:** "On average 25 percent of OOS were shelf OOS", i.e. the product was in the store but not on the shelf when
  the shopper wanted it. The report lists causes: backroom-to-shelf process breakdowns, too little stocking labour,
  holes filled with another item and so not seen as out-of-stock, no way of knowing when to restock.
- **Scope:** 2002 study, packaged goods.
- **Source:** Gruen and Corsten report (fetched).
- **Safety: B.** This is the single most relevant out-of-stock fact for a shelf camera, because it is the share a camera
  can fix without any ordering change.

### O4. Staff cost of out-of-stocks
- **Figure:** Employee time spent trying to satisfy shoppers who ask about an out-of-stock item: about USD 800 per week
  for a typical US grocery store.
- **Source:** Gruen and Corsten report (fetched). 2007 report, US.
- **Safety: C.** Old and US; no method shown in what I read.

### O5. Inventory records are often wrong
- **Figure (1):** DeHoratius and Raman examined nearly 370,000 inventory records from 37 stores of one retailer and found
  65% inaccurate (store-SKU level). Management Science 54(4): 627-641, 2008.
  https://ideas.repec.org/a/inm/ormnsc/v54y2008i4p627-641.html (fetched).
- **Figure (2):** Gruen and Corsten: audited perpetual-inventory accuracy of 32% to 45% across four studies; in one US
  chain, items with correct on-hand records had out-of-stock event rates of 4.1% against 8.9% where records were wrong.
- **Safety: B.** One retailer each; always say so. These show why "what the system thinks is on the shelf" is not
  enough and a direct look at the shelf adds information.

### O6. Missed sales in the US (NielsenIQ)
- **Figure:** Out-of-stocks and out-of-shelf cost US FMCG retailers USD 82 billion in 2021, 7.4% of potential sales.
- **Source:** NielsenIQ press release 7 February 2022, via Business Wire and trade press (search summary only)
  https://www.businesswire.com/news/home/20220207005098/en. Note: NIQ's own blog of 9 February 2022 gives full-year 2021
  on-shelf availability of 94.3% (fetched), while the press coverage gives 92.6%. Same year, two numbers.
- **Safety: C.** US, vendor-published, internally inconsistent availability figures. Do not quote.

### O7. IHL Group inventory distortion
- **Figure:** Sept 2022 (North America): consumers leave without about 1 in 5 planned items; total inventory distortion
  about USD 349 billion lost sales in 2022. Global 2025 edition: USD 1.77 trillion inventory distortion, of which USD 1.2
  trillion out-of-stocks, 6.5% of global retail sales (press pages only).
- **Source:** Supermarket News, 12 September 2022 (fetched) https://www.supermarketnews.com/grocery-trends-data/consumers-say-1-in-5-items-they-want-to-buy-is-out-of-stock-at-their-local-retailer;
  IHL site (search summary only).
- **Safety: C.** Proprietary research firm, scope varies by edition, no produce split.

### O8. Fresh-produce out-of-stock rate: not found
- I searched for a published on-shelf-availability or out-of-stock rate for fresh fruit and vegetables (NIQ, ECR,
  academic, Portuguese sources) and found **none**. NIQ's "Fresh insights" article (9 February 2022, fetched) contains
  no fresh-category figures despite its title. Do not quote any produce-specific lost-sales figure. A Portuguese search
  for a store-switching rate after empty shelves also found nothing; a student thesis from ISCTE mentions European
  grocery out-of-stocks of 7% to 10%, unreferenced (search summary), grade C.

---

## 4. Staff time on shelf work

### S1. Share of store-associate hours spent on shelf work
- **Figure:** Managers' estimate of the share of hourly store-associate hours: stocking shelves 25% (US) and 26%
  (non-US); facing shelves 6% (US) and 8% (non-US); receiving and unloading freight 14% and 19%; customer checkout 23%
  and 27%; e-commerce 12% and 5%; cleaning 8% and 7%; other 13% and 9% (columns can sum to 101 through rounding). One
  interviewed retailer forecast just three drivers (checkout, shelf replenishment, shelf facing) and said they were 60%
  of its labour. The report notes that store staff are usually the second-largest expense after cost of goods.
- **Scope:** Interviews with senior executives at 15 retailers plus a written survey of 60 retail executives in 10
  countries, mostly grocery. Report dated 20 April 2022.
- **Source:** M. Fisher and S. Gallino, "The Future of Retail Grocery Store Labor", The Wharton School, 20 April 2022
  (fetched as PDF) https://faculty.wharton.upenn.edu/wp-content/uploads/2024/06/Future-of-grocery-store-labor-06142024.pdf.
- **Safety: B.** Executives' estimates, not time-and-motion data; "stocking" is not "shelf checking", and no figure
  isolates checking. I read which pie is US from the order of labels in the PDF text layer (US first), consistent with
  the report's remarks on US e-commerce hours; confirm on the figure itself before putting the US/non-US split on a slide.

### S2. Portuguese minimum wage (for scale only)
- **Figure:** Guaranteed monthly minimum wage EUR 920 in 2026 (mainland), paid 14 times a year, Decreto-Lei 139/2025
  of 29 December 2025, in force 1 January 2026.
- **Source:** DGERT https://www.dgert.gov.pt/retribuicao-minima-mensal-garantida-para-2026 and Diario da Republica
  https://files.diariodarepublica.pt/1s/2025/12/24900/0001400016.pdf (both from search results; DGERT page not opened).
- **Safety: A** as a fact. It is a floor, not what a supermarket pays or what labour costs the employer.

### S3. Vendor claims about hours (do not use)
- Simbe: associates spend "up to 30 hours per week" manually checking out-of-stocks and "up to 50 more hours" with
  customers after automation. Focal: replenishment can take "up to 70%" of store hours; "40-60%" less labour on manual
  audits. Both sell shelf monitoring and give no method. **Grade X for the pitch.** I found no independent measure of
  weekly hours on shelf checks.

---

## 5. Planogram compliance and sales

### G1. Compliance and out-of-stocks (the one real study)
- **Figure:** Across four categories (diapers, laundry, feminine care, hair care) at one grocery retailer over 14 weeks,
  planogram compliance was above 90% on average, and a 10% change in compliance went with about a 1% change in
  out-of-stock level (in the report's words, 1/10 of 1 percent of out-of-stock per 1 percent of compliance). Where
  compliance is low it matters: for a category at 60% compliance raised to 90%, the report sees about 3 percentage
  points less out-of-stock. The report describes the effect as statistically significant but "not a large practical
  difference" where compliance is already high. Planogram compliance also helps staff see holes and restock.
- **Scope:** One US grocery retailer, 4 non-fresh categories, 14 weeks; OOS estimated from point-of-sale data.
- **Source:** Gruen and Corsten report, section 3-6 (fetched).
- **Safety: B.** It is the honest answer to "what is planogram compliance worth", and it is modest. Use it to say the
  value is in the stores and areas where compliance is low. Our own labelled sample (pitch.md) has 72 of 1,240 areas
  holding the wrong product, so produce compliance on this day is visibly below 100%, but that is our data from one
  store and one day, not evidence of an effect size.

### G2. Shelf space and sales
- **Figure:** Meta-analysis of 1,268 estimates: average shelf-space elasticity 0.17 (sales rise by 0.17% for each 1%
  more shelf space on average); lowest for commodities, then staples, highest for impulse items; increases in space
  produce larger effects than reductions.
- **Source:** M. Eisend (2014), "Shelf Space Elasticity: A Meta-Analysis", Journal of Retailing 90(2): 168-181 (fetched
  via IDEAS) https://ideas.repec.org/a/eee/jouret/v90y2014i2p168-181.html.
- **Safety: A** for the number; it measures allocated space, **not** planogram compliance itself. The step "a wrong or
  empty area wastes allocated space" is our reasoning, say it as ours. Reading "0.17" as a percentage change per percent
  is the standard meaning of elasticity; the "17% per doubling" reading seen elsewhere is a secondary interpretation.

### G3. Display compliance rates
- Claim seen: CPG firms assumed in-store display compliance near 70%, measured about 40% (attributed to Shop!/POPAI and
  Quri). A Quri/Trax post gives 42% non-compliant for 17 promotional displays in 5,643 US stores. These are promotional
  displays, not planograms, the numbers do not reconcile, and I did not find the original report. **Grade X.**
- Unsourced vendor numbers repeated in glossaries and blogs: "15-20% revenue gap", "up to 7.8% sales lift",
  "planogram compliance 50-70%". **Grade X.**
- I found no published planogram-compliance rate for produce.

---

## 6. Value of real-time shelf monitoring

### V1. Schnucks (US grocer), shelf-scanning robots
- **Figure:** Schnucks' VP of IT infrastructure said the Simbe "Tally" robot gave "at least a 20% reduction in
  out-of-stocks" in stores that use it, and detects out-of-stocks 14 times more often than manual auditing. Rollout to
  62 of 112 stores; about 35,000 products scanned per pass, 2 to 3 passes a day.
- **Source:** Supermarket News, 30 September 2020 (fetched) https://www.supermarketnews.com/grocery-technology/schnuck-markets-rolls-out-shelf-scanning-robots-to-over-half-of-store-base.
- **Safety: C.** The retailer's own statement about a vendor's tool, US, 2020, a robot rather than fixed cameras. Not
  independent. Usable only as "retailers report".

### V2. Walmart ended its shelf-robot pilot
- **Figure:** In October-November 2020 Walmart ended its Bossa Nova shelf-scanning robot programme (about 500 stores),
  reportedly because human associates, already in the aisles for online orders, could do similar checks. Walmart said
  it was one idea tried in roughly 500 stores.
- **Source:** Wall Street Journal reporting via Retail TouchPoints and others (search summaries; the Retail TouchPoints
  page returned 403).
- **Safety: B** as "reported". It supports the argument that a fixed camera is cheaper than a moving robot, but it also
  shows that monitoring has to earn its place against staff walking the aisles. Expect the jury to know this.

### V3. Walmart Canada rolls out fixed shelf cameras
- **Figure:** After a 70-store pilot, chain-wide deployment of Focal Systems cameras that flag out-of-stock and
  low-stock shelves and trigger replenishment through Walmart's inventory systems; part of a CAD 3.5 billion store
  technology investment; testing began 2020. Departments named: grocery, pets, health and beauty, frozen, dairy (no
  produce). No quantified results published.
- **Source:** Supermarket News, 14 September 2022 (fetched) https://www.supermarketnews.com/finance/walmart-canada-sharpens-out-of-stock-intelligence.
- **Safety: A** for the fact of the rollout; there are no numbers to quote.

### V4. RFID and out-of-stocks (historic)
- **Figure:** A University of Arkansas study for Walmart: 24 Dallas-area stores (12 RFID, 12 control), 14 February to
  12 September 2005; out-of-stocks about 30% lower for items selling 0.1 to 15 units a day, after controlling for case
  pack size and shelf quantity; this replaced a preliminary 16%.
- **Source:** University of Arkansas news, 3 May 2006 (fetched) https://news.uark.edu/articles/10693/new-findings-on-rfid-capability.
- **Safety: C.** Case-level RFID, 2005, Walmart-funded. Different technology; shows only that visibility lowers
  out-of-stocks.

### V5. Vendor case claims (do not use)
- Simbe/HomeBase "58% fewer controllable out-of-stocks", Focal "increase availability 2-5%", OneThird "up to 25%
  less waste", Freshflow "up to 30% less waste". All vendor-reported, none independent. **Grade X.**

### V6. Why fresh matters for store choice
- **Figure:** McKinsey pan-European benchmarking survey of 23,000 grocery shoppers in four countries: quality is the
  biggest factor in whether a shopper would recommend a store's fresh-produce department, ahead of price and
  promotions. McKinsey says quality-improvement programmes can lift department sales by more than 10% year on year, even
  in a flat market, and lift traffic and sales in other departments. The 10% comes from McKinsey's experience, not
  the survey.
- **Scope:** UK, France, Germany, Switzerland (countries named in the write-up's examples), survey year not stated,
  article 2018.
- **Source:** McKinsey, "In fresh-food retailing, quality matters more than price" (D. Laubli, N. Ottink), March 2018.
  The McKinsey page timed out three times; confirmed through HortiDaily, 26 April 2018 (fetched)
  https://www.hortidaily.com/article/6042674/in-fresh-food-retailing-quality-matters-more-than-price and Fruitnet
  (search summary). McKinsey link: https://www.mckinsey.com.br/industries/retail/our-insights/in-fresh-food-retailing-quality-matters-more-than-price.
- **Safety: B.** Quote the survey finding (quality first), not the sales uplift. Note: nothing in it is about Portugal.

---

## 7. The sponsor and the store (Sensei, Continente Bom Dia S. Romao, Leiria)

### I1. Store facts
- **Opened:** 10 January 2025 (Sensei insight page, fetched
  https://www.sensei.tech/insights/sensei-and-mc-sonae-unveil-worlds-largest-autonomous-supermarket-in-leiria).
- **Size and range:** 1,200 square metres. SKUs differ by source: "over 11,000" (Sensei), "over 12,000" (IGD), "more
  than 10,000 items" (Retail-Optimiser). Quote none, or say "over 10,000".
- **Technology:** 1,676 cameras, 2,000 scales, 21 servers (Retail-Optimiser, 29 January 2025, giving the company's
  figures; fetched https://retail-optimiser.de/en/mc-sonae-opens-large-scanless-supermarket-with-sensei/); IGD says
  "approximately 1,700 cameras" and six smart checkout lanes. Sensei claims 99% accuracy in tracking consumer
  interaction with products (vendor claim as relayed by Retail-Optimiser).
- **"Largest autonomous supermarket in the world":** Sensei's wording, and the challenge brief's; the page gives no
  basis for the comparison. Say "described as".
- **Safety:** A for the opening date and size, C for the claims.

### I2. Reported performance
- IGD (Toby Pickard, "Dawn of the hyper-connected store", 30 July 2025, fetched
  https://www.igd.com/articles/dawn-of-the-hyper-connected-store/71498): store averages "+3,000 daily baskets", is
  "trading above similar stores without the technology" and "taking traffic from surrounding stores"; no figures behind
  the last two statements. Shrink, waste and availability are not covered.
- Sensei's client page (undated, fetched https://sensei.tech/clients/continente-bom-dia): more than 70% of transactions
  through autonomous checkout, 22.7 minutes less average shopping time, top 10 in the Bom Dia network by sales, 9
  replenishment tasks generated automatically each day, planogram compliance checks and replenishment alerts to staff.
  All vendor-reported; no shrink, waste or availability figures.
- Recognition (Sensei awards page, undated, fetched https://sensei.tech/insights/sensei-recognised-across-global-retail-innovation-awards):
  European Commerce Awards 2025 (EuroCommerce) Digitalisation category winner; IGD Top 25 "Must-See Stores" 2026
  (a selection, not a competition); EHI RETA Awards 2026 nominee only.
- **Safety: C** for performance (vendor), A for "IGD selected it" and "won the 2025 EuroCommerce Digitalisation award"
  if the awards page is accurate.

### I3. What this means for our framing (our reading, check the pages first)
- Sensei's own platform already does planogram checks and replenishment alerts for packaged goods, and its client page
  lists selling loose fruit and vegetables by weight among the limits of other autonomous stores. The brief calls
  produce the hardest section for vision. So the honest positioning is "the produce shelf module for the platform you
  already run", not a replacement. Read the exact wording on the Sensei page before saying anything about how its own
  store handles produce; the page does not say.
- The only Sensei-side number about shelf work we have is "9 replenishment tasks a day" (vendor-reported). Our staff app's
  Do-now list is the same kind of output for produce.

---

## 8. Numbers that must not be combined (traps)

- Eurostat "kg per inhabitant" (all food, edible and inedible, whole chain link) is not a produce number and is not
  a percent of sales.
- USDA 12.6% / 11.6% (US, 2011-12, weight) and Swedish 4.3% / 1.9% (mass delivered) are different units, countries and
  years. Never put them on one slide as a range.
- 8.3% out-of-stock (2002, packaged goods, rate of items) and 4% lost sales (same study) are different quantities;
  7.4% (NIQ, US 2021, share of potential sales) is a third.
- INE's 182.7 kg (Portugal total) and Eurostat's 156 kg (Portugal total, 2023) are two different totals.
- The EU 30% is joint across retail, food service and households, per capita, by Member State.
- Vendor "up to" claims are the maximum of the best case, not an average.

## 9. What I could not find (do not assert these)

- A published out-of-stock rate for fresh fruit and vegetables.
- A European produce-shrink figure expressed as a percentage of sales. US "4% to 8% of department sales" lines in
  trade columns trace to a 2012 industry study (FMI/Retail Control Group, 4.8%), which I could not open. Grade X.
- An independent measurement of hours per week spent on shelf checks or manual planogram audits.
- A produce planogram-compliance rate, or a produce-specific sales impact of compliance.
- A Portugal-only euro cost of retail food waste. Published household-oriented estimates diverge (about EUR 1.2
  billion a year per Too Good To Go versus above EUR 3.3 billion in a 2023 Agroportal story), from a company that sells
  surplus food; **Grade X**.
- An independent, peer-reviewed field experiment of camera-based shelf monitoring (journal search came back with
  vendor blogs and patents only).
- Sonae MC's measured progress against its 2028 waste target, or Continente's fresh-produce waste rate.

## 10. Source index (all accessed 2026-10-11)

| Short name | URL | Fetched? |
|---|---|---|
| Eurostat news 2024 data | https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20260929-1 | yes |
| Eurostat Statistics Explained | https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Food_waste_and_food_waste_prevention_-_estimates | yes |
| Eurostat env_wasfw API | https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/env_wasfw | yes |
| Commission targets page | https://food.ec.europa.eu/food-safety/food-waste/eu-food-waste-relevant-legislation/food-waste-reduction-targets_en | yes |
| Commission food waste page | https://food.ec.europa.eu/food-safety/food-waste_en | yes |
| Parliament topic page | https://www.europarl.europa.eu/topics/en/article/20240318STO19401/food-waste-reduction-what-eu-actions-are-there | yes |
| Linklaters (directive dates) | https://sustainablefutures.linklaters.com/post/102l7yl/eu-revised-waste-framework-directive-to-cater-for-food-and-textile-waste-publish | yes |
| Agroportal / Lusa (INE 2023) | https://www.agroportal.pt/?p=1197620 | yes |
| GPP / CNCDA presentation | https://www.gpp.pt/images/Destaques/Programas_e_Apoios/ENCDA2025/Apresenta%C3%A7%C3%A3o_ENCDA_2025_GPP.pdf | yes |
| Agroportal (Sonae MC 2024) | https://www.agroportal.pt/?p=1150337 | yes |
| Vienna.at (Austria Q4 2023) | https://www.vienna.at/supermarkte-meldeten-lebensmittelabfalle-uber-16-200-tonnen-landeten-im-mull/8597791 | yes |
| EU CAP Network (Austria) | https://eu-cap-network.ec.europa.eu/projects/practice-abstracts/food-waste-austria-consumer-and-retail-level_en | yes |
| SLU thesis (Eriksson 2012) | https://research.slu.se/en/publications/507c424a-45d8-4958-86e3-b56c7ad7002b | yes |
| FoodNavigator (Mattsson 2018) | https://www.foodnavigator.com/Article/2018/02/16/Hotspot-food-groups-make-up-nearly-50-of-waste-retail-costs-study-finds | yes |
| USDA ERS chart | https://www.ers.usda.gov/data-products/charts-of-note/79033 | yes |
| Gruen and Corsten guide | https://www.nacds.org/pdfs/membership/out_of_stock.pdf | yes (PDF text) |
| DeHoratius and Raman 2008 | https://ideas.repec.org/a/inm/ormnsc/v54y2008i4p627-641.html | yes |
| Eisend 2014 | https://ideas.repec.org/a/eee/jouret/v90y2014i2p168-181.html | yes |
| Wharton store labour report | https://faculty.wharton.upenn.edu/wp-content/uploads/2024/06/Future-of-grocery-store-labor-06142024.pdf | yes (PDF text) |
| Supermarket News (IHL 2022) | https://www.supermarketnews.com/grocery-trends-data/consumers-say-1-in-5-items-they-want-to-buy-is-out-of-stock-at-their-local-retailer | yes |
| NIQ fresh OSA article | https://nielseniq.com/global/en/insights/analysis/2022/fresh-insights-about-grocery-on-shelf-availability-in-the-post-covid-era/ | yes |
| NIQ press release (Business Wire) | https://www.businesswire.com/news/home/20220207005098/en | search summary |
| Schnucks (Supermarket News 2020) | https://www.supermarketnews.com/grocery-technology/schnuck-markets-rolls-out-shelf-scanning-robots-to-over-half-of-store-base | yes |
| Walmart Canada (Supermarket News 2022) | https://www.supermarketnews.com/finance/walmart-canada-sharpens-out-of-stock-intelligence | yes |
| Univ. of Arkansas RFID study | https://news.uark.edu/articles/10693/new-findings-on-rfid-capability | yes |
| Walmart/Bossa Nova | https://retailtouchpoints.com/topics/store-operations/wsj-walmart-ends-in-store-robotics-partnership-will-use-associates-instead | no (403) |
| McKinsey fresh quality (HortiDaily copy) | https://www.hortidaily.com/article/6042674/in-fresh-food-retailing-quality-matters-more-than-price | yes |
| Sensei launch page | https://www.sensei.tech/insights/sensei-and-mc-sonae-unveil-worlds-largest-autonomous-supermarket-in-leiria | yes |
| Sensei client page | https://sensei.tech/clients/continente-bom-dia | yes |
| Sensei awards page | https://sensei.tech/insights/sensei-recognised-across-global-retail-innovation-awards | yes |
| Retail-Optimiser (store specs) | https://retail-optimiser.de/en/mc-sonae-opens-large-scanless-supermarket-with-sensei/ | yes |
| IGD, Dawn of the hyper-connected store | https://www.igd.com/articles/dawn-of-the-hyper-connected-store/71498 | yes |
| DGERT minimum wage 2026 | https://www.dgert.gov.pt/retribuicao-minima-mensal-garantida-para-2026 | search result only |

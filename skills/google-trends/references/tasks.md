# The 9 tasks

For each task: the question, where the answer is, the command, the decision rule, what to put in the report. Examples use Ukraine (`UA`) as one possible market; change `--geo` for any other country.

Tasks 1-3 matter most for ecommerce: they drive purchasing, stock and ad budget.

## 1. Validate a product or niche
- **Question:** launch or not?
- **Look at:** 5-year interest over time.
- **Command:** `check --terms "neck massager" --geo UA --sources web shopping`
- **Rule:** shape `growing` = green light; `stable` = demand is flat, price and service win; `fad` = high dead-stock risk; `declining` = avoid; `seasonal` = go to task 2; `insufficient_data` = say so, widen the terms.
- **Report:** verdict, shape reason, the checklist from [product-check.md](product-check.md).

## 2. Seasonality
- **Question:** when to buy stock and start ads?
- **Look at:** 2-5 years of the curve, recurring peaks. The script needs about 2.5+ years.
- **Command:** same as task 1, with `--date "today 5-y"`.
- **Rule:** if `seasonal`, ads start **3-6 weeks before the estimated peak** (`timing.ads_start_from` .. `ads_start_until`). If `seasonality.rise_shift_months` is negative the rise began earlier than last season: move purchasing and ads earlier too.
- **Example:** a heater rises from October; a swimsuit from April.

## 3. Geo-targeting
- **Question:** where to send the ad budget, where to open pickup points?
- **Look at:** interest by region (`regions` in the report).
- **Rule:** write down the top 3-5 regions from the report. Crimea and Sevastopol are left out by default (tiny samples that jump to the top) and the remaining values are rescaled so the top region is 100; `--all-regions` shows everything. If fewer than 3 regions have data, the market is too small for a geo split - say so. Region values are relative within the query, not volumes: a small region can show 100.
- **Report:** top regions as a budget-split suggestion for Meta/TikTok, to be checked with real campaign data.

## 4. Compare options
- **Question:** which name goes into the title, product card and creative?
- **Command:** `check --terms "air fryer" "multicooker" --geo UA` (up to 5 terms, one chart, so the numbers are comparable).
- **Rule:** the recommended term is the largest one among terms with a healthy shape (`growing`, `stable`, `seasonal`); within about 10% of the leader a growing term wins. A term under 8% of the leader is "swamped": rerun it against a mid-sized anchor term.
- **Languages:** compare the Ukrainian, Russian and slang names of the same product.

## 5. Early trends
- **Question:** what to test before competitors?
- **Look at:** *Rising* related queries (`Breakout` = more than +5000%) and the trending list.
- **Command:** `check --terms "<seed>" --date "today 12-m"`, plus `trending --geo UA`.
- **Rule:** a breakout query with a tiny base can be noise. Treat it as a test candidate, then run the full check on it.

## 6. Content and SEO ideas
- **Question:** which articles, videos, categories and FAQ blocks?
- **Command:** `check --terms "<seed>" --sources web youtube`
- **Look at:** related queries. The report tags them: `choose` ("how to choose..."), `compare` ("... or ..."), `review` (reviews), `buy` (price, where to buy). The YouTube source shows which topics deserve reviews and unboxings.
- **Report:** a short list of titles grouped by tag.

## 7. Demand in product searches
- **Question:** is there buying intent, or do people only read?
- **Command:** `check --terms "<product>" --sources web shopping`
- **Rule:** `confirmed` = Shopping follows the web trend. `weak` = little or no Shopping data. A query can be informational on the web and weak in Shopping.

## 8. Brand and competitor monitoring
- **Question:** is our brand marketing working?
- **Command:** `check --terms "our brand" "competitor a" "competitor b" --date "today 12-m"`, repeated after a sale or an ad wave.
- **Rule:** compare shares of the leader between runs; the "Changes since" block shows movement. Brand names are small queries: expect "not enough data" for small shops.

## 9. Demand for a service, profession or niche
- **Question:** what does Google search interest say about "targetologist", "plumber", "yoga classes"? Not a product, so nothing to launch or stock.
- **Command:** `check --kind service --terms "targetolog" "targetovana reklama" --geo UA` (sources default to web and YouTube; no Shopping). With a browser or CSV, pass `--kind service` to `ingest` / `import-csv` too.
- **Look at:** the shape, the season, the regions, and the **intent mix** of related queries: the share of the top-query weight that is definitions ("what is", "це", "это"), career and learning (jobs, courses, salary) or buying words (price, order, hire). It is printed as numbers.
- **Rule:** the reading is `RISING / STEADY / SEASONAL / FALLING / SPIKE / INCONCLUSIVE`. It says what Google search interest does, not whether to start a business. A mostly informational mix means the searches are about the topic, not about hiring; the report states the numbers and nothing more.
- **Language and scale:** compare Ukrainian and Russian wordings. If one term swamps the rest, run the small ones on their own.
- **What Trends cannot show:** Instagram, Telegram, marketplaces, exchanges and referrals. The report lists this; do not turn it into a channel recommendation, or label it "Hypothesis:" with its check.

## Extra modes

- **Trending now:** `trending --geo UA` - daily source of situational creatives and product ideas tied to news. Not a validation: run the full check on anything you want to sell.
- **Test export markets:** `check --terms "air fryer" --geo UA PL DE` - one term, several countries on one chart (labels `air fryer (UA)` ...). Compare levels only inside this chart.

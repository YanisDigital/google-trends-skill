# Presenting the result

The script already writes a complete English report (`report.md`, `report.html`, `report.xlsx`). In chat, give the user a shorter version in their own language.

## Chat summary: five parts, in this order

1. **Verdict** - one line, label plus the product name: `GO / TEST / WAIT / AVOID / INCONCLUSIVE`.
2. **Why** - two or three bullets: the shape, the Shopping check, the season.
3. **What the data supports** - the report's own rules applied, as Reading:
   - seasonal: the report's date range for the ad start (3-6 weeks before the estimated peak);
   - regions: the report's top 3-5, the candidates for a first budget split;
   - rising queries: the report's list, with their tags (choose, compare, review, buy, define, career).
4. **Open items** - the checklist rows that are still `[ ]` or `[!]`, always including Keyword Planner and Meta Ad Library.
5. **Files** - the output folder with the source data, `report.html` and `report.xlsx`.

## Statement types

Each sentence of the answer is exactly one of these:

| Type | What it is | Example |
|---|---|---|
| **Data** | a number, ranking, shape or list quoted from `report.md` / `analysis.json` | "Last 52 weeks average 17, the 52 weeks before 33." |
| **Reading** | what the report's own rule says the data means: the verdict line and its reasons | "Verdict: FALLING (last-12-month level is 0.52x the start)." |
| **Hypothesis** | starts with "Hypothesis:" and ends with the check that would confirm it | "Hypothesis: buyers search elsewhere. Check: ad library and your own lead sources." |

Channel choices, wording advice and business strategy are hypotheses, or they are left out. Facts about the tool (Trends does not show Instagram, Telegram or referrals) are data about the tool and need no label.

## Service mode

Same five parts, with these differences: the verdict line is `RISING / STEADY / SEASONAL / FALLING / SPIKE / INCONCLUSIVE` and describes search interest only; the checklist is the research checklist; part 3 quotes the intent mix as numbers ("definitions 55%, career/learning 28%, buying words 4%") and the report's "What Trends cannot show here" section replaces the marketplace links.

## Regions

Quote the report's list. When it says regions were left out as unreliable (Crimea, Sevastopol), say so in one line and give the left-out names.

## Wording

- Say "interest" and "relative", never "searches per month".
- Say which source and date the data is from (`Data via`, `Collected`).
- For `inconclusive`, say what would help: broader terms, the Topic, a larger market, a longer period.
- Anything beyond the data is a labelled hypothesis with its check. Marketing judgement is the user's.

## Compact examples (Ukraine as the market)

Product:

```
Verdict for "air fryer": GO - worth validating (growing, Shopping confirms).      <- Reading
Data: interest is 3.3x the level of five years ago; Shopping follows the web curve.
Data: top regions: Region A, Region B, Region C (Crimea and Sevastopol left out as unreliable).
Data: rising queries "air fryer vs oven" [compare], "how to choose air fryer" [choose].
Still open: search volume (Keyword Planner), competition (Meta Ad Library), prices (Prom, Rozetka).
Files: google-trends-output/reports/air-fryer-ua-.../2026-10-27/report.html
```

Service:

```
Reading for "targetolog": FALLING - search interest declines (0.52x the start of the window).
Data: last 52 weeks average 17, the 52 weeks before 33. Top related queries by weight:
definitions 55%, career/learning 28%, buying words 4%, no tag 13%.
Data: Trends does not show Instagram, Telegram, exchanges or referrals.
Hypothesis: customers look for this service outside Google search.
Check: where competitors advertise (Meta Ad Library) and where your own leads come from.
Files: google-trends-output/reports/targetolog-.../2026-10-27/report.html
```

Region names and figures above are placeholders; always use those from the report.

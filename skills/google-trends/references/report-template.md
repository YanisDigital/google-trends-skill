# Presenting the result

The script already writes a complete English report (`report.md`, `report.html`, `report.xlsx`). In chat, give the user a shorter version in their own language.

## Chat summary: five parts, in this order

1. **Verdict** - one line, label plus the product name: `GO / TEST / WAIT / AVOID / INCONCLUSIVE`.
2. **Why** - two or three bullets: the shape, the Shopping check, the season.
3. **Actions** - what to do with the data:
   - seasonal: the date range to start ads and when to have stock;
   - regions: the top 3-5 for the first budget split;
   - rising queries: which become hooks, which companion products, which keywords for the product card.
4. **Open items** - the checklist rows that are still `[ ]` or `[!]`, always including Keyword Planner and Meta Ad Library.
5. **Files** - the folder with `report.html` and `report.xlsx`.

## Wording

- Say "interest" and "relative", never "searches per month".
- Say which source and date the data is from (`Data via`, `Collected`).
- For `inconclusive`, say what would help: broader terms, the Topic, a larger market, a longer period.
- Do not add recommendations beyond the data. Marketing judgement is the user's.

## Compact example (Ukraine as the market)

```
Verdict for "air fryer": GO - worth validating (growing, Shopping confirms).
Why: interest is 3.3x the level of five years ago; Google Shopping follows the web curve.
Actions: top regions for the first split: Region A, Region B, Region C; rising queries
"air fryer vs oven" and "how to choose air fryer" are hooks for creatives and the product page.
Still open: search volume (Keyword Planner), competition (Meta Ad Library), prices (Prom, Rozetka).
Files: google-trends-output/reports/air-fryer-ua-.../2026-10-26/report.html
```

Region names above are placeholders; always use the names from the report.

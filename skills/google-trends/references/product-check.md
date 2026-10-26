# Product check in 15 minutes

Eight steps. Steps 1-6 are produced by one `check` run; step 7 is advice for the user; step 8 is the history feature.

| # | Step | How the skill does it |
|---|---|---|
| 1 | Country and period "Last 5 years" | `--geo XX --date "today 5-y"`: trend and seasonality are visible together |
| 2 | Enter 2-4 name variants | `--terms a b c`; use every language buyers use (for Ukraine: Ukrainian, Russian, slang) |
| 3 | Judge the curve shape | `web.shape` in `analysis.json`, rules in [interpretation.md](interpretation.md) |
| 4 | Switch the source to Google Shopping | `--sources web shopping`; `intent.status` = confirmed / weak / unclear |
| 5 | Regions | `regions.top`: write down 3-5 for geo-targeting |
| 6 | Rising related queries | `related.rising`: hooks for creatives, companion products, keywords for the product card |
| 7 | Confirm with other sources | not automated: Keyword Planner for volumes, Meta Ad Library for competition, marketplaces for prices |
| 8 | Save the comparison | every run writes a snapshot; run again in a month and read "Changes since" |

## Curve shapes (step 3)

- Smooth growth - green light.
- Flat line - stable demand; price and service win.
- Sharp peak and decline - a fad; big risk of unsold stock.
- Recurring peaks - seasonal; plan purchasing for the season.

## Pre-launch checklist

The report fills this in. `[x]` done, `[!]` needs attention, `[ ]` not done, `[-]` not applicable.

- Checked the 5-year trend: not a fad and not declining
- Determined the season and the ad start date
- Compared 2-4 product names and picked the main one
- Checked the Google Shopping source
- Listed the top regions for geo-targeting
- Collected rising queries for creatives and the product card
- Confirmed volumes in Keyword Planner and competition in Meta Ad Library (always manual)

## Ask for the missing pieces

If the user gave one name only, suggest two or three variants (other language, slang, singular/plural, the category word) and run them together: step 2 and the name comparison are the cheapest improvement.

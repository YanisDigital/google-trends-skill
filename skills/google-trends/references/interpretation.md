# Interpreting Google Trends

## What the numbers are

- Values are **relative interest**, 0-100, for the chosen period, region and source. 100 is the peak, 50 is half of it, 0 means not enough data.
- Every chart is rescaled to its own highest point. Compare numbers only inside one chart. An index of 100 can be 10,000 searches or 300.
- Use the Keyword Planner, Ahrefs or Serpstat for volumes; Trends for timing, geography and relative size.

## How the script decides the shape

All rules are in `scripts/gtrends/analyze.py` as named constants. Data is averaged per calendar month first, so weekly and monthly series behave alike.

| Shape | Rule (summary) |
|---|---|
| `insufficient_data` | more than 40% zero points, all zeros, or less than 6 months of data |
| `seasonal` | the 12-month trend is removed, the same calendar months sit at least 1.35x above trend in at least 60% of the cycles, and there are 2+ cycles (needs about 2.5+ years) |
| `fad` | the peak is 2.5x the median or more, was 6+ months ago, and the last 3 months are under 30% of it |
| `growing` | last 12 months at least 1.25x the first 12 and at least 1.05x the previous 12 |
| `declining` | last 12 months at most 0.75x the first 12 and at most 0.95x the previous 12 |
| `stable` | everything else |

Seasonal is checked before fad so that a yearly peak is never mistaken for a one-off spike, and the trend is removed first so steady growth is never mistaken for seasonality.

## Verdicts

| Label | Meaning | Typical reason |
|---|---|---|
| `go_validate` | worth validating further | growing, or seasonal with the peak 3+ weeks away |
| `test_small` | small budget only | stable demand, weak Shopping signal, or the peak is under 3 weeks away |
| `wait` | prepare for next season | seasonal, the peak has just passed |
| `avoid` | risky demand shape | fad or declining |
| `inconclusive` | Trends cannot answer | too little data |

A verdict is never "buy it". It says whether Trends supports the next step, and always carries two caveats: volumes are unknown, and competition and margin are unchecked.

## Where Trends is the wrong tool

- Market size or sales estimates.
- Narrow queries and small markets: expect "not enough data" or a sawtooth of zeros.
- Demand nobody searches for: impulse products bought from TikTok or Reels. Use Meta Ad Library and TikTok Creative Center.
- Bids and CPC: Keyword Planner.
- As the only source for a decision: rising interest does not guarantee margin; the niche may already be crowded.

## Pitfalls and fixes

| Pitfall | Fix |
|---|---|
| Only the 12-month view | use 5 years; a seasonal peak looks like a trend in one year |
| Comparing numbers across charts | compare on one chart only |
| Typing a phrase as plain text | choose the Topic from the suggestion list; it merges languages and synonyms |
| A strong query flattens a weak one | similar-sized queries, or add an anchor query of medium size |
| Believing a peak without context | check news, viral video, holiday, outages |
| Ignoring the category for ambiguous words ("mouse", "apple") | set a category such as Shopping |

## Habits worth keeping

- Watch whether the start of a seasonal rise moves earlier than last year (`rise_shift_months`).
- Look at "Trending now" daily for situational creatives and news-driven product ideas.
- The YouTube source shows which topics deserve reviews and unboxings.
- Compare one theme across countries (for example Ukraine, Poland, Germany) to test export.

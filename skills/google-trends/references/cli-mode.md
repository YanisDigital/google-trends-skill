# CLI mode and manual CSV import

`scripts/trends_cli.py` needs Python 3.10+. The analysis, Markdown, HTML and CSV reports use the standard library only. Playwright is needed for `check`, openpyxl for `.xlsx`.

## Setup (ask the user first)

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Commands

| Command | Purpose |
|---|---|
| `check --terms A B --geo UA --date "today 5-y" --sources web shopping` | open the explore page, record the widget data, analyse, report |
| `ingest --compact web.compact.json [shopping.compact.json] --terms A B --geo UA` | build a snapshot from the compact JSON that the [browser mode](browser-mode.md) snippet returns (`--raw DIR` takes raw widget files instead) |
| `import-csv --web-timeline f.csv [--shopping-timeline f.csv] [--regions f.csv] [--related "A=f.csv"]` | build a snapshot from CSV files exported by hand |
| `report SNAPSHOT.json` | re-render reports from a saved snapshot |
| `trending --geo UA` | "Trending now" from the public RSS feed |
| `diff OLD.json NEW.json` | compare two snapshots |

Common flags: `--out DIR` (default `./google-trends-output`), `--formats md html csv xlsx`. `check` also takes `--headed` (show the browser), `--delay` (seconds between pages, minimum 5), `--category`.

Exit codes: `0` ok, `2` invalid input or unreadable file, `3` blocked by Google (stop and use CSV), `4` missing optional dependency.

## What `check` does and does not do

- Opens `trends.google.com/trends/explore?...&hl=en` once per source in a fresh, throwaway browser profile.
- Blocks every request that is not to Google, and images, media and fonts.
- Records the three data responses the page itself requests (time series, regions, related queries). No private endpoints, no tokens of its own.
- Waits at least 5 seconds between pages, retries once after a 429, then stops.
- Does **not** log in, accept cookies on the user's behalf, solve CAPTCHAs, rotate proxies or change its identity. If Google blocks it, the run ends with exit code 3.

## When blocked (HTTP 429, consent page, CAPTCHA)

Automated clients get HTTP 429 from the explore page often, even when the same page opens fine in the user's own Chrome. Do not retry in a loop. Tell the user and either use [browser mode](browser-mode.md) with Claude in Chrome (the user's real browser), or manual CSV:

1. Open the explore page yourself with `hl=en` in the URL (see [url-parameters.md](url-parameters.md)).
2. For web search, click the download arrow on **Interest over time** and save `multiTimeline.csv`.
3. Change the source to **Google Shopping** and download its `multiTimeline.csv` again under another name.
4. Optional: download **Interest by region** (`geoMap.csv`) and **Related queries** (`relatedQueries.csv`, one per term, the interface language must be English).
5. Run:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/trends_cli.py" import-csv --geo UA \
     --web-timeline multiTimeline.csv --shopping-timeline shopping_multiTimeline.csv \
     --regions geoMap.csv --related "air fryer=relatedQueries.csv"
   ```

Series names are read from the CSV header. In `--related "LABEL=file"`, LABEL must equal the term name in the header.

## Output layout

```
google-trends-output/
  raw/<slug>/<date>/<source>/*.json       raw widget responses (check)
  history/<slug>/<date>.json              snapshots, used by "Changes since"
  reports/<slug>/<date>/report.md|html|xlsx, timeline_*.csv, regions.csv, related.csv, analysis.json
```

All of it is user data about their business. It is git-ignored in this repository and should stay out of any commit.

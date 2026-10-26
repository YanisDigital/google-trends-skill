# google-trends-skill

A [Claude Code](https://claude.com/claude-code) skill that turns Google Trends into ecommerce decisions: is a product worth launching, when is its season, where to send the ad budget, which name to use, what is rising, and whether people want to buy or only read.

It collects the curves, classifies them with fixed, auditable rules (no model guesswork in the numbers), and writes a verdict with the caveats attached: Markdown in chat plus HTML, CSV and XLSX files, and a history so you can re-check in a month.

> **Trends is a compass, not a ruler.** It shows relative interest (0-100), never search volumes. The skill says so in every report and points you to Keyword Planner, Meta Ad Library and marketplaces for the rest.

Not affiliated with or endorsed by Google. "Google" and "Google Trends" are trademarks of Google LLC.

## What it does

| Task | Output |
|---|---|
| Product or niche validation | shape of the 5-year curve: growing, stable, fad, seasonal, declining |
| Seasonality | peak month, estimated next peak, ad start window (3-6 weeks before) |
| Geo-targeting | top regions and whether the market is big enough to split |
| Compare options | which name is largest and healthy; swamped terms flagged |
| Early trends | rising and breakout queries, "Trending now" |
| Content and SEO | rising queries tagged choose / compare / review / buy; YouTube source |
| Product demand | does Google Shopping confirm buying intent |
| Brand and competitors | brand vs competitors, change since the last run |
| Export tests | one term across several countries |

The workflow follows a 15-minute product check with a pre-launch checklist; the manual items (search volume, competition) stay unticked on purpose.

## Install

As a plugin (Claude Code):

```text
/plugin marketplace add YanisDigital/google-trends-skill
/plugin install google-trends@google-trends-skill
```

Or copy `skills/google-trends/` into `~/.claude/skills/`.

Optional, for the command line collector and XLSX output (Python 3.10+):

```bash
pip install -r skills/google-trends/scripts/requirements.txt
python -m playwright install chromium
```

The analysis and the Markdown, HTML and CSV reports need nothing beyond the Python standard library.

## Use

Ask Claude in plain language:

> Check demand for "air fryer" and "multicooker" in Ukraine. When is the season and which regions should I target?

Or run the CLI yourself:

```bash
python skills/google-trends/scripts/trends_cli.py check --terms "air fryer" "multicooker" --geo UA --sources web shopping
python skills/google-trends/scripts/trends_cli.py trending --geo UA
python skills/google-trends/scripts/trends_cli.py import-csv --web-timeline multiTimeline.csv --geo UA
```

Three ways to get the data, in order of preference: the CLI (Playwright), Claude driving a browser tool, or CSV files you export by hand from trends.google.com. Google often answers automated clients with HTTP 429; when that happens the tools stop and ask for CSV files instead of trying to get around the block.

Results go to `./google-trends-output/` (git-ignored). Run the same query later and the report ends with "Changes since <date>".

## Privacy and security

- **Network:** only `trends.google.com`. The browser collector blocks every other host. Your terms are sent to Google exactly as if you typed them into the site; nothing is sent to anyone else, and there is no telemetry.
- **No credentials:** no login, no API keys, no cookies from your browser. Playwright runs in a fresh throwaway profile.
- **No evasion:** no proxies, no CAPTCHA solving, no identity tricks. A 429, consent wall or CAPTCHA ends the run.
- **Local data:** reports, raw responses and history stay in your working folder and are ignored by git. They describe your business ideas; do not commit them.
- **Untrusted text:** query texts from Trends are treated as data. HTML reports are escaped and ship with a strict Content-Security-Policy and no scripts; CSV and XLSX cells that start with `=`, `+`, `-` or `@` are neutralised; the RSS parser rejects DOCTYPE/entity declarations; output paths cannot escape the output folder.
- **Supply chain:** two pinned runtime dependencies, GitHub Actions pinned by commit SHA, Dependabot, secret scanning (gitleaks) on every push.

See [SECURITY.md](SECURITY.md) to report a vulnerability.

## Responsible use

This is for personal, low-volume research (a handful of queries at a time). Automated access may be limited or blocked by Google and may be subject to Google's terms of service; check them before using this for anything systematic. The skill keeps volume low on purpose and will not be made to bypass limits.

## Limits

- Trends gives relative interest, so no volumes, sales or revenue; narrow queries and small markets often have no data.
- Impulse products bought from TikTok or Reels are not searched for; use Meta Ad Library and TikTok Creative Center.
- Rising interest does not guarantee margin.
- The page and API formats are Google's and can change. The parsers are covered by tests on synthetic fixtures; live collection is best effort.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

Tests are offline and use synthetic data only. Thresholds for the shape rules are named constants at the top of `skills/google-trends/scripts/gtrends/analyze.py`.

## License

MIT, see [LICENSE](LICENSE).

# google-trends-skill

A Claude skill for the Claude app and [Claude Code](https://claude.com/claude-code) that turns Google Trends into ecommerce decisions: is a product worth launching, when is its season, where to send the ad budget, which name to use, what is rising, and whether people want to buy or only read.

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
| Services, professions, niches | `--kind service`: the shape and season of search interest, the intent mix of related queries (definitions, career and learning, buying words), no launch verdict |
| Export tests | one term across several countries |

The numbers, shapes, rankings and verdicts always come from the scripts, not from the model's own arithmetic. Crimea and Sevastopol (tiny samples that jump to the top of the ranking) are left out of the region list by default; `--all-regions` shows them. Every run keeps its source data, a snapshot and the reports, so it can be reproduced and compared later.

The workflow follows a 15-minute product check with a pre-launch checklist; the manual items (search volume, competition) stay unticked on purpose.

## Install

The skill itself lives in [`skills/google-trends/`](skills/google-trends/). Pick the way that fits where you use Claude.

**Claude app (claude.ai, desktop):** download **`google-trends.zip`** from the [latest release](https://github.com/YanisDigital/google-trends-skill/releases/latest) (under *Assets*) and upload it as a skill in the app's skill settings. Use that file, not *Source code (zip)*: GitHub builds the source archive from the whole repository, and the app rejects it because it holds the plugin wrapper and tests around the skill. In the app the skill runs in a sandbox, so use CSV import or browser mode there; the Playwright collector needs a local machine.

**Claude Code, as a plugin** (updates through `/plugin`):

```text
/plugin marketplace add YanisDigital/google-trends-skill
/plugin install google-trends@google-trends-skill
```

**Claude Code, as a plain skill:** unzip `google-trends.zip` into `~/.claude/skills/`, or copy `skills/google-trends/` there.

Build the archive yourself with `python tools/build_skill_zip.py dist/google-trends.zip`.

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

Three ways to get the data: the CLI (Playwright), Claude driving **your own Chrome** through Claude in Chrome, or CSV files you export by hand from trends.google.com. Google often answers automated browsers with HTTP 429 even when the page opens fine in your Chrome; the CLI then stops after one retry and points to the other two ways instead of trying to get around the block.

Results go to `./google-trends-output/` (git-ignored). Run the same query later and the report ends with "Changes since <date>".

## Privacy and security

- **Network:** only `trends.google.com`. The Playwright collector blocks every other host (service workers and downloads are disabled so nothing slips past the filter); the RSS client refuses redirects to any other host. Your terms are sent to Google exactly as if you typed them into the site; nothing is sent to anyone else, and there is no telemetry.
- **No credentials in the scripts:** no login, no API keys. The CLI's Playwright browser runs in a fresh throwaway profile without your cookies.
- **Browser mode uses your own Chrome session.** With Claude in Chrome the page is opened in your real browser, so if you are signed in to Google, these Trends searches are linked to your Google account exactly as when you search by hand. Use a Chrome profile that is not signed in to Google if you want to avoid that. The skill never reads or stores your cookies.
- **No evasion:** no proxies, no CAPTCHA solving, no identity tricks. A 429, consent wall or CAPTCHA ends the run.
- **Local data:** reports, raw responses and history stay in `./google-trends-output/`. When the tool creates that folder it puts a `.gitignore` with `*` inside, so the reports stay out of your own repositories too; if you point `--out` at an existing folder it warns instead of touching it. The files describe your business ideas; do not commit or share them.
- **Untrusted text:** query texts from Trends are treated as data. HTML reports are escaped and ship with a strict Content-Security-Policy and no scripts; CSV and XLSX cells that start with `=`, `+`, `-` or `@` are neutralised; Markdown output escapes links, images and HTML; the RSS parser rejects DOCTYPE/entity declarations; snapshots are validated strictly before use, and every output path is checked so it cannot escape the output folder, even for a snapshot someone else sent you.
- **Supply chain:** two pinned runtime dependencies, GitHub Actions pinned by commit SHA, Dependabot, secret scanning (gitleaks) on every push.

See [SECURITY.md](SECURITY.md) to report a vulnerability.

## Responsible use

This is for personal, low-volume research (a handful of queries at a time). Automated access may be limited or blocked by Google and may be subject to Google's terms of service; check them before using this for anything systematic. The skill keeps volume low on purpose and will not be made to bypass limits.

## Limits

- Trends gives relative interest, so no volumes, sales or revenue; narrow queries and small markets often have no data.
- Impulse products bought from TikTok or Reels are not searched for; use Meta Ad Library and TikTok Creative Center.
- Rising interest does not guarantee margin.
- The page and API formats are Google's and can change (Google has announced a new Trends experience). Tests run offline on synthetic fixtures. Browser mode with Claude in Chrome was verified end to end on real data (one and two terms); the Playwright collector was not, because Google returned 429 to it in every test.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

Tests are offline and use synthetic data only. Thresholds for the shape rules are named constants at the top of `skills/google-trends/scripts/gtrends/analyze.py`.

## License

MIT, see [LICENSE](LICENSE).

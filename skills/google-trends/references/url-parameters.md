# Explore URL parameters

Base: `https://trends.google.com/trends/explore`

| Parameter | Values | Notes |
|---|---|---|
| `q` | comma-separated terms, URL-encoded | up to 5; a comma inside a term is not allowed |
| `geo` | `UA`, `US`, `US-CA` (country or region); several codes separated by commas; empty = worldwide | one geo per term, or one term with several geos |
| `date` | `now 1-H`, `now 4-H`, `now 1-d`, `now 7-d`, `today 1-m`, `today 3-m`, `today 12-m`, `today 5-y`, `all`, or `YYYY-MM-DD YYYY-MM-DD` | `today 5-y` is the default; `all` is monthly data since 2004 |
| `gprop` | empty = web, `froogle` = Google Shopping, `youtube`, `images`, `news` | the CLI names: `web`, `shopping`, `youtube`, `images`, `news` |
| `cat` | `0` = all categories, `18` = Shopping | pick a category for ambiguous words |
| `hl` | `en` | keep `en`: labels such as "Breakout" and the CSV section names (TOP / RISING) then stay parseable |

Example: `https://trends.google.com/trends/explore?q=air%20fryer,multicooker&date=today%205-y&geo=UA&hl=en&gprop=froogle`

## Search term vs Topic

- A *search term* matches the words typed (and close variants).
- A *Topic* is an entity that merges languages and synonyms, picked from the suggestion list in the Trends interface. In the URL it appears as an ID such as `/m/0abc12`.
- The CLI sends plain search terms because Topic IDs cannot be guessed. For a Topic, use browser mode and pick it from the suggestion list, then pass the same label to `ingest`.

## Data granularity

Up to 5 years the series is weekly; beyond that, monthly. Shorter windows are daily or hourly. The scripts average everything to months for shape decisions, so the granularity does not change a verdict.

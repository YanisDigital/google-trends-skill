"""Explore links for exporting data by hand, for when automated collection is blocked.

Trends compares at most 5 terms on one chart, so a longer list becomes several links; the numbers
of different links are not comparable. Only links to trends.google.com are produced.
"""
from __future__ import annotations

from .fetch_playwright import explore_url, validate_inputs
from .parse import MAX_TERMS
from .util import md_escape

SOURCE_NAME = {"web": "web search", "shopping": "Google Shopping", "youtube": "YouTube", "images": "Google Images", "news": "Google News"}


def build_links(terms: list[str], geos: list[str], date_range: str, sources: list[str], category: int = 0) -> list[dict]:
    """One entry per (term set, source). Several geos need exactly one term and give a single set."""
    if len(geos) > 1:
        groups = [list(terms)]
    else:
        groups = [terms[i:i + MAX_TERMS] for i in range(0, len(terms), MAX_TERMS)]
    out = []
    for n, group in enumerate(groups, 1):
        validate_inputs(group, geos, date_range, sources)
        for source in sources:
            out.append({"set": n, "terms": group, "source": source,
                        "url": explore_url(group, geos, date_range, source, category)})
    return out


def render_markdown(links: list[dict], geos: list[str], kind: str = "product") -> str:
    geo_arg = " ".join(geos) if all(geos) else "UA"
    sets = sorted({link["set"] for link in links})
    lines = [
        "# Google Trends: links for manual export",
        "",
        "Open each link in your own browser (a profile that is not signed in to Google if you prefer). Under "
        "**Interest over time** click the download arrow and save the CSV with the suggested name plus the set "
        "and source in front, for example `set1_web_multiTimeline.csv`.",
        "",
        "Numbers are comparable only inside one set (one link): the index is recalculated for every chart.",
        "",
    ]
    for n in sets:
        mine = [link for link in links if link["set"] == n]
        lines += [f"## Set {n}: " + ", ".join(md_escape(t) for t in mine[0]["terms"]), ""]
        for link in mine:
            lines.append(f"- {SOURCE_NAME[link['source']]}: <{link['url']}>")
        lines.append("")
    kind_flag = " --kind service" if kind == "service" else ""
    lines += [
        "## After exporting",
        "",
        "Optional extras per link: **Interest by region** (`geoMap.csv`) and **Related queries** "
        "(`relatedQueries.csv`, interface language English). Then, for each set:",
        "",
        "```bash",
        f"python trends_cli.py import-csv --geo {geo_arg}{kind_flag} --web-timeline set1_web_multiTimeline.csv \\",
        "  --regions set1_web_geoMap.csv",
        "```",
        "",
    ]
    if kind != "service" and any(link["source"] == "shopping" for link in links):
        lines += ["Add `--shopping-timeline set1_shopping_multiTimeline.csv` for the Google Shopping export.", ""]
    if any(link["source"] not in ("web", "shopping") for link in links):
        lines += ["CSV files from sources other than web search and Google Shopping cannot be imported; "
                  "use browser mode for those.", ""]
    lines += ["The skill folder holds `scripts/trends_cli.py`; use its full path.", ""]
    return "\n".join(lines)

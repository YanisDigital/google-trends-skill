"""Human-readable labels and static next-step links shared by all report formats."""
from __future__ import annotations

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

SHAPE_TEXT = {
    "growing": "Growing: steady rise over the window (green light)",
    "stable": "Stable: flat demand, price and service win",
    "fad": "Fad: sharp peak then collapse (high dead-stock risk)",
    "seasonal": "Seasonal: peaks recur every year, plan purchasing around the season",
    "declining": "Declining: interest is falling",
    "insufficient_data": "Not enough data: the query is too small or the window too short",
}

VERDICT_TEXT = {
    "go_validate": "GO: worth validating further",
    "test_small": "TEST: only with a small budget",
    "wait": "WAIT: prepare for the next season",
    "avoid": "AVOID: the demand shape is risky",
    "inconclusive": "INCONCLUSIVE: Trends cannot answer this one",
}

INTENT_TEXT = {
    "confirmed": "confirmed by Google Shopping",
    "weak": "weak in Google Shopping",
    "unclear": "unclear (partial overlap)",
    "not_checked": "Shopping not collected",
}

CHECK_MARK = {"done": "[x]", "todo": "[ ]", "attention": "[!]", "manual": "[ ]", "n/a": "[-]"}

NEXT_STEPS = [
    ("Search volumes", "Google Keyword Planner", "https://ads.google.com/home/tools/keyword-planner/"),
    ("Competition in ads", "Meta Ad Library", "https://www.facebook.com/ads/library/"),
    ("Short-video competition", "TikTok Creative Center", "https://ads.tiktok.com/business/creativecenter/"),
]

# Example marketplaces for price checks, keyed by Trends geo code. Extend as needed.
MARKETPLACES = {
    "UA": [("Prom", "https://prom.ua"), ("Rozetka", "https://rozetka.com.ua")],
    "US": [("Amazon", "https://www.amazon.com")],
}

PITFALLS = [
    "Compare numbers only on one chart: the index is recalculated for every query.",
    "Use 5 years: over 12 months a seasonal peak is easy to mistake for a trend.",
    "Pick the Topic from the suggestion list when it exists; set a category for ambiguous words.",
    "Check why a peak happened (news, viral video, holiday, outages) before trusting it.",
    "A strong query pushes a weak one to zero: use queries of similar scale or an anchor query.",
]


def month_name(m: int | None) -> str:
    return MONTHS[m - 1] if m else "n/a"


def geo_label(snap: dict) -> str:
    geos = snap["query"].get("geos") or []
    return ", ".join(g or "worldwide" for g in geos) if geos else "worldwide"


def marketplaces_for(snap: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for g in snap["query"].get("geos") or []:
        out.extend(MARKETPLACES.get((g or "").upper(), []))
    return out

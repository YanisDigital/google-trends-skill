"""Collect Trends data by opening the public explore page and passively recording the
widget responses the page itself requests. No login, no cookies from the user's browser,
no API keys, nothing is sent anywhere except to Google.

Limits are deliberate: at most 5 terms, one page per source, a pause between pages, a single
retry after a 429. On a consent wall, CAPTCHA or repeated 429 the run stops and the caller is
told to fall back to manual CSV export. There is no bypass logic.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from urllib.parse import urlparse

from .parse import DATE_RANGE_RE, GEO_RE, MAX_TERMS, SOURCE_GPROP, ParseError, load_widget_json

BASE = "https://trends.google.com/trends/explore"
ALLOWED_HOST_SUFFIXES = (".google.com", ".gstatic.com", ".googleapis.com")


# Service workers are blocked because their requests bypass context.route(), which enforces the
# Google-only host list. Downloads are refused: the collector never needs a file from the page.
CONTEXT_OPTIONS = {
    "locale": "en-US",
    "viewport": {"width": 1280, "height": 2200},
    "service_workers": "block",
    "accept_downloads": False,
}


class BlockedError(RuntimeError):
    """Google showed a consent wall, CAPTCHA or rate limit. Use browser mode or the manual CSV route instead.

    `retryable` is True only for a 429 on a data request after the page itself loaded; a blocked
    explore page is final, because waiting never changed it."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def validate_inputs(terms: list[str], geos: list[str], date_range: str, sources: list[str]) -> None:
    if not 1 <= len(terms) <= MAX_TERMS:
        raise ValueError(f"give between 1 and {MAX_TERMS} terms")
    for t in terms:
        if not t.strip() or len(t) > 100 or "," in t or any(ord(c) < 32 for c in t):
            raise ValueError(f"invalid term {t!r}: 1-100 characters, no commas or control characters")
    if not geos or len(geos) > MAX_TERMS or any(not GEO_RE.match(g) for g in geos):
        raise ValueError("geo must look like UA, US or US-CA (empty = worldwide)")
    if len(geos) > 1 and len(terms) != 1:
        raise ValueError("compare either several terms in one geo or one term in several geos")
    if not DATE_RANGE_RE.match(date_range):
        raise ValueError(f"unsupported date range {date_range!r} (e.g. 'today 5-y', 'today 12-m')")
    bad = [s for s in sources if s not in SOURCE_GPROP]
    if bad:
        raise ValueError(f"unknown source(s): {bad}; choose from {sorted(SOURCE_GPROP)}")


def explore_url(terms: list[str], geos: list[str], date_range: str, source: str, category: int = 0) -> str:
    q = ",".join(urllib.parse.quote(t, safe="") for t in terms)
    # one geo for all terms is written once (the form checked in a real browser); several geos go with one term
    geo_list = geos if len(geos) > 1 else geos[:1]
    params = [f"q={q}", f"date={urllib.parse.quote(date_range, safe='')}", f"geo={','.join(geo_list)}", "hl=en"]
    if category:
        params.append(f"cat={int(category)}")
    if SOURCE_GPROP[source]:
        params.append(f"gprop={SOURCE_GPROP[source]}")
    return BASE + "?" + "&".join(params)


def _route_filter(route) -> None:
    req = route.request
    host = urlparse(req.url).hostname or ""
    if req.resource_type in ("image", "media", "font") or not (host == "google.com" or host.endswith(ALLOWED_HOST_SUFFIXES)):
        route.abort()
    else:
        route.continue_()


def _related_kind(obj: dict) -> str | None:
    try:
        first = next(i for lst in obj["default"]["rankedList"] for i in lst.get("rankedKeyword", []))
    except (KeyError, StopIteration, TypeError):
        return "queries"
    return "queries" if "query" in first else "topics"


def _term_index(url: str, terms: list[str]) -> int | None:
    """Which term does a relatedsearches request belong to? Read it from the req= parameter."""
    try:
        req = json.loads(urllib.parse.parse_qs(urlparse(url).query).get("req", ["{}"])[0])
        kw = req["restriction"]["complexKeywordsRestriction"]["keyword"][0]["value"]
    except (KeyError, IndexError, ValueError, TypeError):
        return None
    for i, t in enumerate(terms):
        if t.lower() == str(kw).lower():
            return i
    return None


def _collect(page, terms: list[str], settle_s: float, timeout_s: float) -> dict[str, object]:
    """Wait for widget responses, then return {filename: parsed JSON} for the files we keep."""
    seen: list = []
    page.on("response", lambda r: seen.append(r) if "/trends/api/" in r.url else None)
    return {"seen": seen, "page": page, "terms": terms, "settle": settle_s, "timeout": timeout_s}


def _gather(ctx: dict) -> dict[str, str]:
    page, seen = ctx["page"], ctx["seen"]
    deadline = time.time() + ctx["timeout"]
    last_count, last_change = -1, time.time()
    have_multiline = False
    while time.time() < deadline:
        page.wait_for_timeout(500)
        if "consent." in page.url or "/sorry/" in page.url:
            raise BlockedError("Google showed a consent or CAPTCHA page")
        if any(r.status == 429 and "/trends/api/" in r.url for r in seen):
            raise BlockedError("HTTP 429 (rate limited) on a data request", retryable=True)
        have_multiline = any("/widgetdata/multiline" in r.url and r.ok for r in seen)
        if len(seen) != last_count:
            last_count, last_change = len(seen), time.time()
        if have_multiline and time.time() - last_change >= ctx["settle"]:
            break
    if not have_multiline:
        raise BlockedError("the explore page did not return time series data (blocked, or the query has no data)")

    files: dict[str, str] = {}
    related_arrival = 0
    for r in seen:
        if not r.ok or "/widgetdata/" not in r.url:
            continue
        body = r.text()
        if "/widgetdata/multiline" in r.url and "multiline.json" not in files:
            files["multiline.json"] = body
        elif "/widgetdata/comparedgeo" in r.url and "comparedgeo.json" not in files:
            files["comparedgeo.json"] = body
        elif "/widgetdata/relatedsearches" in r.url:
            try:
                obj = load_widget_json(body)
            except ParseError:
                continue
            if _related_kind(obj) != "queries":
                continue
            idx = _term_index(r.url, ctx["terms"])
            idx = related_arrival if idx is None else idx
            related_arrival += 1
            files.setdefault(f"related_{idx}.json", body)
    return files


def fetch(terms: list[str], geos: list[str], date_range: str, sources: list[str], raw_dir: Path, *,
          category: int = 0, headed: bool = False, delay_s: float = 8.0, log=print) -> Path:
    """Fetch every requested source into raw_dir/<source>/*.json and return raw_dir."""
    validate_inputs(terms, geos, date_range, sources)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed: pip install -r requirements.txt && "
                           "python -m playwright install chromium") from exc

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        try:
            for n, source in enumerate(sources):
                if n:
                    time.sleep(delay_s)
                url = explore_url(terms, geos, date_range, source, category)
                for attempt in (1, 2):
                    context = browser.new_context(**CONTEXT_OPTIONS)
                    context.route("**/*", _route_filter)
                    page = context.new_page()
                    ctx = _collect(page, terms, settle_s=4.0, timeout_s=60.0)
                    try:
                        log(f"[{source}] opening explore page (attempt {attempt})")
                        resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        if resp is not None and resp.status == 429:
                            raise BlockedError("HTTP 429 (rate limited) on the explore page")
                        files = _gather(ctx)
                        break
                    except BlockedError as exc:
                        if attempt == 2 or not exc.retryable:
                            raise
                        log("rate limited on a data request: waiting 60 s before one retry")
                        time.sleep(60)
                    finally:
                        context.close()
                folder = raw_dir / source
                folder.mkdir(parents=True, exist_ok=True)
                for name, body in files.items():
                    (folder / name).write_text(body, encoding="utf-8")
                log(f"[{source}] saved {sorted(files)}")
        finally:
            browser.close()
    return raw_dir

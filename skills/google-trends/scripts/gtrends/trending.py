"""'Trending now' via Google's public RSS feed (stdlib only, one request, trends.google.com only)."""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .util import clean_text

HOST = "trends.google.com"
MAX_BYTES = 2_000_000
_GEO_RE = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$")
HT = "{https://trends.google.com/trending/rss}"


def feed_url(geo: str) -> str:
    geo = geo.strip().upper()
    if not _GEO_RE.match(geo):
        raise ValueError(f"invalid geo code: {geo!r} (expected e.g. UA, US, DE)")
    return f"https://{HOST}/trending/rss?" + urllib.parse.urlencode({"geo": geo})


def parse_feed(xml_text: str) -> list[dict]:
    """Parse the RSS body. DOCTYPE/ENTITY declarations are rejected (entity-expansion attacks)."""
    head = xml_text[:2048].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in xml_text.upper():
        raise ValueError("refusing to parse XML with a DOCTYPE/ENTITY declaration")
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        news = [clean_text(n.findtext(f"{HT}news_item_title") or "", 160) for n in it.findall(f"{HT}news_item")]
        items.append({
            "title": clean_text(it.findtext("title") or "", 120),
            "traffic": clean_text(it.findtext(f"{HT}approx_traffic") or "", 20),
            "published": clean_text(it.findtext("pubDate") or "", 40),
            "news": [n for n in news if n][:3],
        })
    return items


def fetch(geo: str, timeout: float = 20.0) -> list[dict]:
    url = feed_url(geo)
    req = urllib.request.Request(url, headers={"User-Agent": "google-trends-skill/0.1 (personal research)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https URL built above
        if urllib.parse.urlparse(resp.geturl()).hostname != HOST:
            raise RuntimeError("redirected away from trends.google.com; aborting")
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError("feed is unexpectedly large; aborting")
    return parse_feed(body.decode("utf-8", errors="replace"))


def render(items: list[dict], geo: str) -> str:
    lines = [f"## Trending now ({geo.upper()})", ""]
    for i, it in enumerate(items, 1):
        extra = f" ({it['traffic']})" if it["traffic"] else ""
        lines.append(f"{i}. {it['title']}{extra}")
        for n in it["news"][:1]:
            lines.append(f"   - {n}")
    lines += ["", "Use as inspiration for situational creatives; verify any product idea with the full check."]
    return "\n".join(lines) + "\n"

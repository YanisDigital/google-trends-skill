"""Parse Google Trends widget responses and manual CSV exports (stdlib only).

Produces a *snapshot*: a plain dict that every other module consumes.

snapshot = {
    "schema": 1,
    "created": "YYYY-MM-DD",
    "query": {"terms": [...], "geos": [...], "date": "today 5-y", "category": 0},
    "origin": "playwright" | "browser" | "csv",
    "sources": {
        "web": {
            "timeline": {"dates": [...], "series": {label: [int, ...]}},
            "regions": {label: [{"code": str, "name": str, "value": int}, ...]},
            "related": {label: {"top": [...], "rising": [...]}},
        },
        "shopping": {...},   # same shape, any subset of the three keys
    },
}
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime, timezone

from .util import clean_text

SCHEMA = 1
XSSI_PREFIX = ")]}'"
SOURCE_GPROP = {"web": "", "shopping": "froogle", "youtube": "youtube", "images": "images", "news": "news"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?")
_LABEL_SUFFIX = re.compile(r"^(.*?):\s*\(.*\)\s*$")


class ParseError(ValueError):
    """Input does not look like the expected Trends export."""


def strip_xssi(text: str) -> str:
    text = text.lstrip("﻿").lstrip()
    if text.startswith(XSSI_PREFIX):
        text = text[len(XSSI_PREFIX):]
    return text.lstrip()


def load_widget_json(text: str) -> dict:
    try:
        obj = json.loads(strip_xssi(text))
    except json.JSONDecodeError as exc:
        raise ParseError(f"not valid Trends JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ParseError("Trends JSON root must be an object")
    return obj


def series_labels(terms: list[str], geos: list[str]) -> list[str]:
    """Labels of the comparison items: N terms in one geo, or one term in N geos."""
    if len(geos) <= 1:
        return list(terms)
    if len(terms) != 1:
        raise ValueError("compare either several terms in one geo or one term in several geos")
    return [f"{terms[0]} ({g})" for g in geos]


# ---------------------------------------------------------------- JSON widgets

def parse_multiline(obj: dict) -> dict:
    """widgetdata/multiline -> {"dates": [...], "values": [[...] per series]}. Partial last points are dropped."""
    try:
        rows = obj["default"]["timelineData"]
    except (KeyError, TypeError) as exc:
        raise ParseError("multiline response has no default.timelineData") from exc
    dates: list[str] = []
    columns: list[list[int]] = []
    for row in rows:
        if row.get("isPartial"):
            continue
        day = datetime.fromtimestamp(int(row["time"]), timezone.utc).date().isoformat()
        vals = [int(v) for v in row.get("value", [])]
        if not columns:
            columns = [[] for _ in vals]
        if len(vals) != len(columns):
            raise ParseError("inconsistent number of series in timelineData")
        dates.append(day)
        for col, v in zip(columns, vals):
            col.append(v)
    return {"dates": dates, "values": columns}


def parse_geo(obj: dict) -> list[list[dict]]:
    """widgetdata/comparedgeo -> per series, a list of regions sorted by value (desc)."""
    try:
        rows = obj["default"]["geoMapData"]
    except (KeyError, TypeError) as exc:
        raise ParseError("comparedgeo response has no default.geoMapData") from exc
    width = max((len(r.get("value", [])) for r in rows), default=0)
    out: list[list[dict]] = [[] for _ in range(width)]
    for row in rows:
        for i, v in enumerate(row.get("value", [])):
            out[i].append({
                "code": clean_text(row.get("geoCode", ""), 20),
                "name": clean_text(row.get("geoName", ""), 80),
                "value": int(v),
            })
    for lst in out:
        lst.sort(key=lambda r: (-r["value"], r["name"]))
    return out


def _related_item(item: dict) -> dict:
    query = item.get("query") or (item.get("topic") or {}).get("title") or ""
    formatted = str(item.get("formattedValue", ""))
    value = item.get("value")
    breakout = formatted.lower() == "breakout"
    return {
        "query": clean_text(query),
        "value": None if breakout else (int(value) if isinstance(value, (int, float)) else None),
        "breakout": breakout,
    }


def parse_related(obj: dict) -> dict:
    """widgetdata/relatedsearches -> {"top": [...], "rising": [...]}"""
    try:
        lists = obj["default"]["rankedList"]
    except (KeyError, TypeError) as exc:
        raise ParseError("relatedsearches response has no default.rankedList") from exc
    parsed = [[_related_item(i) for i in lst.get("rankedKeyword", [])] for lst in lists]
    parsed = [[i for i in lst if i["query"]] for lst in parsed]
    return {"top": parsed[0] if parsed else [], "rising": parsed[1] if len(parsed) > 1 else []}


# ------------------------------------------------------------------ CSV exports

def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.lstrip("﻿"))))


def _blocks(rows: list[list[str]]) -> list[list[list[str]]]:
    blocks, cur = [], []
    for r in rows:
        if not any(c.strip() for c in r):
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(r)
    if cur:
        blocks.append(cur)
    return blocks


def _label(cell: str) -> str:
    m = _LABEL_SUFFIX.match(cell.strip())
    return clean_text(m.group(1) if m else cell, 120)


def _num(cell: str) -> int:
    cell = cell.strip().replace("%", "")
    if cell.startswith("<") or cell in ("", "-"):
        return 0
    try:
        return int(float(cell))
    except ValueError as exc:
        raise ParseError(f"not a number: {cell!r}") from exc


def parse_timeline_csv(text: str) -> dict:
    """Trends 'multiTimeline.csv' -> {"dates": [...], "series": {label: [...]}}."""
    for block in _blocks(_rows(text)):
        if len(block) >= 2 and _DATE_RE.match(block[1][0].strip()):
            header, data = block[0], block[1:]
            labels = [_label(c) for c in header[1:]]
            if not labels:
                continue
            if len(set(labels)) != len(labels):
                raise ParseError("duplicate series names in the CSV header")
            dates = []
            for r in data:
                d = r[0].strip()[:10]
                dates.append(d if len(d) == 10 else d + "-01")
            series = {lab: [_num(r[i + 1]) if i + 1 < len(r) else 0 for r in data] for i, lab in enumerate(labels)}
            return {"dates": dates, "series": series}
    raise ParseError("no time series block found (expected a header row followed by dated rows)")


def parse_region_csv(text: str) -> dict[str, list[dict]]:
    """Trends 'geoMap.csv' -> {label: [{"code": "", "name", "value"}, ...]} sorted by value."""
    for block in _blocks(_rows(text)):
        if len(block) >= 2 and len(block[0]) >= 2 and not _DATE_RE.match(block[1][0].strip()):
            header, data = block[0], block[1:]
            try:
                labels = [_label(c) for c in header[1:]]
                out: dict[str, list[dict]] = {lab: [] for lab in labels}
                for r in data:
                    for i, lab in enumerate(labels):
                        out[lab].append({"code": "", "name": clean_text(r[0], 80), "value": _num(r[i + 1])})
            except (ParseError, IndexError):
                continue
            for lst in out.values():
                lst.sort(key=lambda r: (-r["value"], r["name"]))
            return out
    raise ParseError("no region table found in the CSV")


def parse_related_csv(text: str) -> dict:
    """Trends 'relatedQueries.csv' (English UI) -> {"top": [...], "rising": [...]}."""
    section, out = None, {"top": [], "rising": []}
    skip_header = False
    for r in _rows(text):
        if not any(c.strip() for c in r):
            continue
        head = r[0].strip().upper()
        if len(r) == 1 and head in ("TOP", "RISING"):
            section, skip_header = head.lower(), True
            continue
        if section is None:
            continue
        if skip_header:
            skip_header = False
            continue
        value = r[1].strip() if len(r) > 1 else ""
        breakout = value.lower() == "breakout"
        digits = re.sub(r"[^\d]", "", value)
        out[section].append({
            "query": clean_text(r[0]),
            "value": None if breakout or not digits else int(digits),
            "breakout": breakout,
        })
    if not out["top"] and not out["rising"]:
        raise ParseError("no TOP/RISING sections found; export the CSV with the English interface (hl=en)")
    return out


# ------------------------------------------------------------------- snapshots

def new_snapshot(terms: list[str], geos: list[str], date_range: str, origin: str, category: int = 0) -> dict:
    return {
        "schema": SCHEMA,
        "created": date.today().isoformat(),
        "query": {"terms": list(terms), "geos": list(geos), "date": date_range, "category": category},
        "origin": origin,
        "sources": {},
    }


def add_widgets(snapshot: dict, source: str, labels: list[str], *, multiline: dict | None = None,
                comparedgeo: dict | None = None, related: dict[str, dict] | None = None) -> None:
    """Attach parsed widget JSON (already json-loaded) for one source to the snapshot."""
    if source not in SOURCE_GPROP:
        raise ValueError(f"unknown source {source!r}")
    node = snapshot["sources"].setdefault(source, {})
    if multiline is not None:
        parsed = parse_multiline(multiline)
        if len(parsed["values"]) != len(labels):
            raise ParseError(f"{source}: expected {len(labels)} series, got {len(parsed['values'])}")
        node["timeline"] = {"dates": parsed["dates"], "series": dict(zip(labels, parsed["values"]))}
    if comparedgeo is not None:
        per_series = parse_geo(comparedgeo)
        node["regions"] = {lab: per_series[i] for i, lab in enumerate(labels) if i < len(per_series)}
    if related:
        node["related"] = {lab: parse_related(obj) for lab, obj in related.items()}


def add_csv(snapshot: dict, source: str, *, timeline: str | None = None, regions: str | None = None,
            related: dict[str, str] | None = None) -> None:
    """Attach manually exported CSV text. `related` maps a term label to its CSV text."""
    node = snapshot["sources"].setdefault(source, {})
    if timeline is not None:
        node["timeline"] = parse_timeline_csv(timeline)
    if regions is not None:
        node["regions"] = parse_region_csv(regions)
    if related:
        node["related"] = {lab: parse_related_csv(txt) for lab, txt in related.items()}


def validate_snapshot(snap: dict) -> None:
    if not isinstance(snap, dict) or snap.get("schema") != SCHEMA:
        raise ParseError(f"unsupported snapshot (expected schema {SCHEMA})")
    if not isinstance(snap.get("sources"), dict) or "web" not in snap["sources"]:
        raise ParseError("snapshot has no 'web' source")
    for name, src in snap["sources"].items():
        tl = src.get("timeline")
        if tl is None:
            continue
        n = len(tl.get("dates", []))
        for lab, vals in tl.get("series", {}).items():
            if len(vals) != n:
                raise ParseError(f"{name}/{lab}: series length differs from dates")

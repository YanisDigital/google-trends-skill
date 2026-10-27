"""Parse Google Trends widget responses and manual CSV exports (stdlib only).

Produces a *snapshot*: a plain dict that every other module consumes.

snapshot = {
    "schema": 1,
    "created": "YYYY-MM-DD",
    "query": {"terms": [...], "geos": [...], "date": "today 5-y", "category": 0, "kind": "product" | "service"},
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
import math
import re
from datetime import date, datetime, timezone

from .util import clean_text

SCHEMA = 1
XSSI_PREFIX = ")]}'"
SOURCE_GPROP = {"web": "", "shopping": "froogle", "youtube": "youtube", "images": "images", "news": "news"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?")
ISO_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GEO_RE = re.compile(r"^([A-Z]{2}(-[A-Z0-9]{1,3})?)?$")
DATE_RANGE_RE = re.compile(r"^[A-Za-z0-9 \-]{1,30}$")
ORIGINS = ("playwright", "browser", "csv")
KINDS = ("product", "service")
MAX_TERMS = 5
_LABEL_SUFFIX = re.compile(r"^(.*?):\s*\(.*\)\s*$")


class ParseError(ValueError):
    """Input does not look like the expected Trends export."""


def strip_xssi(text: str) -> str:
    text = text.lstrip("﻿").lstrip()
    if text.startswith(XSSI_PREFIX):
        text = text[len(XSSI_PREFIX):].lstrip()
        if text.startswith(","):  # the real prefix is ")]}'," followed by a newline
            text = text[1:]
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
        try:
            day = datetime.fromtimestamp(int(row["time"]), timezone.utc).date().isoformat()
            vals = [int(v) for v in row.get("value", [])]
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise ParseError(f"malformed timelineData row: {exc}") from exc
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
                "value": _int_or_error(v),
            })
    for lst in out:
        lst.sort(key=lambda r: (-r["value"], r["name"]))
    return out


def _int_or_error(v: object) -> int:
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ParseError(f"not an integer: {v!r}") from exc


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
        number = float(cell)
    except ValueError as exc:
        raise ParseError(f"not a number: {cell!r}") from exc
    if not math.isfinite(number):
        raise ParseError(f"not a finite number: {cell!r}")
    return int(number)


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

def new_snapshot(terms: list[str], geos: list[str], date_range: str, origin: str, category: int = 0,
                 kind: str = "product") -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    return {
        "schema": SCHEMA,
        "created": date.today().isoformat(),
        "query": {"terms": list(terms), "geos": list(geos), "date": date_range, "category": category, "kind": kind},
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


def _fail(msg: str) -> None:
    raise ParseError(f"invalid snapshot: {msg}")


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _check_day(value: object, what: str) -> None:
    if not isinstance(value, str) or not ISO_DAY_RE.match(value):
        _fail(f"{what} must be a YYYY-MM-DD string")
    try:
        date.fromisoformat(value)
    except ValueError:
        _fail(f"{what} is not a real date: {value!r}")


def _check_label(value: object, what: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        _fail(f"{what} must be a non-empty string of at most 200 characters")


def validate_snapshot(snap: dict) -> None:
    """Strict structural check. Snapshots may come from other people, and their fields end up in
    file names, Markdown, HTML and spreadsheets, so anything unexpected is rejected."""
    if not isinstance(snap, dict) or snap.get("schema") != SCHEMA:
        raise ParseError(f"unsupported snapshot (expected schema {SCHEMA})")
    _check_day(snap.get("created"), "'created'")
    if snap.get("origin") not in ORIGINS:
        _fail(f"'origin' must be one of {ORIGINS}")
    q = snap.get("query")
    if not isinstance(q, dict):
        _fail("'query' must be an object")
    terms, geos = q.get("terms"), q.get("geos")
    if not isinstance(terms, list) or not 1 <= len(terms) <= MAX_TERMS:
        _fail(f"'query.terms' must hold 1-{MAX_TERMS} terms")
    for t in terms:
        _check_label(t, "a term")
    if not isinstance(geos, list) or len(geos) > MAX_TERMS or not all(isinstance(g, str) and GEO_RE.match(g) for g in geos):
        _fail("'query.geos' must be country/region codes such as UA or US-CA")
    if not isinstance(q.get("date"), str) or not DATE_RANGE_RE.match(q["date"]):
        _fail("'query.date' must look like 'today 5-y'")
    if not _is_int(q.get("category", 0)):
        _fail("'query.category' must be an integer")
    if q.get("kind", "product") not in KINDS:
        _fail(f"'query.kind' must be one of {KINDS}")

    sources = snap.get("sources")
    if not isinstance(sources, dict) or "web" not in sources:
        raise ParseError("snapshot has no 'web' source")
    for name, src in sources.items():
        if name not in SOURCE_GPROP:
            _fail(f"unknown source {name!r}")
        if not isinstance(src, dict) or set(src) - {"timeline", "regions", "related"}:
            _fail(f"source {name!r} may only hold timeline, regions and related")
        tl = src.get("timeline")
        if tl is not None:
            if not isinstance(tl, dict) or not isinstance(tl.get("dates"), list) or not isinstance(tl.get("series"), dict):
                _fail(f"{name}: timeline needs 'dates' and 'series'")
            for d in tl["dates"]:
                _check_day(d, f"{name}: a timeline date")
            if not 1 <= len(tl["series"]) <= MAX_TERMS:
                _fail(f"{name}: timeline must hold 1-{MAX_TERMS} series")
            n = len(tl["dates"])
            for lab, vals in tl["series"].items():
                _check_label(lab, f"{name}: a series label")
                if not isinstance(vals, list) or len(vals) != n:
                    raise ParseError(f"{name}/{lab}: series length differs from dates")
                if not all(_is_int(v) and 0 <= v <= 100 for v in vals):
                    _fail(f"{name}/{lab}: series values must be integers 0-100")
        regions = src.get("regions") or {}
        if not isinstance(regions, dict):
            _fail(f"{name}: regions must be an object")
        for lab, regs in regions.items():
            _check_label(lab, f"{name}: a region label")
            if not isinstance(regs, list):
                _fail(f"{name}/{lab}: regions must be a list")
            for r in regs:
                if not (isinstance(r, dict) and isinstance(r.get("code"), str) and isinstance(r.get("name"), str)
                        and _is_int(r.get("value"))):
                    _fail(f"{name}/{lab}: each region needs code, name and an integer value")
        related = src.get("related") or {}
        if not isinstance(related, dict):
            _fail(f"{name}: related must be an object")
        for lab, rel in related.items():
            _check_label(lab, f"{name}: a related label")
            if not isinstance(rel, dict):
                _fail(f"{name}/{lab}: related must be an object")
            for kind in ("top", "rising"):
                items = rel.get(kind, [])
                if not isinstance(items, list):
                    _fail(f"{name}/{lab}: related.{kind} must be a list")
                for r in items:
                    if not (isinstance(r, dict) and isinstance(r.get("query"), str)
                            and (r.get("value") is None or _is_int(r.get("value"))) and isinstance(r.get("breakout"), bool)):
                        _fail(f"{name}/{lab}: each related query needs query, value (integer or null) and breakout")

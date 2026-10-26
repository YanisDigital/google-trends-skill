"""Compact browser-mode format -> raw widget files.

Browser tools truncate large results, so the in-page snippet (see references/browser-mode.md)
returns this small object instead of the raw 40 KB responses:

{
  "source": "web",                       # web | shopping | youtube | images | news
  "t0": 1635033600, "step": 604800,      # unix seconds of the first point and the spacing ...
  "times": [..],                         # ... or an explicit list when spacing is not uniform
  "series": ["8,0,6,...", "..."],        # one comma-separated string (or list of ints) per term, in --terms order
  "partial_last": true,                  # the last point is the unfinished current period
  "regions": "UA-30|Kyiv city|100,40;UA-21|Zakarpats'ka oblast|74,10",   # or a list of {code, name, values}
  "related": [{"top": "query|100|100;other|55|55", "rising": "query|689900|Breakout"}]   # or lists of [q, v, f]
}

Strings, not nested arrays: browser tools cut long arrays and long top-level strings, but pass
object fields holding a few KB of text. ";" and "|" must not occur inside query texts (the snippet
replaces them with spaces).

expand() writes the same files the Playwright collector writes, so `ingest` reads both alike.
"""
from __future__ import annotations

import json
from pathlib import Path

from .parse import SOURCE_GPROP, ParseError

MAX_SERIES, MAX_POINTS, MAX_REGIONS, MAX_RELATED = 5, 3000, 400, 100
PREFIX = ")]}',\n"


def _ints(values: object, what: str) -> list[int]:
    if not isinstance(values, list) or not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        raise ParseError(f"compact: {what} must be a list of integers")
    return values


def _int_list(value: object, what: str) -> list[int]:
    """Accept "8,0,6" or [8, 0, 6]."""
    if isinstance(value, str):
        try:
            return [int(x) for x in value.split(",")] if value.strip() else []
        except ValueError as exc:
            raise ParseError(f"compact: {what} must be comma-separated integers") from exc
    return _ints(value, what)


def _regions(value: object) -> list[dict]:
    if isinstance(value, str):
        out = []
        for row in filter(None, value.split(";")):
            parts = row.split("|")
            if len(parts) != 3:
                raise ParseError(f"compact: bad region row {row!r} (expected code|name|v1,v2)")
            out.append({"code": parts[0], "name": parts[1], "values": _int_list(parts[2], "region values")})
        return out
    if not isinstance(value, list):
        raise ParseError("compact: regions must be a string or a list")
    return [{"code": r.get("code", ""), "name": r.get("name", ""), "values": _ints(r.get("values"), "region values")}
            for r in value]


def _related_entries(value: object, what: str) -> list[tuple[str, int, str]]:
    if isinstance(value, str):
        rows = []
        for row in filter(None, value.split(";")):
            parts = row.split("|")
            if len(parts) != 3:
                raise ParseError(f"compact: bad {what} row {row!r} (expected query|value|formatted)")
            rows.append((parts[0], parts[1], parts[2]))
        value = rows
    if not isinstance(value, list) or len(value) > MAX_RELATED:
        raise ParseError(f"compact: {what} must be a string or list (max {MAX_RELATED} entries)")
    try:
        return [(str(q), int(v), str(f)) for q, v, f in value]
    except (TypeError, ValueError) as exc:
        raise ParseError(f"compact: bad entry in {what}") from exc


def expand(compact: dict, raw_dir: Path) -> str:
    """Write raw widget files for one source into raw_dir/<source>/ and return the source name."""
    if not isinstance(compact, dict):
        raise ParseError("compact: root must be an object")
    source = compact.get("source", "web")
    if source not in SOURCE_GPROP:
        raise ParseError(f"compact: unknown source {source!r}")
    folder = raw_dir / source
    folder.mkdir(parents=True, exist_ok=True)

    series = compact.get("series")
    if series is not None:
        if not isinstance(series, list) or not 1 <= len(series) <= MAX_SERIES:
            raise ParseError(f"compact: series must hold 1-{MAX_SERIES} lists")
        cols = [_int_list(s, "a series") for s in series]
        n = len(cols[0])
        if n > MAX_POINTS or any(len(c) != n for c in cols):
            raise ParseError(f"compact: series lists must have equal length (max {MAX_POINTS} points)")
        times = compact.get("times")
        if times is None:
            t0, step = compact.get("t0"), compact.get("step")
            if not isinstance(t0, int) or not isinstance(step, int) or step <= 0:
                raise ParseError("compact: give t0 and a positive step, or an explicit times list")
            times = [t0 + i * step for i in range(n)]
        times = _ints(times, "times")
        if len(times) != n:
            raise ParseError("compact: times and series differ in length")
        rows = []
        for i, t in enumerate(times):
            row = {"time": str(t), "value": [c[i] for c in cols], "hasData": [True] * len(cols),
                   "formattedValue": [str(c[i]) for c in cols]}
            if compact.get("partial_last") and i == n - 1:
                row["isPartial"] = True
            rows.append(row)
        _write(folder / "multiline.json", {"default": {"timelineData": rows, "averages": []}})

    regions = compact.get("regions")
    if regions is not None:
        regions = _regions(regions)
        if len(regions) > MAX_REGIONS:
            raise ParseError(f"compact: too many regions (max {MAX_REGIONS})")
        items = []
        for r in regions:
            vals = r["values"]
            items.append({"geoCode": str(r["code"]), "geoName": str(r["name"]), "value": vals,
                          "formattedValue": [str(v) for v in vals], "maxValueIndex": 0, "hasData": [True] * len(vals)})
        _write(folder / "comparedgeo.json", {"default": {"geoMapData": items}})

    related = compact.get("related")
    if related is not None:
        if not isinstance(related, list) or len(related) > MAX_SERIES:
            raise ParseError("compact: related must be a list with one entry per term")
        for i, rel in enumerate(related):
            if not rel:
                continue
            lists = []
            for kind in ("top", "rising"):
                entries = _related_entries(rel.get(kind, []), f"related[{i}].{kind}")
                lists.append({"rankedKeyword": [
                    {"query": q, "value": v, "formattedValue": f, "hasData": True} for q, v, f in entries]})
            _write(folder / f"related_{i}.json", {"default": {"rankedList": lists}})
    return source


def _write(path: Path, obj: dict) -> None:
    path.write_text(PREFIX + json.dumps(obj, ensure_ascii=False), encoding="utf-8")

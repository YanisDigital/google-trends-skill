"""Build a snapshot from a directory of raw widget responses.

Layout (written by fetch_playwright, or by Claude in browser mode):

    <raw>/<source>/multiline.json        source = web | shopping | youtube | images | news
    <raw>/<source>/comparedgeo.json
    <raw>/<source>/related_<i>.json      i = index of the term in --terms (0-based)
"""
from __future__ import annotations

from pathlib import Path

from .parse import (
    SOURCE_GPROP,
    ParseError,
    add_widgets,
    load_widget_json,
    new_snapshot,
    series_labels,
    validate_snapshot,
)
from .util import read_text_capped


def _read(path: Path) -> dict:
    return load_widget_json(read_text_capped(path))


def ingest_raw(raw_dir: Path, terms: list[str], geos: list[str], date_range: str,
               origin: str, category: int = 0, kind: str = "product") -> dict:
    labels = series_labels(terms, geos)
    snap = new_snapshot(terms, geos, date_range, origin, category, kind)
    for source in SOURCE_GPROP:
        folder = raw_dir / source
        if not folder.is_dir():
            continue
        multiline = _read(folder / "multiline.json") if (folder / "multiline.json").exists() else None
        geo = _read(folder / "comparedgeo.json") if (folder / "comparedgeo.json").exists() else None
        related = {}
        for i, lab in enumerate(labels):
            f = folder / f"related_{i}.json"
            if f.exists():
                related[lab] = _read(f)
        if multiline is None and geo is None and not related:
            continue
        add_widgets(snap, source, labels, multiline=multiline, comparedgeo=geo, related=related or None)
    if "web" not in snap["sources"] or "timeline" not in snap["sources"]["web"]:
        raise ParseError(f"no web/multiline.json found under {raw_dir}")
    validate_snapshot(snap)
    return snap

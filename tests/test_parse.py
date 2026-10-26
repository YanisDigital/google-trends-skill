import json

import pytest
from conftest import FIXTURES
from gtrends import parse as P
from gtrends.fetch_playwright import explore_url, validate_inputs
from gtrends.ingest import ingest_raw


def test_strip_xssi_and_bom():
    assert P.load_widget_json("﻿)]}'\n{\"a\": 1}") == {"a": 1}
    assert P.load_widget_json('{"a": 1}') == {"a": 1}


def test_bad_json_raises_parse_error():
    with pytest.raises(P.ParseError):
        P.load_widget_json("<html>captcha</html>")


def test_multiline_drops_partial_last_point():
    obj = P.load_widget_json((FIXTURES / "raw/web/multiline.json").read_text())
    parsed = P.parse_multiline(obj)
    assert len(parsed["values"]) == 2
    assert len(parsed["dates"]) == 259  # 260 rows, last one flagged isPartial
    assert all(len(col) == 259 for col in parsed["values"])


def test_geo_sorted_per_series():
    obj = P.load_widget_json((FIXTURES / "raw/web/comparedgeo.json").read_text())
    per = P.parse_geo(obj)
    assert [r["name"] for r in per[0]][:2] == ["Region A", "Region B"]
    assert per[1][0]["name"] == "Region D"


def test_related_breakout_and_text_cleaning():
    obj = P.load_widget_json((FIXTURES / "raw/web/related_0.json").read_text())
    rel = P.parse_related(obj)
    assert rel["top"][0]["query"] == "acme widget"
    assert rel["rising"][0]["breakout"] is True and rel["rising"][0]["value"] is None
    assert rel["rising"][1]["value"] == 250


def test_timeline_csv_with_labels_and_lt1():
    tl = P.parse_timeline_csv((FIXTURES / "sample_multiTimeline.csv").read_text())
    assert list(tl["series"]) == ["acme widget", "gadget"]
    assert tl["dates"][0] == "2025-11-01"
    assert tl["series"]["acme widget"][7] == 0  # "<1" -> 0


def test_region_csv():
    regs = P.parse_region_csv((FIXTURES / "sample_geoMap.csv").read_text())
    assert regs["acme widget"][0]["name"] == "Region A"
    assert regs["gadget"][0]["name"] == "Region D"


def test_related_csv():
    rel = P.parse_related_csv((FIXTURES / "sample_relatedQueries.csv").read_text())
    assert rel["rising"][0]["breakout"] and rel["rising"][1]["value"] == 250


def test_related_csv_wrong_language_gives_hint():
    with pytest.raises(P.ParseError, match="English"):
        P.parse_related_csv("Query,Value\nfoo,1\n")


def test_ingest_raw_labels_and_sources():
    snap = ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")
    assert set(snap["sources"]) == {"web", "shopping"}
    assert list(snap["sources"]["web"]["timeline"]["series"]) == ["acme widget", "gadget"]
    assert "acme widget" in snap["sources"]["web"]["related"]
    assert snap["sources"]["web"]["regions"]["gadget"][0]["name"] == "Region D"


def test_ingest_series_count_mismatch():
    with pytest.raises(P.ParseError):
        ingest_raw(FIXTURES / "raw", ["only one"], ["UA"], "today 5-y", "browser")


def test_series_labels_geo_compare():
    assert P.series_labels(["x"], ["UA", "PL"]) == ["x (UA)", "x (PL)"]
    with pytest.raises(ValueError):
        P.series_labels(["x", "y"], ["UA", "PL"])


def test_snapshot_is_json_serialisable():
    snap = ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")
    assert json.loads(json.dumps(snap)) == snap


# ---- fetch input validation (no browser, no network) ----
def test_explore_url_shape():
    url = explore_url(["air fryer", "мультипіч"], ["UA"], "today 5-y", "shopping")
    assert url.startswith("https://trends.google.com/trends/explore?")
    assert "gprop=froogle" in url and "geo=UA,UA" in url and "hl=en" in url
    assert "%D0%BC" in url  # non-ASCII term is percent-encoded


@pytest.mark.parametrize("terms,geos,date,sources", [
    ([], ["UA"], "today 5-y", ["web"]),
    (["a"] * 6, ["UA"], "today 5-y", ["web"]),
    (["a,b"], ["UA"], "today 5-y", ["web"]),
    (["a\nb"], ["UA"], "today 5-y", ["web"]),
    (["a"], ["ua"], "today 5-y", ["web"]),
    (["a"], ["UA"], "today 5-y&x=1", ["web"]),
    (["a"], ["UA"], "today 5-y", ["tiktok"]),
    (["a", "b"], ["UA", "PL"], "today 5-y", ["web"]),
])
def test_validate_inputs_rejects(terms, geos, date, sources):
    with pytest.raises(ValueError):
        validate_inputs(terms, geos, date, sources)


def test_validate_inputs_accepts_worldwide():
    validate_inputs(["a"], [""], "today 12-m", ["web", "shopping"])

"""Regression tests for the second security review."""
import copy
from pathlib import Path

import pytest
from conftest import FIXTURES
from gtrends import links, parse, trending
from gtrends.fetch_playwright import explore_url, validate_inputs
from gtrends.ingest import ingest_raw

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("geos,date", [
    (["UA\n"], "today 5-y"),
    (["UA"], "today 5-y\n"),
    (["UA\r\n"], "today 5-y"),
    (["PL", "DE\n"], "today 5-y"),
])
def test_trailing_newlines_are_rejected(geos, date):
    with pytest.raises(ValueError):
        validate_inputs(["x"], geos, date, ["web"])
    with pytest.raises(ValueError):
        links.build_links(["x"], geos, date, ["web"])


def test_snapshot_fields_with_trailing_newline_are_rejected():
    snap = ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")
    for mutate in (lambda s: s["query"].__setitem__("geos", ["UA\n"]),
                   lambda s: s["query"].__setitem__("date", "today 5-y\n"),
                   lambda s: s.__setitem__("created", "2026-10-27\n")):
        s = copy.deepcopy(snap)
        mutate(s)
        with pytest.raises(parse.ParseError):
            parse.validate_snapshot(s)


def test_trending_geo_is_checked_strictly():
    assert trending.feed_url(" ua \n").endswith("geo=UA")  # surrounding whitespace is trimmed first
    with pytest.raises(ValueError):
        trending.feed_url("U\nA")


def test_explore_url_never_contains_raw_control_characters():
    for geos in (["UA"], ["PL", "DE"], [""], ["US-CA"]):
        url = explore_url(["a b", "c"] if len(geos) == 1 else ["a b"], geos, "today 5-y", "web")
        assert not any(ord(ch) < 33 for ch in url), url


def test_skill_md_never_searches_the_whole_disk():
    text = (ROOT / "skills" / "google-trends" / "SKILL.md").read_text(encoding="utf-8")
    assert "find / " not in text
    assert "find ~/.claude /mnt" in text and "Do not search the whole disk" in text


def test_release_workflow_publishes_a_checksum():
    wf = (ROOT / ".github" / "workflows" / "release-skill-zip.yml").read_text(encoding="utf-8")
    assert "sha256sum google-trends.zip > google-trends.zip.sha256" in wf
    assert "dist/google-trends.zip.sha256" in wf.split("gh release upload", 1)[1]
    assert "${{ inputs.tag }}" not in wf.split("run:", 1)[1]  # inputs reach shell steps only through env

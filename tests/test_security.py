"""Regression tests for the security and privacy review: every finding has a test that replays it."""
import copy
import json
import sys
import urllib.error
import urllib.request
from email.message import Message

import pytest
from conftest import FIXTURES, SCRIPTS
from gtrends import history, parse, trending, util
from gtrends.fetch_playwright import CONTEXT_OPTIONS
from gtrends.ingest import ingest_raw

sys.path.insert(0, str(SCRIPTS))
import trends_cli


@pytest.fixture()
def snap():
    return ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")


def _report(tmp_path, snapshot) -> tuple[int, list]:
    out = tmp_path / "a" / "b" / "out"
    f = tmp_path / "shared_snapshot.json"
    f.write_text(json.dumps(snapshot), encoding="utf-8")
    code = trends_cli.main(["report", str(f), "--out", str(out), "--formats", "md", "csv"])
    outside = [p for p in tmp_path.rglob("*ESCAPE*")]
    return code, outside


# ---- path traversal through a shared snapshot ----------------------------------------------------
def test_created_field_cannot_escape_output(tmp_path, snap, capsys):
    snap["created"] = "../../../../ESCAPE"
    code, outside = _report(tmp_path, snap)
    assert code == 2 and outside == []
    assert "created" in capsys.readouterr().err


def test_source_name_cannot_escape_output(tmp_path, snap):
    snap["sources"]["x/../../../../../../ESCAPE"] = {"timeline": copy.deepcopy(snap["sources"]["shopping"]["timeline"])}
    code, outside = _report(tmp_path, snap)
    assert code == 2 and outside == []


def test_safe_join_is_used_for_csv_names(tmp_path, snap):
    from gtrends import report_tables
    from gtrends.analyze import analyze_snapshot
    analysis = analyze_snapshot(snap)
    snap["sources"]["x/../../../ESCAPE"] = snap["sources"].pop("shopping")  # bypass validation on purpose
    with pytest.raises(ValueError):
        report_tables.write_csvs(snap, analysis, tmp_path)


# ---- strict snapshot validation ------------------------------------------------------------------
def test_fixture_snapshot_is_valid(snap):
    parse.validate_snapshot(snap)


@pytest.mark.parametrize("mutate", [
    lambda s: s.__setitem__("created", "2026-13-45"),
    lambda s: s.__setitem__("origin", "<script>"),
    lambda s: s["query"].__setitem__("geos", ["UA/../x"]),
    lambda s: s["query"].__setitem__("terms", []),
    lambda s: s["query"].__setitem__("date", "today 5-y\nexec"),
    lambda s: s["sources"]["web"]["timeline"]["dates"].__setitem__(0, "=HYPERLINK(1)"),
    lambda s: s["sources"]["web"]["timeline"]["series"]["acme widget"].__setitem__(0, "100"),
    lambda s: s["sources"]["web"]["timeline"]["series"]["acme widget"].__setitem__(0, 1000),
    lambda s: s["sources"]["web"]["regions"]["acme widget"][0].__setitem__("value", "1) [x](http://evil.example"),
    lambda s: s["sources"]["web"]["related"]["acme widget"]["rising"][0].__setitem__("breakout", "yes"),
    lambda s: s["sources"]["web"].__setitem__("script", {}),
    lambda s: s["sources"].__setitem__("tiktok", {}),
])
def test_validation_rejects_tampered_snapshots(snap, mutate):
    mutate(snap)
    with pytest.raises(parse.ParseError):
        parse.validate_snapshot(snap)


def test_history_refuses_unvalidated_created(tmp_path, snap):
    snap["created"] = "../x"
    with pytest.raises(parse.ParseError):
        history.save_snapshot(tmp_path, snap)


# ---- output folder never lands in the user's git repository -------------------------------------
def test_new_output_folder_gets_gitignore(tmp_path):
    out = tmp_path / "google-trends-output"
    assert util.prepare_output_dir(out) is True
    assert (out / ".gitignore").read_text(encoding="utf-8").splitlines()[-1] == "*"


def test_existing_folder_is_left_alone(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    assert util.prepare_output_dir(tmp_path) is False
    assert not (tmp_path / ".gitignore").exists()


def test_cli_creates_gitignore_and_warns_once_for_existing_folder(tmp_path, capsys):
    out = tmp_path / "new-out"
    args = ["ingest", "--raw", str(FIXTURES / "raw"), "--terms", "acme widget", "gadget", "--formats", "md"]
    assert trends_cli.main(args + ["--out", str(out)]) == 0
    assert (out / ".gitignore").is_file()
    existing = tmp_path / "existing"
    existing.mkdir()
    capsys.readouterr()
    assert trends_cli.main(args + ["--out", str(existing)]) == 0
    assert capsys.readouterr().err.count("has no .gitignore") == 1


# ---- Markdown injection -------------------------------------------------------------------------
EVIL = "[click](http://evil.example) ![img](http://evil.example/p.png) <b>x</b> | # h"


def test_md_escape_neutralises_links_images_html_tables():
    out = util.md_escape(EVIL)
    for raw in ("[click](", "![img](", "<b>", " | "):
        assert raw not in out
    assert "\\# h" in out


def test_diff_output_is_escaped(snap):
    newer = copy.deepcopy(snap)
    newer["created"] = "2099-01-01"
    newer["sources"]["web"]["related"]["acme widget"]["rising"].append({"query": EVIL, "value": 5, "breakout": False})
    text = history.render_diff(history.diff(snap, newer))
    assert "[click](" not in text and "![img](" not in text


def test_trending_output_is_escaped():
    text = trending.render([{"title": EVIL, "traffic": "200+", "published": "", "news": [EVIL]}], "ua")
    assert "[click](" not in text and "![img](" not in text and "<b>" not in text


# ---- RSS hardening ------------------------------------------------------------------------------
def test_doctype_rejected_anywhere():
    xml = '<?xml version="1.0"?><!--' + "a" * 5000 + '--><!DOCTYPE rss SYSTEM "http://evil.example/x.dtd"><rss/>'
    with pytest.raises(ValueError):
        trending.parse_feed(xml)


@pytest.mark.parametrize("target", ["https://evil.example/rss", "http://trends.google.com/trending/rss",
                                    "https://trends.google.com.evil.example/rss"])
def test_redirects_off_host_are_refused(target):
    handler = trending._SameHostRedirect()
    req = urllib.request.Request("https://trends.google.com/trending/rss?geo=UA")
    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(req, None, 302, "Found", Message(), target)


def test_redirect_within_host_is_allowed():
    handler = trending._SameHostRedirect()
    req = urllib.request.Request("https://trends.google.com/trending/rss?geo=UA")
    new = handler.redirect_request(req, None, 302, "Found", Message(), "https://trends.google.com/trending/rss?geo=UA&x=1")
    assert new.full_url.startswith("https://trends.google.com/")


# ---- Playwright context ------------------------------------------------------------------------
def test_playwright_context_blocks_service_workers_and_downloads():
    assert CONTEXT_OPTIONS["service_workers"] == "block"
    assert CONTEXT_OPTIONS["accept_downloads"] is False


# ---- malformed input gives a clean error, not a traceback ---------------------------------------
@pytest.mark.parametrize("call", [
    lambda: parse.parse_timeline_csv("Week,a\n2024-01-07,1e999\n"),
    lambda: parse.parse_timeline_csv("Week,a\n2024-01-07,nan\n"),
    lambda: parse.parse_multiline({"default": {"timelineData": [{"value": [1]}]}}),
    lambda: parse.parse_multiline({"default": {"timelineData": [{"time": "x", "value": [1]}]}}),
    lambda: parse.parse_geo({"default": {"geoMapData": [{"geoName": "A", "value": ["many"]}]}}),
])
def test_malformed_input_raises_parse_error(call):
    with pytest.raises(parse.ParseError):
        call()


def test_deeply_nested_json_is_a_clean_error(tmp_path, capsys):
    f = tmp_path / "deep.json"
    f.write_text("[" * 100000 + "]" * 100000)
    assert trends_cli.main(["report", str(f), "--out", str(tmp_path / "o")]) == 2
    assert "error" in capsys.readouterr().err


def test_snapshot_reads_are_size_capped(tmp_path):
    big = tmp_path / "big.json"
    big.write_bytes(b" " * (util.MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError):
        history.load_snapshot(big)

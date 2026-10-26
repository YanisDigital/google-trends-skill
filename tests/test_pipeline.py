import json
import sys
from pathlib import Path

import pytest
from conftest import FIXTURES, SCRIPTS
from gtrends import history, report_html, report_md, report_tables, trending, util
from gtrends.analyze import analyze_snapshot
from gtrends.ingest import ingest_raw

sys.path.insert(0, str(SCRIPTS))
import trends_cli  # noqa: E402


@pytest.fixture()
def snap():
    return ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")


def test_analysis_end_to_end(snap):
    a = analyze_snapshot(snap)
    assert a["primary"] == "acme widget"
    t = a["terms"]["acme widget"]
    assert t["web"]["shape"] == "growing"
    assert t["intent"]["status"] == "confirmed"
    assert t["regions"]["top"][0]["name"] == "Region A"
    assert t["verdict"]["label"] == "go_validate"
    assert any(r["breakout"] for r in t["related"]["rising"])
    assert a["terms"]["gadget"]["web"]["shape"] == "stable"


def test_markdown_report_content(snap):
    a = analyze_snapshot(snap)
    md = report_md.render(snap, a)
    assert "GO: worth validating further" in md
    assert "Region A" in md and "Keyword Planner" in md
    assert "Prom" in md  # UA example marketplaces appear only for geo UA
    assert "[-]" in md and "[ ]" in md


def test_extra_source_related_is_reported(snap):
    snap["sources"]["youtube"] = {"related": {"acme widget": {"top": [], "rising": [
        {"query": "acme widget unboxing", "value": 300, "breakout": False}]}}}
    a = analyze_snapshot(snap)
    assert a["extra_sources"]["youtube"]["acme widget"]["rising"][0]["intent"] == ["review"]
    assert "Rising queries on youtube" in report_md.render(snap, a)


def test_markdown_escapes_untrusted_text(snap):
    snap["sources"]["web"]["related"]["acme widget"]["rising"][0]["query"] = "[click](http://evil.example) *x*"
    md = report_md.render(snap, analyze_snapshot(snap))
    assert "[click](http://evil.example)" not in md


def test_html_is_escaped_and_offline(snap):
    snap["query"]["terms"][0] = "<script>alert(1)</script>"
    lab = "acme widget"
    for src in snap["sources"].values():
        for key in ("timeline",):
            if key in src and lab in src[key]["series"]:
                src[key]["series"]["<script>alert(1)</script>"] = src[key]["series"].pop(lab)
        for key in ("regions", "related"):
            if key in src and lab in src[key]:
                src[key]["<script>alert(1)</script>"] = src[key].pop(lab)
    html_out = report_html.render(snap, analyze_snapshot(snap))
    assert "<script" not in html_out.lower()
    assert "&lt;script&gt;" in html_out
    assert "Content-Security-Policy" in html_out and "default-src 'none'" in html_out
    assert 'href="http://' not in html_out  # no plain-http links
    for banned in ("src=\"http", "<link ", "@import", "<iframe"):
        assert banned not in html_out


def test_spreadsheet_injection_guard():
    assert util.spreadsheet_safe("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert util.spreadsheet_safe("@SUM(A1)") == "'@SUM(A1)"
    assert util.spreadsheet_safe("normal") == "normal"
    assert util.spreadsheet_safe(5) == 5


def test_csv_and_xlsx_neutralise_formulas(snap, tmp_path):
    a = analyze_snapshot(snap)
    files = report_tables.write_csvs(snap, a, tmp_path)
    related = (tmp_path / "related.csv").read_text(encoding="utf-8")
    assert "'=HYPERLINK" in related and "\n=HYPERLINK" not in related and ",=HYPERLINK" not in related
    assert any(f.name == "timeline_web.csv" for f in files)
    openpyxl = pytest.importorskip("openpyxl")
    path = report_tables.write_xlsx(snap, a, tmp_path / "r.xlsx")
    wb = openpyxl.load_workbook(path)
    assert {"Summary", "Timeline web", "Regions", "Related", "Checklist"} <= set(wb.sheetnames)
    for row in wb["Related"].iter_rows(values_only=True):
        for cell in row:
            assert not (isinstance(cell, str) and cell.startswith("="))


def test_history_save_diff(snap, tmp_path):
    p1 = history.save_snapshot(tmp_path, snap)
    newer = json.loads(json.dumps(snap))
    newer["created"] = "2099-01-01"
    newer["sources"]["web"]["related"]["acme widget"]["rising"].append({"query": "brand new hook", "value": 90, "breakout": False})
    assert history.previous_snapshot(tmp_path, newer) == p1
    d = history.diff(snap, newer)
    assert d["terms"]["acme widget"]["new_rising_queries"] == ["brand new hook"]
    assert "brand new hook" in history.render_diff(d)


def test_safe_join_blocks_traversal(tmp_path):
    with pytest.raises(ValueError):
        util.safe_join(tmp_path, "..", "elsewhere")
    assert util.safe_join(tmp_path, "a", "b").is_relative_to(tmp_path.resolve())


def test_slug_is_filesystem_safe():
    s = util.slugify("../../etc/passwd мультипіч:*?")
    assert "/" not in s and "\\" not in s and ":" not in s and ".." not in s


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>Example topic</title><ht:approx_traffic>200+</ht:approx_traffic><pubDate>Mon, 26 Oct 2026 10:00:00 +0200</pubDate>
<ht:news_item><ht:news_item_title>Example headline</ht:news_item_title></ht:news_item></item></channel></rss>"""


def test_trending_parse_and_render():
    items = trending.parse_feed(RSS)
    assert items[0]["title"] == "Example topic" and items[0]["traffic"] == "200+"
    assert items[0]["news"] == ["Example headline"]
    assert "Example topic (200+)" in trending.render(items, "ua")


def test_trending_rejects_entities_and_bad_geo():
    evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel/></rss>'
    with pytest.raises(ValueError):
        trending.parse_feed(evil)
    with pytest.raises(ValueError):
        trending.feed_url("UA&evil=1")
    assert trending.feed_url("ua").endswith("geo=UA")


def test_cli_import_csv_end_to_end(tmp_path, capsys):
    code = trends_cli.main([
        "import-csv", "--out", str(tmp_path), "--geo", "UA",
        "--web-timeline", str(FIXTURES / "sample_multiTimeline.csv"),
        "--regions", str(FIXTURES / "sample_geoMap.csv"),
        "--related", f"acme widget={FIXTURES / 'sample_relatedQueries.csv'}",
        "--formats", "md", "html", "csv",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "Google Trends check" in out and "Region A" in out
    reports = list((tmp_path / "reports").rglob("report.html"))
    assert len(reports) == 1
    assert list((tmp_path / "history").rglob("*.json"))


def test_cli_ingest_and_report(tmp_path, capsys):
    code = trends_cli.main(["ingest", "--raw", str(FIXTURES / "raw"), "--terms", "acme widget", "gadget",
                            "--out", str(tmp_path), "--formats", "md"])
    assert code == 0
    snap_file = next((tmp_path / "history").rglob("*.json"))
    capsys.readouterr()
    assert trends_cli.main(["report", str(snap_file), "--out", str(tmp_path / "again"), "--formats", "md"]) == 0


def test_cli_bad_input_exit_code(tmp_path, capsys):
    assert trends_cli.main(["check", "--terms", "a,b", "--out", str(tmp_path)]) == 2
    assert trends_cli.main(["import-csv", "--web-timeline", str(tmp_path / "missing.csv")]) == 2
    assert "error" in capsys.readouterr().err


def test_cli_refuses_huge_input(tmp_path):
    big = tmp_path / "big.csv"
    big.write_bytes(b"x" * (trends_cli.MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError):
        trends_cli._read_text(str(big))
    assert isinstance(Path(trends_cli.__file__), Path)


def test_compact_matches_raw_pipeline(tmp_path):
    raw = FIXTURES / "raw" / "web"
    ml = json.loads((raw / "multiline.json").read_text().split(chr(10), 1)[1])["default"]["timelineData"]
    geo = json.loads((raw / "comparedgeo.json").read_text().split(chr(10), 1)[1])["default"]["geoMapData"]
    rel = json.loads((raw / "related_0.json").read_text().split(chr(10), 1)[1])["default"]["rankedList"]
    compact_obj = {
        "source": "web", "t0": int(ml[0]["time"]), "step": 604800, "partial_last": True,
        "series": [[r["value"][0] for r in ml], [r["value"][1] for r in ml]],
        "regions": [{"code": g["geoCode"], "name": g["geoName"], "values": g["value"]} for g in geo],
        "related": [{"top": [[k["query"], k["value"], k["formattedValue"]] for k in rel[0]["rankedKeyword"]],
                     "rising": [[k["query"], k["value"], k["formattedValue"]] for k in rel[1]["rankedKeyword"]]}],
    }
    f = tmp_path / "web.json"
    f.write_text(json.dumps(compact_obj), encoding="utf-8")
    code = trends_cli.main(["ingest", "--compact", str(f), "--terms", "acme widget", "gadget", "--geo", "UA",
                            "--out", str(tmp_path / "out"), "--formats", "md"])
    assert code == 0
    snap_file = next((tmp_path / "out" / "history").rglob("*.json"))
    new = json.loads(snap_file.read_text(encoding="utf-8"))
    old = ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")
    assert new["sources"]["web"] == old["sources"]["web"]


@pytest.mark.parametrize("bad", [
    {"source": "tiktok"},
    {"series": [[1, 2], [1]], "t0": 1, "step": 1},
    {"series": [[1, "x"]], "t0": 1, "step": 1},
    {"series": [[1, 2]]},
    {"series": [[1, 2]], "t0": 1, "step": 0},
    {"series": [[1] * 6]},
])
def test_compact_rejects_bad_input(bad, tmp_path):
    from gtrends import compact
    from gtrends.parse import ParseError
    with pytest.raises(ParseError):
        compact.expand(bad, tmp_path)


def test_cli_ingest_needs_exactly_one_input(tmp_path):
    assert trends_cli.main(["ingest", "--terms", "a", "--out", str(tmp_path)]) == 2


def test_growing_with_stalling_momentum_is_flagged():
    shape = {"shape": "growing", "reasons": [], "momentum_3m": 0.75}
    v = A_verdict(shape)
    assert any("stalling" in r for r in v["reasons"])
    assert not any("stalling" in r for r in A_verdict({"shape": "growing", "reasons": [], "momentum_3m": 1.1})["reasons"])


def A_verdict(shape):  # noqa: N802
    from gtrends.analyze import verdict
    return verdict(shape, {"status": "confirmed"}, None, 0)


def test_compact_string_encoding_equals_list_encoding(tmp_path):
    from gtrends import compact
    as_lists = {"series": [[1, 2, 3]], "t0": 1635033600, "step": 604800,
                "regions": [{"code": "UA-30", "name": "Kyiv city", "values": [100]}],
                "related": [{"top": [["a", 5, "5"]], "rising": [["b", 9000, "Breakout"]]}]}
    as_strings = {"series": ["1,2,3"], "t0": 1635033600, "step": 604800,
                  "regions": "UA-30|Kyiv city|100", "related": [{"top": "a|5|5", "rising": "b|9000|Breakout"}]}
    compact.expand(as_lists, tmp_path / "x")
    compact.expand(as_strings, tmp_path / "y")
    for name in ("multiline.json", "comparedgeo.json", "related_0.json"):
        assert (tmp_path / "x/web" / name).read_text(encoding="utf-8") == (tmp_path / "y/web" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", [
    {"series": ["1,x"], "t0": 1, "step": 1},
    {"regions": "only|two"},
    {"related": [{"top": "a|b"}]},
])
def test_compact_rejects_bad_strings(bad, tmp_path):
    from gtrends import compact
    from gtrends.parse import ParseError
    with pytest.raises(ParseError):
        compact.expand(bad, tmp_path)

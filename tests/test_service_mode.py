"""Service mode, intent mix and unreliable regions (added after the first real-world run)."""
import copy
import json
import sys

import pytest
from conftest import FIXTURES, SCRIPTS, make_series
from gtrends import analyze as A
from gtrends import history, parse, report_html, report_md, util
from gtrends.ingest import ingest_raw

sys.path.insert(0, str(SCRIPTS))
import trends_cli


@pytest.fixture()
def product():
    return ingest_raw(FIXTURES / "raw", ["acme widget", "gadget"], ["UA"], "today 5-y", "browser")


@pytest.fixture()
def service(product):
    s = copy.deepcopy(product)
    s["query"]["kind"] = "service"
    return s


# ---- kind -----------------------------------------------------------------------------------------
def test_default_kind_is_product(product):
    assert product["query"]["kind"] == "product"
    assert A.analyze_snapshot(product)["kind"] == "product"


def test_old_snapshots_without_kind_still_validate_as_product(product):
    del product["query"]["kind"]
    parse.validate_snapshot(product)
    assert A.analyze_snapshot(product)["kind"] == "product"


def test_invalid_kind_is_rejected(product):
    product["query"]["kind"] = "gadget"
    with pytest.raises(parse.ParseError):
        parse.validate_snapshot(product)
    with pytest.raises(ValueError):
        parse.new_snapshot(["a"], ["UA"], "today 5-y", "csv", kind="other")


def test_service_and_product_history_do_not_collide(product, service):
    assert history.slug_for(product) != history.slug_for(service)


def test_service_analysis_has_no_shopping_and_no_launch_verdict(service):
    a = A.analyze_snapshot(service)
    t = a["terms"]["acme widget"]
    assert a["kind"] == "service"
    assert t["intent"]["status"] == "not_applicable"
    assert t["verdict"]["label"] == "demand_growing"
    assert t["verdict"]["label"] not in ("go_validate", "test_small", "wait", "avoid")
    assert all("Shopping" not in c["item"] and "launch" not in c["item"].lower() for c in t["checklist"])
    assert t["checklist"][-1]["status"] == "manual"


@pytest.mark.parametrize("shape,label", [
    ("growing", "demand_growing"), ("stable", "demand_stable"), ("declining", "demand_falling"),
    ("seasonal", "demand_seasonal"), ("fad", "demand_spiky"), ("sparse", "inconclusive"),
])
def test_service_labels_follow_the_shape(shape, label):
    d, v = make_series(shape)
    info = A.analyze_series(d, v)
    assert A.service_verdict(info, None, None, 0)["label"] == label


def test_service_report_text(service):
    md = report_md.render(service, A.analyze_snapshot(service))
    assert "Mode: service" in md and "Wording comparison" in md and "Research checklist" in md
    assert "What Trends cannot show here" in md
    assert "Instagram, Telegram" in md
    assert "Prom" not in md and "Buying intent" not in md and "Pre-launch" not in md
    assert "dead-stock" not in md and "green light" not in md


def test_service_html_report(service):
    html_out = report_html.render(service, A.analyze_snapshot(service))
    assert "What Trends cannot show here" in html_out and "Research checklist" in html_out
    assert "demand_growing" in html_out and "<script" not in html_out.lower()


def test_product_report_is_unchanged_in_wording(product):
    md = report_md.render(product, A.analyze_snapshot(product))
    assert "Pre-launch checklist" in md and "Name comparison" in md and "Prom" in md
    assert "What Trends cannot show here" not in md


def test_service_caveats_make_no_channel_claims():
    d, v = make_series("declining")
    caveats = " ".join(A.service_verdict(A.analyze_series(d, v), None, None, 0)["caveats"]).lower()
    assert "not visible" in caveats
    for claim in ("you should", "use instagram", "better to", "switch to"):
        assert claim not in caveats


# ---- intent mix -----------------------------------------------------------------------------------
@pytest.mark.parametrize("query,tag", [
    ("таргетолог це", "define"), ("таргетолог это", "define"), ("кто такой таргетолог", "define"),
    ("хто такий таргетолог", "define"), ("what is a targeting specialist", "define"),
    ("вакансии таргетолог", "career"), ("робота таргетолог", "career"), ("курсы таргетолога", "career"),
    ("таргетолог зарплата", "career"), ("marketing course", "career"),
    ("таргетированная реклама цена", "buy"), ("сколько стоит таргетированная реклама", "buy"),
    ("заказать таргетолога", "buy"), ("hire a marketer", "buy"),
])
def test_new_intent_tags(query, tag):
    assert tag in A.tag_intent(query)


def test_intent_mix_shares():
    related = {
        "top": [
            {"query": "таргетолог это", "value": 100, "breakout": False},
            {"query": "таргетолог це", "value": 100, "breakout": False},
            {"query": "вакансии таргетолог", "value": 50, "breakout": False},
            {"query": "смм", "value": 50, "breakout": False},
        ],
        "rising": [{"query": "хто такий таргетолог", "value": 300, "breakout": False},
                   {"query": "заказать таргетолога", "value": None, "breakout": True}],
    }
    mix = A.intent_mix(related)
    assert mix["total_weight"] == 300
    assert mix["share"]["define"] == 67 and mix["share"]["career"] == 17 and mix["share"]["buy"] == 0
    assert mix["other"] == 17
    assert mix["rising_tags"]["define"] == 1 and mix["rising_tags"]["buy"] == 1


def test_intent_mix_handles_empty_lists():
    mix = A.intent_mix({"top": [], "rising": []})
    assert mix["total_weight"] == 0 and mix["share"]["buy"] == 0


def test_service_reasons_quote_the_mix_only_as_numbers():
    d, v = make_series("stable")
    mix = A.intent_mix({"top": [{"query": "x це", "value": 100, "breakout": False}], "rising": []})
    reasons = A.service_verdict(A.analyze_series(d, v), mix, None, 0)["reasons"]
    assert any("definitions 100%" in r for r in reasons)


# ---- unreliable regions ---------------------------------------------------------------------------
REGIONS = [
    {"code": "UA-40", "name": "Sevastopol' city", "value": 100},
    {"code": "UA-30", "name": "Kyiv city", "value": 85},
    {"code": "UA-43", "name": "Crimea", "value": 57},
    {"code": "UA-51", "name": "Odessa Oblast", "value": 60},
    {"code": "UA-63", "name": "Kharkiv Oblast", "value": 50},
    {"code": "UA-12", "name": "Dnipropetrovsk Oblast", "value": 50},
]


def test_crimea_and_sevastopol_are_left_out_and_values_rescaled():
    out = A.top_regions(REGIONS)
    assert [r["name"] for r in out["top"]][:2] == ["Kyiv city", "Odessa Oblast"]
    assert out["top"][0]["value"] == 100 and out["top"][0]["raw_value"] == 85
    assert out["top"][1]["value"] == round(60 * 100 / 85)
    assert {r["name"] for r in out["excluded"]} == {"Crimea", "Sevastopol' city"}
    assert out["regions_with_data"] == 4
    assert any("left out as unreliable" in n and "Sevastopol" in n for n in out["notes"])
    assert any("rescaled" in n for n in out["notes"])


def test_all_regions_keeps_everything():
    out = A.top_regions(REGIONS, include_unreliable=True)
    assert out["top"][0]["name"] == "Sevastopol' city" and out["top"][0]["value"] == 100
    assert out["excluded"] == [] and out["regions_with_data"] == 6
    assert not any("unreliable" in n for n in out["notes"])


@pytest.mark.parametrize("name", ["Крим", "Крым", "Севастополь", "Autonomous Republic of Crimea", "Sevastopol"])
def test_unreliable_region_names_without_codes(name):
    assert A.is_unreliable_region({"code": "", "name": name, "value": 5})
    assert not A.is_unreliable_region({"code": "", "name": "Lviv Oblast", "value": 5})


def test_no_rescale_when_nothing_is_excluded():
    regions = [{"code": "UA-30", "name": "Kyiv city", "value": 100}, {"code": "UA-46", "name": "Lviv Oblast", "value": 80}]
    out = A.top_regions(regions)
    assert "raw_value" not in out["top"][0] and out["notes"] == ["fewer than 3 regions have data: the market is too small for a geo split"]


def test_region_exclusion_reaches_the_report_and_the_flag_undoes_it(product, tmp_path):
    product["sources"]["web"]["regions"]["acme widget"] = copy.deepcopy(REGIONS)
    assert "Kyiv city (100)" in report_md.render(product, A.analyze_snapshot(product))
    assert "Sevastopol' city (100)" in report_md.render(product, A.analyze_snapshot(product, include_unreliable=True))
    # the raw regions stay in the CSV whatever the ranking says
    from gtrends import report_tables
    report_tables.write_csvs(product, A.analyze_snapshot(product), tmp_path)
    assert "Sevastopol" in (tmp_path / "regions.csv").read_text(encoding="utf-8")


# ---- CLI --------------------------------------------------------------------------------------------
def test_default_sources_depend_on_kind():
    ns = lambda **kw: type("N", (), kw)()  # noqa: E731
    assert trends_cli._sources(ns(sources=None, kind="product")) == ["web", "shopping"]
    assert trends_cli._sources(ns(sources=None, kind="service")) == ["web", "youtube"]
    assert trends_cli._sources(ns(sources=["web"], kind="service")) == ["web"]


def test_cli_service_ingest_and_all_regions_flag(tmp_path, capsys):
    base = ["ingest", "--raw", str(FIXTURES / "raw"), "--terms", "acme widget", "gadget", "--kind", "service", "--formats", "md"]
    assert trends_cli.main(base + ["--out", str(tmp_path / "google-trends-output")]) == 0
    out = capsys.readouterr()
    assert "Mode: service" in out.out
    assert "history" in out.err  # the snapshot path is listed among the written files
    assert trends_cli.main(base + ["--all-regions", "--out", str(tmp_path / "o2")]) == 0


def test_compact_input_is_kept_next_to_the_expanded_files(tmp_path):
    f = tmp_path / "web.compact.json"
    f.write_text(json.dumps({"source": "web", "t0": 1635033600, "step": 604800, "series": ["1,2,3,4,5,6,7,8"]}), encoding="utf-8")
    out = tmp_path / "google-trends-output"
    assert trends_cli.main(["ingest", "--compact", str(f), "--terms", "x", "--kind", "service", "--out", str(out), "--formats", "md"]) == 0
    kept = list(out.rglob("web.compact.json"))
    assert len(kept) == 1 and json.loads(kept[0].read_text(encoding="utf-8"))["series"] == ["1,2,3,4,5,6,7,8"]


def test_default_output_folder_created_by_someone_else_still_gets_gitignore(tmp_path):
    out = tmp_path / util.DEFAULT_OUTPUT_NAME
    (out / "input").mkdir(parents=True)  # e.g. Claude saved a compact file here before the first run
    assert util.prepare_output_dir(out) is True
    assert (out / ".gitignore").read_text(encoding="utf-8").strip().endswith("*")


def test_other_existing_folders_are_still_left_alone(tmp_path):
    out = tmp_path / "my-reports"
    out.mkdir()
    assert util.prepare_output_dir(out) is False and not (out / ".gitignore").exists()

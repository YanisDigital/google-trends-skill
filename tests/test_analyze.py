import pytest
from conftest import make_series
from gtrends import analyze as A


@pytest.mark.parametrize("shape,expected", [
    ("growing", "growing"),
    ("growing_exp", "growing"),
    ("stable", "stable"),
    ("declining", "declining"),
    ("seasonal", "seasonal"),
    ("seasonal_growing", "seasonal"),
    ("fad", "fad"),
    ("sparse", "insufficient_data"),
])
def test_shape_classification(shape, expected):
    dates, vals = make_series(shape)
    res = A.analyze_series(dates, vals)
    assert res["shape"] == expected, res


def test_steady_growth_is_not_seasonal():
    dates, vals = make_series("growing_exp")
    res = A.analyze_series(dates, vals)
    assert res["seasonality"] is not None
    assert not res["seasonality"]["is_seasonal"]


def test_seasonal_peak_month_and_ad_window():
    dates, vals = make_series("seasonal")
    res = A.analyze_series(dates, vals)
    assert res["seasonality"]["peak_month"] in (11, 12, 1)
    timing = res["timing"]
    assert timing["days_to_peak"] > 0
    assert timing["ads_start_from"] < timing["ads_start_until"] < timing["next_peak"]


def test_short_window_is_insufficient():
    dates, vals = make_series("stable", weeks=12)
    res = A.analyze_series(dates, vals)
    assert res["shape"] == "insufficient_data"
    assert any("window" in r for r in res["reasons"])


def test_all_zero_series():
    dates, _ = make_series("stable")
    assert A.analyze_series(dates, [0] * len(dates))["shape"] == "insufficient_data"


def test_compare_flags_swamped_term():
    d, big = make_series("stable")
    per = {"big": A.analyze_series(d, big), "small": A.analyze_series(d, [max(1, v // 40) for v in big])}
    per["small"]["avg_last_12m"] = 1.0
    cmp_ = A.compare_terms(per)
    assert cmp_["recommended"] == "big"
    assert any("swamped" in w for w in cmp_["warnings"])


def test_compare_avoids_fad_as_recommendation():
    d, fad = make_series("fad")
    _, grow = make_series("growing")
    per = {"fad name": A.analyze_series(d, fad), "steady name": A.analyze_series(d, grow)}
    per["fad name"]["avg_last_12m"] = 999.0  # even if it were bigger
    assert A.compare_terms(per)["recommended"] == "steady name"


def test_intent_confirmed_when_shapes_match():
    d, vals = make_series("growing")
    web = A.analyze_series(d, vals)
    shop = A.analyze_series(d, [max(0, v - 3) for v in vals])
    res = A.intent_check(web, shop, (d, vals), (d, [max(0, v - 3) for v in vals]))
    assert res["status"] == "confirmed"


def test_intent_weak_when_shopping_has_no_data():
    d, vals = make_series("growing")
    web = A.analyze_series(d, vals)
    shop = A.analyze_series(d, [0] * len(d))
    assert A.intent_check(web, shop, (d, vals), (d, [0] * len(d)))["status"] == "weak"


def test_intent_not_checked_without_shopping():
    d, vals = make_series("growing")
    assert A.intent_check(A.analyze_series(d, vals), None, (d, vals), None)["status"] == "not_checked"


def test_tag_intent_multilingual():
    assert "choose" in A.tag_intent("як обрати аерогриль")
    assert "compare" in A.tag_intent("аерогриль чи мультипіч")
    assert "review" in A.tag_intent("отзывы аэрогриль")
    assert "buy" in A.tag_intent("air fryer price")
    assert A.tag_intent("air fryer") == []


def test_top_regions_flags_small_market():
    regs = [{"code": "", "name": "A", "value": 100}, {"code": "", "name": "B", "value": 0}]
    out = A.top_regions(regs)
    assert out["regions_with_data"] == 1 and out["notes"]


def test_verdicts():
    grow = {"shape": "growing", "reasons": []}
    assert A.verdict(grow, {"status": "confirmed"}, None, 0)["label"] == "go_validate"
    assert A.verdict(grow, {"status": "weak"}, None, 0)["label"] == "test_small"
    assert A.verdict({"shape": "fad", "reasons": []}, {}, None, 0)["label"] == "avoid"
    assert A.verdict({"shape": "insufficient_data", "reasons": []}, {}, None, 0)["label"] == "inconclusive"
    assert A.verdict({"shape": "stable", "reasons": []}, {}, None, 0)["label"] == "test_small"
    v = A.verdict(grow, {}, None, 0)
    assert any("Keyword Planner" in c for c in v["caveats"])


def test_checklist_statuses():
    prim = {"shape": "growing"}
    cl = A.build_checklist(prim, 3, {"status": "confirmed"}, {"regions_with_data": 5}, 2)
    assert [c["status"] for c in cl] == ["done", "n/a", "done", "done", "done", "done", "manual"]
    bad = A.build_checklist({"shape": "fad"}, 1, {"status": "weak"}, None, 0)
    assert [c["status"] for c in bad][:6] == ["attention", "n/a", "todo", "attention", "todo", "todo"]


def test_compare_prefers_growing_when_levels_are_close():
    d, grow = make_series("growing")
    _, flat = make_series("stable")
    per = {"flat name": A.analyze_series(d, flat), "growing name": A.analyze_series(d, grow)}
    per["flat name"]["avg_last_12m"] = 100.0
    per["growing name"]["avg_last_12m"] = 95.0
    assert A.compare_terms(per)["recommended"] == "growing name"
    per["growing name"]["avg_last_12m"] = 60.0
    assert A.compare_terms(per)["recommended"] == "flat name"

"""Deterministic analysis of a snapshot: curve shape, seasonality, regions, intent, verdict.

All thresholds are named constants so they are easy to audit and tune. Everything works on
monthly means, so weekly (<=5y) and monthly (>5y) Trends data are handled the same way.
"""
from __future__ import annotations

import math
import re
from datetime import date, timedelta
from statistics import mean, median

# --- thresholds -------------------------------------------------------------
MIN_MONTHS_SHAPE = 6          # below this the window is too short to call a shape
MIN_MONTHS_SEASON = 30        # about 2.5 cycles are needed for a seasonal index
MAX_ZERO_SHARE = 0.40         # more zeros than this = "not enough data"
SEASON_MIN_INDEX = 1.35       # smoothed seasonal peak must be 35% above trend
SEASON_MIN_CONSISTENCY = 0.6  # share of cycles whose peak window is above trend
FAD_PEAK_VS_MEDIAN = 2.5
FAD_RECENT_VS_PEAK = 0.30
GROWTH_VS_FIRST = 1.25
GROWTH_VS_PREV = 1.05
DECLINE_VS_FIRST = 0.75
DECLINE_VS_PREV = 0.95
SWAMPED_SHARE = 0.08          # a term below 8% of the leader is "swamped"
AD_LEAD_DAYS = (42, 21)       # start ads 3-6 weeks before the peak (guide, task 2)
MOMENTUM_STALL = 0.8          # last 3 months vs the previous 3: at or below this is a warning
INTENT_CORR_OK = 0.6
INTENT_CORR_WEAK = 0.3

SHAPES = ("growing", "stable", "fad", "seasonal", "declining", "insufficient_data")


# --- helpers ----------------------------------------------------------------
def monthly(dates: list[str], values: list[int]) -> list[tuple[int, int, float]]:
    """Aggregate points to calendar-month means: [(year, month, mean), ...] in order."""
    buckets: dict[tuple[int, int], list[int]] = {}
    for d, v in zip(dates, values):
        buckets.setdefault((int(d[:4]), int(d[5:7])), []).append(v)
    return [(y, m, mean(vs)) for (y, m), vs in sorted(buckets.items())]


def _circ(a: int, b: int) -> int:
    """Circular distance between two calendar months (1..12)."""
    d = abs(a - b) % 12
    return min(d, 12 - d)


def _centered_ma12(vals: list[float]) -> list[float | None]:
    """2x12 centered moving average; None where the window does not fit."""
    n, out = len(vals), [None] * len(vals)
    for i in range(6, n - 6):
        window = vals[i - 6:i + 7]
        out[i] = (window[0] / 2 + sum(window[1:-1]) + window[-1] / 2) / 12
    return out


def _month_add(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


# --- seasonality ------------------------------------------------------------
def seasonality(months: list[tuple[int, int, float]]) -> dict | None:
    """Classical decomposition: ratio to the 12-month trend, averaged per calendar month."""
    if len(months) < MIN_MONTHS_SEASON:
        return None
    vals = [m[2] for m in months]
    ma = _centered_ma12(vals)
    ratios: list[tuple[int, int, float]] = []  # (year, month, ratio)
    for (y, m, v), t in zip(months, ma):
        if t and t > 0:
            ratios.append((y, m, v / t))
    if len(ratios) < 18:
        return None
    per_month = {m: [r for (_, mm, r) in ratios if mm == m] for m in range(1, 13)}
    index = {m: (mean(rs) if rs else 1.0) for m, rs in per_month.items()}
    smooth = {m: mean(index[((m + k - 1) % 12) + 1] for k in (-1, 0, 1)) for m in range(1, 13)}
    peak_month = max(smooth, key=lambda m: smooth[m])
    strength = smooth[peak_month]

    # consistency: per cycle (keyed by the peak-month it belongs to), is the window above trend?
    cycles: dict[int, list[tuple[int, float]]] = {}
    for y, m, r in ratios:
        d = ((m - peak_month + 6) % 12) - 6          # signed offset -6..5
        if abs(d) <= 4:
            py, pm = _month_add(y, m, -d)
            cycles.setdefault(py * 12 + pm, []).append((d, r))
    full = {k: v for k, v in cycles.items() if any(d == 0 for d, _ in v) and len(v) >= 6}
    above = [k for k, v in full.items() if mean(r for d, r in v if abs(d) <= 1) >= 1.2]
    consistency = (len(above) / len(full)) if full else 0.0
    out = {
        "peak_month": peak_month,
        "strength": round(strength, 2),
        "consistency": round(consistency, 2),
        "cycles": len(full),
        "is_seasonal": bool(strength >= SEASON_MIN_INDEX and consistency >= SEASON_MIN_CONSISTENCY and len(full) >= 2),
        "index": {m: round(v, 2) for m, v in smooth.items()},
    }
    out["rise_start_month"] = _walk_back_start(smooth, peak_month)
    out["rise_shift_months"] = _rise_shift(full) if out["is_seasonal"] else None
    return out


def _walk_back_start(smooth: dict[int, float], peak: int) -> int:
    """First calendar month (walking back from the peak) where the seasonal index is above trend."""
    m = peak
    for _ in range(6):
        prev = ((m - 2) % 12) + 1
        if smooth[prev] >= 1.0:
            m = prev
        else:
            break
    return m


def _rise_shift(full: dict[int, list[tuple[int, float]]]) -> int | None:
    """How many months earlier (-) / later (+) the rise began in the latest cycle vs the previous one."""
    keys = sorted(full)
    if len(keys) < 2:
        return None

    def rise_offset(cycle: list[tuple[int, float]]) -> int:
        by_d = dict(cycle)
        d = 0
        while d - 1 in by_d and by_d[d - 1] >= 1.2:
            d -= 1
        return d

    return rise_offset(full[keys[-1]]) - rise_offset(full[keys[-2]])


def next_peak_window(dates: list[str], values: list[int], peak_month: int) -> dict | None:
    """Estimate the next peak date from the latest cycle and the ad-start window before it."""
    if not dates:
        return None
    last = date.fromisoformat(dates[-1])
    cutoff = date.fromisoformat(dates[max(0, len(dates) - 1 - 400)])
    best = None
    for d, v in zip(dates, values):
        dd = date.fromisoformat(d)
        if dd >= cutoff and _circ(dd.month, peak_month) <= 1 and (best is None or v > best[1]):
            best = (dd, v)
    if best is None:
        return None
    peak = best[0]
    while peak <= last:
        peak += timedelta(days=364)
    lead_far, lead_near = AD_LEAD_DAYS
    return {
        "next_peak": peak.isoformat(),
        "ads_start_from": (peak - timedelta(days=lead_far)).isoformat(),
        "ads_start_until": (peak - timedelta(days=lead_near)).isoformat(),
        "days_to_peak": (peak - last).days,
    }


# --- shape ------------------------------------------------------------------
def analyze_series(dates: list[str], values: list[int]) -> dict:
    """Classify one series. Returns shape + the metrics behind the decision."""
    n = len(values)
    months = monthly(dates, values)
    res: dict = {"points": n, "months": len(months), "shape": "insufficient_data", "reasons": []}
    if n == 0 or max(values, default=0) == 0:
        res["reasons"].append("no data (all zeros)")
        return res
    zero_share = sum(1 for v in values if v == 0) / n
    res["zero_share"] = round(zero_share, 2)
    if zero_share > MAX_ZERO_SHARE:
        res["reasons"].append(f"{round(zero_share * 100)}% of points are zero: the query is too small for Trends")
        return res
    if len(months) < MIN_MONTHS_SHAPE:
        res["reasons"].append(f"window is only {len(months)} months; use at least 5 years for a shape call")
        return res

    mv = [m[2] for m in months]
    res["avg_last_12m"] = round(mean(mv[-12:]), 1)
    res["avg_all"] = round(mean(mv), 1)
    res["momentum_3m"] = round(mean(mv[-3:]) / max(mean(mv[-6:-3]), 1e-9), 2) if len(mv) >= 6 else None
    prev12 = mean(mv[-24:-12]) if len(mv) >= 24 else None
    res["yoy_ratio"] = round(mean(mv[-12:]) / prev12, 2) if prev12 else None

    seas = seasonality(months)
    res["seasonality"] = seas
    if seas is None and len(months) < MIN_MONTHS_SEASON:
        res["reasons"].append("seasonality not testable: needs about 2.5+ years of data")

    # 1) seasonal
    if seas and seas["is_seasonal"]:
        res["shape"] = "seasonal"
        res["reasons"].append(
            f"peaks recur around month {seas['peak_month']} ({seas['strength']}x trend in {seas['cycles']} cycles)"
        )
        res["timing"] = next_peak_window(dates, values, seas["peak_month"])
        return res

    # 2) fad: one spike far above the norm, already gone
    sm = [mean(mv[max(0, i - 1):i + 2]) for i in range(len(mv))]
    ip = max(range(len(sm)), key=lambda i: sm[i])
    peak, med = sm[ip], median(mv)
    recent = mean(mv[-3:])
    if (med > 0 and peak >= FAD_PEAK_VS_MEDIAN * med and ip <= len(mv) - 7 and recent <= FAD_RECENT_VS_PEAK * peak):
        res["shape"] = "fad"
        res["reasons"].append("one sharp peak followed by a collapse: high risk of dead stock")
        res["peak_month_index"] = ip
        return res

    # 3) growth / decline / stable
    first = mean(mv[:12]) if len(mv) >= 24 else mean(mv[: max(3, len(mv) // 3)])
    last = mean(mv[-12:]) if len(mv) >= 24 else mean(mv[-max(3, len(mv) // 3):])
    vs_first = last / first if first else math.inf
    vs_prev = (last / prev12) if prev12 else vs_first
    res["last_vs_first"] = round(vs_first, 2) if math.isfinite(vs_first) else None
    if vs_first >= GROWTH_VS_FIRST and vs_prev >= GROWTH_VS_PREV:
        res["shape"] = "growing"
        res["reasons"].append(f"last-12-month level is {round(vs_first, 2)}x the start of the window")
    elif vs_first <= DECLINE_VS_FIRST and vs_prev <= DECLINE_VS_PREV:
        res["shape"] = "declining"
        res["reasons"].append(f"last-12-month level is only {round(vs_first, 2)}x the start of the window")
    else:
        res["shape"] = "stable"
        res["reasons"].append("flat demand: price and service decide, not momentum")
    return res


# --- regions, related, compare ---------------------------------------------
def top_regions(regions: list[dict], n: int = 5) -> dict:
    with_data = [r for r in regions if r["value"] > 0]
    out = {"top": with_data[:n], "regions_with_data": len(with_data), "notes": []}
    if len(with_data) < 3:
        out["notes"].append("fewer than 3 regions have data: the market is too small for a geo split")
    return out


_INTENT_PATTERNS = {
    "choose": r"\b(how to choose|which|best|top)\b|як обрати|як вибрати|який |кращ|найкращ|как выбрать|какой |лучш",
    "compare": r"\b(vs|versus|or|alternative)\b| чи | или |порівнян|сравнен",
    "review": r"\b(review|reviews|unboxing|worth it)\b|відгук|огляд|распаков|отзыв|обзор",
    "buy": r"\b(buy|price|cost|cheap|sale|near me)\b|купити|ціна|де купити|купить|цена|где купить",
}


def tag_intent(query: str) -> list[str]:
    q = query.lower()
    return [tag for tag, pat in _INTENT_PATTERNS.items() if re.search(pat, q)]


def summarize_related(related: dict, limit: int = 10) -> dict:
    rising = related.get("rising", [])
    top = related.get("top", [])
    return {
        "rising": [dict(r, intent=tag_intent(r["query"])) for r in rising[:limit]],
        "top": [dict(r, intent=tag_intent(r["query"])) for r in top[:limit]],
        "breakout_count": sum(1 for r in rising if r.get("breakout")),
    }


def compare_terms(per_term: dict[str, dict]) -> dict:
    """Rank terms by their last-12-month level; flag swamped terms and fads."""
    levels = {t: a.get("avg_last_12m") for t, a in per_term.items() if a.get("avg_last_12m") is not None}
    out: dict = {"ranking": [], "recommended": None, "warnings": []}
    if not levels:
        return out
    leader_level = max(levels.values())
    for t, lvl in sorted(levels.items(), key=lambda kv: -kv[1]):
        out["ranking"].append({"term": t, "avg_last_12m": lvl, "shape": per_term[t]["shape"],
                               "share_of_leader": round(lvl / leader_level, 2) if leader_level else 0})
    healthy = [r for r in out["ranking"] if r["shape"] in ("growing", "stable", "seasonal")]
    # near-equal levels: prefer the name that is still growing
    pick = max(healthy or out["ranking"], key=lambda r: r["avg_last_12m"] * (1.1 if r["shape"] == "growing" else 1.0))
    out["recommended"] = pick["term"]
    if not healthy:
        out["warnings"].append("no term shows a healthy shape; the recommendation is only the largest one")
    if len(levels) > 1:
        for r in out["ranking"][1:]:
            if r["share_of_leader"] <= SWAMPED_SHARE:
                out["warnings"].append(
                    f"'{r['term']}' is swamped by the leader (<= {int(SWAMPED_SHARE * 100)}%): "
                    "compare it against a mid-sized anchor term or on its own chart"
                )
    return out


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 6 or len(a) != len(b):
        return None
    ma, mb = mean(a), mean(b)
    da = sum((x - ma) ** 2 for x in a)
    db = sum((y - mb) ** 2 for y in b)
    if da == 0 or db == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(da * db)


def intent_check(web: dict, shopping: dict | None, web_series: tuple[list, list],
                 shop_series: tuple[list, list] | None) -> dict:
    """Does Google Shopping confirm the web trend? (guide, task 7 / step 4)"""
    if shopping is None or shop_series is None:
        return {"status": "not_checked", "note": "Google Shopping source was not collected"}
    if shopping["shape"] == "insufficient_data":
        return {"status": "weak", "note": "little or no Shopping data: purchase intent looks weak"}
    wm = {(y, m): v for y, m, v in monthly(*web_series)}
    sm = {(y, m): v for y, m, v in monthly(*shop_series)}
    keys = sorted(set(wm) & set(sm))
    corr = _pearson([wm[k] for k in keys], [sm[k] for k in keys])
    corr_r = None if corr is None else round(corr, 2)
    same_shape = web["shape"] == shopping["shape"]
    if (corr is not None and corr >= INTENT_CORR_OK) or same_shape:
        return {"status": "confirmed", "correlation": corr_r, "note": "Shopping follows the web trend: buying intent is real"}
    if corr is not None and corr < INTENT_CORR_WEAK:
        return {"status": "weak", "correlation": corr_r, "note": "Shopping does not follow the web trend: people may only be reading"}
    return {"status": "unclear", "correlation": corr_r, "note": "partial overlap; check the two charts by eye"}


# --- verdict ------------------------------------------------------------------
def verdict(shape_info: dict, intent: dict, regions: dict | None, rising_count: int) -> dict:
    shape = shape_info["shape"]
    reasons = list(shape_info.get("reasons", []))
    caveats = [
        "Trends shows relative interest (0-100), not search volume: confirm volumes in Keyword Planner.",
        "Rising interest does not guarantee margin: check competition in Meta Ad Library / TikTok Creative Center and prices on marketplaces.",
    ]
    if shape == "insufficient_data":
        label = "inconclusive"
    elif shape == "fad":
        label = "avoid"
        caveats.append("If you still want to try it, test with no inventory (pre-orders / dropshipping).")
    elif shape == "declining":
        label = "avoid"
    elif shape == "seasonal":
        timing = shape_info.get("timing") or {}
        days = timing.get("days_to_peak")
        if days is not None and days > 300:
            label = "wait"
            reasons.append("the peak just passed: prepare for next season")
        elif days is not None and days <= 21:
            label = "test_small"
            reasons.append("the peak is very close: too late for a long ad ramp-up")
        else:
            label = "go_validate"
    elif shape == "growing":
        label = "go_validate"
    else:  # stable
        label = "test_small"
    momentum = shape_info.get("momentum_3m")
    if shape == "growing" and momentum is not None and momentum <= MOMENTUM_STALL:
        reasons.append(f"watch: the last 3 months are {round((1 - momentum) * 100)}% below the 3 months before; check whether the rise is stalling")
    if intent.get("status") == "weak" and label == "go_validate":
        label = "test_small"
        reasons.append("Google Shopping does not confirm buying intent")
    if intent.get("status") == "confirmed":
        reasons.append("Google Shopping confirms buying intent")
    if regions and regions.get("regions_with_data", 0) >= 3:
        reasons.append("top regions: " + ", ".join(r["name"] for r in regions["top"][:3]))
    if rising_count:
        reasons.append(f"{rising_count} rising related queries to use as hooks/keywords")
    return {"label": label, "reasons": reasons, "caveats": caveats}


def build_checklist(primary: dict, terms_count: int, intent: dict, regions: dict | None, rising_count: int) -> list[dict]:
    """The guide's pre-launch checklist; the last item always needs a human."""
    shape = primary["shape"]
    timing = primary.get("timing")
    return [
        {"item": "Checked the 5-year trend: not a fad and not declining",
         "status": "done" if shape not in ("fad", "declining", "insufficient_data") else "attention"},
        {"item": "Determined the season and the ad start date",
         "status": "done" if timing else ("n/a" if shape != "seasonal" else "attention")},
        {"item": "Compared 2-4 product names and picked the main one",
         "status": "done" if terms_count >= 2 else "todo"},
        {"item": "Checked the Google Shopping source",
         "status": {"confirmed": "done", "weak": "attention", "unclear": "attention"}.get(intent.get("status"), "todo")},
        {"item": "Listed top regions for geo-targeting",
         "status": "done" if regions and regions.get("regions_with_data", 0) >= 3 else "todo"},
        {"item": "Collected rising queries for creatives and the product page",
         "status": "done" if rising_count else "todo"},
        {"item": "Confirmed volumes in Keyword Planner and competition in Meta Ad Library", "status": "manual"},
    ]


# --- entry point ----------------------------------------------------------------
def analyze_snapshot(snap: dict) -> dict:
    web = snap["sources"].get("web", {})
    shop = snap["sources"].get("shopping", {})
    wtl, stl = web.get("timeline"), shop.get("timeline")
    result: dict = {"terms": {}, "warnings": []}
    if not wtl:
        result["warnings"].append("no web timeline in the snapshot")
        return result

    per_term = {lab: analyze_series(wtl["dates"], vals) for lab, vals in wtl["series"].items()}
    shop_term = {lab: analyze_series(stl["dates"], vals) for lab, vals in stl["series"].items()} if stl else {}
    comparison = compare_terms(per_term)
    result["comparison"] = comparison

    for lab, info in per_term.items():
        intent = intent_check(
            info, shop_term.get(lab),
            (wtl["dates"], wtl["series"][lab]),
            (stl["dates"], stl["series"][lab]) if stl and lab in stl["series"] else None,
        )
        reg = top_regions(web["regions"][lab]) if lab in web.get("regions", {}) else None
        rel = summarize_related(web["related"][lab]) if lab in web.get("related", {}) else None
        rising_count = len(rel["rising"]) if rel else 0
        result["terms"][lab] = {
            "web": info,
            "shopping": shop_term.get(lab),
            "intent": intent,
            "regions": reg,
            "related": rel,
            "verdict": verdict(info, intent, reg, rising_count),
            "checklist": build_checklist(info, len(per_term), intent, reg, rising_count),
        }
    result["primary"] = comparison.get("recommended") or next(iter(per_term), None)
    # related queries from extra sources (YouTube, Images, News) - used for content ideas
    extra = {}
    for src, node in snap["sources"].items():
        if src in ("web", "shopping") or not node.get("related"):
            continue
        extra[src] = {lab: summarize_related(rel) for lab, rel in node["related"].items()}
    if extra:
        result["extra_sources"] = extra
    return result

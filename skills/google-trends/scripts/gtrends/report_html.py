"""Self-contained HTML report: inline CSS and inline SVG charts, no scripts, no network.

A strict Content-Security-Policy meta blocks any outbound request even if untrusted Trends text
slipped through; every dynamic string is HTML-escaped anyway.
"""
from __future__ import annotations

from html import escape

from .analyze import monthly
from .texts import (
    CHECK_MARK,
    INTENT_TEXT,
    NEXT_STEPS,
    PITFALLS,
    SERVICE_LIMITS,
    VERDICT_TEXT,
    geo_label,
    marketplaces_for,
    month_name,
    shape_text,
)

PALETTE = ["#2563eb", "#d97706", "#059669", "#9333ea", "#dc2626"]

CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#57534e;--card:#fff;--line:#e7e5e4;--ok:#047857;--warn:#b45309;--bad:#b91c1c}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1c1917;--fg:#fafaf9;--muted:#a8a29e;--card:#292524;--line:#44403c;--ok:#34d399;--warn:#fbbf24;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.15rem;margin:28px 0 8px}
.meta{color:var(--muted);font-size:.9rem}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;border:1px solid currentColor;font-weight:600;font-size:.9rem}
.go_validate,.demand_growing{color:var(--ok)}.test_small,.wait,.inconclusive,.demand_stable,.demand_seasonal{color:var(--warn)}.avoid,.demand_falling,.demand_spiky{color:var(--bad)}
table{border-collapse:collapse;width:100%;font-size:.95rem}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
svg{width:100%;height:auto;display:block}.axis{stroke:var(--line)}.lbl{fill:var(--muted);font-size:11px}
.legend span{display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:.9rem}.legend i{width:12px;height:3px;display:inline-block}
ul{padding-left:20px}a{color:inherit}
"""


def _chart(snap_tl: dict, labels: list[str]) -> str:
    w, h, pl, pb = 760, 240, 34, 22
    series = {lab: monthly(snap_tl["dates"], snap_tl["series"][lab]) for lab in labels if lab in snap_tl["series"]}
    if not series:
        return ""
    n = max(len(s) for s in series.values())
    if n < 2:
        return ""
    x = lambda i: pl + (w - pl - 8) * i / (n - 1)          # noqa: E731
    y = lambda v: 8 + (h - 8 - pb) * (1 - v / 100)         # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Interest over time, monthly averages">']
    for g in (0, 50, 100):
        parts.append(f'<line class="axis" x1="{pl}" x2="{w - 8}" y1="{y(g):.1f}" y2="{y(g):.1f}"/>'
                     f'<text class="lbl" x="2" y="{y(g) + 4:.1f}">{g}</text>')
    first = next(iter(series.values()))
    for i, (yr, mo, _) in enumerate(first):
        if mo == 1:
            parts.append(f'<text class="lbl" x="{x(i):.1f}" y="{h - 6}">{yr}</text>')
    for k, (lab, s) in enumerate(series.items()):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, _, v) in enumerate(s))
        parts.append(f'<polyline fill="none" stroke="{PALETTE[k % len(PALETTE)]}" stroke-width="2" points="{pts}">'
                     f"<title>{escape(lab)}</title></polyline>")
    parts.append("</svg>")
    legend = "".join(f'<span><i style="background:{PALETTE[k % len(PALETTE)]}"></i>{escape(lab)}</span>'
                     for k, lab in enumerate(series))
    return "".join(parts) + f'<div class="legend">{legend}</div>'


def _rising_item(r: dict) -> str:
    growth = "breakout" if r["breakout"] else (f"+{r['value']}%" if r["value"] is not None else "")
    tags = " · " + "/".join(r["intent"]) if r["intent"] else ""
    return f'<li>{escape(r["query"])} <span class="meta">{escape(growth + tags)}</span></li>'


def render(snap: dict, analysis: dict) -> str:
    q, terms = snap["query"], analysis["terms"]
    kind = analysis.get("kind", "product")
    e = escape
    out = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:\">",
        f"<title>Trends check: {e(', '.join(q['terms']))}</title><style>{CSS}</style></head><body><main>",
        f"<h1>Google Trends check: {e(', '.join(q['terms']))}</h1>",
        f"<p class=\"meta\">Geo: {e(geo_label(snap))} · Period: {e(q['date'])} · Collected: {e(snap['created'])} · Data via: {e(snap['origin'])}</p>",
    ]
    primary = analysis.get("primary")
    if primary in terms:
        v = terms[primary]["verdict"]
        out.append(f"<section class=\"card\"><span class=\"badge {e(v['label'])}\">{e(VERDICT_TEXT[v['label']])}</span>"
                   f"<p class=\"meta\">for “{e(primary)}”</p><ul>" + "".join(f"<li>{e(r)}</li>" for r in v["reasons"]) + "</ul></section>")

    web_tl = snap["sources"]["web"].get("timeline")
    if web_tl:
        out.append(f"<h2>Interest over time (web)</h2><div class=\"card\">{_chart(web_tl, list(web_tl['series']))}</div>")
    shop_tl = snap["sources"].get("shopping", {}).get("timeline")
    if shop_tl:
        out.append(f"<h2>Interest over time (Google Shopping)</h2><div class=\"card\">{_chart(shop_tl, list(shop_tl['series']))}</div>")

    comp = analysis.get("comparison", {})
    if len(terms) > 1 and comp.get("ranking"):
        rows = "".join(f"<tr><td>{e(r['term'])}</td><td>{e(r['shape'])}</td><td>{r['avg_last_12m']}</td>"
                       f"<td>{int(r['share_of_leader'] * 100)}%</td></tr>" for r in comp["ranking"])
        out.append(f"<h2>{'Wording' if kind == 'service' else 'Name'} comparison</h2><div class=\"card\"><table><tr><th>Term</th><th>Shape</th><th>Level (12m)</th>"
                   f"<th>Share of leader</th></tr>{rows}</table>"
                   + "".join(f"<p class=\"meta\">⚠ {e(w)}</p>" for w in comp.get("warnings", [])) + "</div>")

    for lab, t in terms.items():
        web = t["web"]
        out.append(f"<h2>{e(lab)}</h2><div class=\"card\"><p><strong>{e(shape_text(web['shape'], kind))}</strong></p>")
        if web.get("yoy_ratio") is not None:
            out.append(f"<p>Year over year: ×{web['yoy_ratio']}</p>")
        seas, tm = web.get("seasonality"), web.get("timing")
        if seas and seas["is_seasonal"]:
            out.append(f"<p>Peak around {e(month_name(seas['peak_month']))}; rise starts around {e(month_name(seas['rise_start_month']))}.</p>")
            if tm:
                out.append(f"<p>Next peak (estimate) {e(tm['next_peak'])}; start ads between {e(tm['ads_start_from'])} and {e(tm['ads_start_until'])}.</p>")
        if t["intent"]["status"] not in ("not_checked", "not_applicable"):
            out.append(f"<p>Buying intent: {e(INTENT_TEXT[t['intent']['status']])}</p>")
        mix = t.get("intent_mix")
        if mix and mix["total_weight"]:
            s = mix["share"]
            out.append(f"<p>Related queries by intent (share of top-query weight): definitions {s['define']}%, career/learning "
                       f"{s['career']}%, buying words {s['buy']}%, choose {s['choose']}%, compare {s['compare']}%, "
                       f"reviews {s['review']}%, no tag {mix['other']}%</p>")
        reg = t.get("regions")
        if reg:
            out.append("<p>Top regions: " + e(", ".join(f"{r['name']} ({r['value']})" for r in reg["top"]) or "none") + "</p>")
            out.extend(f"<p class=\"meta\">{e(n)}</p>" for n in reg["notes"])
        rel = t.get("related")
        if rel and rel["rising"]:
            items = "".join(_rising_item(r) for r in rel["rising"][:8])
            out.append(f"<p>Rising queries:</p><ul>{items}</ul>")
        out.append("</div>")

    if primary in terms:
        out.append(f"<h2>{'Research' if kind == 'service' else 'Pre-launch'} checklist</h2><div class=\"card\"><ul>" + "".join(
            f"<li>{e(CHECK_MARK[c['status']])} {e(c['item'])}</li>" for c in terms[primary]["checklist"]) + "</ul></div>")
    links = "".join(f"<li>{e(what)}: <a href=\"{e(url)}\" rel=\"noopener noreferrer\">{e(name)}</a></li>" for what, name, url in NEXT_STEPS)
    links += "".join(f"<li>Prices: <a href=\"{e(u)}\" rel=\"noopener noreferrer\">{e(n)}</a></li>" for n, u in marketplaces_for(snap))
    out.append(f"<h2>Confirm with other sources</h2><div class=\"card\"><ul>{links}</ul></div>")
    if kind == "service":
        out.append("<h2>What Trends cannot show here</h2><div class=\"card\"><ul>"
                   + "".join(f"<li>{e(s)}</li>" for s in SERVICE_LIMITS) + "</ul></div>")
    caveats = (terms[primary]["verdict"]["caveats"] if primary in terms else []) + PITFALLS
    out.append("<h2>Caveats</h2><div class=\"card\"><ul>" + "".join(f"<li>{e(c)}</li>" for c in caveats) + "</ul></div>")
    out.append("</main></body></html>")
    return "".join(out)

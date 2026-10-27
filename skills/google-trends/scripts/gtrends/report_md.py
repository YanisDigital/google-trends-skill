"""Markdown report (printed in chat and saved as report.md)."""
from __future__ import annotations

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
from .util import md_escape as _md


def render(snap: dict, analysis: dict) -> str:
    q = snap["query"]
    terms = analysis["terms"]
    kind = analysis.get("kind", "product")
    lines = [
        f"# Google Trends check: {_md(', '.join(q['terms']))}",
        "",
        f"Geo: {_md(geo_label(snap))} | Period: {_md(q['date'])} | Collected: {snap['created']} | Data via: {snap['origin']}"
        + (" | Mode: service" if kind == "service" else ""),
        "",
    ]
    primary = analysis.get("primary")
    if primary and primary in terms:
        v = terms[primary]["verdict"]
        lines += [f"## Verdict for \"{_md(primary)}\": {VERDICT_TEXT[v['label']]}", ""]
        lines += [f"- {_md(r)}" for r in v["reasons"]]
        lines.append("")

    comp = analysis.get("comparison", {})
    if len(terms) > 1 and comp.get("ranking"):
        lines += [
            f"## {'Wording' if kind == 'service' else 'Name'} comparison",
            "",
            "| Term | Shape | Level (last 12m) | Share of leader |",
            "|---|---|---|---|",
        ]
        for r in comp["ranking"]:
            lines.append(f"| {_md(r['term'])} | {r['shape']} | {r['avg_last_12m']} | {int(r['share_of_leader'] * 100)}% |")
        lines.append("")
        lines += [f"- Warning: {_md(w)}" for w in comp.get("warnings", [])]
        if comp.get("warnings"):
            lines.append("")

    for lab, t in terms.items():
        web = t["web"]
        lines += [f"## {_md(lab)}", "", f"**Shape:** {shape_text(web['shape'], kind)}"]
        if web.get("yoy_ratio") is not None:
            lines.append(f"**Year over year (last 12m vs previous 12m):** x{web['yoy_ratio']}")
        seas = web.get("seasonality")
        if seas and seas["is_seasonal"]:
            lines.append(f"**Season:** peak around {month_name(seas['peak_month'])}, "
                         f"rise starts around {month_name(seas['rise_start_month'])}")
            tm = web.get("timing")
            if tm:
                what = "prepare between" if kind == "service" else "start ads between"
                lines.append(f"**Next peak (estimate):** {tm['next_peak']}; {what} "
                             f"{tm['ads_start_from']} and {tm['ads_start_until']}")
            shift = seas.get("rise_shift_months")
            if shift:
                direction = "earlier" if shift < 0 else "later"
                lines.append(f"**Watch:** the rise began {abs(shift)} month(s) {direction} than the previous season")
        elif seas is None:
            lines.append("**Season:** not testable (needs about 2.5+ years of data)")
        if t["intent"]["status"] not in ("not_checked", "not_applicable"):
            lines.append(f"**Buying intent:** {INTENT_TEXT[t['intent']['status']]}")
        mix = t.get("intent_mix")
        if mix and mix["total_weight"]:
            s = mix["share"]
            lines.append(f"**Related queries by intent (share of top-query weight):** definitions {s['define']}%, "
                         f"career/learning {s['career']}%, buying words {s['buy']}%, choose {s['choose']}%, "
                         f"compare {s['compare']}%, reviews {s['review']}%, no tag {mix['other']}%")
        reg = t.get("regions")
        if reg:
            top = ", ".join(f"{_md(r['name'])} ({r['value']})" for r in reg["top"])
            lines.append(f"**Top regions:** {top or 'none'}")
            lines += [f"- {_md(n)}" for n in reg["notes"]]
        rel = t.get("related")
        if rel and rel["rising"]:
            items = []
            for r in rel["rising"][:8]:
                tag = f" [{'/'.join(r['intent'])}]" if r["intent"] else ""
                val = "breakout" if r["breakout"] else (f"+{r['value']}%" if r["value"] is not None else "")
                items.append(f"{_md(r['query'])} ({val}){tag}" if val else f"{_md(r['query'])}{tag}")
            lines.append("**Rising queries:** " + "; ".join(items))
        lines.append("")

    for src, per_term in analysis.get("extra_sources", {}).items():
        lines += [f"## Rising queries on {src}", ""]
        for lab, rel in per_term.items():
            items = [f"{_md(r['query'])}" + (f" [{'/'.join(r['intent'])}]" if r["intent"] else "") for r in rel["rising"][:8]]
            lines.append(f"- {_md(lab)}: " + ("; ".join(items) or "none"))
        lines.append("")

    if primary and primary in terms:
        lines += [f"## {'Research' if kind == 'service' else 'Pre-launch'} checklist", ""]
        lines += [f"- {CHECK_MARK[c['status']]} {c['item']}" for c in terms[primary]["checklist"]]
        lines.append("")

    lines += ["## Confirm with other sources", ""]
    lines += [f"- {what}: [{name}]({url})" for what, name, url in NEXT_STEPS]
    mk = marketplaces_for(snap)
    if mk:
        lines.append("- Prices: " + ", ".join(f"[{n}]({u})" for n, u in mk))
    if kind == "service":
        lines += ["", "## What Trends cannot show here", ""] + [f"- {s}" for s in SERVICE_LIMITS]
    lines += ["", "## Caveats", ""]
    if primary and primary in terms:
        lines += [f"- {c}" for c in terms[primary]["verdict"]["caveats"]]
    lines += [f"- {p}" for p in PITFALLS]
    lines.append("")
    return "\n".join(lines)

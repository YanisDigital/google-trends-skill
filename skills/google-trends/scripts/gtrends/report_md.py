"""Markdown report (printed in chat and saved as report.md)."""
from __future__ import annotations

from .texts import (
    CHECK_MARK,
    INTENT_TEXT,
    NEXT_STEPS,
    PITFALLS,
    SHAPE_TEXT,
    VERDICT_TEXT,
    geo_label,
    marketplaces_for,
    month_name,
)
from .util import md_escape as _md


def render(snap: dict, analysis: dict) -> str:
    q = snap["query"]
    terms = analysis["terms"]
    lines = [
        f"# Google Trends check: {_md(', '.join(q['terms']))}",
        "",
        f"Geo: {_md(geo_label(snap))} | Period: {_md(q['date'])} | Collected: {snap['created']} | Data via: {snap['origin']}",
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
        lines += ["## Name comparison", "", "| Term | Shape | Level (last 12m) | Share of leader |", "|---|---|---|---|"]
        for r in comp["ranking"]:
            lines.append(f"| {_md(r['term'])} | {r['shape']} | {r['avg_last_12m']} | {int(r['share_of_leader'] * 100)}% |")
        lines.append("")
        lines += [f"- Warning: {_md(w)}" for w in comp.get("warnings", [])]
        if comp.get("warnings"):
            lines.append("")

    for lab, t in terms.items():
        web = t["web"]
        lines += [f"## {_md(lab)}", "", f"**Shape:** {SHAPE_TEXT[web['shape']]}"]
        if web.get("yoy_ratio") is not None:
            lines.append(f"**Year over year (last 12m vs previous 12m):** x{web['yoy_ratio']}")
        seas = web.get("seasonality")
        if seas and seas["is_seasonal"]:
            lines.append(f"**Season:** peak around {month_name(seas['peak_month'])}, "
                         f"rise starts around {month_name(seas['rise_start_month'])}")
            tm = web.get("timing")
            if tm:
                lines.append(f"**Next peak (estimate):** {tm['next_peak']}; start ads between "
                             f"{tm['ads_start_from']} and {tm['ads_start_until']}")
            shift = seas.get("rise_shift_months")
            if shift:
                direction = "earlier" if shift < 0 else "later"
                lines.append(f"**Watch:** the rise began {abs(shift)} month(s) {direction} than the previous season")
        elif seas is None:
            lines.append("**Season:** not testable (needs about 2.5+ years of data)")
        if t["intent"]["status"] != "not_checked":
            lines.append(f"**Buying intent:** {INTENT_TEXT[t['intent']['status']]}")
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
        lines += ["## Pre-launch checklist", ""]
        lines += [f"- {CHECK_MARK[c['status']]} {c['item']}" for c in terms[primary]["checklist"]]
        lines.append("")

    lines += ["## Confirm with other sources", ""]
    lines += [f"- {what}: [{name}]({url})" for what, name, url in NEXT_STEPS]
    mk = marketplaces_for(snap)
    if mk:
        lines.append("- Prices: " + ", ".join(f"[{n}]({u})" for n, u in mk))
    lines += ["", "## Caveats", ""]
    if primary and primary in terms:
        lines += [f"- {c}" for c in terms[primary]["verdict"]["caveats"]]
    lines += [f"- {p}" for p in PITFALLS]
    lines.append("")
    return "\n".join(lines)

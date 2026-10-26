"""Snapshot history and diffs between two checks of the same query."""
from __future__ import annotations

import json
from pathlib import Path

from .analyze import analyze_snapshot
from .parse import validate_snapshot
from .util import safe_join, slugify


def slug_for(snap: dict) -> str:
    q = snap["query"]
    return slugify(" ".join(q["terms"]) + " " + "-".join(g or "world" for g in q["geos"]) + " " + q["date"])


def history_dir(out: Path, snap: dict) -> Path:
    return safe_join(out, "history", slug_for(snap))


def save_snapshot(out: Path, snap: dict) -> Path:
    folder = history_dir(out, snap)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{snap['created']}.json"
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> dict:
    snap = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_snapshot(snap)
    return snap


def previous_snapshot(out: Path, snap: dict) -> Path | None:
    folder = history_dir(out, snap)
    if not folder.is_dir():
        return None
    older = sorted(p for p in folder.glob("*.json") if p.stem < snap["created"])
    return older[-1] if older else None


def diff(old: dict, new: dict) -> dict:
    """Compare two snapshots by re-analysing both (deterministic)."""
    a, b = analyze_snapshot(old), analyze_snapshot(new)
    changes: dict = {"from": old["created"], "to": new["created"], "terms": {}}
    for lab, nt in b["terms"].items():
        ot = a["terms"].get(lab)
        if ot is None:
            changes["terms"][lab] = {"new_term": True}
            continue
        ow, nw = ot["web"], nt["web"]
        entry: dict = {}
        if ow["shape"] != nw["shape"]:
            entry["shape"] = [ow["shape"], nw["shape"]]
        lo, ln = ow.get("avg_last_12m"), nw.get("avg_last_12m")
        if lo and ln:
            entry["level_change_pct"] = round((ln - lo) / lo * 100, 1)
        if ot["verdict"]["label"] != nt["verdict"]["label"]:
            entry["verdict"] = [ot["verdict"]["label"], nt["verdict"]["label"]]
        old_rise = {r["query"] for r in (ot.get("related") or {}).get("rising", [])}
        new_rise = [r["query"] for r in (nt.get("related") or {}).get("rising", []) if r["query"] not in old_rise]
        if new_rise:
            entry["new_rising_queries"] = new_rise
        old_top = [r["name"] for r in ((ot.get("regions") or {}).get("top", []))]
        new_top = [r["name"] for r in ((nt.get("regions") or {}).get("top", []))]
        if old_top and new_top and old_top != new_top:
            entry["top_regions"] = [old_top, new_top]
        changes["terms"][lab] = entry
    return changes


def render_diff(d: dict) -> str:
    lines = [f"## Changes since {d['from']} (now {d['to']})", ""]
    for lab, e in d["terms"].items():
        if e.get("new_term"):
            lines.append(f"- {lab}: new term, nothing to compare")
            continue
        if not e:
            lines.append(f"- {lab}: no meaningful change")
            continue
        bits = []
        if "shape" in e:
            bits.append(f"shape {e['shape'][0]} -> {e['shape'][1]}")
        if "level_change_pct" in e:
            bits.append(f"level {e['level_change_pct']:+}%")
        if "verdict" in e:
            bits.append(f"verdict {e['verdict'][0]} -> {e['verdict'][1]}")
        if "new_rising_queries" in e:
            bits.append("new rising: " + ", ".join(e["new_rising_queries"][:5]))
        if "top_regions" in e:
            bits.append("top regions: " + ", ".join(e["top_regions"][0]) + " -> " + ", ".join(e["top_regions"][1]))
        lines.append(f"- {lab}: " + "; ".join(bits))
    return "\n".join(lines) + "\n"

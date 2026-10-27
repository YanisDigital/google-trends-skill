#!/usr/bin/env python3
"""Command line entry point for the google-trends skill.

  check       fetch via Playwright, analyse, write reports, save history
  ingest      build a snapshot from raw widget JSON or compact JSON (browser mode) and report
  import-csv  build a snapshot from CSV files exported by hand from Trends and report
  report      re-render reports from a saved snapshot
  trending    "Trending now" from the public RSS feed
  diff        compare two saved snapshots

Everything stays on disk under --out (default ./google-trends-output). The only network
destination is trends.google.com.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gtrends import compact, history, report_html, report_md, report_tables, trending  # noqa: E402
from gtrends.analyze import analyze_snapshot  # noqa: E402
from gtrends.fetch_playwright import BlockedError, fetch, validate_inputs  # noqa: E402
from gtrends.ingest import ingest_raw  # noqa: E402
from gtrends.parse import ParseError, add_csv, new_snapshot, series_labels, validate_snapshot  # noqa: E402
from gtrends.util import MAX_INPUT_BYTES, prepare_output_dir, read_text_capped, safe_join  # noqa: E402

FORMATS = ("md", "html", "xlsx", "csv")
DEFAULT_OUT = "google-trends-output"


def _read_text(path: str) -> str:
    return read_text_capped(path, MAX_INPUT_BYTES)


_warned: set[Path] = set()


def _prepare(out: Path) -> None:
    if not prepare_output_dir(out) and out not in _warned:
        _warned.add(out)
        print(f"warning: {out} already existed and has no .gitignore; make sure it is not committed to git",
              file=sys.stderr)


def finish(snap: dict, out: Path, formats: list[str], quiet: bool = False, all_regions: bool = False) -> int:
    """Save history, analyse, write reports, print the Markdown report."""
    validate_snapshot(snap)
    _prepare(out)
    prev_path = history.previous_snapshot(out, snap)
    snapshot_path = history.save_snapshot(out, snap)
    analysis = analyze_snapshot(snap, include_unreliable=all_regions)
    folder = safe_join(out, "reports", history.slug_for(snap), snap["created"])
    folder.mkdir(parents=True, exist_ok=True)
    md = report_md.render(snap, analysis)
    if prev_path:
        md += "\n" + history.render_diff(history.diff(history.load_snapshot(prev_path), snap))
    (folder / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=1), encoding="utf-8")
    written = [snapshot_path, folder / "analysis.json"]
    if "md" in formats:
        (folder / "report.md").write_text(md, encoding="utf-8")
        written.append(folder / "report.md")
    if "html" in formats:
        (folder / "report.html").write_text(report_html.render(snap, analysis), encoding="utf-8")
        written.append(folder / "report.html")
    if "csv" in formats:
        written += report_tables.write_csvs(snap, analysis, folder)
    if "xlsx" in formats:
        try:
            written.append(report_tables.write_xlsx(snap, analysis, folder / "report.xlsx"))
        except RuntimeError as exc:
            print(f"warning: {exc}", file=sys.stderr)
    if not quiet:
        print(md)
    print("Files written:", file=sys.stderr)
    for p in written:
        print(f"  {p}", file=sys.stderr)
    return 0


def _formats(value: list[str]) -> list[str]:
    bad = [f for f in value if f not in FORMATS]
    if bad:
        raise ValueError(f"unknown format(s) {bad}; choose from {FORMATS}")
    return value


def _sources(a: argparse.Namespace) -> list[str]:
    """Products are checked in web search and Google Shopping, services in web search and YouTube."""
    return a.sources or (["web", "youtube"] if a.kind == "service" else ["web", "shopping"])


def cmd_check(a: argparse.Namespace) -> int:
    out = Path(a.out)
    sources = _sources(a)
    validate_inputs(a.terms, a.geo, a.date, sources)
    _prepare(out)
    raw = safe_join(out, "raw", history.slugify(" ".join(a.terms) + " ".join(a.geo) + a.date), date.today().isoformat())
    raw.mkdir(parents=True, exist_ok=True)
    fetch(a.terms, a.geo, a.date, sources, raw, category=a.category, headed=a.headed, delay_s=a.delay,
          log=lambda m: print(m, file=sys.stderr))
    snap = ingest_raw(raw, a.terms, a.geo, a.date, "playwright", a.category, a.kind)
    print(f"Raw Google responses kept in: {raw}", file=sys.stderr)
    return finish(snap, out, _formats(a.formats), all_regions=a.all_regions)


def cmd_ingest(a: argparse.Namespace) -> int:
    out = Path(a.out)
    if bool(a.raw) == bool(a.compact):
        raise ValueError("give exactly one of --raw DIR or --compact FILE [FILE ...]")
    if a.compact:
        _prepare(out)
        raw = safe_join(out, "raw", history.slugify(" ".join(a.terms) + " ".join(a.geo) + a.date), date.today().isoformat())
        for f in a.compact:
            data = json.loads(_read_text(f))
            source = compact.expand(data, raw)
            # keep the input as received next to the expanded files, so the run can be reproduced
            (raw / f"{source}.compact.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"Source data kept in: {raw}", file=sys.stderr)
    else:
        raw = Path(a.raw)
    snap = ingest_raw(raw, a.terms, a.geo, a.date, "browser", a.category, a.kind)
    return finish(snap, out, _formats(a.formats), all_regions=a.all_regions)


def cmd_import_csv(a: argparse.Namespace) -> int:
    web_tl = _read_text(a.web_timeline)
    snap = new_snapshot([], a.geo, a.date, "csv", kind=a.kind)
    add_csv(snap, "web", timeline=web_tl,
            regions=_read_text(a.regions) if a.regions else None,
            related={k: _read_text(v) for k, v in (kv.split("=", 1) for kv in a.related or [])} or None)
    labels = list(snap["sources"]["web"]["timeline"]["series"])
    snap["query"]["terms"] = a.terms or labels
    if a.shopping_timeline:
        add_csv(snap, "shopping", timeline=_read_text(a.shopping_timeline))
    series_labels(snap["query"]["terms"], a.geo)  # validates the term/geo combination
    return finish(snap, Path(a.out), _formats(a.formats), all_regions=a.all_regions)


def cmd_report(a: argparse.Namespace) -> int:
    return finish(history.load_snapshot(Path(a.snapshot)), Path(a.out), _formats(a.formats), all_regions=a.all_regions)


def cmd_trending(a: argparse.Namespace) -> int:
    print(trending.render(trending.fetch(a.geo), a.geo))
    return 0


def cmd_diff(a: argparse.Namespace) -> int:
    print(history.render_diff(history.diff(history.load_snapshot(Path(a.old)), history.load_snapshot(Path(a.new)))))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser, with_query: bool = True) -> None:
        sp.add_argument("--out", default=DEFAULT_OUT, help="output folder (default: ./google-trends-output)")
        sp.add_argument("--formats", nargs="+", default=["md", "html", "csv", "xlsx"], help="md html csv xlsx")
        sp.add_argument("--all-regions", action="store_true",
                        help="keep Crimea and Sevastopol in the region ranking (left out by default: tiny samples)")
        if with_query:
            sp.add_argument("--kind", choices=["product", "service"], default="product",
                            help="product (default): Google Shopping check, launch verdict; "
                                 "service: professions and niches, YouTube instead of Shopping, no launch verdict")
            sp.add_argument("--geo", nargs="+", default=["UA"], help="country code(s); '' = worldwide")
            sp.add_argument("--date", default="today 5-y", help="Trends period, e.g. 'today 5-y'")

    c = sub.add_parser("check", help="fetch with Playwright and report")
    common(c)
    c.add_argument("--terms", nargs="+", required=True, help="1-5 terms, e.g. 'air fryer' 'multicooker'")
    c.add_argument("--sources", nargs="+", default=None,
                   help="web shopping youtube images news (default: web shopping; for --kind service: web youtube)")
    c.add_argument("--category", type=int, default=0)
    c.add_argument("--headed", action="store_true", help="show the browser window")
    c.add_argument("--delay", type=float, default=8.0, help="seconds between pages (min 5)")
    c.set_defaults(fn=cmd_check)

    i = sub.add_parser("ingest", help="build a snapshot from raw widget JSON saved in browser mode")
    common(i)
    i.add_argument("--raw", help="folder with <source>/multiline.json etc.")
    i.add_argument("--compact", nargs="+", help="compact JSON file(s) from the browser snippet, one per source")
    i.add_argument("--terms", nargs="+", required=True)
    i.add_argument("--category", type=int, default=0)
    i.set_defaults(fn=cmd_ingest)

    v = sub.add_parser("import-csv", help="build a snapshot from CSV files exported from Trends")
    common(v)
    v.add_argument("--web-timeline", required=True, help="multiTimeline.csv (web search)")
    v.add_argument("--shopping-timeline", help="multiTimeline.csv exported with the Google Shopping source")
    v.add_argument("--regions", help="geoMap.csv")
    v.add_argument("--related", nargs="*", help="LABEL=relatedQueries.csv, one per term")
    v.add_argument("--terms", nargs="*", help="override the series labels")
    v.set_defaults(fn=cmd_import_csv)

    r = sub.add_parser("report", help="re-render reports from a saved snapshot")
    common(r, with_query=False)
    r.add_argument("snapshot")
    r.set_defaults(fn=cmd_report)

    t = sub.add_parser("trending", help="'Trending now' from the public RSS feed")
    t.add_argument("--geo", default="UA")
    t.set_defaults(fn=cmd_trending)

    d = sub.add_parser("diff", help="compare two snapshots")
    d.add_argument("old")
    d.add_argument("new")
    d.set_defaults(fn=cmd_diff)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if getattr(args, "delay", None) is not None:
        args.delay = max(5.0, args.delay)
    try:
        return args.fn(args)
    except BlockedError as exc:
        print(f"BLOCKED: {exc}\nStop here. Export CSV files by hand from trends.google.com and use `import-csv`.",
              file=sys.stderr)
        return 3
    except (ParseError, ValueError, OSError, json.JSONDecodeError, RecursionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())

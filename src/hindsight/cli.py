"""Hindsight CLI — show / stats / diff over canonical traces.

Auto-detects the input format by suffix and JSON shape:
  *.jsonl           → canonical Hindsight format
  *.json with `resourceSpans`           → OpenTelemetry GenAI export
  *.json with `child_runs` or `run_type` → LangSmith run-tree export
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import diff, ingest_jsonl, ingest_langsmith, ingest_otel, show
from .diff import diff_markdown
from .stats import stats, stats_markdown


def _auto_ingest(path: pathlib.Path):
    if not path.exists():
        raise SystemExit(f"hindsight: no such file: {path}")
    if path.suffix == ".jsonl":
        return ingest_jsonl(path)
    if path.suffix == ".json":
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and "resourceSpans" in raw:
            return ingest_otel(path)
        if isinstance(raw, dict) and ("child_runs" in raw or "run_type" in raw):
            return ingest_langsmith(path)
        raise SystemExit(f"hindsight: can't auto-detect JSON format for {path}")
    raise SystemExit(f"hindsight: unsupported suffix {path.suffix!r} (want .jsonl or .json)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hindsight",
        description="Flight recorder + replay debugger for LLM agents.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_show = sub.add_parser("show", help="Render a trace as a tree.")
    sp_show.add_argument("path")
    sp_show.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    sp_show.add_argument("--verbose", "-v", action="store_true", help="Include extra fields.")

    sp_stats = sub.add_parser("stats", help="Aggregate stats for a run.")
    sp_stats.add_argument("path")
    sp_stats.add_argument("--md", action="store_true", help="Emit Markdown instead of JSON.")

    sp_diff = sub.add_parser("diff", help="Diff two runs by canonical path.")
    sp_diff.add_argument("a")
    sp_diff.add_argument("b")
    sp_diff.add_argument("--md", action="store_true", help="Emit Markdown instead of JSON.")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "show":
        run = _auto_ingest(pathlib.Path(args.path))
        color = not args.no_color and sys.stdout.isatty()
        print(show(run, color=color, verbose=args.verbose))
        return 0

    if args.cmd == "stats":
        s = stats(_auto_ingest(pathlib.Path(args.path)))
        print(stats_markdown(s) if args.md else json.dumps(s, indent=2, sort_keys=True))
        return 0

    if args.cmd == "diff":
        d = diff(_auto_ingest(pathlib.Path(args.a)), _auto_ingest(pathlib.Path(args.b)))
        if args.md:
            print(diff_markdown(d))
        else:
            print(json.dumps(d.to_dict(), indent=2, sort_keys=True, default=str))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())

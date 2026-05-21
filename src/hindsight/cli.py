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

from . import __version__, diff, replay, show
from .base import INGESTERS, auto_ingest
from .canonical import TraceRun
from .diff import diff_markdown
from .stats import stats, stats_markdown


def _non_neg_int(s: str) -> int:
    n = int(s)
    if n < 0:
        raise argparse.ArgumentTypeError(f"depth must be >= 0, got {n}")
    return n


def _auto_ingest(path: pathlib.Path):
    if not path.exists():
        raise SystemExit(f"hindsight: no such file: {path}")
    try:
        return auto_ingest(path)
    except ValueError as e:
        raise SystemExit(f"hindsight: {e}") from e


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hindsight",
        description="Flight recorder + replay debugger for LLM agents.",
    )
    p.add_argument(
        "--version", action="version", version=f"hindsight {__version__}"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_show = sub.add_parser("show", help="Render a trace as a tree.")
    sp_show.add_argument("path")
    sp_show.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    sp_show.add_argument("--verbose", "-v", action="store_true", help="Include extra fields.")
    sp_show.add_argument(
        "--json", action="store_true",
        help="Emit canonical JSONL instead of the tree (useful for piping / format conversion).",
    )
    sp_show.add_argument(
        "--depth", type=_non_neg_int, default=None,
        help="Cap tree depth (0 = header only, 1 = root only, N = up to N levels). Tree-only; ignored with --json.",
    )

    sp_stats = sub.add_parser("stats", help="Aggregate stats for a run.")
    sp_stats.add_argument("path")
    sp_stats.add_argument("--md", action="store_true", help="Emit Markdown instead of JSON.")

    sp_diff = sub.add_parser("diff", help="Diff two runs by canonical path.")
    sp_diff.add_argument("a")
    sp_diff.add_argument("b")
    sp_diff.add_argument("--md", action="store_true", help="Emit Markdown instead of JSON.")
    sp_diff.add_argument("--strict", action="store_true", help="Also compare tokens_in / tokens_out / latency_ms.")

    sp_rep = sub.add_parser("replay", help="Replay a run from step N onward.")
    sp_rep.add_argument("path")
    sp_rep.add_argument("--from-step", required=True, help="Step id or numeric index to resume from.")
    sp_rep.add_argument("--model", help="Override model on LLM steps in the replayed tail.")
    sp_rep.add_argument("--live", action="store_true", help="Use AnthropicProvider (requires ANTHROPIC_API_KEY + anthropic extra).")
    sp_rep.add_argument("--live-tools", action="store_true", help="Route TOOL steps through the provider too (opt-in; default copies TOOL verbatim).")
    sp_rep.add_argument("--out", help="Write replayed canonical to PATH (JSONL); default stdout JSONL.")

    # ci — nested subparser group for CI-gate variants
    sp_ci = sub.add_parser("ci", help="CI-gate variants of hindsight verbs.")
    ci_sub = sp_ci.add_subparsers(dest="ci_cmd", required=True)

    sp_ci_diff = ci_sub.add_parser("diff", help="Diff two runs; optionally gate on divergence.")
    sp_ci_diff.add_argument("a")
    sp_ci_diff.add_argument("b")
    sp_ci_diff.add_argument("--gate", action="store_true", help="Exit 1 if diff is not clean.")
    sp_ci_diff.add_argument("--md", action="store_true", help="Emit Markdown instead of JSON.")
    sp_ci_diff.add_argument("--strict", action="store_true", help="Also compare tokens_in / tokens_out / latency_ms.")

    # validate — schema conformance check
    sp_validate = sub.add_parser("validate", help="Check canonical-schema conformance of a trace.")
    sp_validate.add_argument("path")

    # version — rich version + adapter list
    sub.add_parser("version", help="Print hindsight version, registered ingesters, and replay providers.")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "show":
        run = _auto_ingest(pathlib.Path(args.path))
        if args.json:
            sys.stdout.write(run.to_jsonl())
            return 0
        color = not args.no_color and sys.stdout.isatty()
        print(show(run, color=color, verbose=args.verbose, max_depth=args.depth))
        return 0

    if args.cmd == "stats":
        s = stats(_auto_ingest(pathlib.Path(args.path)))
        print(stats_markdown(s) if args.md else json.dumps(s, indent=2, sort_keys=True))
        return 0

    if args.cmd == "diff":
        d = diff(_auto_ingest(pathlib.Path(args.a)), _auto_ingest(pathlib.Path(args.b)), strict=args.strict)
        if args.md:
            print(diff_markdown(d))
        else:
            print(json.dumps(d.to_dict(), indent=2, sort_keys=True, default=str))
        return 0

    if args.cmd == "replay":
        run = _auto_ingest(pathlib.Path(args.path))
        from_step: str | int = args.from_step
        try:
            from_step = int(args.from_step)
        except ValueError:
            pass
        replayed: TraceRun = replay(run, from_step, model=args.model, live=args.live, live_tools=args.live_tools)
        out_text = replayed.to_jsonl()
        if args.out:
            pathlib.Path(args.out).write_text(out_text)
        else:
            sys.stdout.write(out_text)
        return 0

    if args.cmd == "ci":
        if args.ci_cmd == "diff":
            d = diff(
                _auto_ingest(pathlib.Path(args.a)),
                _auto_ingest(pathlib.Path(args.b)),
                strict=args.strict,
            )
            # Emit payload to stdout
            if args.md:
                print(diff_markdown(d))
            else:
                print(json.dumps(d.to_dict(), indent=2, sort_keys=True, default=str))
            # Always print one-line summary to stderr
            if d.is_clean:
                print("hindsight ci diff: clean", file=sys.stderr)
            else:
                path_str = " → ".join(d.first_divergent_path or [])
                print(
                    f"hindsight ci diff: diverged at {path_str}"
                    f" on {d.first_divergent_field}",
                    file=sys.stderr,
                )
            if args.gate and not d.is_clean:
                return 1
            return 0

    if args.cmd == "version":
        ingester_names = ", ".join(i.name for i in INGESTERS) or "(none)"
        provider_names = "mock, anthropic, openai"
        py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print(f"hindsight {__version__}")
        print(f"Python {py} on {sys.platform}")
        print(f"Registered ingesters: {ingester_names}")
        print(f"Replay providers: {provider_names}")
        return 0

    if args.cmd == "validate":
        path = pathlib.Path(args.path)
        run = _auto_ingest(path)  # raises SystemExit(1) on missing file
        try:
            run.validate()
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        n_steps = len(run.steps)
        kinds = len({s.kind for s in run.steps})
        print(f"hindsight validate: {path} OK — {n_steps} steps, {kinds} kinds")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())

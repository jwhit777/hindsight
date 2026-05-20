"""Hindsight overnight spike — end-to-end runnable.

Usage:
    python3 spike_run.py

What it does:
  1. Ingests three fixtures: canonical JSONL, LangSmith JSON, OTEL GenAI JSON.
  2. Verifies the structural-identity claim across all three.
  3. Renders the canonical good run as a colored tree (`show`).
  4. Aggregates the run via `stats`.
  5. Ingests the canonical "bad" run.
  6. Diffs good vs. bad.
  7. Writes JSON + Markdown reports under runs/.
  8. Prints a calibration-card-style summary.

stdlib only. No external dependencies. Single-digit ms runtime.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

# Make src/ importable when running directly from inside src/.
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from hindsight import (
    diff,
    ingest_jsonl,
    ingest_langsmith,
    ingest_otel,
    show,
)
from hindsight.diff import diff_markdown
from hindsight.stats import stats, stats_markdown

FIX = ROOT.parent / "fixtures"
OUT = ROOT.parent / "runs"
OUT.mkdir(parents=True, exist_ok=True)


def normalize(run) -> dict:
    """Strip source-provenance fields to compare structural payload only.

    Cross-format identity claim: same logical run, ingested via any
    adapter, produces the same structural payload here.
    """
    return {
        "step_count": len(run.steps),
        "steps": [
            {
                "path": run.path_from_root(s.id),
                "kind": s.kind.value,
                "name": s.name,
                "model": s.model,
                "tokens_in": s.tokens_in,
                "tokens_out": s.tokens_out,
                "error": s.error,
            }
            for s in run.steps
        ],
    }


def main() -> int:
    t0 = time.perf_counter()
    print("=" * 72)
    print("Hindsight overnight spike — 2026-05-15")
    print("=" * 72)

    print("\n[1/7] ingesting canonical_good.jsonl ...")
    run_can = ingest_jsonl(FIX / "canonical_good.jsonl")
    print(f"      -> {len(run_can.steps)} steps  source={run_can.source}")

    print("[2/7] ingesting langsmith_good.json ...")
    run_ls = ingest_langsmith(FIX / "langsmith_good.json")
    print(f"      -> {len(run_ls.steps)} steps  source={run_ls.source}")

    print("[3/7] ingesting otel_good.json ...")
    run_ot = ingest_otel(FIX / "otel_good.json")
    print(f"      -> {len(run_ot.steps)} steps  source={run_ot.source}")

    print("\n[4/7] cross-format structural identity check ...")
    n_can, n_ls, n_ot = (
        normalize(run_can),
        normalize(run_ls),
        normalize(run_ot),
    )
    identical = (n_can == n_ls == n_ot)
    print(f"      -> step counts: jsonl={n_can['step_count']}  "
          f"langsmith={n_ls['step_count']}  otel={n_ot['step_count']}")
    print(f"      -> structural payloads identical: {identical}")
    if not identical:
        # Print the first diff for debugging.
        for i, (a, b, c) in enumerate(
            zip(n_can["steps"], n_ls["steps"], n_ot["steps"])
        ):
            if not (a == b == c):
                print(f"      -> first mismatch at step {i}:")
                print(f"         jsonl: {a}")
                print(f"         lang:  {b}")
                print(f"         otel:  {c}")
                break

    print("\n[5/7] rendering canonical_good.jsonl as a tree (show) ...")
    print()
    print(show(run_can, color=False))

    print("\n[6/7] stats for canonical_good.jsonl ...")
    s = stats(run_can)
    print(f"      step_count={s['step_count']}  errors={s['error_count']}")
    print(f"      tokens in/out = {s['tokens']['in']}/{s['tokens']['out']}")
    print(f"      latency p50/p95 = {s['latency_ms']['p50']}/{s['latency_ms']['p95']} ms")
    print(f"      per_kind = {s['per_kind']}")
    (OUT / "stats_good.json").write_text(json.dumps(s, indent=2, sort_keys=True))
    (OUT / "stats_good.md").write_text(stats_markdown(s))

    print("\n[7/7] diff good vs bad ...")
    run_bad = ingest_jsonl(FIX / "canonical_bad.jsonl")
    d = diff(run_can, run_bad)
    print(f"      matched pairs={d.matched}  only_a={d.only_in_a}  only_b={d.only_in_b}")
    print(f"      reason: {d.reason}")
    if d.first_divergent_path:
        print(f"      first divergent step: {' → '.join(d.first_divergent_path)}")
        print(f"        A.response = {d.first_divergent_a.response}")
        print(f"        B.response = {d.first_divergent_b.response}")
    (OUT / "diff_good_vs_bad.json").write_text(
        json.dumps(d.to_dict(), indent=2, sort_keys=True, default=str)
    )
    (OUT / "diff_good_vs_bad.md").write_text(diff_markdown(d))

    dt = (time.perf_counter() - t0) * 1000.0
    print()
    print("=" * 72)
    print(f"spike done in {dt:.1f} ms · "
          f"identity={identical} · "
          f"diverged_at_router={d.first_divergent_path == ['agent:orchestrator', 'llm:router']}")
    print(f"reports: {OUT}/stats_good.json, .md, diff_good_vs_bad.json, .md")
    print("=" * 72)
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())

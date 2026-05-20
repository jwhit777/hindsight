"""Stats aggregation over a TraceRun."""

from __future__ import annotations

from .canonical import StepKind, TraceRun


def _percentile(values: list[int], p: float) -> int:
    """Linear-interpolation percentile. p in [0, 100]."""
    if not values:
        return 0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return int(d0 + d1)


def stats(run: TraceRun) -> dict:
    """Compute aggregate statistics over the run.

    Returns a dict suitable for JSON output or Markdown rendering.
    """
    per_kind: dict[str, int] = {k.value: 0 for k in StepKind}
    per_model: dict[str, dict] = {}
    per_tool: dict[str, dict] = {}
    error_count = 0
    latencies: list[int] = []
    tokens_in_total = 0
    tokens_out_total = 0

    for s in run.steps:
        per_kind[s.kind.value] += 1
        if s.error:
            error_count += 1
        if s.latency_ms:
            latencies.append(s.latency_ms)
        tokens_in_total += s.tokens_in
        tokens_out_total += s.tokens_out

        if s.kind is StepKind.LLM and s.model:
            slot = per_model.setdefault(
                s.model,
                {"calls": 0, "tokens_in": 0, "tokens_out": 0, "latency_ms": 0},
            )
            slot["calls"] += 1
            slot["tokens_in"] += s.tokens_in
            slot["tokens_out"] += s.tokens_out
            slot["latency_ms"] += s.latency_ms

        if s.kind is StepKind.TOOL:
            slot = per_tool.setdefault(s.name, {"calls": 0, "errors": 0})
            slot["calls"] += 1
            if s.error:
                slot["errors"] += 1

    return {
        "run_id": run.id,
        "source": run.source,
        "step_count": len(run.steps),
        "per_kind": per_kind,
        "per_model": per_model,
        "per_tool": per_tool,
        "error_count": error_count,
        "tokens": {"in": tokens_in_total, "out": tokens_out_total},
        "latency_ms": {
            "total": sum(latencies),
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "count": len(latencies),
        },
    }


def stats_markdown(s: dict) -> str:
    """Render the stats dict as a small Markdown report."""
    lines = [f"# Stats for run `{s['run_id']}`  (source: {s['source']})\n"]
    lines.append("## Steps by kind\n")
    for k, v in s["per_kind"].items():
        lines.append(f"- **{k}** — {v}")
    lines.append("\n## Tokens\n")
    lines.append(f"- input — {s['tokens']['in']}")
    lines.append(f"- output — {s['tokens']['out']}")
    lines.append("\n## Latency (ms)\n")
    lines.append(f"- total — {s['latency_ms']['total']}")
    lines.append(f"- p50 — {s['latency_ms']['p50']}")
    lines.append(f"- p95 — {s['latency_ms']['p95']}")
    if s["per_model"]:
        lines.append("\n## Per-model\n")
        for m, d in s["per_model"].items():
            lines.append(
                f"- **{m}** — {d['calls']} calls · "
                f"{d['tokens_in']} in / {d['tokens_out']} out · "
                f"{d['latency_ms']} ms"
            )
    if s["per_tool"]:
        lines.append("\n## Per-tool\n")
        for t, d in s["per_tool"].items():
            err = f"  · {d['errors']} errors" if d["errors"] else ""
            lines.append(f"- **{t}** — {d['calls']} calls{err}")
    return "\n".join(lines) + "\n"

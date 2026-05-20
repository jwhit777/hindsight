"""Ingest a LangSmith-shaped run-tree export.

We mirror the public LangSmith run-tree JSON shape that's stable across
their 2025-2026 export format:

  {
    "id": "<run-id>",
    "name": "<root-name>",
    "run_type": "chain" | "llm" | "tool" | "agent",
    "start_time": "...",
    "end_time": "...",
    "inputs": {...},
    "outputs": {...},
    "extra": {...},
    "child_runs": [ <recursive same shape> ],
    "error": "..."  (optional),
    "tags": [...]   (optional)
  }

We map run_type -> StepKind, child_runs -> tree structure, inputs/outputs
into request/response. LangSmith-specific fields land under extra["langsmith"].

NOTE: This is the documented shape; real LangSmith export adds vendor
fields we don't yet understand. They will land in extra and survive
round-trip — that's the design point.
"""

from __future__ import annotations

import json
import pathlib

from .canonical import StepKind, TraceRun, TraceStep

# LangSmith run_type -> canonical StepKind
_RUN_TYPE_MAP = {
    "agent": StepKind.AGENT,
    "chain": StepKind.AGENT,  # LangChain "chain" is an agent boundary for us
    "llm": StepKind.LLM,
    "chat_model": StepKind.LLM,
    "tool": StepKind.TOOL,
    "retriever": StepKind.TOOL,
    "parser": StepKind.DECISION,
    "router": StepKind.DECISION,
}


def _kind_of(run_type: str) -> StepKind:
    return _RUN_TYPE_MAP.get(run_type, StepKind.TOOL)


def _latency_ms(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    # Stable parsing of ISO-8601 with optional 'Z'.
    from datetime import datetime

    def _parse(t: str) -> datetime:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))

    try:
        return int((_parse(end) - _parse(start)).total_seconds() * 1000)
    except ValueError:
        return 0


def _tokens(extra: dict) -> tuple[int, int]:
    """LangSmith stores token usage under extra.invocation_params or
    outputs.llm_output.usage depending on integration. We try both."""
    # Path 1: extra.invocation_params.usage
    inv = (extra or {}).get("invocation_params") or {}
    usage = inv.get("usage") or {}
    if usage:
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    # Path 2: explicit token fields
    if "tokens_in" in (extra or {}) or "tokens_out" in (extra or {}):
        return int(extra.get("tokens_in", 0)), int(extra.get("tokens_out", 0))
    return 0, 0


def _walk(node: dict, parent_id: str | None, acc: list[TraceStep]) -> None:
    kind = _kind_of(node.get("run_type", "tool"))
    extra = node.get("extra") or {}
    tokens_in, tokens_out = _tokens(extra)
    model = None
    inv = extra.get("invocation_params") or {}
    if isinstance(inv, dict):
        model = inv.get("model") or inv.get("model_name")
    step = TraceStep(
        id=str(node["id"]),
        parent_id=parent_id,
        kind=kind,
        name=str(node.get("name") or kind.value),
        request=node.get("inputs"),
        response=node.get("outputs"),
        error=node.get("error"),
        latency_ms=_latency_ms(node.get("start_time"), node.get("end_time")),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=model,
        started_at=node.get("start_time"),
        extra={"langsmith": {k: v for k, v in node.items()
                             if k in ("tags", "run_type", "extra")}},
    )
    acc.append(step)
    for child in node.get("child_runs") or []:
        _walk(child, step.id, acc)


def ingest(path: pathlib.Path | str) -> TraceRun:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text())
    steps: list[TraceStep] = []
    _walk(raw, None, steps)
    run = TraceRun(
        id=str(raw["id"]),
        source="langsmith",
        started_at=raw.get("start_time"),
        finished_at=raw.get("end_time"),
        steps=steps,
        extra={"langsmith_root": {"name": raw.get("name")}},
    )
    run.validate()
    return run

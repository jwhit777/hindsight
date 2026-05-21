"""Ingest a Sub-Agent Bench trace export.

Sub-Agent Bench is an offline eval framework for orchestrator+sub-agent
systems. Its trace format wraps a top-level `orchestrator` agent that contains
a `steps` array; any step of kind `tool` may carry a nested `subagent_call`
which itself has its own `steps`. Shape::

    {
      "sab_version": "v0.1",
      "run_id": "...",
      "task_id": "...",
      "started_at": "...",
      "finished_at": "...",
      "orchestrator": {
        "id": "sab_s1", "name": "orchestrator", "kind": "agent",
        "started_at": "...", "latency_ms": ..., "input": {...}, "output": {...},
        "steps": [
          {"id": "sab_s2", "name": "router", "kind": "llm", "parent_id": "sab_s1",
           "model": "...", "tokens_in": N, "tokens_out": M, "input": {...},
           "output": {...}, "error": null, ...},
          {"id": "sab_s3", "name": "subagent.dispatch", "kind": "tool",
           "parent_id": "sab_s1", "subagent_call": {  # recursive: an agent +
             "id": "sab_s4", "kind": "agent", "parent_id": "sab_s3",
             "steps": [ ... ]                        # ... its own steps
           }},
          ...
        ]
      }
    }

The adapter flattens this nesting depth-first into the canonical TraceRun's
flat `steps` list while preserving parent linkage via `parent_id`. Step IDs
are kept verbatim (already SAB-namespaced as `sab_s*`).
"""

from __future__ import annotations

import json
import pathlib

from .canonical import StepKind, TraceRun, TraceStep

_KIND_MAP = {
    "agent": StepKind.AGENT,
    "llm": StepKind.LLM,
    "tool": StepKind.TOOL,
    "decision": StepKind.DECISION,
}


def _to_step(node: dict, *, parent_id: str | None) -> TraceStep:
    """Build a TraceStep from one SAB node. Does NOT recurse into nested steps."""
    kind = _KIND_MAP.get((node.get("kind") or "agent").lower(), StepKind.AGENT)
    return TraceStep(
        id=str(node["id"]),
        parent_id=parent_id,
        kind=kind,
        name=str(node.get("name") or kind.value),
        request=node.get("input"),
        response=node.get("output"),
        error=node.get("error"),
        latency_ms=int(node.get("latency_ms") or 0),
        tokens_in=int(node.get("tokens_in") or 0),
        tokens_out=int(node.get("tokens_out") or 0),
        model=node.get("model"),
        started_at=node.get("started_at"),
        extra={"subagent_bench": {"raw_kind": node.get("kind")}},
    )


def _walk(node: dict, *, parent_id: str | None, out: list[TraceStep]) -> None:
    """Emit a TraceStep for `node`, then recurse into its children.

    Children come from two places:
      1. node["steps"] — direct children with parent_id = node["id"].
      2. node["subagent_call"] — a single nested agent rooted under node;
         its `parent_id` is already set in the JSON to point at `node["id"]`.
         We recurse into the subagent_call as a sibling subtree (its own
         steps live under itself).
    """
    out.append(_to_step(node, parent_id=parent_id))
    this_id = str(node["id"])
    for child in node.get("steps") or []:
        # Honor an explicit child parent_id if present, else fall back to this.
        child_parent = child.get("parent_id") or this_id
        # If child carries a nested subagent_call, emit the child itself first
        # (with this as parent), then recurse into the subagent_call subtree
        # whose own parent_id points back at the child.
        sub_call = child.get("subagent_call")
        if sub_call is None:
            _walk(child, parent_id=child_parent, out=out)
        else:
            # Emit the parent tool step (no recursion into its own .steps —
            # SAB tool steps don't have steps[] unless they carry subagent_call).
            out.append(_to_step(child, parent_id=child_parent))
            sub_parent = sub_call.get("parent_id") or str(child["id"])
            _walk(sub_call, parent_id=sub_parent, out=out)


def ingest(path: pathlib.Path | str) -> TraceRun:
    p = pathlib.Path(path)
    raw: dict = json.loads(p.read_text())

    run_id = str(raw.get("run_id") or "sab_run")
    started_at = raw.get("started_at")
    finished_at = raw.get("finished_at")
    orch = raw.get("orchestrator") or {}

    steps: list[TraceStep] = []
    _walk(orch, parent_id=None, out=steps)

    run = TraceRun(
        id=run_id,
        source="subagent_bench",
        started_at=started_at,
        finished_at=finished_at,
        steps=steps,
        extra={
            "subagent_bench": {
                "sab_version": raw.get("sab_version"),
                "task_id": raw.get("task_id"),
            }
        },
    )
    run.validate()
    return run

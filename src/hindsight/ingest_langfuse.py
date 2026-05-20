"""Ingest a Langfuse trace export.

Langfuse exports a single trace object::

    {
      "id": "trace_abc",
      "name": "agent_run",
      "timestamp": "2026-05-15T09:12:44Z",
      "observations": [
        {
          "id": "obs_1",
          "type": "SPAN" | "GENERATION" | "EVENT",
          "name": "router",
          "startTime": "...",
          "endTime": "...",
          "input": {...},
          "output": {...},
          "model": "claude-haiku-4-5",
          "usage": {"input": 412, "output": 38},
          "parentObservationId": "obs_0" | null,
          "level": "DEFAULT" | "WARNING" | "ERROR",
          "statusMessage": null | "..."
        },
        ...
      ]
    }

Mapping rules:
  - type=GENERATION                          → LLM  (model, tokens from usage)
  - type=SPAN, name looks like an agent      → AGENT
  - type=SPAN (non-agent) or type=EVENT      → TOOL
  - parentObservationId=null                 → root of the observation tree;
    the trace itself acts as the AGENT envelope around all observations.
  - level=ERROR or non-null statusMessage    → step.error
  - Latency = endTime - startTime (ms).

The trace-level envelope is synthesised as a root AGENT step so the canonical
tree always has exactly one root — consistent with the jsonl/langsmith/otel
adapters.  Observation IDs are prefixed with "lf:" to namespace them.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime

from .canonical import StepKind, TraceRun, TraceStep

# Suffix tokens (after splitting a SPAN name on - / _) that mark an agent-boundary
# rather than a tool. Word-boundary, not substring, so "subagent.dispatch" stays TOOL.
_AGENT_SUFFIXES = {"analyst", "agent", "planner", "runner", "orchestrator"}


def _is_agent_span(name: str) -> bool:
    """Treat SPANs whose final hyphen/underscore segment is an agent role
    (e.g. "stock-analyst", "research-agent") as AGENT; everything else is TOOL.

    Substring matching would mis-classify "subagent.dispatch" as AGENT, so we
    require a word-boundary match on the trailing segment.
    """
    parts = (name or "").lower().replace("_", "-").split("-")
    return bool(parts) and parts[-1] in _AGENT_SUFFIXES


def _kind_of(obs: dict) -> StepKind:
    typ = (obs.get("type") or "SPAN").upper()
    if typ == "GENERATION":
        return StepKind.LLM
    if typ == "SPAN":
        return StepKind.AGENT if _is_agent_span(obs.get("name", "")) else StepKind.TOOL
    # EVENT and anything else → TOOL
    return StepKind.TOOL


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latency_ms(start: str | None, end: str | None) -> int:
    a = _parse_iso(start)
    b = _parse_iso(end)
    if a is None or b is None:
        return 0
    return max(0, int((b - a).total_seconds() * 1000))


def _tokens(obs: dict) -> tuple[int, int]:
    usage = obs.get("usage") or {}
    # Langfuse usage keys: "input" / "output" (or sometimes "promptTokens" /
    # "completionTokens" from older SDK versions — support both).
    tin = int(
        usage.get("input")
        or usage.get("promptTokens")
        or usage.get("input_tokens")
        or 0
    )
    tout = int(
        usage.get("output")
        or usage.get("completionTokens")
        or usage.get("output_tokens")
        or 0
    )
    return tin, tout


def _error_of(obs: dict) -> str | None:
    if (obs.get("level") or "").upper() == "ERROR":
        return obs.get("statusMessage") or "ERROR"
    msg = obs.get("statusMessage")
    if msg:
        return msg
    return None


def ingest(path: pathlib.Path | str) -> TraceRun:
    p = pathlib.Path(path)
    raw: dict = json.loads(p.read_text())

    trace_id: str = str(raw.get("id") or "langfuse_trace")
    trace_name: str = str(raw.get("name") or "trace")
    trace_ts: str | None = raw.get("timestamp")
    observations: list[dict] = raw.get("observations") or []

    # ------------------------------------------------------------------
    # Sort observations by startTime so parents come before children when
    # we later do topological insertion (matches other adapters' guarantee).
    # ------------------------------------------------------------------
    def _sort_key(o: dict) -> str:
        return o.get("startTime") or o.get("timestamp") or ""

    observations = sorted(observations, key=_sort_key)

    # ------------------------------------------------------------------
    # Build observation steps.  IDs are prefixed "lf:" to avoid collisions.
    # ------------------------------------------------------------------
    # The root AGENT step represents the trace envelope itself.
    root_step_id = f"lf:{trace_id}"

    # Determine trace-level start/end from observations if not on the trace.
    obs_starts = [o.get("startTime") for o in observations if o.get("startTime")]
    obs_ends = [o.get("endTime") for o in observations if o.get("endTime")]
    trace_start = trace_ts or (min(obs_starts) if obs_starts else None)
    trace_end = raw.get("endTime") or (max(obs_ends) if obs_ends else None)

    root_step = TraceStep(
        id=root_step_id,
        parent_id=None,
        kind=StepKind.AGENT,
        name=trace_name,
        request=raw.get("input"),
        response=raw.get("output"),
        error=None,
        latency_ms=_latency_ms(trace_start, trace_end),
        tokens_in=0,
        tokens_out=0,
        model=None,
        started_at=trace_start,
        extra={"langfuse": {"trace_id": trace_id, "trace_name": trace_name}},
    )

    obs_steps: list[TraceStep] = []
    obs_id_to_step_id: dict[str | None, str] = {}

    for obs in observations:
        obs_id = str(obs.get("id") or "")
        step_id = f"lf:{obs_id}" if obs_id else f"lf:obs_{len(obs_steps)}"
        obs_id_to_step_id[obs_id] = step_id

        kind = _kind_of(obs)
        tin, tout = _tokens(obs)

        obs_step = TraceStep(
            id=step_id,
            parent_id=None,  # filled in second pass
            kind=kind,
            name=str(obs.get("name") or kind.value),
            request=obs.get("input"),
            response=obs.get("output"),
            error=_error_of(obs),
            latency_ms=_latency_ms(obs.get("startTime"), obs.get("endTime")),
            tokens_in=tin,
            tokens_out=tout,
            model=obs.get("model"),
            started_at=obs.get("startTime"),
            extra={
                "langfuse": {
                    "observation_id": obs_id,
                    "type": obs.get("type"),
                    "level": obs.get("level"),
                }
            },
        )
        obs_steps.append(obs_step)

    # ------------------------------------------------------------------
    # Second pass: wire parent_id.
    # parentObservationId=null → child of the trace root.
    # ------------------------------------------------------------------
    for obs, step in zip(observations, obs_steps):
        parent_obs_id = obs.get("parentObservationId")
        if parent_obs_id:
            step.parent_id = obs_id_to_step_id.get(str(parent_obs_id), root_step_id)
        else:
            step.parent_id = root_step_id

    # ------------------------------------------------------------------
    # Topological sort: ensure parents appear before children in the list.
    # ------------------------------------------------------------------
    all_steps_by_id: dict[str, TraceStep] = {root_step_id: root_step}
    for s in obs_steps:
        all_steps_by_id[s.id] = s

    sorted_steps: list[TraceStep] = []
    visited: set[str] = set()

    def visit(sid: str) -> None:
        if sid in visited or sid not in all_steps_by_id:
            return
        s = all_steps_by_id[sid]
        if s.parent_id and s.parent_id not in visited:
            visit(s.parent_id)
        visited.add(sid)
        sorted_steps.append(s)

    for sid in all_steps_by_id:
        visit(sid)

    run = TraceRun(
        id=trace_id,
        source="langfuse",
        started_at=trace_start,
        finished_at=trace_end,
        steps=sorted_steps,
        extra={"langfuse_root": {"name": trace_name}},
    )
    run.validate()
    return run

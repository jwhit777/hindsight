"""Ingest OpenTelemetry GenAI span JSON.

We target the OTEL GenAI semantic conventions
(https://opentelemetry.io/docs/specs/semconv/gen-ai/) which define attributes
like gen_ai.operation.name, gen_ai.request.model, gen_ai.usage.input_tokens.

Input shape: a JSON object with a `resourceSpans[]` list, each containing
`scopeSpans[]`, each containing `spans[]`. Each span has:

  {
    "spanId": "hex",
    "parentSpanId": "hex" | "" | null,
    "name": "<op-name>",
    "startTimeUnixNano": "...",
    "endTimeUnixNano": "...",
    "attributes": [{"key": "...", "value": {"stringValue": "..."}}, ...],
    "status": {"code": "STATUS_CODE_OK" | "STATUS_CODE_ERROR", "message": "..."}
  }

The attribute key list distinguishes step kind:
  - gen_ai.operation.name in {chat, text_completion, generate_content} -> LLM
  - gen_ai.agent.* set, no model -> AGENT
  - gen_ai.tool.name set -> TOOL
  - else -> DECISION

Spec is still experimental as of 2026-05; this adapter pins to a single
documented attribute set and surfaces unknowns under extra["otel"].
"""

from __future__ import annotations

import json
import pathlib

from .canonical import StepKind, TraceRun, TraceStep


def _attr_value(v: dict) -> object:
    """OTEL attribute values are tagged unions. Unwrap them."""
    if not isinstance(v, dict):
        return v
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in v:
            val = v[key]
            if key == "intValue" and isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    return val
            return val
    if "arrayValue" in v:
        return [_attr_value(x) for x in v["arrayValue"].get("values", [])]
    return v


def _attrs_dict(attrs: list) -> dict:
    out: dict = {}
    for a in attrs or []:
        k = a.get("key")
        if not k:
            continue
        out[k] = _attr_value(a.get("value", {}))
    return out


def _kind_of(attrs: dict, name: str) -> StepKind:
    op = attrs.get("gen_ai.operation.name")
    if op in {"chat", "text_completion", "generate_content", "embeddings"}:
        return StepKind.LLM
    if any(k.startswith("gen_ai.tool.") for k in attrs) or attrs.get("gen_ai.tool.name"):
        return StepKind.TOOL
    if any(k.startswith("gen_ai.agent.") for k in attrs):
        return StepKind.AGENT
    # name-based hint
    n = (name or "").lower()
    if "tool" in n:
        return StepKind.TOOL
    if "agent" in n:
        return StepKind.AGENT
    return StepKind.DECISION


def _latency_ms(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    try:
        a = int(start)
        b = int(end)
    except (TypeError, ValueError):
        return 0
    return max(0, (b - a) // 1_000_000)


def _started_at_iso(start_ns: str | None) -> str | None:
    if not start_ns:
        return None
    try:
        from datetime import datetime, timezone

        ns = int(start_ns)
        sec = ns / 1_000_000_000
        return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return None


def ingest(path: pathlib.Path | str) -> TraceRun:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text())

    # Flatten into list of spans.
    raw_spans: list[dict] = []
    for rs in raw.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                raw_spans.append(sp)

    steps: list[TraceStep] = []
    span_id_to_step_id: dict[str, str] = {}

    # First pass: build steps; defer parent linkage to second pass to allow
    # arbitrary span order in the input.
    for sp in raw_spans:
        attrs = _attrs_dict(sp.get("attributes", []))
        kind = _kind_of(attrs, sp.get("name", ""))
        span_id = sp.get("spanId") or sp.get("span_id") or ""
        step_id = f"otel:{span_id}"
        span_id_to_step_id[span_id] = step_id
        request = None
        response = None
        # Capture model + tokens
        model = attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model")
        tokens_in = int(attrs.get("gen_ai.usage.input_tokens", 0) or 0)
        tokens_out = int(attrs.get("gen_ai.usage.output_tokens", 0) or 0)
        # Request/response shapes vary; we keep raw under request/response
        if "gen_ai.request.messages" in attrs:
            request = {"messages": attrs["gen_ai.request.messages"]}
        elif "gen_ai.prompt" in attrs:
            request = {"prompt": attrs["gen_ai.prompt"]}
        if "gen_ai.response.content" in attrs:
            response = {"content": attrs["gen_ai.response.content"]}
        elif "gen_ai.completion" in attrs:
            response = {"completion": attrs["gen_ai.completion"]}

        status = sp.get("status") or {}
        error = None
        if status.get("code") == "STATUS_CODE_ERROR":
            error = status.get("message") or "OTEL status error"

        # Prefer the GenAI-attribute name (canonical) over the OTEL span name
        # (which often contains "tool." / "agent." prefixes for routing).
        name = (
            attrs.get("gen_ai.tool.name")
            or attrs.get("gen_ai.agent.name")
            or sp.get("name")
            or kind.value
        )

        step = TraceStep(
            id=step_id,
            parent_id=None,  # filled in second pass
            kind=kind,
            name=name,
            request=request,
            response=response,
            error=error,
            latency_ms=_latency_ms(
                sp.get("startTimeUnixNano"), sp.get("endTimeUnixNano")
            ),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            started_at=_started_at_iso(sp.get("startTimeUnixNano")),
            extra={
                "otel": {
                    "span_id": span_id,
                    "attributes": attrs,
                    "status": status,
                }
            },
        )
        steps.append(step)

    # Second pass: wire parents (must run after all span_id->step_id known).
    for sp, step in zip(raw_spans, steps):
        parent = sp.get("parentSpanId") or sp.get("parent_span_id") or ""
        if parent:
            step.parent_id = span_id_to_step_id.get(parent)

    # Topological sort: parents before children. OTEL doesn't promise this.
    by_id = {s.id: s for s in steps}
    sorted_steps: list[TraceStep] = []
    visited: set[str] = set()

    def visit(sid: str) -> None:
        if sid in visited or sid not in by_id:
            return
        s = by_id[sid]
        if s.parent_id and s.parent_id not in visited:
            visit(s.parent_id)
        visited.add(sid)
        sorted_steps.append(s)

    for s in steps:
        visit(s.id)

    # Choose the root: first step with no parent_id in our set.
    roots = [s for s in sorted_steps if s.parent_id is None]
    run_id = "otel:" + (raw_spans[0].get("traceId") or roots[0].id if raw_spans else "unknown")

    run = TraceRun(
        id=run_id,
        source="otel",
        started_at=roots[0].started_at if roots else None,
        finished_at=None,
        steps=sorted_steps,
        extra={"otel_meta": {"resource_count": len(raw.get("resourceSpans", []))}},
    )
    run.validate()
    return run

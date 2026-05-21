#!/usr/bin/env python3
"""Capture a real OTEL GenAI trace from a live Anthropic SDK call.

Run this once with `ANTHROPIC_API_KEY` set in env. It instruments the
Anthropic SDK with `opentelemetry-instrumentation-anthropic`, issues one
short `claude-haiku-4-5` request, collects the resulting spans, and
serializes them into the OTLP JSON shape that `hindsight.ingest_otel`
expects. Output is written to `fixtures/otel_real.json` (or `--out`).

Why this matters: the existing `fixtures/otel_good.json` is hand-written
from the OTEL GenAI semconv spec. This script validates the adapter
against *captured reality*. PLAN.md leading-indicator: Day-2/3 work to
prove the OTEL adapter survives contact with real SDK output.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/capture_otel_anthropic.py
    hindsight show fixtures/otel_real.json    # if the adapter parses it
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any


def _value_to_otlp(v: Any) -> dict:
    """Map a Python value to an OTLP AnyValue dict.

    OTLP wire format uses `{"stringValue": "..."}` / `{"intValue": "..."}` /
    `{"boolValue": true}` / `{"doubleValue": 1.5}` / `{"arrayValue": ...}`.
    The adapter (`hindsight/ingest_otel.py`) reads several of these.
    """
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}  # OTLP serializes int64 as JSON string
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [_value_to_otlp(x) for x in v]}}
    # Default: stringify.
    return {"stringValue": str(v)}


def _attrs_to_otlp(attrs: dict[str, Any] | None) -> list[dict]:
    if not attrs:
        return []
    return [{"key": k, "value": _value_to_otlp(v)} for k, v in attrs.items()]


def _span_to_otlp(span: Any) -> dict:
    """Convert a `ReadableSpan` (from opentelemetry-sdk) into an OTLP span dict."""
    ctx = span.get_span_context()
    parent = span.parent
    out: dict[str, Any] = {
        "traceId": format(ctx.trace_id, "032x"),
        "spanId": format(ctx.span_id, "016x"),
        "name": span.name,
        "kind": int(span.kind.value) if hasattr(span.kind, "value") else 1,
        "startTimeUnixNano": str(span.start_time),
        "endTimeUnixNano": str(span.end_time),
        "attributes": _attrs_to_otlp(dict(span.attributes or {})),
    }
    if parent is not None:
        out["parentSpanId"] = format(parent.span_id, "016x")
    if span.status and span.status.status_code:
        out["status"] = {
            "code": int(span.status.status_code.value)
            if hasattr(span.status.status_code, "value")
            else 0,
        }
        if span.status.description:
            out["status"]["message"] = span.status.description
    return out


def _spans_to_resource_spans(spans: list[Any]) -> dict:
    """Group ReadableSpans into a single OTLP `resourceSpans[]` document."""
    if not spans:
        return {"resourceSpans": []}
    first = spans[0]
    resource_attrs = _attrs_to_otlp(dict(first.resource.attributes or {})) if first.resource else []
    # Group by instrumentation scope (name + version).
    by_scope: dict[tuple[str, str], list[Any]] = {}
    for s in spans:
        scope = s.instrumentation_scope
        key = (scope.name if scope else "", scope.version if scope else "")
        by_scope.setdefault(key, []).append(s)
    scope_spans = [
        {
            "scope": {"name": name, "version": version},
            "spans": [_span_to_otlp(s) for s in spans_for_scope],
        }
        for (name, version), spans_for_scope in by_scope.items()
    ]
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeSpans": scope_spans,
            }
        ]
    }


def main() -> int:
    p = argparse.ArgumentParser(prog="capture_otel_anthropic")
    p.add_argument(
        "--out",
        default="fixtures/otel_real.json",
        help="Output path for the captured OTLP JSON (default: fixtures/otel_real.json).",
    )
    p.add_argument(
        "--model",
        default="claude-haiku-4-5",
        help="Anthropic model to call (default: claude-haiku-4-5 — cheapest path).",
    )
    p.add_argument(
        "--prompt",
        default="Reply with just the word 'pong'.",
        help="One-shot user prompt; kept tiny to minimize cost.",
    )
    args = p.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is not set. Export it and re-run.",
            file=sys.stderr,
        )
        return 2

    # Lazy imports — these are in the [otel] + [live] extras.
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
    except ImportError as exc:
        print(f"ERROR: missing OTEL extras: {exc}", file=sys.stderr)
        print("Install with: pip install -e '.[otel,live]'", file=sys.stderr)
        return 2

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        print(f"ERROR: missing anthropic SDK: {exc}", file=sys.stderr)
        print("Install with: pip install -e '.[live]'", file=sys.stderr)
        return 2

    # ------------------------------------------------------------------
    # Stand up an in-process tracer pipeline and instrument the SDK.
    # ------------------------------------------------------------------
    resource = Resource.create({"service.name": "hindsight-otel-capture"})
    provider = TracerProvider(resource=resource)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    AnthropicInstrumentor().instrument()

    # ------------------------------------------------------------------
    # One small API call — tokens kept tiny.
    # ------------------------------------------------------------------
    client = Anthropic()
    resp = client.messages.create(
        model=args.model,
        max_tokens=32,
        messages=[{"role": "user", "content": args.prompt}],
    )
    text = "".join(getattr(b, "text", "") for b in resp.content)
    print(f"[capture] model={args.model} reply={text!r}", file=sys.stderr)

    # Force-flush spans, then read.
    provider.force_flush()
    spans = list(exporter.get_finished_spans())
    if not spans:
        print(
            "ERROR: no spans captured. AnthropicInstrumentor may not be wired correctly.",
            file=sys.stderr,
        )
        return 1

    print(f"[capture] {len(spans)} span(s) captured", file=sys.stderr)
    payload = _spans_to_resource_spans(spans)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"[capture] wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

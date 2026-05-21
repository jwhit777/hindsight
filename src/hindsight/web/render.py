"""HTML rendering of a TraceRun.

Mirrors `hindsight.show.show()` but emits HTML rather than ANSI. The
emitted markup uses HTML5 `<details>` for collapsible request/response
drill-down so the page needs zero JavaScript.
"""

from __future__ import annotations

import html
import json
from typing import Any

from ..canonical import StepKind, TraceRun

_KIND_LABEL = {
    StepKind.AGENT: "AGENT",
    StepKind.LLM: "LLM",
    StepKind.TOOL: "TOOL",
    StepKind.DECISION: "DEC",
}


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _json_block(label: str, value: Any) -> str:
    """Collapsible <details> block with pretty-printed JSON inside."""
    try:
        text = json.dumps(value, indent=2, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return (
        f'<details class="kv"><summary>{_esc(label)}</summary>'
        f'<pre class="json">{_esc(text)}</pre></details>'
    )


def render_tree(run: TraceRun) -> str:
    """Return an HTML fragment representing the trace as an indented tree.

    Mirrors `show.show()` semantically; one `<div class="step">` per step.
    """
    parts: list[str] = []
    tokens_in, tokens_out = run.total_tokens()
    parts.append(
        '<div class="run-header">'
        f'<span class="run-id">{_esc(run.id)}</span> '
        f'<span class="run-source">source={_esc(run.source)}</span>'
        '</div>'
    )
    parts.append(
        '<div class="run-summary">'
        f'{len(run.steps)} steps · {tokens_in} tok in / {tokens_out} tok out · '
        f'{run.total_latency_ms()} ms total'
        '</div>'
    )
    parts.append('<div class="trace-tree">')

    for depth, step in run.walk_tree():
        kind_class = step.kind.value
        label = _KIND_LABEL.get(step.kind, "?")
        indent = "&nbsp;" * (depth * 4)
        meta_chunks: list[str] = []
        if step.model:
            meta_chunks.append(f'<span class="meta model">{_esc(step.model)}</span>')
        if step.tokens_in or step.tokens_out:
            meta_chunks.append(
                f'<span class="meta tokens">{step.tokens_in} in / {step.tokens_out} out</span>'
            )
        if step.latency_ms:
            meta_chunks.append(
                f'<span class="meta latency">{step.latency_ms} ms</span>'
            )
        if step.error:
            meta_chunks.append(
                f'<span class="meta error">ERROR: {_esc(step.error)}</span>'
            )
        meta = " · ".join(meta_chunks)

        detail_blocks: list[str] = []
        if step.request:
            detail_blocks.append(_json_block("request", step.request))
        if step.response:
            detail_blocks.append(_json_block("response", step.response))

        parts.append(
            f'<div class="step kind-{_esc(kind_class)}" data-step-id="{_esc(step.id)}">'
            f'{indent}<span class="kind-badge">{label}</span> '
            f'<span class="step-name">{_esc(step.name)}</span>'
            + (f' <span class="meta-bar">· {meta}</span>' if meta else '')
            + (f'<div class="step-details">{"".join(detail_blocks)}</div>'
               if detail_blocks else '')
            + '</div>'
        )

    parts.append('</div>')
    return "\n".join(parts)

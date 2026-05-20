"""Terminal-pretty tree rendering for a TraceRun.

stdlib only. ANSI escapes for color; disable with color=False.
"""

from __future__ import annotations

from .canonical import StepKind, TraceRun

# ANSI palette (kept tiny; readable on most terminals).
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"
_RED = "\x1b[31m"
_YELLOW = "\x1b[33m"
_GREEN = "\x1b[32m"
_BLUE = "\x1b[34m"
_MAGENTA = "\x1b[35m"
_CYAN = "\x1b[36m"

_KIND_ICON = {
    StepKind.AGENT: "AGENT",
    StepKind.LLM: " LLM ",
    StepKind.TOOL: " TOOL",
    StepKind.DECISION: " DEC ",
}
_KIND_COLOR = {
    StepKind.AGENT: _MAGENTA,
    StepKind.LLM: _CYAN,
    StepKind.TOOL: _GREEN,
    StepKind.DECISION: _BLUE,
}


def _paint(text: str, color: str, enable: bool) -> str:
    if not enable:
        return text
    return f"{color}{text}{_RESET}"


def show(run: TraceRun, *, color: bool = True, verbose: bool = False) -> str:
    """Returns a multi-line string representation of the run tree."""
    lines: list[str] = []
    lines.append(
        _paint(f"run {run.id}  source={run.source}", _BOLD, color)
    )
    tokens_in, tokens_out = run.total_tokens()
    summary = (
        f"  {len(run.steps)} steps · "
        f"{tokens_in} tok in / {tokens_out} tok out · "
        f"{run.total_latency_ms()} ms total"
    )
    lines.append(_paint(summary, _DIM, color))
    lines.append("")

    for depth, step in run.walk_tree():
        indent = "  " * depth
        icon = _paint(_KIND_ICON[step.kind], _KIND_COLOR[step.kind], color)
        name = step.name
        if step.model:
            name += _paint(f"  · {step.model}", _DIM, color)
        if step.tokens_in or step.tokens_out:
            name += _paint(
                f"  · {step.tokens_in} in / {step.tokens_out} out",
                _DIM, color,
            )
        if step.latency_ms:
            name += _paint(f"  · {step.latency_ms} ms", _DIM, color)
        if step.error:
            name += "  " + _paint(f"ERROR: {step.error}", _RED, color)
        lines.append(f"{indent}{icon}  {name}")
        if verbose and step.request:
            lines.append(
                f"{indent}      "
                + _paint("req=", _DIM, color)
                + str(step.request)[:200]
            )
        if verbose and step.response:
            lines.append(
                f"{indent}      "
                + _paint("res=", _DIM, color)
                + str(step.response)[:200]
            )
    return "\n".join(lines)

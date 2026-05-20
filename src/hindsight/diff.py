"""Structural diff between two TraceRuns.

Alignment key: the (kind, name) path from root to each step.
Within a matched path, steps are aligned by `started_at` order, then by their
order in the run if timestamps are absent.

The diff is intentionally simple, deterministic, and *explainable*. We do not
use an LLM to explain divergences. We give the FDE the structural delta and
let them reason.

The first divergence is the only one the v0.1 diff highlights. Phase 2 can
walk past the first divergence and report cascades.
"""

from __future__ import annotations

from dataclasses import dataclass

from .canonical import StepKind, TraceRun, TraceStep

# Fields compared by default. tokens_* and latency_ms are excluded — they
# vary across runs of "the same" agent due to caching, billing rounding,
# clock jitter. Use --strict to compare them.
_DEFAULT_FIELDS = ("request", "response", "error", "model", "kind", "name")

# AGENT steps are span boundaries, not events. Their request/response are
# usually aggregates of their children's behavior — so a difference there
# almost always means there's a more interesting difference inside. Default
# diff skips request/response on AGENT, comparing only structural fields.
_AGENT_FIELDS = ("error", "model", "kind", "name")


@dataclass
class Divergence:
    matched: int                 # number of step pairs aligned
    only_in_a: int               # steps in A with no counterpart in B
    only_in_b: int               # steps in B with no counterpart in A
    first_divergent_path: list[str] | None   # path-from-root of first diff
    first_divergent_field: str | None
    first_divergent_a: TraceStep | None
    first_divergent_b: TraceStep | None
    reason: str                  # plain-English summary

    @property
    def is_clean(self) -> bool:
        return (
            self.first_divergent_path is None
            and self.only_in_a == 0
            and self.only_in_b == 0
        )

    def to_dict(self) -> dict:
        return {
            "matched": self.matched,
            "only_in_a": self.only_in_a,
            "only_in_b": self.only_in_b,
            "first_divergent_path": self.first_divergent_path,
            "first_divergent_field": self.first_divergent_field,
            "first_divergent_a_id": (
                self.first_divergent_a.id if self.first_divergent_a else None
            ),
            "first_divergent_b_id": (
                self.first_divergent_b.id if self.first_divergent_b else None
            ),
            "reason": self.reason,
            "clean": self.is_clean,
        }


def _index_by_path(run: TraceRun) -> dict[tuple[str, ...], list[TraceStep]]:
    """Group steps by their path-from-root tuple. Multiple steps may share
    a path (e.g. retries of the same tool). They're ordered by started_at
    then by their position in run.steps."""
    out: dict[tuple[str, ...], list[TraceStep]] = {}
    # Build a stable position index so we can sort children at the same path.
    position: dict[str, int] = {s.id: i for i, s in enumerate(run.steps)}
    for s in run.steps:
        path = tuple(run.path_from_root(s.id))
        out.setdefault(path, []).append(s)
    # Sort each bucket
    for path, bucket in out.items():
        bucket.sort(key=lambda x: ((x.started_at or ""), position[x.id]))
    return out


def _compare(a: TraceStep, b: TraceStep, fields: tuple[str, ...]) -> str | None:
    """Return the name of the first differing field, or None.

    AGENT steps use the restricted _AGENT_FIELDS set (no request/response).
    """
    use = _AGENT_FIELDS if a.kind is StepKind.AGENT else fields
    for f in use:
        va = getattr(a, f)
        vb = getattr(b, f)
        if va != vb:
            return f
    return None


def diff(
    run_a: TraceRun,
    run_b: TraceRun,
    *,
    fields: tuple[str, ...] = _DEFAULT_FIELDS,
    strict: bool = False,
) -> Divergence:
    if strict:
        fields = fields + ("tokens_in", "tokens_out", "latency_ms")

    idx_a = _index_by_path(run_a)
    idx_b = _index_by_path(run_b)

    only_a = 0
    only_b = 0
    matched_pairs: list[tuple[TraceStep, TraceStep]] = []

    all_paths = sorted(set(idx_a) | set(idx_b))
    for path in all_paths:
        a_bucket = idx_a.get(path, [])
        b_bucket = idx_b.get(path, [])
        # Align by position within the bucket.
        for i in range(max(len(a_bucket), len(b_bucket))):
            sa = a_bucket[i] if i < len(a_bucket) else None
            sb = b_bucket[i] if i < len(b_bucket) else None
            if sa and sb:
                matched_pairs.append((sa, sb))
            elif sa and not sb:
                only_a += 1
            elif sb and not sa:
                only_b += 1

    # First divergence: walk matched pairs in path-then-order; stop on
    # first differing field.
    first_div_a: TraceStep | None = None
    first_div_b: TraceStep | None = None
    first_div_field: str | None = None
    first_div_path: list[str] | None = None

    # Sort matched pairs by the path-from-root of A (stable).
    matched_pairs.sort(key=lambda pair: run_a.path_from_root(pair[0].id))
    for sa, sb in matched_pairs:
        f = _compare(sa, sb, fields)
        if f is not None:
            first_div_a = sa
            first_div_b = sb
            first_div_field = f
            first_div_path = run_a.path_from_root(sa.id)
            break

    # Build reason string.
    if first_div_path:
        reason = (
            f"first divergence at path {' → '.join(first_div_path)} "
            f"on field {first_div_field!r}"
        )
    elif only_a or only_b:
        reason = f"structural-only: only_in_a={only_a}, only_in_b={only_b}"
    else:
        reason = "no divergence — runs are structurally equivalent"

    return Divergence(
        matched=len(matched_pairs),
        only_in_a=only_a,
        only_in_b=only_b,
        first_divergent_path=first_div_path,
        first_divergent_field=first_div_field,
        first_divergent_a=first_div_a,
        first_divergent_b=first_div_b,
        reason=reason,
    )


def diff_markdown(d: Divergence) -> str:
    """Render a Divergence as a short Markdown report."""
    lines = ["# Diff report\n"]
    lines.append(f"- matched pairs — {d.matched}")
    lines.append(f"- only in A — {d.only_in_a}")
    lines.append(f"- only in B — {d.only_in_b}")
    lines.append(f"- clean — {d.is_clean}")
    lines.append(f"\n**{d.reason}**\n")
    if d.first_divergent_a and d.first_divergent_b:
        lines.append("## First-divergent step\n")
        lines.append(f"- path — `{' → '.join(d.first_divergent_path or [])}`")
        lines.append(f"- field — `{d.first_divergent_field}`")
        lines.append(f"- A: {d.first_divergent_a.name}  "
                     f"({d.first_divergent_a.kind.value})  "
                     f"value={getattr(d.first_divergent_a, d.first_divergent_field or '')!r}")
        lines.append(f"- B: {d.first_divergent_b.name}  "
                     f"({d.first_divergent_b.kind.value})  "
                     f"value={getattr(d.first_divergent_b, d.first_divergent_field or '')!r}")
    return "\n".join(lines) + "\n"

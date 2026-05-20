"""Canonical TraceRun / TraceStep schema — the spine of Hindsight.

Design choices:
  * Flat list of steps with `parent_id` to encode the tree.
    Greppable, awk-able, partial-loadable. Trees are cheap to compute.
  * `extra: dict[str, dict]` namespaced by source ("langsmith", "otel", ...)
    so adapter-local fields survive round-trip without polluting top-level.
  * stdlib only: dataclasses + json. No pydantic.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum


class StepKind(str, Enum):
    """Four kinds of step, exhaustive for v0.1.

    Note: subclassing str makes Enum values JSON-serializable directly.
    """

    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    DECISION = "decision"


@dataclass
class TraceStep:
    """One step in an agent run.

    `request` and `response` are stored as dicts (not strings) so we can
    diff structured fields like message arrays without re-parsing.
    """

    id: str
    parent_id: str | None
    kind: StepKind
    name: str
    request: dict | None = None
    response: dict | None = None
    error: str | None = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None
    started_at: str | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce string -> enum for JSON-loaded objects.
        if isinstance(self.kind, str):
            self.kind = StepKind(self.kind)
        if not isinstance(self.id, str) or not self.id:
            raise ValueError(f"TraceStep.id must be non-empty str, got {self.id!r}")
        if self.parent_id is not None and not isinstance(self.parent_id, str):
            raise ValueError(
                f"TraceStep.parent_id must be str or None, got {self.parent_id!r}"
            )
        if self.tokens_in < 0 or self.tokens_out < 0 or self.latency_ms < 0:
            raise ValueError("counts must be non-negative")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class TraceRun:
    """A complete trace run = run-level metadata + topologically-ordered steps."""

    id: str
    source: str  # "jsonl" | "langsmith" | "otel" | ...
    started_at: str | None = None
    finished_at: str | None = None
    steps: list[TraceStep] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    # ---- tree helpers --------------------------------------------------

    def root(self) -> TraceStep:
        roots = [s for s in self.steps if s.parent_id is None]
        if len(roots) != 1:
            raise ValueError(
                f"TraceRun {self.id!r} must have exactly one root step, "
                f"got {len(roots)}"
            )
        return roots[0]

    def children_of(self, step_id: str) -> list[TraceStep]:
        return [s for s in self.steps if s.parent_id == step_id]

    def step_by_id(self, step_id: str) -> TraceStep:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)

    def path_from_root(self, step_id: str) -> list[str]:
        """Returns the list of (kind, name) tuples from root to this step.

        Used as the structural alignment key in diff. As a stringified list
        for stable hashing.
        """
        path: list[str] = []
        cur: str | None = step_id
        while cur is not None:
            s = self.step_by_id(cur)
            path.append(f"{s.kind.value}:{s.name}")
            cur = s.parent_id
        path.reverse()
        return path

    # ---- aggregates ----------------------------------------------------

    def total_tokens(self) -> tuple[int, int]:
        return (
            sum(s.tokens_in for s in self.steps),
            sum(s.tokens_out for s in self.steps),
        )

    def total_latency_ms(self) -> int:
        return sum(s.latency_ms for s in self.steps)

    # ---- serialization -------------------------------------------------

    def to_jsonl(self) -> str:
        """Canonical JSONL: header line + one step per line, deterministic keys."""
        header = {
            "type": "header",
            "id": self.id,
            "source": self.source,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "extra": self.extra,
        }
        lines = [json.dumps(header, sort_keys=True, separators=(",", ":"))]
        for s in self.steps:
            d = s.to_dict()
            d["type"] = "step"
            lines.append(json.dumps(d, sort_keys=True, separators=(",", ":")))
        return "\n".join(lines) + "\n"

    @classmethod
    def from_jsonl(cls, text: str) -> TraceRun:
        header: dict | None = None
        steps: list[TraceStep] = []
        for raw in text.strip().splitlines():
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            typ = obj.pop("type", None)
            if typ == "header":
                header = obj
            elif typ == "step":
                steps.append(TraceStep(**obj))
            else:
                raise ValueError(f"unknown JSONL row type: {typ!r}")
        if header is None:
            raise ValueError("JSONL is missing the header line")
        return cls(steps=steps, **header)

    # ---- validation ----------------------------------------------------

    def validate(self) -> None:
        ids = {s.id for s in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("duplicate step IDs")
        for s in self.steps:
            if s.parent_id is not None and s.parent_id not in ids:
                raise ValueError(
                    f"step {s.id!r} has parent_id {s.parent_id!r} "
                    f"with no matching step"
                )
        self.root()  # raises if not exactly one root

    # ---- iteration helpers (topological) ------------------------------

    def walk_tree(self) -> Iterable[tuple[int, TraceStep]]:
        """Pre-order walk, yielding (depth, step)."""
        order: list[tuple[int, TraceStep]] = []

        def visit(step_id: str, depth: int) -> None:
            s = self.step_by_id(step_id)
            order.append((depth, s))
            for child in self.children_of(step_id):
                visit(child.id, depth + 1)

        visit(self.root().id, 0)
        return order

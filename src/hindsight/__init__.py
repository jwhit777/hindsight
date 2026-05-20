"""Hindsight — flight recorder + replay debugger for LLM agents.

Spike build, 2026-05-15. v0.0.1.
"""

from .canonical import StepKind, TraceRun, TraceStep
from .diff import Divergence, diff
from .ingest_jsonl import ingest as ingest_jsonl
from .ingest_langsmith import ingest as ingest_langsmith
from .ingest_otel import ingest as ingest_otel
from .show import show
from .stats import stats

__all__ = [
    "StepKind",
    "TraceStep",
    "TraceRun",
    "ingest_jsonl",
    "ingest_langsmith",
    "ingest_otel",
    "show",
    "stats",
    "diff",
    "Divergence",
]

__version__ = "0.0.1"

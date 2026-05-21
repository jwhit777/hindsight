"""Hindsight — flight recorder + replay debugger for LLM agents."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from .base import INGESTERS, BaseIngester, auto_ingest, register
from .canonical import StepKind, TraceRun, TraceStep
from .diff import Divergence, diff
from .ingest_jsonl import ingest as ingest_jsonl
from .ingest_langfuse import ingest as ingest_langfuse
from .ingest_langsmith import ingest as ingest_langsmith
from .ingest_otel import ingest as ingest_otel
from .ingest_subagent_bench import ingest as ingest_subagent_bench
from .replay import AnthropicProvider, MockProvider, OpenAIProvider, Provider, replay
from .show import show
from .stats import stats

__all__ = [
    "StepKind",
    "TraceStep",
    "TraceRun",
    "ingest_jsonl",
    "ingest_langsmith",
    "ingest_otel",
    "ingest_langfuse",
    "ingest_subagent_bench",
    "show",
    "stats",
    "diff",
    "Divergence",
    "replay",
    "Provider",
    "MockProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "BaseIngester",
    "auto_ingest",
    "register",
    "INGESTERS",
]

try:
    __version__ = _pkg_version("hindsight-trace")
except PackageNotFoundError:
    # Running from source without `pip install -e .` (e.g., the spike
    # driver scripts that sys.path-insert ROOT). Mark explicitly.
    __version__ = "0.0.0+source"

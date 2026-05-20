"""Plugin protocol for Hindsight ingest adapters.

BaseIngester is a runtime-checkable Protocol so third-party adapters can
participate without subclassing anything from hindsight.  The global INGESTERS
registry + register() decorator + auto_ingest() dispatcher give callers a
single entry point that dispatches across all registered adapters.

Usage (third-party adapter)::

    from hindsight.base import BaseIngester, register
    from pathlib import Path

    @register
    class MyAdapter:
        name = "my-format"

        def can_ingest(self, path: Path) -> bool:
            return path.suffix == ".myext"

        def ingest(self, path: Path):
            ...  # return TraceRun

Usage (caller)::

    from hindsight.base import auto_ingest
    run = auto_ingest(Path("trace.myext"))

The three built-in adapters (jsonl, langsmith, otel) are *not* modified.
They are wrapped in lightweight _JsonShimIngester instances that peek at a
JSON file's top-level keys to disambiguate format — so all four .json-based
adapters co-exist in the registry without ambiguity.  The Langfuse adapter
is also registered here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from .canonical import TraceRun


@runtime_checkable
class BaseIngester(Protocol):
    """Minimal protocol every Hindsight ingester must satisfy."""

    name: str

    def can_ingest(self, path: Path) -> bool:
        """Return True if this adapter can parse the file at *path*."""
        ...

    def ingest(self, path: Path) -> TraceRun:
        """Parse *path* and return a validated TraceRun."""
        ...


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

INGESTERS: list[BaseIngester] = []


def register(ingester: BaseIngester) -> BaseIngester:
    """Register an ingester instance (or class instance) with the global registry.

    Can be used as a decorator on a class *or* called with an already-constructed
    instance::

        @register
        class FooIngester:
            name = "foo"
            ...

        # — or —
        register(FooIngester())   # if you need __init__ args
    """
    # Support decorator-on-class usage: instantiate if a class is passed.
    if isinstance(ingester, type):
        ingester = ingester()
    if not isinstance(ingester, BaseIngester):
        raise TypeError(
            f"{ingester!r} does not satisfy BaseIngester protocol "
            f"(needs .name, .can_ingest(), .ingest())"
        )
    INGESTERS.append(ingester)
    return ingester


def auto_ingest(path: Path) -> TraceRun:
    """Walk INGESTERS in registration order; return the first match.

    Raises FileNotFoundError if *path* does not exist, and ValueError if no
    registered adapter claims the file.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    for ing in INGESTERS:
        if ing.can_ingest(p):
            return ing.ingest(p)
    raise ValueError(
        f"No registered ingester can handle {p!r}.  "
        f"Registered: {[i.name for i in INGESTERS]}"
    )


# ---------------------------------------------------------------------------
# Shims for the three built-in adapters (wrap without modifying them)
# ---------------------------------------------------------------------------

class _ShimIngester:
    """Wraps a bare ingest(path) function as a BaseIngester.

    For .jsonl files (suffix-only check) and any format with a unique
    top-level key, this is sufficient.
    """

    def __init__(self, name: str, suffix: str, fn) -> None:
        self.name = name
        self._suffix = suffix
        self._fn = fn

    def can_ingest(self, path: Path) -> bool:
        return path.suffix == self._suffix

    def ingest(self, path: Path) -> TraceRun:
        return self._fn(path)


def _peek_json_keys(path: Path) -> set[str]:
    """Read just enough of a JSON file to get its top-level keys.

    Parses the full file but only returns the top-level key set.  Used by
    the JSON-based shims to disambiguate format without full parsing.
    """
    try:
        obj = json.loads(path.read_text())
        if isinstance(obj, dict):
            return set(obj.keys())
    except (OSError, json.JSONDecodeError):
        pass
    return set()


class _JsonShimIngester:
    """Content-sniffing shim for .json-based formats.

    ``required_keys`` is a set of top-level JSON keys that *must* be present
    for this adapter to claim the file.  ``forbidden_keys`` are keys whose
    presence disqualifies the file (used to break ties between formats that
    share some keys).
    """

    def __init__(
        self,
        name: str,
        fn,
        required_keys: set[str],
        forbidden_keys: set[str] | None = None,
    ) -> None:
        self.name = name
        self._fn = fn
        self._required = required_keys
        self._forbidden = forbidden_keys or set()

    def can_ingest(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        keys = _peek_json_keys(path)
        return self._required <= keys and not (self._forbidden & keys)

    def ingest(self, path: Path) -> TraceRun:
        return self._fn(path)


def _register_builtins() -> None:
    """Register jsonl / langsmith / otel / langfuse shims at import time.

    These modules are NOT modified — they are wrapped here.

    Disambiguation logic for .json files (checked in registration order):
      - OTEL: must have "resourceSpans" at top level.
      - Langfuse: must have "observations" at top level (and not "resourceSpans").
      - LangSmith: must have "id" and "run_type" (and not "resourceSpans" /
        "observations") — the classic run-tree export shape.
    """
    # The package's __init__ re-exports `from .ingest_jsonl import ingest as
    # ingest_jsonl`, so `from . import ingest_jsonl` resolves to the FUNCTION,
    # not the module. Pull the functions in directly to avoid that shadow.
    from .ingest_jsonl import ingest as _ingest_jsonl_fn  # noqa: PLC0415
    from .ingest_langfuse import ingest as _ingest_langfuse_fn  # noqa: PLC0415
    from .ingest_langsmith import ingest as _ingest_langsmith_fn  # noqa: PLC0415
    from .ingest_otel import ingest as _ingest_otel_fn  # noqa: PLC0415

    INGESTERS.append(_ShimIngester("jsonl", ".jsonl", _ingest_jsonl_fn))

    INGESTERS.append(
        _JsonShimIngester(
            name="otel",
            fn=_ingest_otel_fn,
            required_keys={"resourceSpans"},
        )
    )

    INGESTERS.append(
        _JsonShimIngester(
            name="langfuse",
            fn=_ingest_langfuse_fn,
            required_keys={"observations"},
            forbidden_keys={"resourceSpans"},
        )
    )

    INGESTERS.append(
        _JsonShimIngester(
            name="langsmith",
            fn=_ingest_langsmith_fn,
            required_keys={"id", "run_type"},
            forbidden_keys={"resourceSpans", "observations"},
        )
    )


_register_builtins()

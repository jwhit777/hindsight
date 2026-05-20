"""Ingest Hindsight-native JSONL.

This is the *identity* adapter: the canonical format on disk.
Other adapters must round-trip through this format losslessly.
"""

from __future__ import annotations

import pathlib

from .canonical import TraceRun


def ingest(path: pathlib.Path | str) -> TraceRun:
    p = pathlib.Path(path)
    text = p.read_text()
    run = TraceRun.from_jsonl(text)
    run.validate()
    # Tag canonical runs as source="jsonl" only if not already labeled.
    if not run.source:
        run.source = "jsonl"
    return run

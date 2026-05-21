"""Hindsight spike self-tests — 10 assertions over the spike.

Run:
    python3 test_spike.py
    # or
    python3 -m unittest test_spike

Properties tested:
  A. cross-format structural identity
  B. lossless JSONL round-trip
  C. divergence detection on three designed pairs:
        C1 — LLM-content divergence (response value)
        C2 — Tool-error divergence (error field)
        C3 — Routing divergence (response field at the router LLM step)
  D. stats math (totals match summed step values)
  E. tree depth (10-deep linear chain renders all 10 lines)
  F. extra-field preservation across LangSmith round-trip
"""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from hindsight import (
    diff,
    ingest_jsonl,
    ingest_langsmith,
    ingest_otel,
    show,
)
from hindsight.base import auto_ingest
from hindsight.canonical import StepKind, TraceRun, TraceStep
from hindsight.ingest_langfuse import ingest as ingest_langfuse
from hindsight.stats import stats

FIX = ROOT.parent / "fixtures"


def _normalize(run: TraceRun) -> dict:
    return {
        "step_count": len(run.steps),
        "steps": [
            {
                "path": run.path_from_root(s.id),
                "kind": s.kind.value,
                "name": s.name,
                "model": s.model,
                "tokens_in": s.tokens_in,
                "tokens_out": s.tokens_out,
                "error": s.error,
            }
            for s in run.steps
        ],
    }


def _build_synthetic_run(depth: int) -> TraceRun:
    """Build a linear parent chain of `depth` AGENT steps for tree-depth test."""
    steps = []
    for i in range(depth):
        steps.append(
            TraceStep(
                id=f"x{i}",
                parent_id=f"x{i-1}" if i > 0 else None,
                kind=StepKind.AGENT,
                name=f"level{i}",
            )
        )
    return TraceRun(id="synth", source="jsonl", steps=steps)


def _build_pair_with_field_div(field: str, value_a, value_b) -> tuple[TraceRun, TraceRun]:
    """Build two two-step runs that differ only in the given field on step 2."""
    steps_a = [
        TraceStep(id="r", parent_id=None, kind=StepKind.AGENT, name="root"),
        TraceStep(
            id="c", parent_id="r", kind=StepKind.LLM, name="call", model="m",
            response={"x": "ok"},
        ),
    ]
    steps_b = [
        TraceStep(id="r", parent_id=None, kind=StepKind.AGENT, name="root"),
        TraceStep(
            id="c", parent_id="r", kind=StepKind.LLM, name="call", model="m",
            response={"x": "ok"},
        ),
    ]
    # Apply the divergence to step 2 of each run.
    setattr(steps_a[1], field, value_a)
    setattr(steps_b[1], field, value_b)
    return (
        TraceRun(id="a", source="jsonl", steps=steps_a),
        TraceRun(id="b", source="jsonl", steps=steps_b),
    )


class SpikeTests(unittest.TestCase):

    # ---- A: cross-format structural identity ----

    def test_A_cross_format_identity(self):
        a = ingest_jsonl(FIX / "canonical_good.jsonl")
        b = ingest_langsmith(FIX / "langsmith_good.json")
        c = ingest_otel(FIX / "otel_good.json")
        d = ingest_langfuse(FIX / "langfuse_good.json")
        self.assertEqual(
            _normalize(a), _normalize(b),
            "JSONL and LangSmith produced different structural payloads",
        )
        self.assertEqual(
            _normalize(a), _normalize(c),
            "JSONL and OTEL produced different structural payloads",
        )
        self.assertEqual(
            _normalize(a), _normalize(d),
            "JSONL and Langfuse produced different structural payloads",
        )

    # ---- B: lossless round-trip ----

    def test_B_round_trip(self):
        a = ingest_jsonl(FIX / "canonical_good.jsonl")
        s = a.to_jsonl()
        b = TraceRun.from_jsonl(s)
        b.validate()
        self.assertEqual(_normalize(a), _normalize(b))
        # And the byte-identical case:
        self.assertEqual(s, b.to_jsonl())

    # ---- C1: LLM-content divergence ----

    def test_C1_llm_content_divergence(self):
        good = ingest_jsonl(FIX / "canonical_llm_content_good.jsonl")
        bad = ingest_jsonl(FIX / "canonical_llm_content_bad.jsonl")
        d = diff(good, bad)
        self.assertFalse(d.is_clean)
        self.assertEqual(d.first_divergent_field, "response")
        self.assertTrue(
            (d.first_divergent_path or [])[-1] == "llm:summarize",
            f"expected path to end with 'llm:summarize'; got {d.first_divergent_path}",
        )

    # ---- C2: Tool-error divergence ----

    def test_C2_tool_error_divergence(self):
        good = ingest_jsonl(FIX / "canonical_tool_error_good.jsonl")
        bad = ingest_jsonl(FIX / "canonical_tool_error_bad.jsonl")
        d = diff(good, bad)
        self.assertFalse(d.is_clean)
        self.assertEqual(d.first_divergent_field, "error")
        self.assertTrue(
            (d.first_divergent_path or [])[-1] == "tool:get_quote",
            f"expected path to end with 'tool:get_quote'; got {d.first_divergent_path}",
        )

    # ---- C3: Routing divergence on real fixtures ----

    def test_C3_routing_divergence_on_fixtures(self):
        good = ingest_jsonl(FIX / "canonical_good.jsonl")
        bad = ingest_jsonl(FIX / "canonical_bad.jsonl")
        d = diff(good, bad)
        self.assertFalse(d.is_clean)
        # The router LLM step's response should be the first divergence.
        self.assertEqual(
            d.first_divergent_path,
            ["agent:orchestrator", "llm:router"],
            f"expected divergence at router; got {d.first_divergent_path}",
        )
        self.assertEqual(d.first_divergent_field, "response")

    # ---- C4 / C5: strict-mode catches token / latency divergence ----

    def test_C4_tokens_diff_only_in_strict_mode(self):
        good = ingest_jsonl(FIX / "canonical_token_div_good.jsonl")
        bad = ingest_jsonl(FIX / "canonical_token_div_bad.jsonl")
        # Default diff: tokens_out is not in _DEFAULT_FIELDS, so clean.
        self.assertTrue(diff(good, bad).is_clean)
        # Strict diff: tokens_out is compared and diverges at s5 (llm:analyse).
        d = diff(good, bad, strict=True)
        self.assertFalse(d.is_clean)
        self.assertEqual(d.first_divergent_field, "tokens_out")
        self.assertEqual(d.first_divergent_path[-1], "llm:analyse")

    def test_C5_latency_diff_only_in_strict_mode(self):
        good = ingest_jsonl(FIX / "canonical_latency_div_good.jsonl")
        bad = ingest_jsonl(FIX / "canonical_latency_div_bad.jsonl")
        # Default diff: clean (latency_ms not in default fields).
        self.assertTrue(diff(good, bad).is_clean)
        # Strict diff: latency_ms diverges at s5.
        d = diff(good, bad, strict=True)
        self.assertFalse(d.is_clean)
        self.assertEqual(d.first_divergent_field, "latency_ms")
        self.assertEqual(d.first_divergent_path[-1], "llm:analyse")

    def test_C6_default_diff_ignores_strict_fields_on_good_pair(self):
        # Sanity guard: identical runs are clean in both modes.
        good = ingest_jsonl(FIX / "canonical_good.jsonl")
        again = ingest_jsonl(FIX / "canonical_good.jsonl")
        self.assertTrue(diff(good, again).is_clean)
        self.assertTrue(diff(good, again, strict=True).is_clean)

    def test_C7_strict_mode_still_catches_routing_divergence(self):
        # Strict mode adds fields; it does not remove or replace the default set.
        # The existing router divergence (response field) must still fire.
        good = ingest_jsonl(FIX / "canonical_good.jsonl")
        bad = ingest_jsonl(FIX / "canonical_bad.jsonl")
        d = diff(good, bad, strict=True)
        self.assertFalse(d.is_clean)
        self.assertEqual(d.first_divergent_field, "response")
        self.assertEqual(
            d.first_divergent_path,
            ["agent:orchestrator", "llm:router"],
        )

    # ---- D: stats math ----

    def test_D_stats_math(self):
        a = ingest_jsonl(FIX / "canonical_good.jsonl")
        s = stats(a)
        # Compute expected sums from raw steps.
        sum_in = sum(st.tokens_in for st in a.steps)
        sum_out = sum(st.tokens_out for st in a.steps)
        self.assertEqual(s["tokens"]["in"], sum_in)
        self.assertEqual(s["tokens"]["out"], sum_out)
        self.assertEqual(
            s["latency_ms"]["total"],
            sum(st.latency_ms for st in a.steps),
        )
        # per_kind counts add up to total steps.
        self.assertEqual(sum(s["per_kind"].values()), len(a.steps))

    # ---- E: tree depth ----

    def test_E_tree_depth(self):
        run = _build_synthetic_run(10)
        text = show(run, color=False)
        # Each level must appear once.
        for i in range(10):
            self.assertIn(f"level{i}", text)

    # ---- F: LangSmith extra-field preservation ----

    def test_F_langsmith_extra_preserved(self):
        b = ingest_langsmith(FIX / "langsmith_good.json")
        # The first LLM step (router) should have langsmith provenance.
        router = next(s for s in b.steps if s.name == "router")
        self.assertIn("langsmith", router.extra)
        self.assertEqual(router.extra["langsmith"]["run_type"], "llm")

    # ---- G: OTEL parent linkage ----

    def test_G_otel_parent_linkage(self):
        c = ingest_otel(FIX / "otel_good.json")
        # Find the analyse step; its parent should be the stock-analyst agent.
        # The OTEL adapter prefers gen_ai.agent.name over the raw span name,
        # so the canonical step name is "stock-analyst".
        analyse = next(s for s in c.steps if s.name == "analyse")
        parent = c.step_by_id(analyse.parent_id)
        self.assertEqual(parent.name, "stock-analyst")
        self.assertEqual(parent.kind, StepKind.AGENT)

    # ---- H: diff clean on identical runs ----

    def test_H_diff_clean_identical(self):
        a = ingest_jsonl(FIX / "canonical_good.jsonl")
        b = ingest_jsonl(FIX / "canonical_good.jsonl")
        d = diff(a, b)
        self.assertTrue(d.is_clean, f"expected clean diff, got {d.reason}")

    # ---- I: validate() catches dangling parents ----

    def test_I_validate_catches_dangling_parent(self):
        steps = [
            TraceStep(id="r", parent_id=None, kind=StepKind.AGENT, name="root"),
            TraceStep(id="orphan", parent_id="nonexistent",
                      kind=StepKind.LLM, name="hi"),
        ]
        run = TraceRun(id="x", source="jsonl", steps=steps)
        with self.assertRaises(ValueError):
            run.validate()

    # ---- J: Langfuse round-trip ----

    def test_J_langfuse_round_trip(self):
        """Langfuse fixture round-trips losslessly through to_jsonl / from_jsonl."""
        d = ingest_langfuse(FIX / "langfuse_good.json")
        serialized = d.to_jsonl()
        d2 = TraceRun.from_jsonl(serialized)
        d2.validate()
        self.assertEqual(_normalize(d), _normalize(d2))
        # Byte-identical round-trip.
        self.assertEqual(serialized, d2.to_jsonl())

    # ---- K: plugin protocol dispatch ----

    def test_K_plugin_protocol_dispatch(self):
        """auto_ingest() on each of the four fixtures returns an equivalent
        TraceRun to the direct adapter call.
        """
        pairs = [
            (FIX / "canonical_good.jsonl", ingest_jsonl),
            (FIX / "langsmith_good.json",  ingest_langsmith),
            (FIX / "otel_good.json",       ingest_otel),
            (FIX / "langfuse_good.json",   ingest_langfuse),
        ]
        for path, direct_fn in pairs:
            with self.subTest(fixture=path.name):
                via_auto   = auto_ingest(path)
                via_direct = direct_fn(path)
                self.assertEqual(
                    _normalize(via_auto),
                    _normalize(via_direct),
                    f"auto_ingest diverged from direct call for {path.name}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Hindsight replay self-tests.

Run:
    python3 -m unittest test_replay
    # or with the spike harness:
    python3 -m unittest discover -s src -p 'test_*.py'

Properties tested:
  1. replay from step 0 with MockProvider is a structural identity on
     fixtures/canonical_good.jsonl
  2. replay from step 3 leaves steps 0..2 byte-identical and re-derives
     steps 3..end through a counting provider — proving the cutoff works
  3. `model` override mutates only LLM steps in the tail; AGENT/TOOL/
     DECISION steps are copied verbatim
  4. invalid `from_step` (unknown id or out-of-range int) raises ValueError
  5. importing `hindsight.replay` does not import `anthropic` — the SDK is
     in the [live] extra, the default install must not need it
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from hindsight import ingest_jsonl
from hindsight.canonical import StepKind, TraceStep
from hindsight.replay import MockProvider, Provider, replay

FIX = ROOT.parent / "fixtures"


def _normalize_step(s: TraceStep) -> dict:
    """Comparable snapshot of a step. Skips `extra` because replay() stamps
    replay-provenance onto the run's `extra`, not steps'."""
    return {
        "id": s.id,
        "parent_id": s.parent_id,
        "kind": s.kind.value,
        "name": s.name,
        "model": s.model,
        "request": s.request,
        "response": s.response,
        "error": s.error,
        "latency_ms": s.latency_ms,
        "tokens_in": s.tokens_in,
        "tokens_out": s.tokens_out,
        "started_at": s.started_at,
    }


class _CountingProvider:
    """Test double — wraps MockProvider, counts simulate() calls. Lets us
    assert *exactly which* steps were routed through the provider."""

    name = "counting"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._inner = MockProvider()

    def simulate(self, step: TraceStep, *, model: str | None = None) -> TraceStep:
        self.calls.append(step.id)
        return self._inner.simulate(step, model=model)


class ReplayTests(unittest.TestCase):

    # ---- 1: identity replay from step 0 ----

    def test_replay_from_step_0_identity_with_mock(self) -> None:
        run = ingest_jsonl(FIX / "canonical_good.jsonl")
        out = replay(run, 0)  # MockProvider default
        self.assertEqual(len(out.steps), len(run.steps))
        for a, b in zip(run.steps, out.steps):
            self.assertEqual(_normalize_step(a), _normalize_step(b))
        # Provenance landed on the run-level extra:
        self.assertEqual(out.extra["replay"]["provider"], "mock")
        self.assertEqual(out.extra["replay"]["from_index"], 0)
        self.assertEqual(out.extra["replay"]["from_step"], run.steps[0].id)
        self.assertIsNone(out.extra["replay"]["model_override"])
        self.assertFalse(out.extra["replay"]["live"])

    # ---- 2: cutoff respected, tail goes through provider ----

    def test_replay_from_step_3_replays_only_tail(self) -> None:
        run = ingest_jsonl(FIX / "canonical_good.jsonl")
        prov = _CountingProvider()
        # Use the id of step at index 3 so we exercise the id-based lookup
        # path while still pinning the cutoff to index 3.
        cutoff_id = run.steps[3].id
        out = replay(run, cutoff_id, provider=prov)

        # Steps 0..2: byte-identical.
        for i in range(3):
            self.assertEqual(_normalize_step(run.steps[i]), _normalize_step(out.steps[i]))

        # Steps 3..end: every LLM step was routed through the provider,
        # every non-LLM step was not.
        expected_calls = [
            s.id for s in run.steps[3:] if s.kind is StepKind.LLM
        ]
        self.assertEqual(prov.calls, expected_calls)
        # And the structural payload is still equivalent (MockProvider is
        # the identity).
        for i in range(3, len(run.steps)):
            self.assertEqual(_normalize_step(run.steps[i]), _normalize_step(out.steps[i]))

    # ---- 3: model override only touches LLM steps in the tail ----

    def test_replay_with_model_override_changes_llm_steps(self) -> None:
        run = ingest_jsonl(FIX / "canonical_good.jsonl")
        new_model = "claude-opus-4-7"
        out = replay(run, 0, model=new_model)

        for orig, repl in zip(run.steps, out.steps):
            if orig.kind is StepKind.LLM:
                self.assertEqual(repl.model, new_model)
            else:
                # AGENT / TOOL / DECISION: model field untouched.
                self.assertEqual(repl.model, orig.model)

        # Override is recorded in run-level extra.
        self.assertEqual(out.extra["replay"]["model_override"], new_model)

    # ---- 4: invalid step id raises ValueError ----

    def test_replay_invalid_step_id_raises(self) -> None:
        run = ingest_jsonl(FIX / "canonical_good.jsonl")
        # Unknown id.
        with self.assertRaises(ValueError):
            replay(run, "does-not-exist")
        # Out-of-range int.
        with self.assertRaises(ValueError):
            replay(run, len(run.steps))
        with self.assertRaises(ValueError):
            replay(run, -1)

    # ---- 5: lazy anthropic import ----

    def test_anthropic_provider_lazy_import(self) -> None:
        """`from hindsight.replay import replay, MockProvider` must work
        without the `anthropic` SDK installed. We can't uninstall the SDK
        from inside the test, so we shell out to a fresh Python whose
        sys.modules can't resolve `anthropic` and run the import there."""
        code = (
            "import sys\n"
            # Poison anthropic: any attempt to import it raises ImportError.
            "class _Blocker:\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name == 'anthropic' or name.startswith('anthropic.'):\n"
            "            raise ImportError('blocked by test')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Blocker())\n"
            "from hindsight.replay import replay, MockProvider, Provider  # noqa\n"
            "from hindsight import ingest_jsonl\n"
            "import pathlib\n"
            f"run = ingest_jsonl(pathlib.Path({str(FIX / 'canonical_good.jsonl')!r}))\n"
            "out = replay(run, 0)\n"
            "assert len(out.steps) == len(run.steps)\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"lazy-import subprocess failed.\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn("OK", result.stdout)

    # ---- bonus: Provider is a runtime-checkable Protocol ----

    def test_mock_provider_satisfies_protocol(self) -> None:
        self.assertIsInstance(MockProvider(), Provider)

    # ---- bonus: replay output is a valid TraceRun ----

    def test_replay_output_validates(self) -> None:
        run = ingest_jsonl(FIX / "canonical_good.jsonl")
        out = replay(run, 0)
        out.validate()  # raises on dangling parents / dup ids / multi-root


if __name__ == "__main__":
    unittest.main(verbosity=2)

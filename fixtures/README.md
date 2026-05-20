# fixtures/

Trace fixtures used by `spike_run.py` and `test_spike.py`.

The first three are the **same logical run** in three formats:

* `canonical_good.jsonl` — Hindsight-native JSONL (the canonical format).
* `langsmith_good.json` — same run, expressed as a LangSmith run-tree export.
* `otel_good.json` — same run, expressed as OTEL GenAI spans.

The cross-format-identity test asserts that all three ingest into a
byte-identical canonical when re-serialized via `TraceRun.to_jsonl()`.

The fourth fixture is the **paired-but-divergent** run used for diff testing:

* `canonical_bad.jsonl` — same starting prompt, but the router LLM step
  returns a different decision, leading the agent down the wrong sub-agent
  and producing a wrong final answer.

Diff(`canonical_good.jsonl`, `canonical_bad.jsonl`) must report the first
divergence at the router LLM step (`response` field).

These fixtures are deliberately tiny (7 steps) so the spike runs in
milliseconds.

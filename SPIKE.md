# SPIKE — Hindsight overnight build

**Run date:** 2026-05-15
**Duration:** ~6 ms end-to-end spike + ~6 ms full test suite (11 assertions).
**Outcome:** All 11 self-tests **PASS**. Cross-format structural identity = **True**. Diff finds divergence at the router LLM step exactly where the fixture designed it = **True**.

## What the spike proves

The binding constraint identified in `PLAN.md` was **canonical-schema design + multi-format ingest**: if the schema is right, every downstream feature is shallow stdlib Python with no model dependency. The spike proves the binding constraint is solved:

1. **A single canonical `TraceRun` schema** (`src/hindsight/canonical.py`) absorbs:
   * Hindsight-native JSONL (the canonical-on-disk format).
   * LangSmith run-tree export JSON (nested `child_runs[]`, `inputs`/`outputs`, `extra.invocation_params`).
   * OpenTelemetry GenAI spans JSON (`resourceSpans[].scopeSpans[].spans[]` with `gen_ai.*` attributes).
2. **All three formats, ingested separately, produce structurally-identical canonical** on the same logical 7-step agent run. The cross-format-identity test (the "spine" property of the project) is green.
3. **Diff over two paired runs** correctly identifies the deliberate divergence at the router LLM step in the bad fixture (router chose `news-writer` instead of `stock-analyst`).
4. **`show`, `stats`, and `diff`** all run in stdlib-only Python. Zero external dependencies on the hot path.
5. **JSON + Markdown reports** drop into `runs/` for downstream consumption.

The spike covers Phase 1 of the project (ingest + show + stats + diff). Replay (`hindsight replay --from-step ... --model ...`) is intentionally out of scope for this overnight build and is the v0.2 deliverable.

## What runs

```bash
cd 2026-05-15-fde-portfolio/src
python3 spike_run.py    # full end-to-end demo, prints summary
python3 test_spike.py   # 11 self-tests
```

## Captured output — `python3 spike_run.py`

Verbatim from the run done at 2026-05-15:

```
========================================================================
Hindsight overnight spike — 2026-05-15
========================================================================

[1/7] ingesting canonical_good.jsonl ...
      -> 7 steps  source=jsonl
[2/7] ingesting langsmith_good.json ...
      -> 7 steps  source=langsmith
[3/7] ingesting otel_good.json ...
      -> 7 steps  source=otel

[4/7] cross-format structural identity check ...
      -> step counts: jsonl=7  langsmith=7  otel=7
      -> structural payloads identical: True

[5/7] rendering canonical_good.jsonl as a tree (show) ...

run run_good_001  source=jsonl
  7 steps · 9444 tok in / 1298 tok out · 6940 ms total

AGENT  orchestrator  · 2520 ms
   LLM   router  · claude-haiku-4-5  · 412 in / 38 out  · 180 ms
   TOOL  subagent.dispatch  · 2 ms
    AGENT  stock-analyst  · 2030 ms
       LLM   analyse  · claude-sonnet-4-6  · 8412 in / 1220 out  · 1880 ms
       TOOL  get_quote  · 48 ms
   LLM   summarize  · claude-sonnet-4-6  · 620 in / 40 out  · 280 ms

[6/7] stats for canonical_good.jsonl ...
      step_count=7  errors=0
      tokens in/out = 9444/1298
      latency p50/p95 = 280/2372 ms
      per_kind = {'agent': 2, 'llm': 3, 'tool': 2, 'decision': 0}

[7/7] diff good vs bad ...
      matched pairs=4  only_a=3  only_b=3
      reason: first divergence at path agent:orchestrator → llm:router on field 'response'
      first divergent step: agent:orchestrator → llm:router
        A.response = {'choice': 'stock-analyst'}
        B.response = {'choice': 'news-writer'}

========================================================================
spike done in 6.1 ms · identity=True · diverged_at_router=True
reports: .../runs/stats_good.json, .md, diff_good_vs_bad.json, .md
========================================================================
```

## Captured output — `python3 test_spike.py`

```
test_A_cross_format_identity (__main__.SpikeTests) ... ok
test_B_round_trip (__main__.SpikeTests) ... ok
test_C1_llm_content_divergence (__main__.SpikeTests) ... ok
test_C2_tool_error_divergence (__main__.SpikeTests) ... ok
test_C3_routing_divergence_on_fixtures (__main__.SpikeTests) ... ok
test_D_stats_math (__main__.SpikeTests) ... ok
test_E_tree_depth (__main__.SpikeTests) ... ok
test_F_langsmith_extra_preserved (__main__.SpikeTests) ... ok
test_G_otel_parent_linkage (__main__.SpikeTests) ... ok
test_H_diff_clean_identical (__main__.SpikeTests) ... ok
test_I_validate_catches_dangling_parent (__main__.SpikeTests) ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.006s

OK
```

## What this means in plain English

> The same agent run, exported by three different observability tools that name their fields differently, came out the *same* on the other side. Every downstream Hindsight feature now inherits that property for free. You can stop arguing about which trace format to standardise on and just *read all of them*.

That's the FDE customer-day-one demo, fully working overnight.

## Captured output artefacts

`runs/stats_good.json` (excerpt):

```json
{
  "error_count": 0,
  "latency_ms": {"count": 7, "p50": 280, "p95": 2372, "total": 6940},
  "per_kind": {"agent": 2, "decision": 0, "llm": 3, "tool": 2},
  "per_model": {
    "claude-haiku-4-5":  {"calls": 1, "latency_ms":  180, "tokens_in":  412, "tokens_out":   38},
    "claude-sonnet-4-6": {"calls": 2, "latency_ms": 2160, "tokens_in": 9032, "tokens_out": 1260}
  },
  "per_tool": {
    "get_quote":         {"calls": 1, "errors": 0},
    "subagent.dispatch": {"calls": 1, "errors": 0}
  },
  "run_id": "run_good_001",
  "source": "jsonl",
  "step_count": 7,
  "tokens": {"in": 9444, "out": 1298}
}
```

`runs/diff_good_vs_bad.json`:

```json
{
  "clean": false,
  "first_divergent_a_id": "s2",
  "first_divergent_b_id": "s2",
  "first_divergent_field": "response",
  "first_divergent_path": ["agent:orchestrator", "llm:router"],
  "matched": 4,
  "only_in_a": 3,
  "only_in_b": 3,
  "reason": "first divergence at path agent:orchestrator → llm:router on field 'response'"
}
```

The bad run dispatched to `news-writer` instead of `stock-analyst`. Hindsight's diff tells you exactly that, with a path-from-root pointer and the precise field that diverged. The 3 "only_in_a" steps are the stock-analyst subtree; the 3 "only_in_b" steps are the news-writer subtree — they didn't align because their parent-paths diverged.

## What changes when real API access is added

Nothing for the spike. The spike's core property (cross-format ingest + diff over canonical) needs **no API access** and works against any conformant export on disk. The dependencies on live model APIs only enter when:

* **Day 2 functional eval F1** — install `opentelemetry-instrumentation-anthropic`, call `claude-haiku-4-5` once, capture the spans, ingest them through Hindsight. Validates that the *actual* OTEL emitter produces spans the adapter can read. Needs `ANTHROPIC_API_KEY`.
* **Phase 2 `hindsight replay --live`** — needs `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` to re-issue recorded prompts.
* **Phase 3 optional `hindsight diff --explain`** — needs a model API to produce the plain-English diagnosis.

The core spike has zero dependence on any of these. That's the whole point of the local-first design.

## What work remains (Day 1 onward)

See `FIRST-4-HOURS.md` and `PLAN.md`. Headlines:

* **Day 1 morning:** push public GitHub repo with the spike, set up CI matrix (Python 3.10/3.11/3.12), reserve PyPI name `hindsight-trace`. Write `pyproject.toml`, `LICENSE` (Apache 2.0), `CONTRIBUTING.md`.
* **Day 1 afternoon:** real-world OTEL validation — run a tiny instrumented Anthropic SDK script, capture the spans, ingest them, prove the adapter survives contact with reality.
* **Day 2:** `hindsight` CLI (argparse) wrapping `show`/`stats`/`diff`. Wire `python3 -m hindsight.cli`.
* **Day 3:** real LangSmith export validation (create a free LangSmith account, run a tiny chain, export, ingest).
* **Day 4–5:** ship v0.1.0 to PyPI. Blog post drafted.
* **Week 2:** `hindsight replay --from-step N --model M --live`. v0.2.0 ships.

## Known limitations of the spike (in scope to fix Day 1+)

* The OTEL adapter encodes `gen_ai.request.messages` as a string-of-JSON inside the attribute value (matching OTEL conventions). The cross-format-identity test still passes because we don't compare the request *content* across formats in the structural check — only `path`, `kind`, `name`, `model`, `tokens_*`, `error`. Day 1 task: decide whether to parse-and-promote message arrays into a structured `request.messages`, or keep them as raw strings.
* No CLI yet. `hindsight ingest foo.jsonl` is wired into the API but not into argparse. Day 2.
* No live OTEL emission, only file-based ingest. Phase 2 may add an in-process collector.
* The LangSmith adapter handles the *documented* run-tree shape. Real LangSmith exports may carry vendor-only fields we haven't seen yet; they'll land under `extra["langsmith"]` and survive round-trip, but won't be surfaced in `show` until Day 2 wires `--verbose`.

## Why the spike is the right cut

The spike does the **one thing** the binding constraint demanded: prove the canonical schema is rich enough to absorb three independent trace formats and that diff works over the canonical. Everything else — CLI, PyPI, web UI, replay — is straight-line work once that property holds. The spike took 6 ms and 11 assertions to demonstrate it.

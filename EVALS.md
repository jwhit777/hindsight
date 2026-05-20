# EVALS

How Hindsight knows it works. Two layers: **self-tests on the codebase** (run on every commit, catch regressions) and **functional evals on real data** (run before each release, catch real-world drift).

The discipline matches Skillsmith, MCP Probe, and Sub-Agent Bench: stdlib-only fast tests, fixtures committed to the repo, every metric reported in JSON + Markdown.

---

## Self-tests (CI, every commit)

Lives in `src/test_spike.py` (v0.1) and grows into `tests/test_*.py` from Day 1.

### A. Cross-format identity (the spine of the project)

**Claim:** The same logical trace, exported as canonical JSONL, LangSmith JSON, and OTEL GenAI spans JSON, ingests into byte-identical canonical when serialized back to JSONL.

**Why it matters:** This is the project's correctness property. If this passes, downstream features inherit correctness. If this fails, every downstream feature is broken in a subtle way.

**Test:** Three fixture files that encode the *same* run in three formats. Ingest each, serialize to canonical JSONL, assert `sha256(a) == sha256(b) == sha256(c)`.

### B. Lossless round-trip

**Claim:** `canonical → JSONL → canonical` produces the same in-memory object graph.

**Test:** Round-trip a known `TraceRun`, assert all fields equal including `extra` dicts.

### C. Divergence detection

**Claim:** Given a pair of traces with a *known designed* divergence at step `k`, `diff(a, b).first_divergent_step` returns step `k`.

**Test:** Three fixture pairs:
* C1 — LLM-content divergence (Haiku said "hold" on the good run, "sell" on the bad).
* C2 — Tool-error divergence (good run got 200, bad got rate-limited).
* C3 — Routing divergence (good run dispatched to stock-analyst, bad dispatched to news-writer).

### D. Stats math

**Claim:** Reported totals match summed step values.

**Test:** Construct a `TraceRun` with known token sums; assert `run.total_tokens()` equals the sum.

### E. Tree depth

**Claim:** `show()` renders arbitrary nesting depth without truncation or crash.

**Test:** Construct a 10-deep linear parent chain; render; assert all 10 lines present.

### F. Cross-format identity preserves `extra`

**Claim:** Adapter-local fields land in `extra[<source>]` and survive round-trip.

**Test:** Ingest a LangSmith fixture with a vendor-specific field, round-trip, assert the field is still readable under `extra["langsmith"]`.

### G. CLI smoke

**Claim:** `python3 -m hindsight.cli show fixtures/canonical_good.jsonl` exits 0 and emits at least N lines.

**Test:** Run via subprocess.

### Spike test count (overnight): **10 assertions covering A through F.** CLI smoke (G) is added Day 1.

---

## Functional evals (pre-release, on real data)

### F1. Real OTEL ingest from a live Anthropic instrumentation

**Setup:** install `opentelemetry-instrumentation-anthropic`, run a tiny script that calls `claude-haiku-4-5` once, capture the spans to JSON. Ingest with Hindsight.

**Pass:** Ingest succeeds, canonical has exactly 1 LLM step, model is `claude-haiku-4-5`, `tokens_in` and `tokens_out` are non-zero. Verified Day 2.

### F2. Real LangSmith export

**Setup:** Create one LangSmith account, run any small chain, export the run to JSON.

**Pass:** Ingest succeeds; canonical step kind / name / model reflect the chain accurately; round-trip JSONL is valid.

### F3. Diff a real failing run from a Justin's triptych

**Setup:** Sub-Agent Bench produces JSON run logs. Run a Sub-Agent Bench eval, take one passing trace and one failing trace, run `hindsight diff`.

**Pass:** The diff's `first_divergent_step` corresponds to the assertion-failing step the Sub-Agent Bench judge flagged.

### F4. Replay (v0.2 only)

**Setup:** Take F3's failing trace, run `hindsight replay --from-step <k> --model claude-sonnet-4-6 --live`.

**Pass:** The replayed run completes; its tokens and latency are reasonable (within 3× of original); the final response is *different* from the bad run's final response.

---

## What counts as "good enough to ship"

Each version has a clear bar.

| Version | Required passing |
|---|---|
| **Spike (Day 0)** | A, B, C1, C2, C3, D, E, F (10 assertions) |
| **v0.1 (Day 7 — public ship)** | A, B, C1–C3, D, E, F, G + F1 + F2 |
| **v0.2 (Day 14 — replay)** | All above + F4 + replay-determinism property (replay with no overrides reproduces original within tolerance) |
| **v1.0 (Day 60)** | All above + 90% line coverage + 0 ruff warnings + 0 mypy errors + 3 third-party-contributed adapters or fixture-pairs |

---

## Metrics surfaced in every `hindsight stats` / `hindsight diff` run

* Per-step latency: count, mean, p50, p95.
* Per-kind step count.
* Per-model token totals.
* Per-tool call count and error rate.
* For diff: divergence point, divergence kind ({llm_content, tool_error, routing, structural}), structural-similarity ratio (steps_matched / max(len_a, len_b)).
* For replay: cost delta (recorded vs. replayed tokens × model price), latency delta, response-similarity (Jaccard on tokens — proxy, not gospel).

Every metric is part of the JSON output. The Markdown output is a flattened, human-readable rendering. No metric exists *only* in the Markdown — JSON is the source of truth so downstream tools can consume it.

---

## What we are explicitly **not** measuring in v1

* No "is the agent good" judgment. That's the eval-framework job (Sub-Agent Bench, Skillsmith). Hindsight is the *debugger*, not the judge.
* No automated root-cause classification. Diff reports the structural divergence; FDE engineers reason about *why*. Phase 3 may add an optional LLM-explain step.
* No production performance benchmarking. p95 latency over time is the observability vendors' job. Hindsight is post-hoc.

This restraint is deliberate. The triptych measures quality offline; Hindsight reconstructs runs post-hoc. Each tool has one job.

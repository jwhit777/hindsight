# PLAN — Hindsight

**Bottleneck-scoping skill output for the winning candidate.**

---

**Project in one sentence:** Hindsight is a local-first, pip-installable CLI + Python library that ingests LLM-agent traces in any format (OpenTelemetry GenAI, LangSmith export, Langfuse export, plain JSONL), normalizes them to a canonical `TraceRun` schema, and supports step-through inspection, diff between two runs, and replay-from-step with optional model swap.

**Binding constraint: canonical-schema design and multi-format ingest.**

Every downstream feature of Hindsight (show, diff, stats, replay, web UI, CI gate) reads from the canonical schema. If the schema is the right shape — flexible enough to absorb OTEL GenAI experimental fields, OpenAI Responses-format traces, LangSmith run-tree exports, Langfuse trace exports, and naked JSONL — every other feature is short, mostly stdlib-Python, with no model dependency. If the schema is the wrong shape, every downstream feature inherits the pain. This is also the place where a customer-facing FDE candidate demonstrates *deployment-pattern literacy* most directly: it requires reading half a dozen real exporters and choosing what stays in the canonical and what becomes adapter-local. The schema is the project's spine.

The second-place binding constraint is **diff semantics**: comparing two runs of arbitrary, non-deterministic agents and producing a useful "this is where they diverged" answer. But diff is downstream of canonical — solve canonical first, diff becomes a straight-line week.

---

## First sprint (1–2 weeks) — attack the binding constraint head-on

**Week 1**

* **Day 0 (overnight, this run):** spike the binding constraint. Ship `src/hindsight/canonical.py` (one dataclass tree), three ingesters (`ingest_jsonl.py`, `ingest_langsmith.py`, `ingest_otel_genai.py`), three matching fixtures in `fixtures/`, and `diff.py` with one divergence-detection pass. Self-test asserts all three ingesters produce identical canonical for equivalent input, and that the diff correctly identifies the deliberate divergence in fixture pair B. **Done.** See `SPIKE.md` for the captured output.
* **Day 1 (Justin in Claude Code):** ship the public GitHub repo. CI green on the spike tests. README hero example reproduces verbatim. `pyproject.toml` builds. `pip install -e .` works on Justin's machine.
* **Day 2–3:** real OTEL GenAI ingester against actual `opentelemetry-instrumentation-anthropic` output (run a tiny prompt → capture span → ingest). Real LangSmith ingester against the documented run-tree export shape. Both gated on the spike's identity test.
* **Day 4–5:** `hindsight show <run>` — terminal tree renderer, color, latencies and token counts. `hindsight stats <run>` — totals + per-node breakdown. Ship as v0.1.0 on PyPI under `hindsight-trace` (name verified on day 1; reserve immediately).
* **Day 6–7:** `hindsight diff <run-a> <run-b>` — terminal side-by-side, with divergence highlighted. Ship v0.2.0.

**Week 2**

* `hindsight replay <run> --from-step <n>` — re-runs from step `n` using the recorded inputs, calls the live model API for that step and any downstream steps. Supports `--model` override (e.g. swap Sonnet for Haiku and see whether the run still succeeds). Live calls only behind `--live`; default is record-substitution dry-run.
* CI matrix on Python 3.10 / 3.11 / 3.12. Pre-commit hooks. `make smoke` runs the binding-constraint test in <2s.
* Public blog post: "I built a flight recorder for LLM agents in a weekend — here's the canonical schema." Cross-post to `r/LocalLLaMA`, `r/Anthropic`, Hacker News, Reddit `r/programming`. Tag Anthropic FDE Twitter accounts. Submit to [agentskills.io](https://agentskills.io/) ecosystem index, the [OTEL GenAI SIG mailing list](https://opentelemetry.io/docs/specs/semconv/gen-ai/), the [LangChain awesome-list](https://github.com/langchain-ai/awesome-llmops).

---

## Three leading indicators (the constraint is being solved)

1. **Same JSONL trace, ingested via all three adapters, produces a canonical that round-trips losslessly.** Tested in CI on every commit. If this test stays green, the schema is doing its job.
2. **Diff correctly identifies the divergence point in a pair of designed traces with known divergence.** Tested on at least three pairs (LLM-content divergence, tool-call-divergence, routing-divergence). The spike covers one pair; week-1 expands to all three.
3. **A real OSS user (or me at a customer) can ingest their existing trace and get a useful diff or stats output in <60 seconds of CLI use.** Tracked by GitHub issues and DMs from the launch post.

## Kill criteria

* **Two weeks in, OTEL GenAI semantic conventions have changed enough that the adapter is rewriting weekly** — OTEL is still experimental ([opentelemetry.io](https://opentelemetry.io/docs/specs/semconv/gen-ai/) labels GenAI as such); if upstream churn outpaces my maintenance, pin to a frozen OTEL version and document the limit, but if the churn keeps eating week-3 and week-4, downgrade OTEL to a "best-effort" adapter and refocus on LangSmith + JSONL as primary.
* **A bigger player (Langfuse, Phoenix, or a new entrant) ships cross-format diff in v0–v1 timeframe** — if Langfuse 4.0 (or equivalent) lands "import any vendor's trace, diff any pair" as a flagship feature, my differentiation collapses. Fallback: lean into the *replay-with-model-swap* feature, which still isn't covered by anyone except partial efforts (LangSmith's "replay against new models" works only inside LangChain).
* **Schema design is taking >5 sessions and still doesn't fit one of the four input formats** — at that point, narrow scope: support 2 input formats fully, ship, and revisit later.
* **Zero traction by week 4** (no stars, no issues, no DMs) — pivot the cover-letter narrative from "I built and shipped Hindsight" to "I built a thing teams should use; here's the design doc and the spec gaps it exposed in OTEL GenAI." That's still a strong artifact.

## 90-day arc — if the constraint is solved

* **Day 30 (v0.5):** ingest + show + diff + stats + replay (offline). 200+ GitHub stars. One real OSS user filing useful issues. Blog post ranked on Hacker News.
* **Day 60 (v1.0):** local web UI (FastAPI + zero-build HTML, no node, no React) for the navigation flow; the CLI remains the canonical interface. Plugin protocol for new ingesters. `hindsight ci diff --gate` for use in PR checks. 500+ GitHub stars. Two real OSS users. Listed in the OTEL GenAI ecosystem page.
* **Day 90:** the *FDE deployment-pattern catalog* — start collecting common Hindsight diffs into a publicly shared library of "agent deployment patterns" ("routing-too-eager," "context-window-overflow," "tool-loop-divergence," etc). This is the artifact the Anthropic FDE bullet asks for: *"codify repeatable deployment patterns and contribute insights back."* Each pattern is a Hindsight diff + a 2-paragraph diagnosis + a fix recipe. Anthropic will see this and notice.

---

**Cross-links.** Sub-Agent Bench produces traces that Hindsight can ingest. MCP Probe produces tool-description-poisoning issues that show up *as Hindsight diffs* between the poisoned and clean runs. Skillsmith calibration runs are also Hindsight-ingestible. The four projects compose: triptych for offline pre-deployment evals, Hindsight for post-deployment runtime debugging.

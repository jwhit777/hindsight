# Hindsight

> Open-source flight recorder + replay debugger for LLM agents.
> Read any trace. Branch from any step. Diff two runs. Locally. No account.

[![Status](https://img.shields.io/badge/status-spike-yellow)]() [![Python](https://img.shields.io/badge/python-3.10+-blue)]() [![Stdlib](https://img.shields.io/badge/deps-stdlib--only-brightgreen)]() [![License](https://img.shields.io/badge/license-Apache_2.0-green)]()

**Project status:** Day 0 — overnight spike complete (2026-05-15). v0.1 in progress. See [`PLAN.md`](./PLAN.md), [`SPIKE.md`](./SPIKE.md), and [`FIRST-4-HOURS.md`](./FIRST-4-HOURS.md).

---

## The 30-second pitch

Every existing LLM-agent observability tool is hosted SaaS or framework-locked. Langfuse, LangSmith, Arize Phoenix, Helicone, Datadog LLM, and Laminar all want your data on their cloud or your SDK in their flavor. When an Anthropic FDE walks into a Fortune 100 customer with regulated data and an existing OpenTelemetry collector, none of them are a drop-in. The customer's question is *"my agent is failing in production, where did it go wrong?"* — they want a step-by-step view, a way to re-run from the point of failure, and a way to diff a known-good run against the broken one. That's a primitive, not a product.

Hindsight is that primitive: a local-first, pip-installable CLI + library that ingests any trace format, normalizes it to a canonical schema, and exposes step-through, diff, and replay-from-step over it. No accounts, no cloud, stdlib Python core.

```
$ pip install hindsight-trace
$ hindsight ingest my-failing-run.jsonl
  → ingested 23 steps (4 agent · 11 llm · 8 tool) → run_2026-05-15T09-12-44

$ hindsight show run_2026-05-15T09-12-44
  ROUTER  → orchestrator/route_to_subagent
    LLM   ─ claude-haiku-4-5  ▸ 412 tok in / 38 tok out  (180 ms)
    TOOL  ─ subagent.dispatch("stock-analyst")  (2 ms)
    AGENT ─ stock-analyst
      LLM ─ claude-sonnet-4-6  ▸ 8 412 tok in / 1 220 tok out  (4 110 ms)
      TOOL─ get_quote("AAPL")  → ERROR(rate_limited)             ⚠
      ... 17 more steps

$ hindsight diff run_GOOD run_BAD
  divergence at step #6 (TOOL get_quote):
    GOOD: got_quote → continued to summarise
    BAD : rate_limited → retried 3x → context overflow → hallucinated quote

$ hindsight replay run_BAD --from-step 6 --model claude-sonnet-4-6
  [LIVE] re-running 18 downstream steps with sonnet-4-6 in place of haiku-4-5...
  → succeeds. 4 270 ms total. 12 580 tok.
```

That's the whole demo. One Linux box, one trace file, four commands.

---

## Why this exists (the trendlines)

Three independent curves converge here:

1. **Agents in production, exponential.** Every 2026 FDE / Applied AI posting lists "deployment at scale" and "production LLM experience" as universal requirements. [Anthropic + Blackstone + Goldman Sachs + Hellman & Friedman announced a $1.5B enterprise-AI JV on 2026-05-04](https://www.anthropic.com/news/enterprise-ai-services-company); [OpenAI launched its Deployment Company plus a Tomoro acquisition on 2026-05-11](https://openai.com/index/openai-launches-the-deployment-company/). The number of enterprise agents in production is on a near-vertical curve. Each one will, at some point, fail in production. None of the failure modes can be debugged from logs.

2. **OpenTelemetry GenAI semantic conventions, real but unfinished.** [OTEL GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) defines `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.provider.name`, plus span shapes for agent and framework. Status: experimental. Vendor adoption: real. Datadog [shipped support in OTel v1.37](https://opentelemetry.io/docs/specs/semconv/gen-ai/); Grafana started collecting LLM traces in Loki. Whoever ships a *cross-vendor reader* before the spec stabilises owns the integration layer.

3. **The "deterministic replay as missing primitive" thesis.** Sakura Sky's 2026 series calls deterministic replay [the missing primitive for trustworthy AI](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/). [Tian Pan independently argues the same on his blog (2026-04)](https://tianpan.co/blog/2026-04-12-deterministic-replay-debugging-non-deterministic-ai-agents). The [Litmus](https://github.com/rylinjames/litmus) and [agent-replay](https://github.com/manasvardhan/agent-replay) GitHub projects attack the HTTP-interception slice but neither does cross-format ingest nor diff. [arxiv 2505.17716](https://arxiv.org/abs/2505.17716) makes the academic case for record + replay in agent loops. The thesis is converging from three directions; what's missing is a polished, documented, pip-installable tool that hits all three.

---

## Where this fits in Justin's portfolio

This is the fourth project in a deliberately-stacked FDE portfolio.

| Project | Layer | Mode | Output |
|---|---|---|---|
| [Sub-Agent Bench](../2026-05-12-fde-portfolio/) | Orchestrator + sub-agents | Offline eval | Routing accuracy, per-sub-agent quality, κ-calibrated judge |
| [MCP Probe](../2026-05-13-fde-portfolio/) | MCP protocol | Offline scan | Trust report, prompt-injection / schema / tool-poisoning probes |
| [Skillsmith](../2026-05-14-fde-portfolio/) | Agent Skills | Offline eval | Trigger precision/recall, cross-skill confusion, autotune loop |
| **Hindsight** (this) | **Runtime traces** | **Post-hoc + replay** | **Step-through, diff, branch-from-step, deployment-pattern catalog** |

The first three are offline pre-deployment evals; Hindsight is the runtime post-deployment debugger. Together they match every bullet of the Anthropic Forward Deployed Engineer posting: *"deliver technical artifacts for customers like MCP servers, sub-agents, and agent skills … identify and codify repeatable deployment patterns and contribute insights back to our Product and Engineering teams"* ([Greenhouse 4985877008](https://job-boards.greenhouse.io/anthropic/jobs/4985877008)).

The 90-day deliverable for Hindsight is the **deployment-pattern catalog** — a publicly shared library of recurring agent-failure Hindsight diffs with diagnoses and fix recipes. That artifact is the literal *thing* the FDE bullet asks for.

---

## Architecture (one paragraph)

A trace from any supported source is parsed by a format-specific *ingester* into the canonical `TraceRun` dataclass tree. Each `TraceStep` is one of {`AGENT`, `LLM`, `TOOL`, `DECISION`} and carries `request`, `response`, `latency_ms`, `tokens_in/out`, `parent_id`, plus a free-form `extra` dict for adapter-local fields. Operations are pure functions over `TraceRun`: `show()` walks the tree, `stats()` aggregates, `diff(a, b)` aligns step-by-step and reports the first divergence, `replay(run, from_step, model_override)` re-emits requests live from step *n* onward. The optional web UI (Phase 2) is a FastAPI server that re-uses the same library; nothing in the core talks HTTP unless `--live` is passed. The spike (this overnight build) implements ingest from 3 formats + `show` + `stats` + `diff` against fixtures, with self-tests covering schema round-trip, cross-format identity, and divergence detection. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full diagram.

---

## Repository layout

```
2026-05-15-fde-portfolio/
├── README.md                ← this file
├── PLAN.md                  ← bottleneck-scoping output (single-page plan)
├── CANDIDATES.md            ← 6 candidates considered, why Hindsight won
├── TECH-STACK.md            ← stack, with rationale
├── ARCHITECTURE.md          ← system diagram + data shapes + failure modes
├── EVALS.md                 ← what gets tested, what counts as "good enough"
├── DEMO-PLAN.md             ← 5-minute interview demo script
├── SPIKE.md                 ← what the overnight spike proved (+ output)
├── FIRST-4-HOURS.md         ← Day-1 step-by-step
├── elevator-pitch.md        ← 60-second verbal pitch
├── cover-letter-snippet.md  ← 2-paragraph cover-letter fragment
├── CLAUDE-CODE-PROMPT.md    ← copy-paste handoff prompt for Claude Code
├── prompts/
│   └── replay-system.md     ← system prompt template for replay (v0)
├── fixtures/
│   ├── canonical_good.jsonl
│   ├── canonical_bad.jsonl
│   ├── langsmith_good.json
│   ├── otel_good.json
│   └── README.md
├── src/
│   ├── hindsight/
│   │   ├── __init__.py
│   │   ├── canonical.py     ← dataclasses for TraceRun, TraceStep
│   │   ├── ingest_jsonl.py
│   │   ├── ingest_langsmith.py
│   │   ├── ingest_otel.py
│   │   ├── show.py
│   │   ├── stats.py
│   │   ├── diff.py
│   │   └── cli.py           ← argparse entrypoint
│   ├── spike_run.py         ← the overnight runnable end-to-end
│   └── test_spike.py        ← 10 self-test assertions
└── runs/                    ← captured spike output for inspection
```

## Quickstart (after Day 1)

```
cd src/
python3 spike_run.py        # runs the overnight spike end-to-end
python3 test_spike.py       # 10 self-test assertions
```

## What's already done overnight (Day 0)

* Canonical schema written, 4 step types, lossless JSONL round-trip.
* Three ingesters (JSONL, LangSmith-export shape, OTEL GenAI span shape) writing into the same canonical.
* `show()`, `stats()`, `diff()` all working in stdlib Python (no numpy, no pydantic).
* Three fixture pairs in `fixtures/`. Designed divergences for diff testing.
* `spike_run.py` runs end-to-end, prints a calibration-card-style report.
* `test_spike.py` — 10 assertions covering cross-format identity, round-trip, divergence detection, stats math, tree depth handling.
* All tests pass; total spike runtime is single-digit milliseconds.

Spike output captured verbatim in [`SPIKE.md`](./SPIKE.md). Reproduction command in [`FIRST-4-HOURS.md`](./FIRST-4-HOURS.md).

## What ships next

See [`PLAN.md`](./PLAN.md) and [`FIRST-4-HOURS.md`](./FIRST-4-HOURS.md). Short version: tomorrow morning, push the repo public, confirm CI, then implement a real OTEL-GenAI-instrumented Anthropic SDK call and ingest its output through Hindsight to close the demo loop.

## License

Apache 2.0. See `LICENSE` (to be added Day 1).

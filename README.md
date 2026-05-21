# Hindsight

> Open-source flight recorder + replay debugger for LLM agents.
> Read any trace. Branch from any step. Diff two runs. Locally. No account.

[![CI](https://github.com/jwhit777/hindsight/actions/workflows/ci.yml/badge.svg)](https://github.com/jwhit777/hindsight/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/hindsight-trace.svg)](https://pypi.org/project/hindsight-trace/) [![Python](https://img.shields.io/badge/python-3.10+-blue)]() [![License](https://img.shields.io/badge/license-Apache_2.0-green)]()

**Project status:** v0.1.0 shipped (2026-05-21). See [`PLAN.md`](./PLAN.md), [`CHANGELOG.md`](./CHANGELOG.md), and [`SPIKE.md`](./SPIKE.md).

> **Install today** *(until `hindsight-trace` lands on PyPI; install from source):*
> ```bash
> git clone https://github.com/jwhit777/hindsight && cd hindsight
> python3 -m venv .venv && source .venv/bin/activate
> pip install -e .
> ```
> The `pip install hindsight-trace` form in the demo below is the post-launch command.

---

```
      production              hindsight
        ___   ___                ___   ___
       /   \ /   \              /   \ /   \
      | ??  | ??  |    ───►    | s6  | s7  |
       \___/ \___/              \___/ \___/
     "why did it fail?"     "tool→rate_limited;
                              retry-loop overflowed
                              context; hallucinated."
```

<sub><i>Hindsight is 20/20.</i></sub>

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

## Architecture (one paragraph)

A trace from any supported source is parsed by a format-specific *ingester* into the canonical `TraceRun` dataclass tree. Each `TraceStep` is one of {`AGENT`, `LLM`, `TOOL`, `DECISION`} and carries `request`, `response`, `latency_ms`, `tokens_in/out`, `parent_id`, plus a free-form `extra` dict for adapter-local fields. Operations are pure functions over `TraceRun`: `show()` walks the tree, `stats()` aggregates, `diff(a, b)` aligns step-by-step and reports the first divergence, `replay(run, from_step, model_override)` re-emits requests live from step *n* onward. The optional web UI (Phase 2) is a FastAPI server that re-uses the same library; nothing in the core talks HTTP unless `--live` is passed. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full diagram.

---

## Repository layout

```
hindsight/
├── README.md                  ← this file
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                    ← Apache-2.0
├── Makefile                   ← smoke / test / lint / build targets
├── pyproject.toml             ← hatchling, name=hindsight-trace
├── PLAN.md                    ← bottleneck-scoping output (single-page plan)
├── ARCHITECTURE.md            ← system diagram + data shapes + failure modes
├── EVALS.md                   ← what gets tested, what counts as "good enough"
├── SPIKE.md                   ← what the spike proved (+ output)
├── CANDIDATES.md              ← 6 candidates considered, why Hindsight won
├── DEMO-PLAN.md
├── TECH-STACK.md
├── LAUNCH.md                  ← v0.2 launch post draft (not published)
├── .github/
│   └── workflows/
│       └── ci.yml             ← matrix on Python 3.10 / 3.11 / 3.12
├── examples/
│   └── walkthrough.md         ← copy-paste end-to-end demo
├── prompts/
│   └── replay-system.md       ← system prompt template for replay
├── fixtures/
│   ├── canonical_good.jsonl
│   ├── canonical_bad.jsonl                   ← routing divergence
│   ├── canonical_llm_content_good.jsonl
│   ├── canonical_llm_content_bad.jsonl       ← LLM-content divergence
│   ├── canonical_tool_error_good.jsonl
│   ├── canonical_tool_error_bad.jsonl        ← tool-call divergence
│   ├── canonical_token_div_good.jsonl
│   ├── canonical_token_div_bad.jsonl         ← token divergence (strict-mode)
│   ├── canonical_latency_div_good.jsonl
│   ├── canonical_latency_div_bad.jsonl       ← latency divergence (strict-mode)
│   ├── langsmith_good.json
│   ├── otel_good.json
│   ├── langfuse_good.json
│   ├── subagent_bench_good.json
│   └── README.md
├── src/
│   ├── hindsight/
│   │   ├── __init__.py
│   │   ├── canonical.py       ← dataclasses for TraceRun, TraceStep
│   │   ├── base.py            ← BaseIngester Protocol + register() + auto_ingest()
│   │   ├── ingest_jsonl.py
│   │   ├── ingest_langsmith.py
│   │   ├── ingest_otel.py
│   │   ├── ingest_langfuse.py
│   │   ├── ingest_subagent_bench.py
│   │   ├── show.py
│   │   ├── stats.py
│   │   ├── diff.py            ← --strict adds tokens / latency to compared fields
│   │   ├── replay.py          ← record-substitution + --live-tools + lazy live providers
│   │   └── cli.py             ← argparse: show (--json/--depth) / stats / diff / replay / ci diff / validate / version
│   ├── spike_run.py           ← runnable end-to-end demo
│   ├── test_spike.py          ← 18 schema / ingest / diff tests
│   ├── test_replay.py         ← 12 replay-engine tests
│   └── test_cli_verbs.py      ← 9 subprocess-driven CLI tests
└── runs/                      ← captured spike output for inspection
```

## Quickstart

```
cd src/
python3 spike_run.py        # runs the spike end-to-end
python3 -m unittest discover -s . -p 'test_*.py' -v   # 39 tests across 3 suites
```

## What's already done

* Canonical schema written, 4 step types, lossless JSONL round-trip.
* Five ingesters (JSONL, LangSmith run-tree, OTEL GenAI, Langfuse, Sub-Agent Bench) writing into the same canonical. Cross-format structural identity is a tested invariant.
* `show()` (with `--json` for canonical-JSONL emission and `--depth N` for tree-depth capping), `stats()`, `diff()` (with `--strict` for token / latency regressions), `replay()` (with `--live-tools` opt-in for TOOL re-execution) all working in stdlib Python (no numpy, no pydantic). CLI adds `ci diff --gate` (PR-check exit codes), `validate` (schema conformance), and `version` (prints version + adapter / provider list). Live providers (Anthropic, OpenAI) sit behind the `[live]` extra.
* `BaseIngester` Protocol — third parties can register new format adapters without touching the core.
* Fixtures cover three semantic divergence patterns (routing, LLM-content, tool-call), two strict-mode divergence patterns (tokens, latency), and five cross-format identity fixtures (jsonl, langsmith, otel, langfuse, subagent_bench).
* `spike_run.py` runs end-to-end, prints a calibration-card-style report.
* 39 tests across `test_spike.py` (18), `test_replay.py` (12), and `test_cli_verbs.py` (9) — covering cross-format identity, round-trip, five divergence patterns, stats math, replay semantics including `--live-tools`, lazy-import guards for live providers, and CLI exit codes.
* All tests pass on Python 3.10 / 3.11 / 3.12 in CI (now on the Node 24 runtime); total spike runtime is single-digit milliseconds.

Spike output captured verbatim in [`SPIKE.md`](./SPIKE.md).

## Use in CI

`hindsight ci diff` is the PR-check variant of `diff`. With `--gate`, it
exits 1 on any divergence — drop it into a GitHub Actions step and a PR
that regresses a known-good trace fails before merge.

```yaml
# .github/workflows/regression-gate.yml
name: trace-regression
on: [pull_request]
jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install hindsight-trace
      - name: Run the agent and capture a trace
        run: python scripts/run_agent.py > runs/head.jsonl
      - name: Gate the PR on the cross-run diff
        run: hindsight ci diff baseline/good.jsonl runs/head.jsonl --gate --md
```

`hindsight validate <path>` is the lighter companion — exits 0 on canonical
conformance, 2 on schema violation, 1 on missing file. Use it as a cheap
first-pass check before the diff.

## Browse in a web UI

For traces deeper than the terminal can comfortably render, Hindsight
ships an opt-in local web UI:

```bash
pip install 'hindsight-trace[web]'
hindsight serve --root ./fixtures
# → open http://127.0.0.1:8080/
```

The UI lists every `.jsonl` / `.json` trace under `--root`, renders any
of them as an HTML tree with a stats sidebar, diffs two of them
side-by-side, and replays from any step (MockProvider only on the web
path — live API replay stays in the CLI for clear audit trails). Server
binds to `127.0.0.1` by default; all path inputs are bounded to `--root`.
Zero JavaScript, zero build step.

## What ships next

See [`PLAN.md`](./PLAN.md). Three concrete next items, independent:

- **Reserve `hindsight-trace` on PyPI** — the v0.1.0 wheel + sdist are already built and attached to the [v0.1.0 GitHub release](https://github.com/jwhit777/hindsight/releases/tag/v0.1.0); the upload itself is one `twine upload` away.
- **Validate the OTEL adapter against captured reality** — the current `otel_good.json` fixture was hand-written from the spec. Wire up `opentelemetry-instrumentation-anthropic`, capture a real `claude-haiku-4-5` call, ingest the resulting spans, and pin the captured trace as a fixture.
- **Flip the repo public** when the launch posture is ready.

## License

Apache 2.0. See [`LICENSE`](./LICENSE).

# Hindsight

> Open-source flight recorder + replay debugger for LLM agents.
> Read any trace. Branch from any step. Diff two runs. Locally. No account.

[![CI](https://github.com/jwhit777/hindsight/actions/workflows/ci.yml/badge.svg)](https://github.com/jwhit777/hindsight/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/hindsight-trace.svg)](https://pypi.org/project/hindsight-trace/) [![Python](https://img.shields.io/badge/python-3.10+-blue)]() [![License](https://img.shields.io/badge/license-Apache_2.0-green)]()

**Project status:** v0.2.0 shipped (2026-05-21) — five ingest adapters, seven CLI verbs, optional FastAPI web UI, 55 tests across four suites. See the [v0.2.0 release](https://github.com/jwhit777/hindsight/releases/tag/v0.2.0), [`CHANGELOG.md`](./CHANGELOG.md), [`PLAN.md`](./PLAN.md), and [`SPIKE.md`](./SPIKE.md).

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

The four commands below all run verbatim against fixtures in this repo — copy, paste, see the same output:

```
$ hindsight show fixtures/canonical_good.jsonl
run run_good_001  source=jsonl
  7 steps · 9444 tok in / 1298 tok out · 6940 ms total

AGENT  orchestrator  · 2520 ms
   LLM   router  · claude-haiku-4-5  · 412 in / 38 out  · 180 ms
   TOOL  subagent.dispatch  · 2 ms
    AGENT  stock-analyst  · 2030 ms
       LLM   analyse  · claude-sonnet-4-6  · 8412 in / 1220 out  · 1880 ms
       TOOL  get_quote  · 48 ms
   LLM   summarize  · claude-sonnet-4-6  · 620 in / 40 out  · 280 ms

$ hindsight diff fixtures/canonical_good.jsonl fixtures/canonical_bad.jsonl --md
# Diff report
- matched pairs — 4
- only in A — 3
- only in B — 3
- clean — False
**first divergence at path agent:orchestrator → llm:router on field 'response'**
  A: router  (llm)  value={'choice': 'stock-analyst'}
  B: router  (llm)  value={'choice': 'news-writer'}

$ hindsight replay fixtures/canonical_good.jsonl --from-step 3 --model claude-sonnet-4-6 --out /tmp/r.jsonl
$ hindsight show /tmp/r.jsonl    # replayed tree, model swapped on every LLM step in the tail

$ hindsight serve --root ./fixtures        # optional web UI; pip install 'hindsight-trace[web]' first
Serving hindsight UI at http://127.0.0.1:8080/ (root=…/fixtures)
```

That's the whole demo. One Linux box, one trace file, four commands — five with the web UI.

---

## Why this exists (the trendlines)

Three independent curves converge here:

1. **Agents in production, exponential.** Every 2026 FDE / Applied AI posting lists "deployment at scale" and "production LLM experience" as universal requirements. [Anthropic + Blackstone + Goldman Sachs + Hellman & Friedman announced a $1.5B enterprise-AI JV on 2026-05-04](https://www.anthropic.com/news/enterprise-ai-services-company); [OpenAI launched its Deployment Company plus a Tomoro acquisition on 2026-05-11](https://openai.com/index/openai-launches-the-deployment-company/). The number of enterprise agents in production is on a near-vertical curve. Each one will, at some point, fail in production. None of the failure modes can be debugged from logs.

2. **OpenTelemetry GenAI semantic conventions, real but unfinished.** [OTEL GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) defines `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.provider.name`, plus span shapes for agent and framework. Status: experimental. Vendor adoption: real. Datadog [shipped support in OTel v1.37](https://opentelemetry.io/docs/specs/semconv/gen-ai/); Grafana started collecting LLM traces in Loki. Whoever ships a *cross-vendor reader* before the spec stabilises owns the integration layer.

3. **The "deterministic replay as missing primitive" thesis.** Sakura Sky's 2026 series calls deterministic replay [the missing primitive for trustworthy AI](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/). [Tian Pan independently argues the same on his blog (2026-04)](https://tianpan.co/blog/2026-04-12-deterministic-replay-debugging-non-deterministic-ai-agents). The [Litmus](https://github.com/rylinjames/litmus) and [agent-replay](https://github.com/manasvardhan/agent-replay) GitHub projects attack the HTTP-interception slice but neither does cross-format ingest nor diff. [arxiv 2505.17716](https://arxiv.org/abs/2505.17716) makes the academic case for record + replay in agent loops. The thesis is converging from three directions; what's missing is a polished, documented, pip-installable tool that hits all three.

---

## Architecture (one paragraph)

A trace from any supported source is parsed by a format-specific *ingester* into the canonical `TraceRun` dataclass tree. Each `TraceStep` is one of {`AGENT`, `LLM`, `TOOL`, `DECISION`} and carries `request`, `response`, `latency_ms`, `tokens_in/out`, `parent_id`, plus a free-form `extra` dict for adapter-local fields. Operations are pure functions over `TraceRun`: `show()` walks the tree, `stats()` aggregates, `diff(a, b)` aligns step-by-step and reports the first divergence, `replay(run, from_step, model_override)` re-emits requests through a `Provider` (mock by default, Anthropic or OpenAI behind the `[live]` extra) from step *n* onward. The optional web UI is a FastAPI server (behind the `[web]` extra) that re-uses the same library; nothing in the core talks HTTP unless `--live` is passed. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full diagram.

## Supported trace formats

| Format | Detection | Adapter | Notes |
|---|---|---|---|
| **JSONL** (canonical) | `.jsonl` suffix | `ingest_jsonl` | Native on-disk form; lossless round-trip via `to_jsonl` / `from_jsonl`. |
| **LangSmith run-tree** | `.json` with `id` + `run_type` | `ingest_langsmith` | Standard LangSmith export. Vendor-specific fields preserved under `extra["langsmith"]`. |
| **OpenTelemetry GenAI** | `.json` with `resourceSpans` | `ingest_otel` | Per [OTEL GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/). Use `scripts/capture_otel_anthropic.py` to generate a real fixture from a live `claude-haiku-4-5` call. |
| **Langfuse** | `.json` with `observations` | `ingest_langfuse` | Standard Langfuse trace export. Observation IDs prefixed `lf:` in canonical output to namespace. |
| **Sub-Agent Bench** | `.json` with `orchestrator` + `sab_version` | `ingest_subagent_bench` | Nested `orchestrator → steps → subagent_call → steps` shape. Demonstrates the plugin protocol with a real third-party-shaped format. |

All five produce **structurally-identical** canonical output for equivalent input — the cross-format-identity property is the project's spine and a tested CI invariant. New formats register via `hindsight.base.BaseIngester`; see [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the three-step recipe.

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
├── scripts/
│   └── capture_otel_anthropic.py  ← operator-run: live OTEL capture for fixture validation
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
│   ├── web/                   ← optional FastAPI UI (see [web] extra)
│   │   ├── app.py             ← routes (browse / show / diff / replay + JSON twins)
│   │   ├── render.py          ← HTML tree renderer
│   │   ├── templates/         ← 6 Jinja2 templates
│   │   └── static/style.css   ← single stylesheet, zero JS framework
│   ├── spike_run.py           ← runnable end-to-end demo
│   ├── test_spike.py          ← 18 schema / ingest / diff tests
│   ├── test_replay.py         ← 12 replay-engine tests
│   ├── test_cli_verbs.py      ← 14 subprocess-driven CLI tests
│   └── test_web.py            ← 11 TestClient web-UI tests (skip if `[web]` not installed)
└── runs/                      ← captured spike output for inspection
```

## Quickstart

```bash
# Clone, venv, editable install.
git clone https://github.com/jwhit777/hindsight && cd hindsight
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Three Makefile gates.
make smoke       # ~1ms — runs the spike end-to-end
make test        # 55 tests across 4 suites (test_spike + test_replay + test_cli_verbs + test_web)
make lint        # ruff clean

# Optional extras when you need them.
pip install -e '.[web]'      # FastAPI web UI
pip install -e '.[live]'     # anthropic + openai replay providers
pip install -e '.[otel]'     # opentelemetry SDK + Anthropic instrumentation
```

The web tests in `test_web.py` skip gracefully when `[web]` isn't installed — CI's default `[dev]`-only test jobs report 44 tests; running with `[dev,web]` reports 55.

## What's already done

### Core
- Canonical schema (`TraceRun` / `TraceStep`), 4 step kinds, lossless JSONL round-trip.
- Five ingest adapters; cross-format-identity is a tested CI invariant.
- Pure-function operations: `show()`, `stats()`, `diff()`, `replay()`.
- Plugin protocol (`BaseIngester`) — third parties can add new formats without touching the core.

### CLI surface
- `hindsight show <path>` — render the tree (`--json` emits canonical JSONL for piping; `--depth N` caps tree depth).
- `hindsight stats <path>` — aggregate (JSON by default; `--md` for Markdown).
- `hindsight diff <a> <b>` — structural diff (`--md`; `--strict` adds tokens/latency to the comparison).
- `hindsight replay <path> --from-step N [--model M] [--live] [--live-tools]` — re-derive the tail; mock-default, real providers behind `[live]`.
- `hindsight ci diff <a> <b> --gate [--strict] [--md]` — exits 1 on divergence; drop into a PR check.
- `hindsight validate <path>` — schema conformance check; exit 0 OK, 2 schema violation, 1 missing file.
- `hindsight version` — version + registered ingesters + replay providers; `--version` also works as a top-level flag.
- `hindsight serve [--root .] [--port 8080]` — local FastAPI web UI (behind `[web]` extra).

### Replay providers
- `MockProvider` — deterministic identity replay; no network, no SDK; default.
- `AnthropicProvider`, `OpenAIProvider` — lazy-imported, in `[live]` extra. Drop in your own `Provider` by satisfying the Protocol.

### Fixtures (14 total)
- Five cross-format identity fixtures (one per adapter).
- Three semantic divergence-pair fixtures (routing, LLM-content, tool-call) for default diff.
- Two strict-mode divergence-pair fixtures (tokens, latency) that default diff intentionally ignores but `--strict` catches.

### Tests + gates
- 55 tests across four suites: `test_spike.py` (18) / `test_replay.py` (12) / `test_cli_verbs.py` (14) / `test_web.py` (11, skip-if-`[web]`-not-installed).
- CI green on Python 3.10 / 3.11 / 3.12 (Node 24 runtime via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`).
- Dedicated `typecheck` CI job: mypy 0 errors on `src/hindsight/`.
- ruff lint clean. Pre-commit config ships in repo (`pre-commit install` to enable).

Spike output captured verbatim in [`SPIKE.md`](./SPIKE.md).

## Add your own adapter

The plugin protocol is 50 lines in [`src/hindsight/base.py`](./src/hindsight/base.py). A new adapter is three pieces:

```python
# src/hindsight/ingest_myformat.py
from __future__ import annotations
from pathlib import Path
from .canonical import StepKind, TraceRun, TraceStep

def ingest(path: Path) -> TraceRun:
    """Parse <path>, return a TraceRun. All five existing adapters
    follow this signature; the registry wraps it."""
    raw = ...  # read your format
    steps = [TraceStep(id=..., parent_id=..., kind=StepKind.LLM, ...) for ...]
    run = TraceRun(id=..., source="myformat", steps=steps)
    run.validate()
    return run
```

Register it in `_register_builtins()` in `src/hindsight/base.py`. Add a fixture in the canonical 7-step shape, then extend `test_A_cross_format_identity` to include it. CI gates the cross-format-identity property — your adapter is correct iff that test stays green.

[`CONTRIBUTING.md`](./CONTRIBUTING.md) has the full recipe with reference to the canonical example (`ingest_langfuse.py`).

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

See [`PLAN.md`](./PLAN.md) for the 90-day arc. Concrete near-term items:

- **PyPI publish.** v0.2.0 wheel + sdist are built and attached to the [v0.2.0 GitHub release](https://github.com/jwhit777/hindsight/releases/tag/v0.2.0); reserving the `hindsight-trace` name on PyPI is one `twine upload` away. Until then, install from source or grab the wheel from the release.
- **Validate the OTEL adapter against captured reality** — `scripts/capture_otel_anthropic.py` is shipped; bring your own `ANTHROPIC_API_KEY`, run it once, and compare the captured `fixtures/otel_real.json` against the hand-written `fixtures/otel_good.json`. Any adapter bug surfaces immediately.
- **Day-90 — the deployment-pattern catalog.** PLAN.md's marquee artifact: a public library of recurring agent-failure Hindsight diffs with diagnoses and fix recipes. Each one is a `<good, bad>` pair of canonical traces + a 2-paragraph diagnosis. Contributions welcome via the issue templates.

## License

Apache 2.0. See [`LICENSE`](./LICENSE).

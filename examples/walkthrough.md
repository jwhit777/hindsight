# Hindsight walkthrough — copy-paste demo

A complete end-to-end demo you can run from a fresh clone. No account, no
cloud, no API key required for steps 1–4.

---

## 1. Install

**Post-release (from PyPI):**

```bash
pip install hindsight-trace
```

**Source install (until PyPI release, or for development):**

```bash
git clone https://github.com/jwhit777/hindsight && cd hindsight
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Optional extras:

```bash
pip install 'hindsight-trace[live]'   # adds anthropic + openai for --live replay
pip install 'hindsight-trace[otel]'   # adds opentelemetry-sdk for real OTEL emission
```

---

## 2. Ingest a trace and inspect it

The native format is JSONL: one JSON object per line, one line per step.

```bash
hindsight show fixtures/canonical_good.jsonl
```

Output:

```
run run_good_001  source=jsonl
  7 steps · 9444 tok in / 1298 tok out · 6940 ms total

AGENT  orchestrator  · 2520 ms
   LLM   router  · claude-haiku-4-5  · 412 in / 38 out  · 180 ms
   TOOL  subagent.dispatch  · 2 ms
    AGENT  stock-analyst  · 2030 ms
       LLM   analyse  · claude-sonnet-4-6  · 8412 in / 1220 out  · 1880 ms
       TOOL  get_quote  · 48 ms
   LLM   summarize  · claude-sonnet-4-6  · 620 in / 40 out  · 280 ms
```

This is a 7-step agent run: an orchestrator routes to a stock-analyst
sub-agent, which calls an LLM to analyse and a tool to fetch a quote, then the
orchestrator summarises.

### Format conversion + depth cap

Pipe the canonical out as JSONL — handy for converting any input format to
the native form, or for piping into `jq`:

```bash
hindsight show fixtures/otel_good.json --json > /tmp/canonical.jsonl
hindsight show fixtures/canonical_good.jsonl --json | jq '.steps[] | select(.kind=="llm")'
```

For deeply-nested traces, cap the tree depth:

```bash
hindsight show fixtures/canonical_good.jsonl --depth 1   # root step only
hindsight show fixtures/canonical_good.jsonl --depth 2   # root + immediate children
```

`--depth 0` prints the run header without any steps.

Get aggregate stats in Markdown:

```bash
hindsight stats fixtures/canonical_good.jsonl --md
```

Output:

```markdown
# Stats for run `run_good_001`  (source: jsonl)

## Steps by kind

- **agent** — 2
- **llm** — 3
- **tool** — 2
- **decision** — 0

## Tokens

- input — 9444
- output — 1298

## Latency (ms)

- total — 6940
- p50 — 280
- p95 — 2372

## Per-model

- **claude-haiku-4-5** — 1 calls · 412 in / 38 out · 180 ms
- **claude-sonnet-4-6** — 2 calls · 9032 in / 1260 out · 2160 ms

## Per-tool

- **subagent.dispatch** — 1 calls
- **get_quote** — 1 calls
```

---

## 3. Same trace, five formats — cross-format identity

The same logical 7-step run is available in all five supported formats.
Run `hindsight show` on each:

```bash
hindsight show fixtures/langsmith_good.json
hindsight show fixtures/otel_good.json
hindsight show fixtures/langfuse_good.json
hindsight show fixtures/subagent_bench_good.json
```

Each command produces the identical tree structure shown in step 2 — same step
names, same step counts, same models, same token numbers. The adapter
auto-detects the format from the file suffix and top-level JSON keys.

This is the **cross-format-identity property**: once a trace is in the
canonical `TraceRun` schema, `show`, `stats`, `diff`, and `replay` are
indifferent to which tool captured it. A Langfuse trace, a LangSmith trace,
an OpenTelemetry export, and a Sub-Agent Bench export of the same agent run
are interchangeable.

---

## 4. Diff two runs

The `canonical_bad.jsonl` fixture contains the same orchestrator run, but the
router LLM chose the wrong sub-agent.

```bash
hindsight diff fixtures/canonical_good.jsonl fixtures/canonical_bad.jsonl --md
```

Output:

```markdown
# Diff report

- matched pairs — 4
- only in A — 3
- only in B — 3
- clean — False

**first divergence at path agent:orchestrator → llm:router on field 'response'**

## First-divergent step

- path — `agent:orchestrator → llm:router`
- field — `response`
- A: router  (llm)  value={'choice': 'stock-analyst'}
- B: router  (llm)  value={'choice': 'news-writer'}
```

Hindsight tells you exactly where the two runs split: the router LLM step
responded with `'choice': 'news-writer'` instead of `'choice': 'stock-analyst'`.
The 3 steps listed as "only in A" are the stock-analyst subtree; the 3 in "only
in B" are the news-writer subtree — they didn't align because their shared
parent diverged.

Drop `--md` for JSON output suitable for programmatic processing.

### Strict mode — tokens and latency

By default the diff compares semantic fields (`response`, `error`, `model`,
`kind`, `name`). Pass `--strict` to also compare `tokens_in`, `tokens_out`,
and `latency_ms`. Useful when you want a token-cost or wall-clock regression
gate that's independent of semantic divergence:

```bash
# Default diff: clean, even though tokens_out differs at step s5.
hindsight diff fixtures/canonical_token_div_good.jsonl fixtures/canonical_token_div_bad.jsonl --md

# Strict diff: catches the token divergence.
hindsight diff fixtures/canonical_token_div_good.jsonl fixtures/canonical_token_div_bad.jsonl --md --strict
```

The same pattern applies to `canonical_latency_div_{good,bad}.jsonl` for
latency regressions. Both flags pair with `--gate` on the CI variant
(`hindsight ci diff ... --gate --strict`) for a token-budget PR check.

---

## 5. Replay from a step

`hindsight replay` re-runs the tail of a trace from a specified step, with an
optional model swap. The default provider is `MockProvider` — deterministic,
zero network calls. Pass `--live` (and `ANTHROPIC_API_KEY` in your environment)
to use the real Anthropic API.

```bash
hindsight replay fixtures/canonical_good.jsonl \
    --from-step 3 \
    --model claude-sonnet-4-6 \
    --out /tmp/replayed.jsonl
```

What this does:

- Steps 0–2 are copied byte-for-byte from the original trace.
- From step index 3 onward, every `LLM` step is re-issued through the
  provider (MockProvider by default, which echoes the recorded request back
  as the response).
- All `LLM` steps in the replayed tail have their `model` field overridden to
  `claude-sonnet-4-6`, regardless of what model the original recorded.
- The output is written as JSONL to `/tmp/replayed.jsonl`.
- Run-level `extra["replay"]` records the provenance: `from_index`, `from_step`
  id, `model_override`, `provider`, and `live` flag.

To inspect the replayed trace:

```bash
hindsight show /tmp/replayed.jsonl
```

### Opt-in TOOL re-execution

By default only LLM steps in the replayed tail go through the provider —
AGENT, TOOL, and DECISION steps are copied verbatim, because re-executing
a tool may be destructive (`get_current_time`, a DB write, an irreversible
API call). The `--live-tools` flag opts TOOL steps into provider routing
too:

```bash
hindsight replay fixtures/canonical_good.jsonl --from-step 3 --live-tools --out /tmp/lt.jsonl
```

With `MockProvider` (default), this is still identity — TOOL steps come
back unchanged. The flag exists so callers supplying a custom provider
that actually re-executes tools have an explicit opt-in. AGENT and
DECISION steps are *always* copied verbatim — they're orchestration state,
not externally-derived results.

---

## 6. Use in CI

Hindsight's `diff` command exits non-zero when the two runs are not clean (i.e.,
when divergence is detected). This makes it straightforward to wire into a CI
pipeline that compares a golden trace against a newly captured one.

For documentation on setting up the CI gate, see the README's CI section.
(The README CI section is a merge-time addition by the maintainer; the pattern
is: capture a run in your test step, then call `hindsight diff golden.jsonl
captured.jsonl` and fail the job if the exit code is non-zero.)

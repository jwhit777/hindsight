# Hindsight — flight recorder and replay for LLM agents

*Draft. Not for publication until v0.2 (replay) ships and at least one real case study is in `case-studies/`.*

## The problem

Every LLM-agent observability tool worth its salt is hosted SaaS or framework-locked. Langfuse wants your data on their cloud. LangSmith wants you on LangChain. Phoenix wants your spans in Arize. Helicone proxies your requests. Datadog wants the contract. When an Anthropic FDE walks into a Fortune 100 customer with regulated data, an in-house OpenTelemetry collector, and a Compliance-signed-off Python venv, none of these are a drop-in. The customer's question — *"my agent failed in production, where did it go wrong?"* — has no local-first answer. The vendors solve their problem, not the customer's.

## What Hindsight is

A local-first, stdlib-core CLI plus library. Reads OpenTelemetry GenAI / LangSmith / Langfuse / native JSONL traces into one canonical `TraceRun` schema. Step through, aggregate stats, diff two runs, replay from any step (optionally swapping the model). No accounts. No cloud. The wheel is 36 KB; the core has zero non-stdlib dependencies. Live API calls happen only behind a `--live` flag in `hindsight replay`; everything else is offline.

```
$ pip install hindsight-trace
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
```

## The "missing primitive" framing

Three independent sources have converged on the same diagnosis in 2026. Sakura Sky's series on [missing primitives for trustworthy AI](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/) calls deterministic replay the missing primitive. Tian Pan makes [the same case from a different angle](https://tianpan.co/blog/2026-04-12-deterministic-replay-debugging-non-deterministic-ai-agents) — record once, replay deterministically, swap one variable at a time. [arxiv 2505.17716](https://arxiv.org/abs/2505.17716) makes the academic case for record-and-replay in agent loops. The GitHub projects [Litmus](https://github.com/rylinjames/litmus) and [agent-replay](https://github.com/manasvardhan/agent-replay) attack the HTTP-interception slice but neither does cross-format ingest nor diff. Hindsight is the assembled, documented, pip-installable tool that hits all three primitives (ingest + diff + replay) where prior work covers one.

## A worked demo

```
$ hindsight diff fixtures/canonical_good.jsonl fixtures/canonical_bad.jsonl --md
# Diff report
- matched pairs — 4
- only in A — 3
- only in B — 3
- clean — False

**first divergence at path agent:orchestrator → llm:router on field 'response'**
  A: router  (llm)  value={'choice': 'stock-analyst'}
  B: router  (llm)  value={'choice': 'news-writer'}
```

One path-from-root pointer, one diverged field, one bad routing decision. Same shape if the divergence is a hallucinated tool response or a different summary text. `hindsight replay <run> --from-step 6 --model claude-sonnet-4-6` re-runs from the divergent step with the swapped model. The replayed run is itself a `TraceRun` you can `hindsight diff` against the original.

## What it isn't

Not a Langfuse replacement. Not a LangSmith replacement. Not an observability platform — your production tracing pipeline stays exactly where it is. Hindsight sits *next to* your stack as the local-first debugger. Customer trace data only leaves the machine when the operator explicitly passes `--live`, and even then only the replayed prompts go out, not the recorded inputs.

## What's shipped

v0.1.0 is tagged on [GitHub](https://github.com/jwhit777/hindsight/releases/tag/v0.1.0) with wheel and sdist attached. CI is green on Python 3.10 / 3.11 / 3.12. 35+ tests cover the cross-format-identity spine, three divergence patterns (routing, LLM-content, tool-call), strict-mode token / latency diffs, replay semantics including model swap and the new `--live-tools` opt-in, and CLI exit codes for the `ci diff --gate` PR-check verb. PyPI publish is imminent.

## Call to action

Try it. Bring your own trace file in any of five supported formats. File issues on adapter edge cases. Contribute an adapter — the `BaseIngester` Protocol is 50 lines and the cross-format-identity test in CI is the contract. The 90-day target is a public catalog of canonical agent-failure diffs with diagnoses and fix recipes; the more real traces, the better that catalog gets.

— `https://github.com/jwhit777/hindsight`

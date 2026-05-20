# DEMO-PLAN — 5-minute interview demo

The interview demo is the single most-leveraged surface this project gives Justin. Five minutes, one screen, one terminal. The hiring manager must feel "oh, this is the thing every customer wants" inside 60 seconds.

---

## Pre-demo setup (done before the interview, off-camera)

* `~/demo/` directory with one good run and one bad run already on disk:
  * `runs/good_run.jsonl` — a 19-step run that ends successfully.
  * `runs/bad_run.jsonl` — same starting prompt, ends in a context-window overflow on step 14.
  * `runs/bad_run.langsmith.json` — same bad run, exported in LangSmith shape, to make the "cross-format" point.
* `hindsight` installed (`pip install -e .` from local checkout).
* Terminal font cranked to readable; `tput cols` >= 100.
* Single browser tab open to the README on GitHub (only if asked "is this real?").

---

## The 5-minute script

### 0:00 — 0:30 — frame the problem in two sentences

> *"You're an FDE at a Fortune 100. The agent your customer deployed last week is failing 4% of the time. Their security team will not let you put traces on a SaaS observability platform. What do you do?"*

(Pause. They've thought about this.)

> *"This is Hindsight. It's pip-installable, stdlib-only core, reads any trace format, and lets you find the divergence in 60 seconds without exfiltrating a single byte of customer data."*

### 0:30 — 1:30 — the "show" command — they see a real trace

```bash
$ hindsight ingest runs/bad_run.jsonl
  → ingested 19 steps · run_2026-05-15T09-12-44
$ hindsight show run_2026-05-15T09-12-44
```

Output is a colored tree. They see agent boundaries, LLM calls, tool calls, the error highlighted in red on step 14.

Narrate: *"Each step has kind, model, tokens, latency. Tools and LLM calls are leaves. Errors are red. Tree comes from `parent_id`."*

### 1:30 — 2:30 — diff is the wow

```bash
$ hindsight diff runs/good_run.jsonl runs/bad_run.jsonl
```

Output: side-by-side, divergence at step 8 highlighted, downstream cascade visible.

Narrate: *"Two runs with the same starting prompt. Diff aligns by structural path. Divergence point is step 8 — the router went to `news-writer` instead of `stock-analyst`. Everything after that is downstream of that one routing decision. So I don't need to read 19 steps. I read one."*

(This is the punchline. If they nod here, the demo has already worked.)

### 2:30 — 3:30 — the cross-format trick

```bash
$ hindsight ingest runs/bad_run.langsmith.json
  → ingested 19 steps · run_2026-05-15T09-15-02 (source: langsmith)
$ hindsight diff run_2026-05-15T09-12-44 run_2026-05-15T09-15-02
  → no structural divergence (12 steps matched, 0 divergent fields)
```

Narrate: *"Same run, exported in LangSmith shape. Different field names, different structure on disk. Hindsight reads it into the same canonical, and diff confirms they're structurally identical. That's how you debug across customer environments that each pick a different vendor."*

### 3:30 — 4:30 — replay is the lock-in

```bash
$ hindsight replay run_BAD --from-step 8 --model claude-sonnet-4-6 --live
  → re-running 11 downstream steps with claude-sonnet-4-6 (router was haiku-4-5)...
  → run_2026-05-15T09-22-10 created (replay)
  → cost delta: +$0.012  ·  latency delta: +3.4s  ·  outcome: SUCCESS
$ hindsight diff run_BAD run_2026-05-15T09-22-10
  → divergence at step 8 (LLM: router decision)
  → bad: routed to news-writer
  → replayed: routed to stock-analyst → ran to completion
```

Narrate: *"Branch from step 8, override the model to Sonnet, hit live API, get a new run that succeeds. Pay an extra penny per query, get correctness. That's the FDE recommendation to the customer: bump the router to Sonnet."*

### 4:30 — 5:00 — close on the FDE bullet

> *"That last screen is what the Anthropic FDE posting calls 'codifying repeatable deployment patterns'. I've started a public catalog of these: routing-too-eager, context-window-overflow, tool-loop-divergence. Each one is a Hindsight diff plus a 2-paragraph diagnosis plus a fix recipe. Customers paste them into their runbook. That's the artifact I'd want to bring to a customer engagement on day one."*

End.

---

## Technical follow-up questions — pre-canned answers

### Q: How do you align steps across formats with different IDs?

A: Adapters reconstruct deterministic IDs as SHA-1 over `(parent_path, kind, name, started_at)` if the source doesn't carry stable IDs. The path-from-root tuple is the actual alignment key in diff — IDs are convenience.

### Q: What happens if the trace formats disagree on what a "step" is?

A: The canonical schema defines step kinds explicitly (AGENT / LLM / TOOL / DECISION). Adapters do the mapping: an OTEL `agent.invocation` span becomes an AGENT step; a `gen_ai.client.inference.operation` becomes an LLM step. Mapping decisions are documented per-adapter and unit-tested by the cross-format-identity assertion.

### Q: How do you handle non-determinism on replay?

A: Two modes. Default — re-emit recorded tool responses, hit the live API only for LLM calls from step `k` onward. Aggressive — `--live-tools` actually re-executes tools (dangerous, behind an opt-in). Tools that should never re-execute (write APIs) can be marked in a config file; the replayer surfaces them as warnings.

### Q: How does this compare to Langfuse / LangSmith?

A: Both want your data on their cloud (LangSmith) or on your self-hosted Postgres + ClickHouse (Langfuse). Both export only their own format on the way out. Hindsight is local-first stdlib Python, reads *their* exports, doesn't replace them — sits next to them as the cross-vendor debugger.

### Q: How big can a trace get before this falls over?

A: v0.1 loads the whole JSONL into memory. ~1 MB / 1000 steps. Above 100k steps, switch to SQLite-backed (Phase 3). For a typical customer agent that fails once, the trace is hundreds of steps, not thousands.

### Q: What about PII?

A: Hindsight is local, no network on the default install. PII never leaves the box. `hindsight redact` (Phase 2) strips configurable fields before sharing.

### Q: Why not just contribute to Langfuse?

A: Langfuse's value is the SaaS / self-host platform — the dashboard, the metrics, the prompt management. Adding "read any vendor's export and diff it" would dilute their core product. Hindsight is the cross-vendor diagnostic *next to* whichever observability stack the customer picks. The two compose.

### Q: Wait — there's [Litmus](https://github.com/rylinjames/litmus), wasn't this already built?

A: Litmus is HTTP-interception-based recording; it doesn't do cross-format ingest, it doesn't do structural diff, it doesn't do replay-with-model-swap. agent-replay does some of the recording side but no diff. The literature ([Sakura Sky](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/), [arxiv 2505.17716](https://arxiv.org/abs/2505.17716)) calls deterministic replay a missing primitive. Hindsight is the assembled tool with all three primitives (ingest + diff + replay) and zero vendor lock-in.

### Q: What's the eval discipline?

A: See `EVALS.md`. Spike has 10 self-tests, all passing. The canonical-identity assertion is the spine: same logical run, three formats, byte-identical canonical. If that test goes red, every downstream feature is suspect. CI runs in <2 seconds.

---

## Demo failure modes (and recovery)

* **Live API rate-limits during replay step.** Backup: have the replayed-run pre-recorded; demo it as if live. Disclose if asked.
* **Color escapes garbled on their projector.** `--no-color` flag exists; cuts to plain.
* **They ask about a format I don't support.** Honest answer: adapter takes one afternoon to write, the canonical-identity test makes it safe to land.

# CANDIDATES — 2026-05-15 portfolio-project run

This is the fourth overnight run of the portfolio-project skill. The first three runs produced **Sub-Agent Bench** (orchestrator-layer evals, 2026-05-12), **MCP Probe** (MCP protocol-layer evals, 2026-05-13), and **Skillsmith** (Agent Skills layer calibration, 2026-05-14). Together they map verbatim onto the Anthropic FDE bullet "MCP servers, sub-agents, and agent skills."

The *next* Anthropic FDE bullet is the one this run targets: **"Identify and codify repeatable deployment patterns and contribute insights back to our Product and Engineering teams."** Deployment patterns get codified by looking at production runs that worked vs. ones that didn't. That requires production-trace tooling. The triptych is offline evals; this run extends into the runtime side.

---

## Step 1 recap — calibrated target

Pulled from postings and confirmed against the May 2026 hiring shocks (Anthropic + Blackstone + Goldman Sachs + Hellman & Friedman $1.5B JV announced 2026-05-04; OpenAI Deployment Company + Tomoro acquisition 2026-05-11):

**Anthropic Forward Deployed Engineer, Applied AI** ([Greenhouse 4985877008](https://job-boards.greenhouse.io/anthropic/jobs/4985877008), re-fetched 2026-05-15):
> "Work within customer systems to build production applications with Claude models … Deliver technical artifacts for customers like MCP servers, sub-agents, and agent skills that will be used in production workflows … **Identify and codify repeatable deployment patterns** and contribute insights back to our Product and Engineering teams."

**Anthropic Forward Deployed Engineer (broader)**: [Greenhouse 5121563008](https://job-boards.greenhouse.io/anthropic/jobs/5121563008).
**Anthropic Applied AI Engineer (Startups)**: [Greenhouse 5116274008](https://job-boards.greenhouse.io/anthropic/jobs/5116274008).
**Anthropic Applied AI Engineer (Digital Natives)**: [Greenhouse 5057647008](https://job-boards.greenhouse.io/anthropic/jobs/5057647008).
**OpenAI Forward Deployed Software Engineer, NYC**: [Ashby 533c0fc9](https://jobs.ashbyhq.com/openai/533c0fc9-b773-476d-9f96-a0528efbab0e).
**Sierra Software Engineer, Agent**: [Ashby c0003c50](https://jobs.ashbyhq.com/Sierra/c0003c50-f3e9-4096-8553-45fc1b7c7f91) — "complete ownership and autonomy from initial pilot through deployment and continuous iteration, including building, tuning, and evolving AI agents in **production environments**".
**Scale Applied AI Engineer, Enterprise GenAI**: [Scale 4514173005](https://scale.com/careers/4514173005).
**Cohere Applied AI Engineer – Agentic Workflows**: [Ashby 1fa01a03](https://jobs.ashbyhq.com/cohere/1fa01a03-9253-4f62-8f10-0fe368b38cb9).
**Harvey Staff Applied AI Engineer**: [Ashby 14bc0927](https://jobs.ashbyhq.com/harvey/14bc0927-4e68-45ad-809e-d44fc860dbe0).

**Skills that repeat across all eight postings** (signal of universal screening criteria):
1. **Production LLM experience, deployment at scale** — every posting.
2. **Evaluation frameworks** — every posting (the triptych covers this).
3. **Agent architectures: MCP, sub-agents, skills, tool use** — Anthropic, OpenAI, Sierra, Cohere.
4. **Python + TypeScript proficiency** — every posting.
5. **Customer-facing translation** — Anthropic (3 bullets), OpenAI, Scale, Harvey.
6. **Production debugging, observability, codifying deployment patterns** — Anthropic ("codify repeatable deployment patterns"), Sierra ("continuous iteration in production"), Scale, Harvey.
7. **Travel 25–50% to customer sites** — Anthropic FDE only.

**The gap in my current portfolio**: items 1–4 are demonstrated by the triptych. Item 5 is implicit in the writing of the project blog posts. Item 6 — **production observability / debugging in customer environments** — is the one bullet I haven't covered. Postings reward it heavily (Anthropic's literal phrase "codify repeatable deployment patterns"; Sierra's literal phrase "continuous iteration in production").

That's the target this project must hit.

---

## Step 2 — Six candidate projects

### Candidate A — Hindsight: open-source flight recorder + replay debugger for LLM agents

**Pitch (30s):** Hindsight is a local-first, pip-installable CLI + library that ingests any LLM agent trace — OpenTelemetry GenAI, LangSmith export, Langfuse export, or plain JSONL — normalizes it to a canonical schema, and lets you step through it, branch from any step (with optional model swap), and diff two runs side-by-side to find where the agent diverged. The format-war problem ([OTEL GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) are still experimental, every vendor exports differently) plus the local-first constraint (Langfuse / LangSmith / Phoenix / Helicone / Laminar are SaaS-first and require accounts) leaves a clean opening. Sakura Sky calls deterministic replay [a "missing primitive for trustworthy AI" (2026)](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/); arxiv 2505.17716 makes the same argument from the research side.

**Skills demonstrated:** production trace handling, OTEL GenAI semantic conventions, multi-format adapters, deterministic replay semantics, CLI engineering, eval/diff algorithms, customer-facing diagnostic UX.

**Why differentiated:** Every existing tool in this space is hosted SaaS or framework-specific. Hindsight is the *interop* play: read any format, diff any pair, replay from any step, no account required. Litmus and agent-replay (both 2026 GitHub repos) attack one slice (HTTP-interception recording) but neither does diff, neither does branch-from-step with model swap, neither speaks 3 formats.

**Time:** 4–5 weeks of evenings/weekends to v1.0. Spike (ingest + canonical + diff) is one overnight session. v0.1 ingest+show+diff (no replay yet, no UI) ships in week 1. Replay-from-step lands week 2. Local web UI (FastAPI + zero-build HTML) lands week 3.

**Biggest risk to shipping:** Schema drift — OTEL GenAI spec is experimental, vendors are still on different versions. Mitigation: design canonical schema first; add adapter per format; lock to a single OTEL version per release; fail loud with helpful error on mismatched fields. The schema work is exactly the point of the project, so the risk is also the value.

---

### Candidate B — Costmap: token + latency forecaster for agent workflows

**Pitch (30s):** Read an agent workflow spec (YAML, or extracted from a trace), predict per-step token cost and total latency before you run it, suggest model swaps (Haiku for routing, Sonnet for synthesis), validate predictions against real runs. Closes the budget-anxiety gap every FDE hears from enterprise procurement.

**Skills demonstrated:** workflow modeling, model-pricing knowledge, prediction calibration, customer-facing reporting.

**Why differentiated:** Predicting cost *before* running, rather than reporting it after, is rare. Anthropic admin token analytics, OpenAI dashboard, Helicone — all are observational. Pre-flight modeling is a different category.

**Time:** 3–4 weeks. Spike-friendly (pure offline modeling, no API calls).

**Biggest risk:** Pricing tables go stale within weeks; need a pricing-table-refresh job. Real workflows vary so wildly that headline accuracy numbers will be embarrassing unless I find a narrow, well-defined slice (sub-agents-from-the-triptych is the obvious one).

---

### Candidate C — Demo Forge: customer-spec → demo prototype pipeline

**Pitch (30s):** Given a customer's plain-English problem statement, generate (a) a structured engagement spec, (b) an eval-suite stub that plugs into Sub-Agent Bench / Skillsmith, (c) a deployable Streamlit demo. This is *literally* the FDE day-job automated — the "translation layer" Anthropic and Sierra postings name.

**Skills demonstrated:** structured-output prompting, codegen, customer translation, UI scaffolding.

**Why differentiated:** No public tool does this end-to-end. Demo-builders exist (Vercel v0, Streamlit Designer) but none output an eval suite. The eval-suite output is the differentiator and the FDE-flavor signal.

**Time:** 5–6 weeks (the Streamlit codegen alone is a multi-week project).

**Biggest risk:** Scope creep. The "generate eval + demo + spec" combo is three projects pretending to be one. Risk of shipping nothing.

---

### Candidate D — PromptOps: production prompt deployment + rollback tooling

**Pitch (30s):** Treat prompts like code. Version them, A/B by user cohort, roll back with one command, gate every promotion on an eval-pack pass. Differentiated from PromptLayer (SaaS) and from open-source prompt-flow (too heavy, Microsoft-flavored).

**Skills demonstrated:** prompt versioning, A/B infra, deployment workflows, eval-gate integration.

**Why differentiated:** Limited. PromptLayer covers most of the surface, even if it's SaaS. Promptfoo also exists. Real chance of being a "PromptLayer-but-OSS" knockoff.

**Time:** 4–5 weeks. Spike requires real backend infrastructure (DB + auth + rollback). Hard to spike convincingly overnight.

**Biggest risk:** Either you make it customer-grade (months of work) or you make it a toy. Hard middle ground.

---

### Candidate E — Brief: structured FDE-engagement intake bot

**Pitch (30s):** A Claude-powered intake interview that turns a 30-minute customer call into a structured engagement brief — pain points, success criteria, data sources, integration constraints, decision-makers, fitness-to-deploy gate. Feeds Demo Forge.

**Skills demonstrated:** structured extraction, multi-turn elicitation, Claude tool use, customer-discovery doc patterns.

**Why differentiated:** Generic chat-with-customer bots exist; *structured-brief-extraction-for-FDE-specifically* doesn't. But the wins are mostly in the prompt and the schema — hard to make a 4-week-shippable repo around it.

**Time:** 2–3 weeks. Mostly prompt work + schema design + one demo loop.

**Biggest risk:** Too thin for a portfolio centerpiece. Could be a small companion side-project but not a featured one.

---

### Candidate F — Citadel: production guardrail evaluator

**Pitch (30s):** Take a guardrail spec (regex, semantic, classifier-based, or constitutional-AI-style ruleset), run it against synthetic adversarial prompts, report pass rate + false-positive rate. Complements MCP Probe (which is reviewer-side) by giving operator-side guardrail testing.

**Skills demonstrated:** adversarial prompting, classifier evaluation, FP/FN tradeoff analysis, safety eng patterns.

**Why differentiated:** Some overlap with Anthropic Constitutional AI tooling, with Lakera, with Nvidia NeMo Guardrails. The differentiator would have to be the synthetic-attack-generation quality.

**Time:** 4–5 weeks.

**Biggest risk:** Plays in a regulated space — easy to look like a toy next to Lakera. And — uncomfortably — competes with my own MCP Probe story (both are "scan an artifact for safety issues"). Adds noise to the triptych instead of completing it.

---

## Step 3 — Situational Awareness ranking

Scoring rubric per tenet. Each cell uses ★ 1–5.

| Project    | Trendline fit | Insider view | Differentiation | Concreteness | Total |
|------------|---------------|--------------|-----------------|--------------|-------|
| A Hindsight| ★★★★★         | ★★★★★        | ★★★★            | ★★★★★        | **19** |
| B Costmap  | ★★★★          | ★★★          | ★★★             | ★★★★         | 14    |
| C Demo Forge| ★★★★★        | ★★★★         | ★★★★★           | ★★★          | 17    |
| D PromptOps| ★★★           | ★★★          | ★★              | ★★★★         | 12    |
| E Brief    | ★★★           | ★★★★         | ★★★             | ★★★          | 13    |
| F Citadel  | ★★★★          | ★★★★         | ★★★             | ★★★★         | 15    |

### Defense of the pick — Hindsight

**Trendline fit (tenet 1).** Three independent trendlines converge on agent-trace tooling. (1) The agent layer itself: every 2026 FDE/Applied AI posting names "production agents." More agents in production means more bugs in production means more trace-debugging work. (2) Standards adoption: the OTEL GenAI semantic conventions exist and are being implemented (Datadog v1.37, Grafana Loki). Once the format settles, a tool that reads the format wins. (3) Open-source-vs-SaaS pendulum: with Langfuse, Phoenix, and Laminar all having open cores, the gravity is toward OSS, but each one is tied to its own export format. A true interop layer wins on the cross-vendor axis.

**Insider view (tenet 3).** The Anthropic FDE posting literally says "Identify and codify repeatable deployment patterns and contribute insights back to our Product and Engineering teams." Mainstream candidates read that bullet as "you'll write a blog post." The insider read: you'll produce *artifacts* — replay-able traces with annotations, deployment-pattern catalogs sourced from real runs. Hindsight produces those artifacts as its primary output. It is the **literal tool a future FDE would build** while doing the job.

**Differentiation / third-way positioning (tenet 5).** The tribal positions: (a) SaaS-tribal — "use Langfuse / LangSmith / Phoenix"; (b) DIY-tribal — "just print() and grep your logs." The third way: local-first OSS that reads every export. Plays well with whatever stack the customer already has, requires no migration, leaves no SaaS lock-in. Litmus and agent-replay are early efforts in this direction but each handles one slice; Hindsight is the integration layer + diff/replay engine.

**Concreteness (tenet 6).** The demo is one sentence: "I have a trace where my agent failed; let me show you me finding the divergence in 60 seconds, then re-running from step 4 with Sonnet instead of Haiku." A hiring manager understands that demo in three breaths.

**Burden of evidence cuts both ways (tenet 8).** Cost: the space is crowded, the OSS bar is high. Counter: every existing tool requires a SaaS sign-up or a single-vendor SDK; none of them does *cross-format diff*. The empty quadrant is real.

**Find the binding constraint (tenet 7).** The binding constraint is **canonical-schema design across heterogeneous trace formats**. Once that's solved, everything downstream (show, diff, stats, replay) is shallow. That's the overnight spike target.

### Why Hindsight beats Candidate C (Demo Forge), the #2 pick

Demo Forge is more impressive at first glance — three deliverables in one. It loses on three counts. (1) Scope risk: three deliverables in one means three places for the project to stall; Hindsight has one core deliverable and four cleanly-bounded surface features. (2) Spike-overnight feasibility: Hindsight's binding constraint (canonical schema + multi-format ingest + diff) is exactly the kind of thing that fits in one stdlib-only Python overnight build. Demo Forge's binding constraint (Streamlit codegen quality) is multi-week. (3) Triptych complement: Hindsight gives the *runtime* counterpart to the offline triptych, completing a clean four-piece narrative. Demo Forge starts a new narrative.

### Why Hindsight beats Candidate F (Citadel), the #3 pick

Citadel is closer to the triptych theme (more evals) but that's the problem — it's the *fourth* evals tool in a portfolio that has three. Marginal value drops. Hindsight is the first runtime tool, so it expands the surface the portfolio covers, which is the better hiring-manager story.

**Final pick: Hindsight.**

The remaining file in this folder, `PLAN.md`, is the bottleneck-scoping skill applied to Hindsight.

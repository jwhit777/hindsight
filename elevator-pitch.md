# Elevator pitch — 60 seconds, verbal

For interviews and "what are you working on?" conversations. Memorise the structure, not the exact words.

---

**Hook (5 sec):** *"Every LLM-agent observability tool today wants your data on their cloud or your SDK in their flavor. So when an FDE walks into a Fortune 100 with regulated data and a 'why did my agent fail at 3 a.m.' problem, there's no drop-in answer. That's the gap Hindsight fills."*

**What it is (15 sec):** *"Hindsight is an open-source, pip-installable Python tool that reads any LLM agent trace — OpenTelemetry GenAI, LangSmith export, Langfuse export, naked JSONL — normalizes them into one canonical schema, and lets you do three things: step through the run, diff a passing run against a failing one to find exactly where the agent diverged, and replay from any step with a different model to see what would have fixed it."*

**The wow moment (15 sec):** *"The demo is four terminal commands. I show two seven-step traces — one where the agent answered correctly, one where it hallucinated — and Hindsight diffs them in milliseconds and tells me the divergence happened at the router LLM step where Haiku picked the wrong sub-agent. Then I replay from that step with Sonnet and the run succeeds. The customer gets a one-line recommendation: 'bump the router to Sonnet, you pay a penny extra per query, you get correctness.' That's the actual FDE deliverable."*

**Why now (15 sec):** *"Three trendlines converge. Anthropic + Blackstone just announced a $1.5B enterprise-AI joint venture; OpenAI launched a Deployment Company. The number of agents in production is going vertical. OpenTelemetry GenAI semantic conventions are finally being adopted by Datadog and Grafana. And the OSS observability tools — Langfuse, Phoenix, Laminar — are all winning their lanes, leaving the cross-vendor diagnostic layer empty. Hindsight is that empty quadrant."*

**Close (10 sec):** *"This is the fourth piece of an FDE portfolio I've been building — alongside Sub-Agent Bench for orchestrator evals, MCP Probe for protocol-layer security, and Skillsmith for skill calibration. Together they match the Anthropic FDE bullets word for word: MCP servers, sub-agents, agent skills, plus 'codify repeatable deployment patterns,' which is what Hindsight produces."*

---

## Compressed version (30 seconds)

*"Hindsight is a flight recorder for LLM agents. Pip install. Reads any trace format — OTEL, LangSmith, JSONL. Diff two runs to find where the agent diverged. Replay from any step with a different model. All local — no SaaS account, no exfiltration. The demo is one terminal screen: I diff a good run against a bad run, find the routing mistake at the LLM step, replay with Sonnet, get correctness. That's the FDE customer-day-one deliverable."*

## Ten-second version (for "what are you working on this week?")

*"An open-source flight recorder for LLM agents — reads any trace format, diffs two runs to find the divergence, replays from any step with a different model. Local-first. The empty quadrant in the observability landscape."*

---

## Variants for context

* **For Anthropic specifically:** lead with the FDE bullet. *"Anthropic's FDE posting says 'identify and codify repeatable deployment patterns and contribute insights back.' Hindsight produces the artifact that bullet describes — a catalog of recurring agent-failure diffs with diagnoses."*
* **For OpenAI / Sierra / Cohere:** lead with the production-debugging pain. *"Every agent in production fails somewhere. The current answer is paste-the-trace-into-LangSmith and squint. Hindsight is local-first and reads everyone's format."*
* **For an OSS-flavored conversation (Modal, Together, Replicate):** lead with the integration layer point. *"Observability has won — Langfuse, Phoenix, Laminar all have working tools. What hasn't been built is the cross-vendor diagnostic that reads everyone's export and does structural diff."*

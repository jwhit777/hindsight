# Cover-letter snippet

Two paragraphs. Drop into the body of a cover letter where you'd normally describe a project. Tune the company name and the specific bullet they list. The framing below targets the Anthropic FDE posting on Greenhouse.

---

I have been building a four-piece open-source toolkit that maps onto the deliverables your FDE posting lists verbatim — *MCP servers, sub-agents, agent skills,* and *codifying repeatable deployment patterns.* The first three are pre-deployment evaluation frameworks: Sub-Agent Bench measures orchestrator-plus-sub-agents systems with a κ-calibrated LLM judge; MCP Probe is a defensive trust-scanner for Model Context Protocol servers that runs deterministic probes for schema fidelity, prompt-injection, and tool-description poisoning; Skillsmith is an eval-and-tuning toolkit for Agent Skills packs that measures cross-skill confusion as a first-class metric and produces Cohen's-κ calibration cards. All three are stdlib-first Python, public on GitHub, with passing CI, and used as dogfood inputs to each other.

The fourth piece — Hindsight, shipped this week — is the runtime counterpart to the offline triptych. It is a local-first, pip-installable flight recorder + replay debugger that ingests any agent trace format (OpenTelemetry GenAI semantic conventions, LangSmith export, Langfuse export, plain JSONL), normalizes them into one canonical schema, and supports step-through, structural diff between two runs, and replay-from-any-step with optional model swap. The design is opinionated about *staying local*: the default install has zero external dependencies and never touches the network, because the customer data that needs debugging the most is the data that can't go to a SaaS observability platform. The 90-day deliverable is a publicly shared deployment-pattern catalog — a library of recurring Hindsight diffs with two-paragraph diagnoses and fix recipes. That artifact is the literal thing your "codify repeatable deployment patterns" bullet describes, and I think it is the right portfolio piece to bring into a customer engagement on day one.

---

## Alternate first paragraph for Applied AI Engineer (non-FDE) postings

I have been building an open-source toolkit for the agentic stack — orchestrator-plus-sub-agents evals, MCP server security probes, Agent-Skills calibration, and now a cross-format trace debugger. The discipline through all four is the same: stdlib-first Python core, public κ-floor of 0.65 on every judged output, JSON + Markdown calibration cards from every run, offline-first execution with live API access behind opt-in flags. The reason for the discipline is that each tool is meant to be installed by a customer behind a corporate proxy without escalating to a security review, and each tool produces an artifact the customer can paste into their own documentation. The newest piece, Hindsight, is the runtime debugger — it reads any agent trace export, normalizes it to a canonical schema, and supports structural diff and replay-from-step. It is the artifact a forward-deployed engineer wants for the day-three production-bug call that every enterprise agent deployment eventually generates.

---

## Notes for assembly

* Pair the first paragraph with the post's "what we're looking for" bullets — pick the two that most clearly match the toolkit, name them, and explicitly say "this is what the [tool name] piece does."
* If the company emphasizes a specific model, weight the demo description toward that model. (e.g., for an Anthropic application, lead with Claude-Haiku-vs-Claude-Sonnet routing; for OpenAI, frame it as o-series vs. GPT-series).
* Include one URL: the public GitHub repo (Hindsight, when shipped) and a one-line description of the demo. Hiring managers reviewing FDE applications click on links — make the click rewarding by pointing to the README hero example, not the project root.

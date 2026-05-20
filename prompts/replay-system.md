# prompts/replay-system.md — versioning note

Hindsight is a tool, not an agent. The only LLM call Hindsight ever makes is during `hindsight replay --live`, when it re-issues recorded prompts to a real model. There is no Hindsight-authored prompt in that path: we replay *the customer's* prompt verbatim.

This file exists for two future use cases:

## v0.3 — `--explain` flag on diff (optional, opt-in)

If/when Phase 3 ships the optional Haiku-judge explanation of a divergence, this is the template. Current draft (NOT YET WIRED IN):

```
# system
You are a debugging assistant for LLM agent runs.
Two agent runs diverged at a specific step. Below are the two steps and the
two preceding steps for context. Produce ONE paragraph of plain English
explaining the most likely cause of the divergence. No lists. No code. No
speculation about steps you cannot see.

# user
Step k-2 (shared): {step_k_minus_2}
Step k-1 (shared): {step_k_minus_1}
Step k from run A: {step_k_a}
Step k from run B: {step_k_b}
```

Version: v0 (drafted 2026-05-15, not in production).

## v0.4 — `--suggest` flag on replay (optional)

If Phase 4 adds a "suggest the smallest change that would have made run B succeed", this is where its template lives. Current draft: not yet written; gather a corpus of paired good/bad runs first to anchor the prompt with real examples.

## Versioning discipline

Every prompt change must include:

* a version bump in the YAML frontmatter at the top of the prompt file (not yet present — added when v0.3 lands);
* a regression test in `tests/test_prompts.py` comparing the new prompt's output against the prior version on a fixed 10-pair gold set;
* a CHANGELOG entry under the version.

Until v0.3 ships, this file is reserved scaffolding.

---
name: Bug report
about: Something Hindsight does wrong, crashes on, or misreports.
title: ""
labels: ["bug"]
assignees: ""
---

## What broke

A one-sentence summary of the bug.

## Environment

- Hindsight version: <!-- e.g. 0.1.0; check with `pip show hindsight-trace` -->
- Python version: <!-- e.g. 3.12.4 -->
- OS: <!-- e.g. macOS 14.5, Ubuntu 24.04 -->
- Trace format: <!-- jsonl / langsmith / otel / langfuse / subagent_bench / other -->

## Reproduction

Smallest command + smallest input that reproduces the bug:

```bash
hindsight <verb> <args>
```

If the input is a trace file: paste a *minimal* excerpt (or point at an
existing `fixtures/*.{json,jsonl}` file). The
cross-format-identity property is the spine of this project — a single
failing fixture that violates it is the gold-standard repro.

## Expected vs actual

- **Expected:** what Hindsight should have done.
- **Actual:** what it did instead (paste output / error / traceback).

## Anything else

Workarounds you've found, related issues, hypotheses about the cause.

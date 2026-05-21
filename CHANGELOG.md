# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-05-21

### Added
- **Canonical TraceRun schema** — single dataclass tree (`TraceRun` /
  `TraceStep`) that absorbs four trace formats and exposes them through a
  uniform interface.
- **Four ingest adapters**: native JSONL, LangSmith run-tree export,
  OpenTelemetry GenAI spans, Langfuse trace export. All four produce
  structurally-identical canonical output for equivalent input
  (cross-format-identity property).
- **Plugin protocol** (`hindsight.BaseIngester`) — third parties can register
  new format adapters without touching the core. `register()` works as a
  decorator or a function call; `auto_ingest()` dispatches across all
  registered adapters in registration order.
- **CLI verbs**: `hindsight show`, `hindsight stats`, `hindsight diff`,
  `hindsight replay`, `hindsight ci diff [--gate] [--md]`,
  `hindsight validate`. The `ci diff --gate` form exits 1 on divergence
  so it can be wired into a PR check; `validate` exits 0 on conformance,
  2 on schema violation, 1 on missing file.
- **Replay engine** — record-substitution from any step (`--from-step N`),
  with optional model override (`--model M`) and live API mode (`--live`,
  behind the `[live]` extra). `MockProvider` is the deterministic default
  (zero network calls).
- **CI matrix** on Python 3.10 / 3.11 / 3.12.
- **31 tests** across three suites (`test_spike.py`, `test_replay.py`,
  `test_cli_verbs.py`): cross-format-identity spine (A), round-trip (B),
  three divergence-fixture pairs (C1–C3), stats math (D), tree depth (E),
  extra-field preservation (F), OTEL parent linkage (G), clean diff (H),
  dangling-parent validation (I), Langfuse round-trip (J), plugin-protocol
  dispatch (K), plus 10 replay tests covering step cutoff, model override,
  invalid-step errors, and lazy-import guards for both Anthropic and OpenAI
  providers, plus 9 subprocess-driven CLI tests covering `ci diff --gate`
  exit codes and `validate` schema checks.

### Project shape
- Stdlib-only core; `[live]` extra adds `anthropic` + `openai`;
  `[otel]` extra adds `opentelemetry-sdk`.
- Apache-2.0 licensed.

[Unreleased]: https://github.com/jwhit777/hindsight/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jwhit777/hindsight/releases/tag/v0.1.0

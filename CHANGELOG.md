# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-05-21

### Added
- **Sub-Agent Bench adapter** (`ingest_subagent_bench`) — 5th ingest format.
  Maps the nested `orchestrator → steps → subagent_call → steps` structure
  into the canonical schema. Cross-format-identity property now holds
  across 5 adapters.
- **`replay --live-tools` flag** — opt-in routing of `StepKind.TOOL` steps
  through the provider in the replayed tail. Default behavior unchanged
  (TOOL steps copied verbatim). `MockProvider` identity-passes them with
  zero network; live providers fall back to identity when the recorded
  request has no `messages`. Callers who want real tool re-execution
  supply their own provider.
- **`diff --strict` and `ci diff --strict` CLI flags** — expose the
  pre-existing `strict=True` semantic that also compares `tokens_in`,
  `tokens_out`, and `latency_ms` per step. Useful for token/latency
  regression gates separate from semantic divergence.
- **Strict-mode divergence fixture pairs** —
  `canonical_token_div_{good,bad}.jsonl` and
  `canonical_latency_div_{good,bad}.jsonl` plus 4 new tests (C4–C7)
  verifying that default diff stays clean while `--strict` catches the
  divergence at the affected step.
- **LAUNCH.md draft** at repo root — not for publication; launch-post
  outline for when v0.2 hits PyPI.
- **README visual** — small ASCII "Hindsight is 20/20" panel before the pitch.
- **Pre-commit hooks** (`.pre-commit-config.yaml`) — `ruff --fix` + `mypy`
  on every commit. Enable with `pre-commit install` after a fresh clone.
- **mypy CI job** — catches type regressions on push; runs in
  `--ignore-missing-imports` mode against `src/hindsight/`. Codebase is
  currently 0 mypy errors.
- **OSS welcome surface** — `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.md`,
  `.github/pull_request_template.md`, expanded `pyproject.toml` classifiers
  / keywords / project URLs, and `Makefile` `install`/`dev`/`dev-live`/
  `publish-test`/`publish` targets.
- **`hindsight version`** subcommand + top-level `--version` — prints
  version (read from `importlib.metadata` so it can't drift from
  `pyproject.toml`), Python version, registered ingesters, replay providers.
- **`hindsight show --json`** — emit canonical JSONL instead of the tree;
  one-liner for cross-format conversion (`hindsight show otel.json --json >
  canonical.jsonl`).
- **`hindsight show --depth N`** — cap tree depth (0 = header only,
  1 = root only, N = up to N levels). Tree-only; silently ignored with
  `--json`.
- **`hindsight serve`** + new `[web]` extra — local FastAPI web UI
  (browse / show / diff / replay) behind `pip install
  'hindsight-trace[web]'`. Zero-build HTML, no JS framework, server-
  rendered Jinja2 with HTML5 `<details>` for collapsible request/response
  drill-down. Path inputs strict-bounded to `--root` to prevent traversal.
  Replay on the web path is MockProvider-only by design — `--live` /
  `--live-tools` stay CLI-only for clear audit trails. The `hindsight.web`
  module is opt-in; core remains stdlib-only.

### Changed
- **`__version__`** now read from package metadata via `importlib.metadata`
  rather than a literal string; eliminates version-drift class of bugs.
- **Test count: 55** across `test_spike.py` (18), `test_replay.py` (12),
  `test_cli_verbs.py` (14), `test_web.py` (11, skip when `[web]` not installed).
- **CI runs on Node 24** via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` in
  the workflow env. Surfaces any incompatibility now ahead of GitHub's
  2026-09-16 hard cutover; current actions/checkout@v4 +
  actions/setup-python@v5 are compatible.
- **README cleanup** — dropped the "Where this fits in Justin's portfolio"
  section and all Day-0 / Day-1 / `FIRST-4-HOURS.md` references; refreshed
  file tree, test count, adapter count, and "What ships next" section to
  match v0.1.0+ reality.

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

[Unreleased]: https://github.com/jwhit777/hindsight/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jwhit777/hindsight/releases/tag/v0.2.0
[0.1.0]: https://github.com/jwhit777/hindsight/releases/tag/v0.1.0

# Contributing to Hindsight

## The spine: cross-format identity

The binding constraint of Hindsight is that every supported trace format
produces structurally-identical canonical output for the same logical agent run.
This is the **cross-format-identity property**, and it is the one invariant you
must not break.

The test that guards it lives at `src/test_spike.py::SpikeTests::test_A_cross_format_identity`
(lines 106–123). It currently asserts four-way identity: JSONL, LangSmith, OTEL
GenAI, and Langfuse all agree on `step_count`, `path`, `kind`, `name`, `model`,
`tokens_in`, `tokens_out`, and `error` for the same logical 7-step agent run
(`fixtures/canonical_good.jsonl`). Any new adapter must extend this test to
five-way identity before a PR is merged.

---

## How to add a new ingest adapter

### Three-step recipe

New adapters target the `BaseIngester` Protocol defined in
`src/hindsight/base.py` (lines 44–56). You do not subclass anything — you
satisfy the Protocol structurally.

**Step 1 — define the class:**

```python
# src/hindsight/ingest_myformat.py
from __future__ import annotations

from pathlib import Path
from .canonical import TraceRun

class MyFormatIngester:
    name = "myformat"

    def can_ingest(self, path: Path) -> bool:
        # Return True only for files this adapter can parse.
        # Example: suffix + content sniff.
        return path.suffix == ".myfmt"

    def ingest(self, path: Path) -> TraceRun:
        # Parse the file; return a validated TraceRun.
        ...
        run = TraceRun(id=..., source="myformat", steps=steps)
        run.validate()   # raises ValueError on dangling parents / dup IDs
        return run
```

**Step 2 — register it:**

```python
from hindsight.base import register
from hindsight.ingest_myformat import MyFormatIngester

register(MyFormatIngester())
# — or use the decorator form —
@register
class MyFormatIngester:
    ...
```

For adapters that ship with Hindsight core, add the registration call inside
`_register_builtins()` in `src/hindsight/base.py` (line 179). For third-party
adapters, call `register()` at import time in your own package.

**Step 3 — confirm `auto_ingest()` dispatches correctly:**

```python
from hindsight.base import auto_ingest
run = auto_ingest(Path("my_trace.myfmt"))
```

`auto_ingest()` walks the registry in registration order and returns the first
match (lines 92–107 of `src/hindsight/base.py`). If two adapters could both
claim the same file, use the `_JsonShimIngester` `required_keys` / `forbidden_keys`
mechanism (see the OTEL vs. Langfuse vs. LangSmith disambiguation at lines
200–224 of `src/hindsight/base.py`).

### Canonical example

The Langfuse adapter (`src/hindsight/ingest_langfuse.py`) is the most recent
adapter added and is the canonical reference. Notable patterns:

- Root AGENT synthesised from the trace envelope (line 151) so the canonical
  tree always has exactly one root, consistent with all other adapters.
- Two-pass parent wiring: build steps first, resolve parent IDs second
  (lines 205–211).
- Topological sort before handing the list to `TraceRun` (lines 213–230).
- `run.validate()` called at the end (line 242) to catch adapter bugs early.

---

## How to add a new fixture

New fixtures must represent the **same logical 7-step agent run** as
`fixtures/canonical_good.jsonl` — the orchestrator root, router LLM call,
dispatch tool call, stock-analyst agent, analyse LLM call, get_quote tool call,
and summarize LLM call — just serialised in the new format.

1. Read `fixtures/canonical_good.jsonl` to understand the step IDs, names,
   models, token counts, and latencies you must replicate.
2. Create `fixtures/<format>_good.<ext>` expressing the same 7-step run in the
   new format's schema.
3. Run `make smoke PYTHON=python` and verify the new fixture ingests without
   error.
4. Open `src/test_spike.py` and extend `test_A_cross_format_identity` to
   include your adapter (currently lines 106–123). Add a fifth assertion that
   `_normalize(your_run) == _normalize(jsonl_run)`.
5. If your adapter introduces any new extra-field semantics, add a targeted
   unit test (follow the pattern of `test_F_langsmith_extra_preserved` at
   lines 204–209 or `test_G_otel_parent_linkage` at lines 212–222).
6. Run `make test PYTHON=python` — all tests must remain green.
7. Update `CHANGELOG.md` under `[Unreleased]`.

---

## Local dev loop

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

make smoke PYTHON=python   # spike end-to-end: ~6 ms, must pass
make test  PYTHON=python   # full test suite, must be 100 % green
make lint  PYTHON=python   # ruff — must be clean
```

`make smoke` runs `src/spike_run.py` and is the fastest feedback loop: it
exercises ingest + show + stats + diff over the four canonical fixtures in
about 6 ms. It is the first gate before running the full suite.

`make test` discovers all `test_*.py` files under `src/` via
`python -m unittest discover -s src -p 'test_*.py' -v` (see `Makefile`).

`make lint` runs `ruff check src/` with the config in `pyproject.toml`
(line-length 110, target py310, select E/F/I/W/UP, ignore E501).

### Pre-commit hooks (recommended)

After cloning + `pip install -e .[dev]`, enable the hooks once:

```bash
pre-commit install
```

This wires `ruff --fix` and `mypy --ignore-missing-imports` to every
`git commit`, so the dev loop catches the same things CI does, faster.
The `typecheck` CI job runs mypy on push; running it locally as a
pre-commit hook closes that gap.

---

## Code style

- **Stdlib-only on the core hot path.** Nothing in `src/hindsight/` may import
  a third-party package at module level except via the `[live]` or `[otel]`
  extras, and those imports must be lazy.
- **Lazy-import third-party SDKs inside `__init__` or the method that first
  needs them.** The `AnthropicProvider` in `src/hindsight/replay.py` is the
  canonical example: `import anthropic` appears inside `__init__`, not at
  module top level. This lets `from hindsight.replay import MockProvider` work
  without the `[live]` extra installed (verified by `test_replay.py` test 5,
  lines 145–177).
- **`from __future__ import annotations` at the top of every Python file.**
  This is present in all existing modules and must stay consistent.
- **`ruff` is the linter.** Config lives in `pyproject.toml` under
  `[tool.ruff]` and `[tool.ruff.lint]`. Run `make lint` before pushing.
  `E402` is silenced only for `src/spike_run.py`, `src/test_spike.py`, and
  `src/test_replay.py` (driver scripts that prepend `ROOT` to `sys.path`
  before importing `hindsight`).

---

## PR checklist

Before opening a pull request, confirm all five:

1. `make test PYTHON=python` — green (zero failures, zero errors).
2. `make lint PYTHON=python` — clean (zero ruff violations).
3. `make smoke PYTHON=python` — green (spike end-to-end runs in <10 ms).
4. If you added a new fixture or adapter: `test_A_cross_format_identity`
   still passes and has been extended to cover the new format.
5. `CHANGELOG.md` has an entry under `[Unreleased]` describing what changed.

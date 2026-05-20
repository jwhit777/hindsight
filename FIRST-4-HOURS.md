# FIRST-4-HOURS — Hindsight, Day 1

The very first concrete actions to take. Granular. Time-boxed. The end state at Hour 4: **public GitHub repo with green CI, PyPI name reserved, README hero example reproducing on a fresh clone.**

The spike from 2026-05-15 already runs. Your job for the first 4 hours is to get it shipped publicly with a CI gate, a reserved package name, and a self-contained README demo a stranger can clone-and-run.

> **Shortcut:** open `CLAUDE-CODE-PROMPT.md`, copy the fenced block, paste it into Claude Code launched in a fresh directory. Claude Code does Hour 1 and Hour 2 for you. The hours below are the manual version if you'd rather drive yourself.

---

## Hour 0 — the standing start (15 min)

Before opening any editor:

1. Run the spike yourself, to confirm the overnight build still works on your machine:
   ```bash
   cd ~/Documents/situational-awareness/project-builder/projects/2026-05-15-fde-portfolio/src
   python3 spike_run.py    # expect: identity=True · diverged_at_router=True · ~6ms
   python3 test_spike.py   # expect: 11 tests pass
   ```
2. Skim, in order: `README.md` → `SPIKE.md` → `PLAN.md` → `EVALS.md`. Roughly 8 minutes of reading.
3. Check PyPI: `python3 -m pip index versions hindsight-trace` — should still report "no matching distribution" (verified on 2026-05-15; reserve today before someone else does).
4. Check GitHub: `gh repo view <your-handle>/hindsight 2>&1 | head -1` — should 404. If not, pick `hindsight-trace` instead and update all references with `rg -l hindsight | xargs sed -i.bak 's/hindsight$/hindsight-trace/g'` and commit.

---

## Hour 1 — make the spike a real Python package (45–60 min)

### 1.1 — promote `src/hindsight/` into the package root

The spike was structured for in-place execution. We need to make it `pip install`-able.

```
mkdir -p /tmp/hindsight-bootstrap && cd /tmp/hindsight-bootstrap
cp -r ~/Documents/situational-awareness/project-builder/projects/2026-05-15-fde-portfolio/* .
git init -b main
```

### 1.2 — write `pyproject.toml`

Use Hatchling. Match the version `0.0.1` from `__init__.py`.

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "hindsight-trace"
version = "0.0.1"
description = "Flight recorder + replay debugger for LLM agents. Read any trace, branch from any step, diff two runs — locally, no account."
readme = "README.md"
requires-python = ">=3.10"
authors = [{name = "Justin Whitcomb", email = "jwhitua@gmail.com"}]
license = {text = "Apache-2.0"}
classifiers = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Debuggers",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

[project.scripts]
hindsight = "hindsight.cli:main"

[project.optional-dependencies]
live = ["anthropic>=0.40.0", "openai>=1.40.0"]
otel = ["opentelemetry-sdk>=1.27.0", "opentelemetry-instrumentation-anthropic>=0.40.0"]
dev = ["ruff>=0.4.0", "mypy>=1.10.0"]

[tool.hatch.build.targets.wheel]
packages = ["src/hindsight"]
```

### 1.3 — minimal `src/hindsight/cli.py`

You don't have a CLI yet. Add one (≤80 lines):

```python
# src/hindsight/cli.py
import argparse, json, pathlib, sys
from . import ingest_jsonl, ingest_langsmith, ingest_otel, show, diff
from .stats import stats, stats_markdown
from .diff import diff_markdown

_INGESTERS = {".jsonl": ingest_jsonl, ".json": None}  # decide json by content

def _auto_ingest(path: pathlib.Path):
    if path.suffix == ".jsonl":
        return ingest_jsonl(path)
    # peek the JSON shape
    raw = json.loads(path.read_text())
    if "resourceSpans" in raw:
        return ingest_otel(path)
    if "child_runs" in raw or "run_type" in raw:
        return ingest_langsmith(path)
    raise SystemExit(f"can't auto-detect format for {path}")

def main(argv=None):
    p = argparse.ArgumentParser(prog="hindsight")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("show");  sp.add_argument("path")
    sp = sub.add_parser("stats"); sp.add_argument("path"); sp.add_argument("--md", action="store_true")
    sp = sub.add_parser("diff");  sp.add_argument("a"); sp.add_argument("b"); sp.add_argument("--md", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "show":
        print(show(_auto_ingest(pathlib.Path(args.path))))
    elif args.cmd == "stats":
        s = stats(_auto_ingest(pathlib.Path(args.path)))
        print(stats_markdown(s) if args.md else json.dumps(s, indent=2, sort_keys=True))
    elif args.cmd == "diff":
        d = diff(_auto_ingest(pathlib.Path(args.a)), _auto_ingest(pathlib.Path(args.b)))
        print(diff_markdown(d) if args.md else json.dumps(d.to_dict(), indent=2, sort_keys=True, default=str))

if __name__ == "__main__":
    main()
```

Test it:
```bash
pip install -e .
hindsight show fixtures/canonical_good.jsonl
hindsight diff fixtures/canonical_good.jsonl fixtures/canonical_bad.jsonl
```

### 1.4 — `.gitignore`, `LICENSE` (Apache-2.0), basic `CONTRIBUTING.md`

```bash
curl https://www.apache.org/licenses/LICENSE-2.0.txt > LICENSE
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
EOF
```

### 1.5 — `make smoke` shortcut

`Makefile`:
```makefile
.PHONY: smoke test lint
smoke:
	@python3 src/spike_run.py
test:
	@python3 -m unittest discover -s src -p 'test_*.py' -v
lint:
	@python3 -m ruff check src/
```

---

## Hour 2 — CI green (45–60 min)

### 2.1 — `.github/workflows/ci.yml`

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        py: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "${{ matrix.py }}"}
      - run: python -m pip install -e .[dev]
      - run: make smoke
      - run: make test
      - run: make lint
```

### 2.2 — first commit + first push

```bash
git add -A
git commit -m "init: Hindsight spike — canonical schema + 3 ingesters + diff, 11 tests green"
gh repo create hindsight --public --source=. --remote=origin --push
```

CI starts. Watch the Actions tab. Common Day-1 misses:
* ruff complains about unused imports — `make lint` locally first.
* GitHub Actions ubuntu image doesn't have Python 3.10 by default — `setup-python@v5` handles it; just make sure you use `python -m unittest` not `python3 -m unittest` inside the runner.

### 2.3 — PyPI name reservation

```bash
python3 -m pip install build twine
python3 -m build
python3 -m twine upload --repository testpypi dist/*   # test first
# then real:
python3 -m twine upload dist/*
```

`twine` will prompt for the PyPI API token. Generate one at https://pypi.org/manage/account/token/.

Verify: `pip install hindsight-trace` from a fresh venv should now succeed.

---

## Hour 3 — close the README loop (45–60 min)

The README has a hero example. Right now that example uses `pip install hindsight-trace` and `hindsight show / diff` — make sure both work from a clean machine.

### 3.1 — README dogfood

```bash
deactivate; rm -rf /tmp/dogfood; python3 -m venv /tmp/dogfood; source /tmp/dogfood/bin/activate
pip install hindsight-trace
# copy README example commands verbatim, run them, paste output if it differs.
```

Fix anything that doesn't reproduce. Commit any drift. The principle: **a stranger cloning the README should be able to copy-paste their way to the demo output.**

### 3.2 — Real OTEL ingest validation (this is the day-1 functional eval F1)

The spike used a hand-written OTEL fixture. Replace it with a captured one from real instrumentation.

```bash
pip install opentelemetry-sdk opentelemetry-instrumentation-anthropic anthropic
export ANTHROPIC_API_KEY=...
python3 scripts/capture_otel_anthropic.py > fixtures/otel_real.json
hindsight show fixtures/otel_real.json   # expect: 1+ steps, kind=llm, model=claude-haiku-4-5
```

If `capture_otel_anthropic.py` doesn't exist yet, write it (≤30 lines: SDK init, exporter to in-memory JSON, single `claude-haiku-4-5` call, dump spans).

If the captured output doesn't ingest cleanly, that's the second-best signal you'll get from Day 1 — your hand-written fixture wasn't reality, and now you have a real corpus to expand the adapter against. File an issue, fix forward.

---

## Hour 4 — public surface (45 min)

### 4.1 — repository description

GitHub repo description (≤120 chars):

> Flight recorder + replay debugger for LLM agents. Read OTEL/LangSmith/JSONL traces, diff two runs, replay from any step. Local-first, stdlib core.

Topics: `llm`, `agents`, `observability`, `tracing`, `opentelemetry`, `langsmith`, `debugging`, `python`.

### 4.2 — README badges (sanity-checkable)

Already in the README. Verify each renders:
* `![ci](https://github.com/<you>/hindsight/actions/workflows/ci.yml/badge.svg)`
* `![PyPI](https://img.shields.io/pypi/v/hindsight-trace.svg)`
* `![Python](https://img.shields.io/pypi/pyversions/hindsight-trace.svg)`

### 4.3 — launch post draft

Write `LAUNCH.md` (not part of the package; just for you). 600 words. Outline:

1. The problem (one paragraph): SaaS observability for LLM agents has won, but customer data won't go to SaaS. Open-source tools are framework-locked.
2. What Hindsight does (one paragraph + one terminal screenshot): one canonical, three adapters, diff, replay.
3. The "missing primitive" framing (one paragraph): cite Sakura Sky and arxiv 2505.17716. Position Hindsight as the assembled tool with all three primitives (ingest + diff + replay) where prior work covers one.
4. Demo (the four-command terminal block from README).
5. What it isn't (one paragraph): not Langfuse, not LangSmith, not Phoenix, not replacing observability — sitting next to it as the local debugger.
6. Call to action: try it, file issues, contribute adapters.

Don't post yet. Sit on it until v0.2 (replay) ships. Hour 4 deliverable is the **draft**, not the launch.

---

## End-of-day checkpoint (the leading indicators from PLAN.md)

By Hour 4, you should be able to honestly answer YES to all three:

* **Canonical-schema property holds in CI:** the cross-format-identity test runs on every push. (Confirmed automatic from the spike.)
* **A stranger can install and run the demo:** `pip install hindsight-trace && hindsight diff a.jsonl b.jsonl` works on a clean machine.
* **The README hero example reproduces verbatim.**

If any of those is NO, hour 4 doesn't end. Push until they're all YES.

---

## Failure-mode table (when you get stuck)

| Symptom | First thing to try |
|---|---|
| `hindsight: command not found` after `pip install -e .` | Reactivate the venv. `which hindsight`. If still missing, `pip install -e . --force-reinstall`. |
| Cross-format identity test fails locally | `python3 spike_run.py` — check which adapter's `normalize()` output differs. Most likely a fixture rather than adapter bug — fixtures are hand-written and brittle. |
| CI passes locally, fails on Actions | Python version mismatch. Pin `python -m unittest discover` not `python3`. Check `setup-python` matrix entries. |
| `twine upload` rejects the package | Name conflict — someone reserved `hindsight-trace` between yesterday and today. Pivot to `agent-hindsight`. Update `pyproject.toml`, `README.md`, `pip install` instructions. |
| Real OTEL captured spans don't ingest | Most likely the `gen_ai.usage.input_tokens` field comes through as a `stringValue` rather than `intValue` — the adapter already handles both, but check the actual value type. Print `attrs` for one span to see. |
| You realize the schema is missing a field | Don't panic. Add it to `TraceStep` with a default. Bump version to `0.0.2`. Re-run `make test`. The `extra` dict is exactly there for this case — try landing it under `extra[<source>]` first before promoting to top-level. |

Good luck. The spike already works. Day 1 is mostly about making it visible.

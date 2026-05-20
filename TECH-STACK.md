# TECH-STACK

The discipline: **stdlib-first, hot-path zero-dependency, optional dependencies cleanly behind flags.**

| Layer | Pick | Rationale |
|---|---|---|
| Language | **Python 3.10+** | Match `Sub-Agent Bench`, `MCP Probe`, `Skillsmith`. Dataclasses + structural pattern matching make the canonical schema clean. Async optional via `asyncio` (only behind `--live`). |
| Packaging | **`pyproject.toml` (PEP 621), Hatchling backend** | One file. Modern. No setup.py drama. Wheel-friendly. Same as the rest of the triptych. |
| Distribution | **PyPI as `hindsight-trace`** | Name available as of 2026-05-15 per `pip index versions hindsight-trace` (returns "not found"); reserve on Day 1. (Backup name: `agent-hindsight`.) |
| Core dependencies | **None.** stdlib only for v0.1 core. | The canonical schema, three ingesters, `show`, `stats`, and `diff` use only `json`, `dataclasses`, `pathlib`, `argparse`, `sys`, `textwrap`, `enum`, `typing`. Zero pip-install pain for a customer behind a corporate proxy. |
| Optional: replay (`--live`) | **`anthropic` + `openai` SDKs**, both behind `extras_require=["live"]` | Only loaded when `hindsight replay --live` is used. Customer who doesn't replay never pays the dependency cost. |
| Optional: OTEL ingest from live system | **`opentelemetry-sdk` + `opentelemetry-instrumentation-anthropic`**, behind `extras_require=["otel"]` | For Phase 2 only. v0.1 reads OTEL traces from disk via the static JSON shape, no OTEL runtime required. |
| Optional: web UI | **FastAPI + Jinja2 + plain HTML**, behind `extras_require=["ui"]` | No bundler, no node, no React. Pure server-rendered. Loads in <100ms on localhost. Phase 2 (post-v0.2). |
| Test framework | **stdlib `unittest`**, plus a single `pytest` shim file for `pytest`-runner users | `test_spike.py` is `python -m unittest`-runnable. CI runs `python3 -m unittest discover`. No pytest dependency for the core test suite. |
| CI | **GitHub Actions** matrix on Python 3.10 / 3.11 / 3.12 | One YAML file. Same as the triptych. |
| Lint / format | **`ruff`** (Day 1 add) | Fast. Replaces black + isort + pyflakes. One tool. |
| Type checking | **Optional `mypy --strict` on Day 1** | Enable but allow `# type: ignore[...]` until v0.2. |
| Diff engine | **Custom step-aligner** | The 2-run alignment is *not* `difflib.SequenceMatcher` over strings — it's a structural alignment of typed steps with parent-id awareness. Written from scratch in <120 lines. |
| Replay scheduler | **Pure synchronous in v0.1** | Re-emit recorded requests in topological order. Async only when needed (Phase 2 when a customer trace has parallel sub-agent fan-out). |
| Schema validation | **Hand-rolled `__post_init__` validators on dataclasses** | Pydantic would be cleaner but adds an install. Hand-rolled buys stdlib-only. |
| Logging | **`logging` stdlib, `Hindsight()`-namespaced loggers** | Standard. No `loguru`. |
| Storage | **Local JSONL in `~/.hindsight/runs/`** | Each ingested run gets a directory; canonical JSON is the source of truth, optional cached views alongside. SQLite optional in Phase 3 (when run count >10 000). |
| Pricing data | **Static JSON `pricing.json` shipped with package, refreshed via a `scripts/refresh_pricing.py` script** | Avoids `httpx` dependency on hot path. The refresh script uses `urllib.request` (stdlib). |

## What I am explicitly NOT picking

* **No LangChain dependency.** Hindsight reads LangSmith *exports*, not LangChain runtime. The whole point is framework-agnostic.
* **No pydantic.** Dataclasses + hand-rolled validators is enough. Same as triptych.
* **No Click / Typer for CLI.** argparse is fine, zero dep, same as MCP Probe.
* **No Rich.** Pretty output uses ANSI escape codes directly in <40 lines. Customers in locked-down terminals will thank me.
* **No Datadog / Honeycomb / NewRelic SDK.** Read their exports if they expose one; never depend on their SDKs.
* **No GraphQL.** REST + JSON when Phase 2 ships an API.
* **No npm in the build.** The optional web UI uses zero-build HTML — Jinja2 templates emit self-contained pages.

## Why "stdlib-first" matters for the FDE story

The Anthropic FDE bullet "deliver technical artifacts for customers like MCP servers, sub-agents, and agent skills that will be used in production workflows" implies handing customers something they will install and run. Enterprise installation friction is real: every additional dependency is one more compliance-review ticket. A stdlib-only core makes the friction near-zero. Once the customer trusts it, the `[live]` and `[otel]` extras can opt them up.

Same discipline as the triptych. Justin is consistent in this — that consistency itself is a hireable signal.

## Versions pinned in CI

* Python 3.10.14 / 3.11.9 / 3.12.5 (latest patch releases as of 2026-05-15).
* Ruff 0.4.x.
* OTEL spec target: `gen_ai` semconv v1.30 (current as of May 2026; bump tracked in `CHANGELOG.md`).

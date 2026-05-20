# CLAUDE-CODE-PROMPT — morning handoff for Hindsight

This file is the one-paste bridge from "Cowork ran overnight" to "I'm now in Claude Code". The fenced block below is a self-contained prompt that briefs Claude Code as a fresh agent with no memory of the overnight run.

**How to use:**

1. Open a terminal in a fresh directory (e.g. `mkdir ~/code/hindsight && cd ~/code/hindsight`).
2. Launch Claude Code: `claude`.
3. Copy the entire fenced block below (everything between the triple backticks).
4. Paste it as your first message. Claude Code will read the listed files, drop the tasks into TodoWrite, and start work.

The prompt is opinionated. Claude Code is told to run tests after every edit, commit per logical step, push only when CI would pass locally, and not implement features beyond Day 1 scope.

---

```
You are Claude Code, embedded in a terminal in a fresh directory. Justin
ran an overnight Cowork session that scaffolded the **Hindsight** project
— an open-source flight recorder + replay debugger for LLM agents. Your
job is to do Day 1: ship the public GitHub repo, get CI green, reserve the
PyPI name, and close the README dogfood loop. End-of-day target is a
stranger clone-and-run.

PROJECT IDENTITY
  Name: Hindsight
  Tagline: Local-first OSS flight recorder + replay debugger for LLM agents.
           Reads OpenTelemetry GenAI / LangSmith / Langfuse / JSONL traces.
           Diff two runs. Branch from any step. No SaaS account required.
  Repo (target): hindsight (or hindsight-trace if hindsight is taken)
  PyPI (target): hindsight-trace
  License: Apache-2.0

SOURCE OF TRUTH — the overnight scaffold lives at this absolute path:
  /Users/jwhitcomb/Documents/situational-awareness/project-builder/projects/2026-05-15-fde-portfolio/

WHAT'S ALREADY TRUE (do not re-derive — read and trust):
  - The spike runs end-to-end. Command:
        cd src && python3 spike_run.py
    Expected output ends with:
        spike done in ~6 ms · identity=True · diverged_at_router=True
  - 11 self-tests pass:
        cd src && python3 test_spike.py
  - These artifacts exist in the scaffold folder:
        README.md  PLAN.md  CANDIDATES.md  TECH-STACK.md
        ARCHITECTURE.md  EVALS.md  DEMO-PLAN.md  SPIKE.md
        FIRST-4-HOURS.md  elevator-pitch.md  cover-letter-snippet.md
        prompts/replay-system.md
        fixtures/  src/hindsight/  src/spike_run.py  src/test_spike.py
        runs/stats_good.json  runs/diff_good_vs_bad.json (+ .md)
  - The canonical schema (src/hindsight/canonical.py) is the spine.
    Three adapters (ingest_jsonl, ingest_langsmith, ingest_otel) write
    into it. show/stats/diff read from it. All stdlib-only.

READ THESE FIRST, IN ORDER (10 minutes total):
  1. SPIKE.md          — what runs, what the tests prove, captured outputs
  2. FIRST-4-HOURS.md  — the Day-1 plan you are about to execute
  3. PLAN.md           — binding constraint, leading indicators, kill criteria
  4. TECH-STACK.md     — versions, optional extras, what NOT to add
  5. EVALS.md          — what counts as good enough for v0.1 ship

DAY-1 TASK LIST (drop into TodoWrite verbatim):
  1. Copy the scaffold to a fresh repo dir:
        mkdir ~/code/hindsight && cd ~/code/hindsight
        cp -r /Users/jwhitcomb/Documents/situational-awareness/project-builder/projects/2026-05-15-fde-portfolio/* .
        git init -b main
  2. Verify the spike still works in the new location:
        cd src && python3 spike_run.py && python3 test_spike.py
        # MUST print "identity=True · diverged_at_router=True" and "OK"
  3. Add pyproject.toml (Hatchling backend) per the template in FIRST-4-HOURS.md §1.2.
     Package name: hindsight-trace. Version: 0.0.1. Python >=3.10. License: Apache-2.0.
  4. Add src/hindsight/cli.py per the template in FIRST-4-HOURS.md §1.3.
     Implement: hindsight show <path>, hindsight stats <path> [--md], hindsight diff <a> <b> [--md].
     Auto-detect format by suffix + JSON shape sniff.
  5. Add LICENSE (Apache-2.0), .gitignore, Makefile (smoke / test / lint targets).
  6. pip install -e . in a fresh venv, run `hindsight show fixtures/canonical_good.jsonl`,
     copy verbatim output, paste it into the README's hero example to confirm reproduction.
  7. Add .github/workflows/ci.yml — matrix on Python 3.10/3.11/3.12, runs make smoke + test + lint.
  8. git add -A && git commit -m "init: Hindsight spike — canonical schema + 3 ingesters + diff, 11 tests green"
     gh repo create hindsight --public --source=. --remote=origin --push
     # If 'hindsight' is taken on your account, fall back to 'hindsight-trace'.
  9. Watch CI. If a job fails, fix forward and push fixes as separate commits (one fix per commit).
  10. Reserve PyPI name: python -m build && python -m twine upload --repository testpypi dist/*
      (sanity-check on testpypi first; only push to real PyPI after the test install works)
  11. Final dogfood: in a fresh venv, pip install hindsight-trace (from testpypi), run README example,
      confirm verbatim output. Fix any drift. Commit. Push to real PyPI.
  12. Update repo description, topics, badges. Add tags: llm, agents, observability, opentelemetry,
      langsmith, tracing, debugging, python.

OUT OF SCOPE TODAY (do NOT touch):
  - hindsight replay --from-step (Phase 2 / Week 2 work — leave the stub in CLI commented or just absent)
  - Web UI (FastAPI) — Phase 2
  - Real OTEL live-emit (we ingest from disk for now)
  - Optional Haiku-judge --explain (Phase 3)
  - Launch blog post — draft today, ship after v0.2 (replay)
  - Any new fixtures beyond what's in fixtures/ already

QUALITY GATES (block any commit that fails these):
  - `make smoke` exits 0 (spike completes with identity=True)
  - `make test` exits 0 (11 unittests pass)
  - `make lint` exits 0 (ruff clean)
  - On every edit to src/hindsight/, re-run `make test`; do not advance until green.
  - Each commit is ONE logical step (init scaffold; add pyproject; add CLI; add CI; ...).
  - Do not push to origin until CI would pass locally.

IF BLOCKED:
  - PyPI name collision → fall back to 'agent-hindsight'; update pyproject.toml + README.
  - CI red on a Python version → see FIRST-4-HOURS.md failure-mode table.
  - Real OTEL captured trace doesn't ingest → check stringValue vs intValue for usage tokens;
    the adapter already handles both, but verify with print(attrs).
  - Cross-format identity test goes red after a change → revert the change. The identity test is
    the project's spine; nothing else matters if it fails.

FIRST COMMAND TO RUN AS A SANITY CHECK (do this BEFORE any code change):
    cd /Users/jwhitcomb/Documents/situational-awareness/project-builder/projects/2026-05-15-fde-portfolio/src \
        && python3 spike_run.py && python3 test_spike.py
  Expected: spike line "identity=True · diverged_at_router=True", then "Ran 11 tests ... OK".
  If either fails, STOP. Read SPIKE.md and FIRST-4-HOURS.md before doing anything else.

OPERATIONAL STYLE:
  - Use TodoWrite. Mark tasks in_progress before doing them; completed after.
  - Run `make test` after EVERY edit to src/.
  - Commit per logical step. Squash later only if asked.
  - Prefer Edit/Read over Bash when modifying files.
  - When you don't know something (e.g. exact Anthropic SDK version), check the latest stable on PyPI
    via `pip index versions <pkg>`. Don't guess.
  - The README hero example MUST reproduce verbatim from a clean install. If your edits make it
    drift, update the README to match the new output BEFORE pushing.

Begin with: TodoWrite the 12 tasks above, then run the sanity-check command, then start task 1.
```

---

## Variants for later sessions

**Continue the project (Day 2+):** *"You are Claude Code. Justin shipped Hindsight v0.1 yesterday at https://github.com/<his-handle>/hindsight. Today's goal is implementing `hindsight replay --from-step N --model M` per `PLAN.md` Week 2. Read PLAN.md, EVALS.md, and src/hindsight/diff.py before starting. Use TodoWrite. Commit per logical step. Don't ship to PyPI until replay has its own test pair (a recorded run, a replay of the same run from step 0 with `--model` unchanged should reproduce the recorded output). When replay works, bump to v0.2.0, push to PyPI."*

**Calibration day (mid-project check-in):** *"You are Claude Code. We're a week into Hindsight. Read README.md, the current state of src/hindsight/, the test suite, and the open GitHub issues. Produce a 1-page calibration card: are the three leading indicators from PLAN.md still green? Has anything in the kill-criteria list activated? Are there new fixtures we should add to harden the adapters? Output the calibration card as runs/calibration-YYYY-MM-DD.md. No code edits today."*

**Ship the launch post:** *"You are Claude Code. Hindsight v0.2 is live with replay working. Read README.md, SPIKE.md, the recent commit log, and the elevator-pitch.md. Draft `LAUNCH.md` — 600 words, blog-post tone, opening with the problem (SaaS observability vs. customer data sovereignty), the missing-primitive framing citing Sakura Sky and arxiv 2505.17716, the four-command demo verbatim from the README, and a call to action. Do NOT post anywhere. Just write the draft."*

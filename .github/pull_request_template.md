<!--
Thanks for sending a PR! Fill in the sections below to help reviewers
understand the change and trust the diff.
-->

## What + Why

One paragraph: what does this PR change, and why. Link the issue if there
is one (`closes #N`).

## Checklist

- [ ] `make smoke` exits 0 (`spike done · identity=True · diverged_at_router=True`).
- [ ] `make test` green (39 tests currently; update the count in
      [`README.md`](../blob/main/README.md) and
      [`CHANGELOG.md`](../blob/main/CHANGELOG.md) if you add tests).
- [ ] `make lint` clean.
- [ ] If you added a new ingest adapter:
  - [ ] New fixture under `fixtures/` representing the same logical
        7-step run as `canonical_good.jsonl`.
  - [ ] `test_A_cross_format_identity` extended to include the new
        adapter; cross-format identity holds.
  - [ ] Adapter registered in `src/hindsight/base.py::_register_builtins()`.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] No new non-stdlib dependency on the default code path. New SDK
      dependencies go in an extra (see `[live]` / `[otel]` in
      `pyproject.toml`).

## Notes for reviewers

Anything specific you want a second pair of eyes on — a tricky edge case,
a deliberate trade-off, an API choice you're not sure about.

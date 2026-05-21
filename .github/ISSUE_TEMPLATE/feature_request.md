---
name: Feature request
about: A new adapter, CLI verb, flag, or library API.
title: ""
labels: ["enhancement"]
assignees: ""
---

## Use case

One paragraph describing the situation where Hindsight falls short and
what you wish it could do.

## Proposed shape

How would the feature surface? Pick one or sketch your own:

- New ingest adapter for `<format>` — see `src/hindsight/base.py` for the
  `BaseIngester` Protocol and `src/hindsight/ingest_langfuse.py` as the
  canonical example.
- New CLI verb / flag — sketch the command line:
  ```bash
  hindsight <new-verb> ...
  ```
- New library function on `TraceRun` / `TraceStep`.
- Other.

## Alternatives considered

What's the workaround today? What would the cost of *not* shipping this be?

## Implementation interest

- [ ] I'd be willing to send a PR for this.
- [ ] I'd review a PR but can't write one.
- [ ] I'm just flagging the need; happy if it stays open as a discussion.

For new adapters: the
[cross-format-identity test](https://github.com/jwhit777/hindsight/blob/main/src/test_spike.py)
(`test_A_cross_format_identity`) is the contract. A new adapter must
produce a structurally-identical canonical TraceRun from a fixture
representing the same logical run as the existing fixtures.

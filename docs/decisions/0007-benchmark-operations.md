# 0007. Benchmark tests call named operations, not fixed URLs

- Status: Proposed
- Date: 2026-10-18
- Decided by: —

## Context

The agent may name an endpoint `/events` or `/church-events`, a field `capacity` or `max_people`. A correct backend should not fail a test because of naming.

## Options considered

- Hidden tests with fixed URLs and field names.
- Tests that call named operations, translated through an `ops.json` mapping the agent writes.

## Decision

Hidden tests call operations by name; `benchmark/conftest.py` translates them using `ops.json`. See `benchmark/README.md` and the worked example `benchmark/church_signup/`.

## Consequences

- Tests measure behaviour, not naming.
- The agent has one extra job: writing `ops.json`.
- Checked: the example's 10 tests pass with a correct mapping and 7 fail with a broken one.

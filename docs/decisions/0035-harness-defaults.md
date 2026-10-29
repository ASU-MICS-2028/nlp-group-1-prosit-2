# 0035. How the eval harness runs: 4 side by side, stop if Docker is off, flag incomplete maps

- Status: Accepted
- Date: 2026-10-28
- Decided by: Joseph

## Context

`eval/harness.py` scores any backend against the benchmark (S2.3). Its settings decide how fast scoring is and whether a wrong score can be mistaken for a real one. Measured in `learnings/W4-evaluation-and-knowledge-base.md`, rows 18–21.

## Options considered

- Side by side: 1, 2, 4, 8 or 16 backends at once. 21 correct backends took 51, 24, 13, 11 s; 16 was no faster. All scores identical.
- Docker off: score every backend 0 (what happened first) · stop with a clear message.
- A name map missing an operation: score it silently (6/10 for a correct backend) · score it and warn.

## Decision

- 4 side by side by default (`--workers` changes it).
- If Docker cannot be reached, the harness stops before scoring anything and says why.
- A map that has no entry for some operation is still scored, with the missing operations named in the result.
- A test run that takes over 300 s counts as failed; it never stops the whole run.

## Consequences

- A full check of the 21 correct backends takes about 13 s, so it can be run often.
- Zero scores always mean the backend failed, never that the harness could not run.
- Laptops with fewer cores may want `--workers 2`.

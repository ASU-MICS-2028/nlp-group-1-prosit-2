# 0051. Every test result is saved in the repo

- Status: Accepted
- Date: 2026-11-06
- Decided by: Joseph

## Context

The report and the presentation use our test results. An audit found some results existed only in terminal output, in a temporary folder or on the server.

## Options considered

- Rely on each person's learnings file. It explains results, but the numbers cannot be checked later.
- Save every result as a file in `eval/results/`, with an index.

## Decision

Any test, comparison or check saves its result to `eval/results/` and is listed in `eval/results/README.md` in the same commit. A number that goes in the report must come from one of those files.

## Consequences

- Anyone can recheck a number, and Eric can write Section B from the index.
- Experiment scripts must write a file, not just print.
- A result recorded by hand says so in its file (`crash_test.json`).

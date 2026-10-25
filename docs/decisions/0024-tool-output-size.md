# 0024. Tool output is cut to 4,000 characters, keeping the start and the end

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

## Context

Every tool reply is sent back to the LLM, and the agent sends the whole conversation again on every step, so long replies cost tokens many times over. One debug print made a single test run print 151,259 characters (about 38,000 tokens). But if we cut too much, the LLM cannot see which test failed or why.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log rows 5–6 (7 planted bugs, 21 facts to keep visible):

- Limit 2,000 / 4,000 / 8,000 characters: start and end kept 21/21 at all three.
- Keep the start and the end, or only the start: start only kept 14–20/21, because pytest's summary is at the end.
- pytest detail `--tb=long` / `short` / `line`: all 21/21. `short` is about 35% smaller than `long`.

## Decision

`cut()` in `runtime/tools.py` keeps the first 2,000 and the last 2,000 characters and says how many were removed in between. It applies to every tool's output. `run_tests` uses `pytest -q --tb=short`.

## Consequences

- One tool reply is at most about 1,000 tokens.
- The middle of a very long output is lost. If more than about 22 tests fail at once, some failing names are cut. The summary line and the last ones stay.
- `--tb=line` might be enough and is 30% smaller again; that needs the agent loop to test (S3).

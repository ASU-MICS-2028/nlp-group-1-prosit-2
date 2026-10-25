# 0026. Failing tests are reported to the LLM as pytest prints them

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

## Context

When the agent's tests fail, `run_tests` returns pytest's output so the LLM can fix the bug. The planning notes suggested putting a one-line reason first, in case the LLM misses the cause in a long printout.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log row 9: 7 planted bugs × 2 formats × 3 repeats on `claude-opus-5-5`, cost $0.85.

- A: pytest's output as it is, cut to 4,000 characters (start and end): 21/21 fixed, 609 output tokens on average.
- B: the failing lines and summary copied to the top first: 21/21 fixed, 582 output tokens on average.

## Decision

A. `run_tests` returns pytest's own output, with `ok: false` when any test fails.

## Consequences

- No extra formatting code to maintain or explain.
- The test was easy (the LLM saw the whole `app.py`). If Alice's agent loop shows the LLM missing causes, B is one small function in `runtime/experiments/error_format.py` that can be moved into `run_tests`.

# 0039. Every build writes trace.jsonl as it happens and run.json at the end

- Status: Proposed
- Date: 2026-11-03
- Decided by: Alice (to sign off)

## Context

S3.3 asks every run to record its time, tokens, cost, tool calls and test results. Michael's UI (Stage 4) will need to show a build while it runs, and S3.4 to S3.9 need the same numbers to compare options. So the format is an interface between W1 and W3.

## Options considered

- **One JSON file written at the end.** Simple, but a UI sees nothing until the build is over, and a crash loses everything.
- **Only print to the screen.** Nothing is kept, and a UI cannot read it.
- **A line per event, written as it happens (`trace.jsonl`), plus the totals at the end (`run.json`).** A UI can follow the file or get the same events through `build(..., on_event=...)`. The test `test_trace_is_written_even_when_the_build_breaks` shows that after a network error the file still holds the start and the error. One real church build made an 11.5 KB trace, so keeping the full tool inputs (the code Claude wrote) is cheap.

## Decision

The third option. Events are `start`, `reply`, `tool` and `end`, with the fields listed in `learnings/W1-agent-core.md` section 6. `run.json` replaces the earlier `build.json`.

## Consequences

- A UI can show live progress and the final cost without new code in the agent.
- The trace holds the client's request and the code Claude wrote. It lives in `projects/`, which is git-ignored. Never commit it.
- Adding a field later is safe, but renaming or removing one breaks the UI: write a new decision first.

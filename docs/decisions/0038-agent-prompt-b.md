# 0038. The agent's system prompt is version B (SQLite, write and run your own tests)

- Status: Proposed
- Date: 2026-11-03
- Decided by: Alice (to sign off)

## Context

The agent (S3.2) needs fixed instructions for Claude, the system prompt. The first version told Claude to keep data in memory, which breaks decision 0002 (generated backends use SQLModel and SQLite). We compared four versions before choosing.

## Options considered

All 15 benchmark tasks, one build per task per version, Opus, scored by the harness with `--repeat 3` (log row 1 in `learnings/W1-agent-core.md`):

- **A**, the first version, data in memory: 87.5% of hidden tests, 12 of 15 tasks fully pass, $1.51 for 15 builds, 31 s each.
- **B**, A with "store the data with SQLModel in SQLite": 87.0%, 10 of 15, $1.73, 34 s.
- **C**, a short 36-word version: 88.5%, 11 of 15, $2.56, 53 s.
- **D**, B without "write and run your own tests": 86.5%, 11 of 15, $1.60, 35 s. Claude tested anyway, by starting the server and sending 109 requests by hand.

The baseline (one call, no tools) scored 89%.

## Decision

Use B. A, B, C and D are within 2 points of each other, which is less than what one build that chose a different design costs (7 to 12 tests). So the score cannot pick a winner. B is the version that follows decision 0002, costs about the same as A and D, and is 1.5 times cheaper and faster than C.

## Consequences

- Generated backends keep their data in a SQLite file, as the team agreed.
- This is not a proven score win. Each version was built once per task, so a 1 to 2 point gap is noise. Repair (S3.4) and spec-first (S3.5) are the planned ways to beat 89%.
- Revisit if a later experiment with more builds per task shows a real gap.

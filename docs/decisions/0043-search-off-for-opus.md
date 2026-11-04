# 0043. Recipe search stays available but off for Opus

- Status: Proposed
- Date: 2026-11-04
- Decided by: Alice (to sign off)

## Context

S3.7 wired Joseph's `search_docs` (decision 0037) into the agent as a tool (`--search`). Joseph found that recipes made the small local model pass 9 times more tests (W4 row 27).

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log row 8 (15 tasks, Opus, harness `--repeat 3`):

- No search: 87.0%.
- Search as a tool: 92.7%, but Opus searched only 2 times in 15 builds, both on tasks that already score 100%. The tasks that improved never searched, so the difference is build-to-build luck.

## Decision

`--search` stays in the code, off by default. Opus does not use it. The local model is tested with and without it (S3.9), where it can matter.

## Consequences

- No extra cost or slower start (the search model takes about 7 s to load the first time).
- If a future model makes the mistakes the recipes cover, turn it on and measure again.

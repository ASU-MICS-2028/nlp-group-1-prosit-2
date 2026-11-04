# 0040. The repair loop stays in the code but is off by default

- Status: Accepted
- Date: 2026-11-04
- Decided by: Alice

## Context

S3.4 added an independent checker: after the build, a second Claude call writes tests from the client's request alone, and failures are sent back to the builder to fix (`--repairs N`). The plan asked how many repair rounds are worth it.

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log row 3 (15 tasks, Opus, prompt B, harness `--repeat 3`):

- 0 repairs: 87.0% of hidden tests, 33/45 fully passing.
- 1, 3 or 5 repairs: also 87.0%, 33/45. The checker passed all 15 apps on its first look, so no repair ever ran.
- The check itself costs about $0.06 to $0.14 per build (builds averaged 66 s with it, 41 to 47 s without).

## Decision

`--repairs 0` (no check) stays the default. The checker and repair code stay, so `--repairs N` can be turned on.

## Consequences

- Builds are cheaper and faster, with no loss on this benchmark.
- The apps that lose points are not broken; they understood the request differently from the hidden tests. Repairs cannot fix that; the plan step and clarifying questions (S3.8) are meant to.
- Worth turning on again if a model makes real bugs (for example, the local Qwen in S3.9).

# 0028. run_tests stops tests after 60 seconds and removes their container

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

## Context

Generated tests can get stuck (an endless loop, waiting for something that never comes). The agent must not wait forever, but a limit that is too short would kill good runs and make the LLM "fix" code that was fine.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log row 12: good runs took at most 5.4 s (8 tests) and 7.4 s (40 tests). A stuck test was stopped after 30.7 / 60.8 / 120.6 s, with no container left behind each time.

- 30 s: 4 times the slowest good run.
- 60 s: 8 times.
- 120 s: 16 times, but a stuck test costs the agent two minutes.

## Decision

60 seconds by default (`run_tests(root, path, timeout=60)`). When the limit is reached, the container is removed with `docker rm -f`, because stopping the `docker` command alone leaves it running.

## Consequences

- Slower laptops and bigger generated projects still fit comfortably.
- A stuck test costs the agent one minute. Callers (Alice's agent, Joseph's harness) can pass a different `timeout`.

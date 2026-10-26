# 0030. The evaluation harness runs every backend in the Docker sandbox, side by side, and cleans up first

- Status: Accepted
- Date: 2026-10-26
- Decided by: Joseph

## Context

The harness (S2.3) will start hundreds of generated backends with Bernard's `start_server` and score them with hidden tests. Checking his handoff (S2.1, `learnings/W4-evaluation-and-knowledge-base.md` rows 1–5) showed how his tools behave in the cases the harness will hit.

## Options considered

- Scored runs in Docker mode · in subprocess mode (2.5x faster).
- Tasks one after the other · side by side.
- Trust every run to clean up · clean up leftovers when the harness starts.

## Decision

- Every scored run uses Docker mode. Subprocess mode isolates nothing (Bernard's row 11), so its results would not be safe to collect.
- Tasks may run side by side: two at once both scored 10/10 on separate ports, in 2.0 s instead of 3.1 s. Each server is started and stopped inside the same program.
- A backend that fails to start counts as a failed task, recorded with the tool's error message (all three broken apps tested gave `ok=false` and the real error).
- When the harness starts, it removes any leftover `w2-…` containers and networks (a killed run left 2 containers and 1 network; the command in `knowledge/environment.md` removes them).

## Consequences

- Results are always collected under the same, isolated conditions.
- About 2–3 s of Docker overhead per server start, partly won back by running tasks side by side.
- The cleanup at start would also stop a sandbox server that someone else on the same laptop is using at that moment. The harness should say how many it removed.

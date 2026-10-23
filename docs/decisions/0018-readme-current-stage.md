# 0018. The README shows only the current stage

- Status: Accepted
- Date: 2026-10-23
- Decided by: Joseph

## Context

The README's status listed every person and every task. Anyone opening the repo had to read a table to find out where the team is.

## Options considered

- A table of every person's in-progress, ready and waiting tasks.
- Only the current stage at the very top: its name, who is responsible, its unfinished tasks and what comes next.

## Decision

The top of the README shows only the current stage, generated from `docs/PLAN.md`. The current stage is the first stage with an unfinished `Must` task, so leftover `Should`/`Could` work in an earlier stage does not hold the README back. Everything else stays in `docs/PLAN.md`.

## Consequences

- A quick glance shows the stage and the person responsible.
- Tested on a copy of the repo: a task in progress, a stage whose Musts are all done, every task done, the last stage, mixed owners, a typo in a status (refused) and deleted markers (refused). The last two cases found bugs, now fixed: "Who" listed people whose tasks were already done, and missing markers passed the check silently.

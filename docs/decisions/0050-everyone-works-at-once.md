# 0050. Everyone works at the same time; the README lists each person's tasks

- Status: Accepted
- Date: 2026-11-06
- Decided by: Joseph, for the group to confirm

## Context

With one person working at a time, most people were waiting. The platform is now live (decision 0049), so the remaining work no longer depends on one stage finishing first. The team is aiming to finish the week of Nov 9.

## Options considered

- **Keep the relay.** Michael, then Joseph, then Eric. Nobody overlaps, but it will not finish next week.
- **Work at the same time on the live platform.** Each person starts now, and only real blockers remain.

## Decision

Replaces decisions 0013 and 0018. Everyone works at once, each on their own branch, with a teammate reviewing every merge. `docs/PLAN.md` keeps only real blockers. The README lists every person's unfinished tasks and what "done" means for each. Learnings files stay, with section 6 written as soon as someone else needs it.

New tasks: S4.7 (Bernard, safety of the public platform) and S4.8 (Alice, plain-word summaries and following mid-build messages properly). Could-priority tasks, such as S1.4 (MCP), stay in the plan but are not listed in the README.

## Consequences

- Nobody waits on Michael's page: the evaluation uses the agent, and Section B starts from what exists.
- Two people may change the same file, so changes need to stay small and be merged often.
- Results can change while Section B is being written: Eric takes the final numbers from S5.5.

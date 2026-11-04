# 0044. One agent that asks questions, not a Planner / Builder / Tester split

- Status: Proposed
- Date: 2026-11-04
- Decided by: Alice (to sign off)

## Context

S3.6 asked whether splitting the agent into three roles (a Planner that asks questions and writes the plan, a Builder that follows it, a Tester that checks the result and sends failures back) builds better backends than one agent.

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log row 10 (15 tasks, 1 build, Opus, harness `--repeat 3`):

- One agent that asks up to 3 questions first (decision 0042): 95.8% of hidden tests, 39/45 fully passing.
- Split (`plan --ask 3 --client answers --yes`, then `build --plan --repairs 2`): 84.4%, 30/45. The Tester passed all 15 apps first time, so no repair ran. Costs about $4.06 for 15 tasks against about $1.90.

## Decision

The agent stays one agent that asks questions first. The three roles stay available as separate commands (`plan`, `build --plan`, `--repairs`), so a person can approve a plan and turn the check on.

## Consequences

- Cheaper and simpler: one conversation, nothing extra to explain or keep in step.
- A fixed plan cannot fix designs the client never discussed; questions can. The Tester never caught anything on this benchmark (also decision 0040).
- Worth measuring again with a weaker model, where the Tester may find real bugs.

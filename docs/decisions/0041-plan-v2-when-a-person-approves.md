# 0041. Plan first (planner v2) when a person approves; no plan in automatic benchmark runs

- Status: Accepted
- Date: 2026-11-04
- Decided by: Alice
- Replaces: 0004 (spec-first for every build)

## Context

Decision 0004 said the agent drafts a plain-language plan, the client approves it, and only then is code written. S3.5 built this (`python -m builder plan`, then `build --plan`) and measured it on the benchmark, where nobody reads the plans, so they are approved automatically.

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log rows 4 and 5 (15 tasks, 1 build each, Opus, harness `--repeat 3`):

- No plan: 87.0% of hidden tests, 33/45 fully passing.
- Plan v1 (plan only what was asked): 74.5%, 24/45. On 3 tasks the plan added a password nobody asked for, and the hidden tests were refused (church 10/10 to 3/10, library 13/13 to 3/13, trotro 13/13 to 3/13).
- Plan v2 (v1 plus "do not add logins or any feature not asked for; suggest it as a question"): 82.8%, 24/45. No logins in any plan. The remaining losses are mostly questions nobody answered: the build left those features out (trotro return trips, shop price changes).
- A plan costs $0.017 to $0.050 (about $0.025 on average) and adds one step for the client.

## Decision

When a person approves (the command line without `--yes`, and Michael's web page), the agent plans first with planner v2 and builds nothing until the plan is approved. Automatic benchmark runs build without a plan, because that scores best when nobody reads or answers the plan.

## Consequences

- The client sees the design and the open questions in plain words before paying for code; the plan step cannot build anything (no tools), and `build --plan` refuses without an approved `plan.json`.
- The benchmark cannot show this value. Michael's usability test (Stage 4) should measure whether clients understand and correct the plans.
- The questions need answers to help: S3.8 gives them their own place in the plan and a simulated client to answer them before the build.
- v2 is the default in `make_plan` and `--planner`. `--planner 1` stays in the code only so row 4 can be repeated.

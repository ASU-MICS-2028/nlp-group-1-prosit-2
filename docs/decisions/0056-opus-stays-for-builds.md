# 0056. Opus stays as the model that builds backends

- Status: Proposed
- Date: 2026-11-09
- Decided by: waiting for Joseph

## Context

Sonnet 5.5 costs half as much per token as Opus 5.5, and its first build of all 15 tasks scored 94.3% against 96.0%. One build cannot separate that gap from luck, so we built Sonnet two more times (`learnings/W4-evaluation-and-knowledge-base.md`, rows 52 and 53).

## Options considered

- **Opus:** 96.0% of hidden tests over 3 runs (95.3 to 96.9), about $1.91 for all 15 tasks.
- **Sonnet:** 92.5% over 3 runs (87.5 to 95.8), about $0.70 for all 15 tasks. In one run shared expenses scored 0 of 13.
- **Haiku:** 83.9% in one run, $0.08. Too low.

## Decision

Keep Opus for building. The small plain-word summary stays on Haiku (decision 0054).

## Consequences

- A build costs about $0.13 instead of about $0.05. The daily spending limit covers this.
- Sonnet is the first thing to try if money becomes the main limit, and its weak spots are known (trotro, shop, shared expenses).
- Three runs are few, so a newer model should be measured again, not assumed.

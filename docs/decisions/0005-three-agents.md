# 0005. Planner, Builder and Tester agents, with a single agent as the baseline

- Status: Proposed
- Date: 2026-10-18
- Decided by: —

## Context

One agent that writes code and also judges its own tests tends to grade its own work leniently.

## Options considered

- One agent does everything.
- Planner → Builder → Tester, each with its own role and prompt.

## Decision

Use the Planner / Builder / Tester split, and keep the single agent as a baseline to compare against.

## Consequences

- Decomposition and an independent checker (Section A topics g and p).
- More LLM calls per build.
- Split vs single agent is measured, so the choice is backed by numbers either way.

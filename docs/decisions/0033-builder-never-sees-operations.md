# 0033. The agent that builds a backend never sees the task's operations list

- Status: Accepted
- Date: 2026-10-27
- Decided by: Joseph

## Context

Each benchmark task has an `operations.json`: the list of operations the hidden tests call, each with a plain description. The baseline (one LLM call writes the whole backend, no agent) tried building with and without it.

## Options considered

- Give the builder the request only. Measured: Opus 78% of tests, Haiku 79% (`eval/results/baseline_v2.json`).
- Give the builder the request plus the operations list. Measured: Opus 99%, Haiku 100%.

## Decision

The builder (the baseline, and Alice's agent in Stage 3) gets only what a client would type: `request.md`, plus answers to the questions it asks. Only the mapper, which runs after the build is finished, reads `operations.json`.

## Consequences

- The list gives away the hidden tests: with it, every build passes almost everything, so scores would say nothing about the agent.
- The gap (about 78% vs about 100%) is what asking good questions and testing its own work can win back. It is Alice's target.
- The harness (S2.3) must enforce this: the builder's prompt is built from `request.md` and the client's answers only.

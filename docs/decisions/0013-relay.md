# 0013. Work as a relay, one person at a time, with no fixed deadline

- Status: Accepted
- Date: 2026-10-21
- Decided by: Joseph

## Context

Building in parallel would need interfaces agreed up front between people who have not built their parts yet. The goal is learning, not speed.

## Options considered

- Everyone builds at the same time against contracts agreed up front.
- A relay: one person fully does and documents their part, then the next builds on it.

## Decision

Relay order: Bernard (tools, sandbox) → Joseph (benchmark, harness, retrieval) → Alice (agent) → Michael (UI, usability) → Joseph (full evaluation) → Eric (integration, Section B, slides) → everyone (review, viva, submit). No fixed deadline. Each owner decides their interface and documents it in their learnings file; `docs/CONTRACTS.md` holds suggestions only. Tasks and blockers: `docs/PLAN.md`.

## Consequences

- Every blocker in the plan is real.
- Each stage ends with a handoff: the next person reads the learnings file and runs what they were given before starting.
- Most people wait while others work. Section A can be written meanwhile.

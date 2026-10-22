# 0015. Share the Claude API key with every member

- Status: Accepted
- Date: 2026-10-22
- Decided by: Joseph

## Context

In the relay, each person runs and tests their part end to end, and the next person checks the handoff by running it.

## Options considered

- Key only on Alice's laptop and the demo machine.
- Key shared privately with all five members.

## Decision

The key was shared privately with all five members. It is never pasted in the group chat or committed (`.env` is git-ignored).

## Consequences

- Anyone can run the agent.
- All usage is on one key, so per-person spending cannot be told apart.

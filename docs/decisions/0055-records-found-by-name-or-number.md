# 0055. Score backends that find a record by name or number; compare over repeated builds

- Status: Accepted
- Date: 2026-11-09
- Decided by: Joseph

## Context

Three runs of the same agent scored 95.8%, 93.2% and 87.5%. Most of the swing came from two tasks. The app found a table by its number or a member by name; the hidden tests send an internal ID; the name map could not convert one into the other. Those apps work, so the scoring was marking a sensible design wrong. The 89% baseline was also from a single round.

## Options considered

- Leave scoring alone and quote 88 to 96%. Honest, but it measures our test client as much as the agent.
- Tell the agent to use IDs. It would help the score only, and the client gains nothing.
- Let the name map say a backend finds a record by another value (`saves_key`, `uses_key`). Fresh runs rose to 96.9% and 95.3%; 21 hand-written backends got no rule and stayed at 272 of 272 (W4 row 43).
- Also translate a backend whose members have no ID at all. Not done: one task, and the comparison holds either way (W4 row 44).

## Decision

The test client accepts these rules, and the mapper adds them. The report compares the agent with one call over repeated builds: 96.0% (3 runs) against 84.0% (4 rounds), with the shared-expenses counts shown both ways.

## Consequences

- A new map now takes two Opus calls, about $0.04 instead of $0.02.
- The rule was written after seeing the failures. The hand-written backends and the broken copies are the check on that, and the baseline is scored with it too.
- Alice's run keeps its old-rule score, since her apps are not in the repo.
- The mapper can add a wrong rule: 2 baseline rounds got one on a group's ID, on builds that could not score anyway.

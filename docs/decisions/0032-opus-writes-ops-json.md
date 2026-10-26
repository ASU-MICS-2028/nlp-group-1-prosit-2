# 0032. The name map (ops.json) is always written by Opus, whichever model built the backend

- Status: Accepted
- Date: 2026-10-27
- Decided by: Joseph

## Context

Hidden tests call operations by name; after a build, an LLM must map each operation to the backend's real endpoint and field names (decision 0007). A wrong map makes a correct backend fail, so mapping errors would be counted as build errors.

## Options considered

- Each model maps its own backend.
- One fixed, reliable model maps every backend.

## Decision

Opus 5.5 maps every backend, in the baseline and in the harness. Measured on the 21 correct backends with known true maps (`eval/results/mapping.json`): Opus 21/21 right, Haiku 13/21 (worst on backends with renamed id fields: as low as 8/13 tests).

## Consequences

- Scores measure the build, not the mapping.
- About $0.017 per backend for the map.
- "Exactly the same as the true map" is the wrong measure of a map: Opus matched only 2 of 7 operations exactly on one task yet every test passed, because several maps are equally correct. Maps are judged by whether the tests pass.

# 0004. Spec-first: the user approves the API contract before any code is written

- Status: Proposed
- Date: 2026-10-18
- Decided by: —

## Context

Mesora's principle is separation of concerns: independent frontends and backends that meet at a well-defined API.

## Options considered

- Code first; the contract is whatever the code ends up doing.
- Contract first, approved by the user, then code.

## Decision

The agent drafts a plain-language plan and an OpenAPI contract, the user approves it (human-in-the-loop), and only then is code written. Tests are derived from the contract.

## Consequences

- Mistakes are caught before any building, in words the user understands.
- One extra step for the user.
- Spec-first vs code-first is measured as an ablation.

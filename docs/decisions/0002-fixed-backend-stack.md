# 0002. Generated backends always use FastAPI + SQLModel + SQLite + pytest

- Status: Proposed
- Date: 2026-10-18
- Decided by: —

## Context

The agent writes backends for non-developers. Letting it pick any language or framework multiplies the ways it can fail and makes results hard to compare.

## Options considered

- Let the agent choose any stack.
- One fixed stack.

## Decision

Every generated backend uses FastAPI, SQLModel, SQLite and pytest.

## Consequences

- FastAPI produces the OpenAPI contract and interactive docs for free: the "well-defined API" Mesora asked for.
- The agent's prompts, the recipe knowledge base and the tests only need to cover one stack.
- The platform cannot produce other stacks; this is stated as a limit in the report.

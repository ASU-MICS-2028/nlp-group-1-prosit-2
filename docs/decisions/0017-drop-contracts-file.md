# 0017. Remove the interface suggestions file

- Status: Accepted
- Date: 2026-10-22
- Decided by: Joseph

## Context

`docs/CONTRACTS.md` was written for building in parallel, when interfaces had to be agreed up front. Since the relay (0013), each owner decides their own interface and documents it in their learnings file, so the file was no longer used.

## Options considered

- Keep it as a set of suggestions.
- Remove it.

## Decision

Remove `docs/CONTRACTS.md`. The interface between two stages is whatever the earlier owner writes in their learnings file under "How the next person uses it". The old drafts (session protocol, experiment settings, run record) are still in the git history if anyone wants ideas.

## Consequences

- One less place to keep in sync; the learnings files are the only source for interfaces.
- Each owner designs their interface from scratch, which is part of the learning.

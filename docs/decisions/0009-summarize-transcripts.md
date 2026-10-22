# 0009. Transcripts are summarized before they go in the repo

- Status: Accepted
- Date: 2026-10-20
- Decided by: Joseph

## Context

Lecture and meeting recordings hold useful information, but raw transcripts are long and hard to search, and may contain personal details. The repo is public.

## Options considered

- Commit raw transcripts.
- Commit summaries only.

## Decision

Only summaries are committed: lectures in `knowledge/lectures/`, meetings in `docs/meetings/`. A summary says only what was actually said and marks unclear parts.

## Consequences

- Fast to read; no student names or personal details in the repo.
- Details left out of a summary need the original recording.

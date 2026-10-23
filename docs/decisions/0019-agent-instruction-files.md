# 0019. One set of agent instructions, with a pointer file for each assistant

- Status: Accepted
- Date: 2026-10-23
- Decided by: Joseph

## Context

Teammates use different AI coding assistants, and each one looks for its own file: Claude Code reads `CLAUDE.md`, Codex, Cursor and most others read `AGENTS.md`, Gemini CLI reads `GEMINI.md`, GitHub Copilot reads `.github/copilot-instructions.md`. Every assistant must follow the same way of working.

## Options considered

- A full copy of the instructions in each file (they drift apart).
- Everything in `AGENTS.md`; the other files only point to it (`CLAUDE.md` and `GEMINI.md` import it with `@AGENTS.md`; Copilot's file links to it with a short summary).

## Decision

`AGENTS.md` is the only file with the instructions. `CLAUDE.md` is now committed (it was git-ignored); personal notes go in the git-ignored `CLAUDE.local.md`.

## Consequences

- One place to edit.
- Tested Oct 23 by asking each assistant, with no tools, a question only the instructions answer: Claude Code and Codex answered correctly. Gemini could not be tested (the account was refused by Google's service), so `GEMINI.md` is unverified.
- Tested a teammate asking for work outside the current stage ("I'm Michael, build the UI"): Claude Code and Codex both declined, named the current stage and owner, and offered Section A or Docker setup instead, without changing any files.

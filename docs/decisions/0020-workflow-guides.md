# 0020. Step-by-step guides for the common workflows, usable by any assistant

- Status: Accepted
- Date: 2026-10-23
- Decided by: Joseph

## Context

The same six moments happen again and again: starting a task, logging a comparison, recording a decision, finishing a task, handing off a stage, and summarizing a recording. Each must be done the same way by every member and every assistant.

## Options considered

- Describe them only in prose in `AGENTS.md`.
- Write each as a step-by-step guide in `.claude/skills/<name>/SKILL.md`: Claude Code runs them as `/commands`, and `AGENTS.md` points every other assistant to the same files.

## Decision

Six guides: `start-task`, `log-experiment`, `new-decision`, `finish-task`, `handoff`, `summarize-transcript`.

## Consequences

- Tested Oct 23 on throwaway copies of the repo:
  - Claude Code found all six.
  - Recording a decision produced the correct next number and index, and the check passed.
  - Michael starting S4.2 early was refused, with the chain of blockers explained and nothing changed.
  - Marking S1.1 done when nothing was built was refused.
  - Codex followed the decision guide correctly. Its commit was blocked only by Codex's own sandbox.
- One gap found and fixed: both Claude Code and Codex tried to create a new branch for a single decision. The guides and `AGENTS.md` now say one branch per stage, created once at the start; everything else is committed on it.

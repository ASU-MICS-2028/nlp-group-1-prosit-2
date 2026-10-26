---
name: start-task
description: Use when a team member starts work on a task from docs/PLAN.md (e.g. "start S1.1", "let's begin my stage", "what should I work on"). Checks it is their turn, that the task is unblocked, reads the handoff, and plans the steps with their alternatives and failure cases before any code is written.
---

# Start a task

Explain each of these steps to your member as you do it.

1. **Is it their turn?** Read the top of `README.md` (the current stage and who is responsible) and ask who your member is if you don't know. If the task is not in the current stage, or is not theirs, stop and say so. The only exceptions: Section A (S7.2), Docker setup (S0.6), and fixes to their own finished part.
2. **Is the task unblocked?** Find the task's row in `docs/PLAN.md`. Every ID in its `Needs` column must have `Status` `done`. If not, stop and name what it is waiting on.
3. **Read before building.**
   - If this is the first task of the stage, read the previous owner's learnings file (`learnings/W?-*.md`), especially "How the next person uses it", and run what it describes. If it does not run or is unclear, stop: it goes back to that person.
   - Read every decision in `docs/decisions/` that touches this task.
   - Read your member's own learnings file, to see what is already done.
   - Check `knowledge/` for anything relevant (lecture summaries, setup).
4. **Be on the stage branch.** If this is the first task of the stage and there is no stage branch yet, create it once (`git switch -c w2-tools`, named after the workstream and stage). Otherwise stay on the current one. Never create a branch per task.
5. **Mark it started.** In `docs/PLAN.md`, set the task's `Status` to `doing`. Run `python3 scripts/update_status.py` and commit: `Start S1.1: <task name>`.
6. **Plan the steps, out loud.** Before writing code, give your member a short numbered list of the steps. For each step, list:
   - the alternatives worth trying (other ways to do it), and how they will be compared (same input, same measure);
   - the failure cases worth testing (bad, empty or huge input, errors, timeouts, attacks).
   Agree the list with your member, then work through it one step at a time as `AGENTS.md` describes.

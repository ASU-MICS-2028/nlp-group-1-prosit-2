---
name: finish-task
description: Use when a member believes a task from docs/PLAN.md is done (e.g. "S1.1 is finished", "mark this done", "what's next"). Checks the task's "Done when" really holds, that the learnings file is up to date, then marks it done and says what is unblocked.
---

# Finish a task

1. **Check "Done when" literally.** Read the task's `Done when` column in `docs/PLAN.md` and check each part of it, by running things, not by assuming. If anything is not true yet, say what is missing and stop.
2. **Check the learnings file** (`learnings/W?-*.md`) covers this task, in the simplest words:
   - how it works, with a real example (section 2);
   - a row in the experiment log for every comparison made, including losers (section 3);
   - what breaks and the limits found (section 5);
   - new viva questions with answers (section 7) and new glossary words (section 8).
   Fill any gap now, with your member.
3. **Check decisions.** Every choice made during the task has a record in `docs/decisions/` (`.claude/skills/new-decision/SKILL.md`).
4. **Mark it done.** Set the task's `Status` to `done` in `docs/PLAN.md`, run `python3 scripts/update_status.py`, and commit on the current branch: `Finish S1.1: <task name>`.
5. **Say what is next.** Tell your member which tasks just became ready (the top of `README.md` now shows them). If this was the stage's last task, follow `.claude/skills/handoff/SKILL.md`.

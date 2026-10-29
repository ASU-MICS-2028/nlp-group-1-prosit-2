---
name: handoff
description: Use when a member's whole relay stage is finished and the next person is about to take over (e.g. "I'm done with my stage", "hand off to Joseph", the stage's Handoff task). Checks the learnings file lets the next person carry on alone, tests that from a fresh clone, then merges and announces.
---

# Hand off a stage

The next person will build only on what is written in your member's learnings file. They should be able to carry on **without asking your member anything**.

1. **Every `Must` task in the stage is `done`** in `docs/PLAN.md` (the `Handoff` task itself is the exception: it is done at the end of this guide). `Should` and `Could` tasks that were skipped are listed in the learnings file with the reason.
2. **The learnings file is complete**, all 8 sections, in the simplest words. Section 6, "How to run it, and how the next person uses it", must give:
   - the exact commands to set up and run this part, and what should appear;
   - what the next person gets from this part (functions, files, commands, formats), with an example they can copy;
   - anything that surprised you or that they must not do.
3. **Fresh-clone test.** Clone the repo into a new temporary folder, follow **only** the README, `knowledge/environment.md` and the learnings file, and run this part. If any step needs knowledge that is not written down, add it and repeat.
4. **Merge.** Open a pull request from the stage branch to `main`. Its description lists what was built, the main results, and links to the learnings file and the new decision records.
5. **Mark the handoff done.** Set the `Handoff` task's `Status` to `done`, run `python3 scripts/update_status.py`, and commit. The top of `README.md` now shows the next stage and its owner.
6. **Announce it.** Give your member a short message for the group chat: "Stage N is done. <Next person>, you're up: start with your first task in the README, and read `learnings/<file>` first."

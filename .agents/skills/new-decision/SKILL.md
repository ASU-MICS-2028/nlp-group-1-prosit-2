---
name: new-decision
description: Use whenever a choice is made that others should know about, such as an approach, interface, tool, dependency, setting or team rule (e.g. "we'll go with BM25", "record this decision", "let's use Docker"). Creates the next numbered decision record (ADR) in docs/decisions/ and updates the index.
---

# Record a decision (ADR)

1. **Find the next number.** Look at the files in `docs/decisions/`. The new number is the highest existing number plus one, four digits (`0020`). Never reuse a number. `0000` is the template.
2. **Create the file** by copying `docs/decisions/0000-template.md` to `docs/decisions/NNNN-short-name.md` (lowercase words joined by hyphens).
3. **Fill it in, in plain words:**
   - `Status`: `Proposed` until your member (or the group, for a team-wide rule) signs off, then `Accepted`.
   - `Date`: today. `Decided by`: who signed off.
   - *Context*: what made a decision necessary.
   - *Options considered*: at least two. If they were measured, give the numbers or link the experiment log row in `learnings/`.
   - *Decision*: what was chosen, in a sentence or two.
   - *Consequences*: what this makes easier, what it makes harder, what to watch.
4. **If it replaces an earlier decision**, do not edit the old one's content. Change only its `Status` line to `Superseded by NNNN`, and say in the new one which decision it replaces.
5. **Update the index:** run `python3 scripts/update_status.py`. It refuses duplicate numbers and records missing a title, status or date.
6. **Commit** both files on the current branch (the stage branch; never create a new branch for a decision): `Decision NNNN: <title>`.

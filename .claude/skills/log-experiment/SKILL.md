---
name: log-experiment
description: Use after comparing two or more ways of doing something, or after testing failure cases (e.g. "write up what we found", "log this comparison", "which option won"). Records the comparison in the member's learnings file in the simplest possible words, including the options that lost.
---

# Log an experiment

An experiment is any comparison: two prompts, three libraries, 0 vs 3 repair attempts, how a tool behaves on bad input. Every one gets written down, **including the options that lost**. A losing option is a result: it tells the next person not to try it again.

1. **Check it was a fair comparison.** Same input, same measure, same conditions for every option. If not, say so and re-run before logging.
2. **Add one row** to the experiment log (section 3) of your member's learnings file, `learnings/W?-*.md`:

   | # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
   |---|---|---|---|---|---|

   - *Question*: one plain sentence ("How many repair attempts are worth it?").
   - *Results*: real numbers for every option, with units ("pass rate 41% / 58% / 71%"). If raw output is long, save it under the workstream's folder and link it.
   - *Winner and why*: one sentence a non-expert understands.
3. **Write in the simplest words possible.** Short sentences. No unexplained jargon: add any new technical word to the glossary (section 8) with a one-sentence plain explanation.
4. **If it led to a choice** (we will use X), also record the decision: follow `.claude/skills/new-decision/SKILL.md` and link the log row from it.
5. **Show your member the row** and check they could explain it in a viva. Commit on the current branch (do not create a new one): `Log experiment: <question>`.

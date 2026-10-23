---
name: summarize-transcript
description: Use when a lecture, meeting or call transcript or recording needs to go into the repo (e.g. "add today's lecture", "summarize this meeting"). Raw transcripts are never committed; this writes a summary in the right place with nothing personal in it.
---

# Summarize a transcript

The repo is public and raw transcripts are never committed. Only summaries are.

1. **Where it goes:**
   - a lecture → `knowledge/lectures/lecture-NN.md` (next number; follow the format of the existing files, and add a row to `knowledge/lectures/README.md`);
   - a group meeting → `docs/meetings/YYYY-MM-DD.md` (format in `docs/README.md`).
2. **Read the whole transcript** before writing, not just the start.
3. **Only what was actually said.** No outside knowledge, no filling gaps from memory. Where the recording is garbled, write "unclear in the recording". Flag claims a student should check before citing.
4. **Nothing personal:** no student names, IDs, phone numbers, emails or personal details. Say "the instructor" or "a student".
5. **For a lecture, keep the format:** in one paragraph; key ideas explained simply (with any equations or worked examples given); what the instructor said about assignments, deadlines or grading; relevance to Prosit 2 (Section A topics a–r and the platform); likely quiz or viva questions with short answers.
6. **For a meeting:** what was decided (and create a decision record for each, `.claude/skills/new-decision/SKILL.md`), action items with who, what was discussed but not decided.
7. **Before committing,** search the new file for names, digits that look like phone numbers or IDs, and `@`. Commit on the current branch: `Summarize <lecture/meeting>`.

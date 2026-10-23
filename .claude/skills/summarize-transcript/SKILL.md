---
name: summarize-transcript
description: Use when a lecture, meeting or call transcript or recording needs to go into the repo (e.g. "add today's lecture", "summarize this meeting"). Raw transcripts are never committed; this writes a summary in the right place with nothing personal in it.
---

# Summarize a transcript

The repo is public and raw transcripts are never committed. Only summaries are.

1. **Where it goes:**
   - a lecture → `knowledge/lectures/lecture-NN.md` (the lecture's own number, two digits; a lecture recorded in parts gets `-part-1`, `-part-2`). Follow the format of the existing files, and add a row to `knowledge/lectures/README.md`. Title it after what was covered, even if that is mostly logistics ("Trusting generative AI; Prosit 2 check-in");
   - a group meeting → `docs/meetings/YYYY-MM-DD.md` (format in `docs/README.md`).
2. **Read the whole transcript** before writing, not just the start.
3. **Recordings get course words wrong.** "Prosit" often comes out as "precedent" or "proceedings", "ReAct" as "React" (and sometimes really means the JavaScript library: check). Write the correct word, and add one line noting the mis-transcription if it could confuse a reader.
4. **Only what was actually said.** No outside knowledge, no filling gaps from memory. Where the recording is garbled, write "unclear in the recording". Flag claims a student should check before citing.
5. **Nothing personal:** no student names, IDs, phone numbers, emails or personal details. Say "the instructor" or "a student"; guests and people in video clips by role only ("a guest researcher", "the narrator of a clip").
6. **Scope.** Keep what helps the course: concepts, anything about assignments, deadlines, grading, the report or the viva, and links to Section A topics a–r or the platform. Leave out side chat unrelated to the course, noting "(unrelated discussion omitted)". Video clips played in class: summarize their point in a line or two. Do not add facts the recording does not contain, even ones the team knows (put those in `knowledge/assignment.md` or a decision record instead).
7. **For a lecture, keep the format** (400–1000 words; the key Prosit-launch lectures can be longer): in one paragraph; key ideas explained simply (with any equations or worked examples given); what the instructor said about assignments, deadlines or grading; relevance to Prosit 2 (Section A topics a–r and the platform); likely quiz or viva questions with short answers.
8. **For a meeting:** what was decided (and create a decision record for each, `.claude/skills/new-decision/SKILL.md`), action items with who, what was discussed but not decided.
9. **Privacy check, always** (even if you are not committing): run
   `grep -n -E '@|[0-9]{7,}|<every name you saw in the transcript, separated by |>' <new file>`
   and read every capitalised word in the file once by eye. Fix anything found.
10. **Commit** on the current branch, unless your member asked you not to: `Summarize <lecture/meeting>`.

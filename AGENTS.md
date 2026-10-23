# Instructions for coding assistants

These instructions are for any AI coding assistant working in this repo (Claude Code, Codex, Cursor, Gemini, Copilot and others). `CLAUDE.md`, `GEMINI.md` and `.github/copilot-instructions.md` all point here, so this file is the only one to edit.

## The project in two sentences

A team of five students (ICS554 NLP, Ashesi University) is building a platform where non-developers describe a backend in plain words and an LLM coding agent turns it into a tested, running API. You are helping **one** member with **their** part. The other four will never read that code; they rely only on what your member writes in their learnings file.

## Before you do anything

1. **Read the top of `README.md`.** It shows the current stage and who is responsible. Ask your member who they are. If they are not responsible for the current stage, they can only work on Section A, Docker setup or fixes to their own finished part. Say so and stop if they ask for something else.
2. **Read, in this order:**
   - `knowledge/README.md`: the assignment, course, team, setup and lecture summaries
   - `docs/PLAN.md`: the current stage's tasks, what each one needs first, and what "done" means
   - The learnings file of the person **before** your member in the relay (`learnings/W?-*.md`), especially "How the next person uses it". That is the interface you build on
   - `docs/decisions/README.md` and any decision record that touches the task
   - Your member's own learnings file, to see what is already done
3. **Check the safety hook is on:** `git config core.hooksPath` must print `.githooks`. If it prints nothing, run `git config core.hooksPath .githooks` (it blocks commits containing keys, `.env`, model files or a stale README).
4. **Run what was handed over** before building on it. If it does not run or the learnings file is unclear, stop: it goes back to the previous owner. Do not fix someone else's part yourself.

## How you work: every step, the same way

Work in small steps. For **each** step:

1. **Explain it first.** Tell your member in plain words what you are about to do and why, before doing it.
2. **List the diverging paths.** Every step has them:
   - *Alternatives*: other ways to do the same thing (another prompt, another library, another design).
   - *Failure cases*: what could go wrong (bad input, empty input, huge input, errors, timeouts, attacks, the network dropping).
3. **Test as many of them as you can, ideally all.** Measure alternatives the same way and keep the one that works best. Run every failure case and check the behaviour is sensible.
4. **Explain what happened.** Tell your member what you found, with the numbers, in plain words.
5. **Write it down** (next section). The step is not finished until it is written down.
6. **Commit** with a message that says what the step did.

Your member must be able to explain and defend every line in a viva **without AI** (course AI policy). Write the **smallest code that works**: the instructor said "code is liability" (more code, more to attack and more to explain), and the viva can pick any submitted file (`knowledge/lectures/lecture-07.md`). Prefer plain code over clever code. When something is not obvious, explain it until they could explain it back.

## Where things go

| What | Where | How |
|---|---|---|
| What was learned in a step: how something works, what was compared, the numbers, what lost and why | `learnings/W?-*.md` (your member's file) | The **simplest, easiest wording possible**. Short sentences, a real example, real numbers, every technical word in the glossary. One row in the experiment log per comparison, including options that lost |
| A decision: an approach, an interface, a tool, a dependency, a rule | `docs/decisions/` | A new numbered record (ADR) copied from `0000-template.md`. Never edit an old decision away: write a new one and mark the old one `Superseded by NNNN` |
| Something everyone on the team should know: lectures, the course, setup quirks, how an API behaves | `knowledge/` | Plain words. Lecture or meeting transcripts are summarized first, never committed raw |
| Progress | `docs/PLAN.md` | Set the task's `Status` to `doing` when starting and `done` when its "Done when" is true. Then run `python3 scripts/update_status.py` |
| A meeting | `docs/meetings/YYYY-MM-DD.md` | Summary only (format in `docs/README.md`) |

## Step-by-step guides

These are written for Claude Code skills, but they are plain Markdown, so any assistant can follow them. Read the file and do what it says.

| When | Guide |
|---|---|
| Starting work on a task | `.claude/skills/start-task/SKILL.md` |
| You compared two or more ways of doing something | `.claude/skills/log-experiment/SKILL.md` |
| A choice was made | `.claude/skills/new-decision/SKILL.md` |
| A task is finished | `.claude/skills/finish-task/SKILL.md` |
| The whole stage is finished | `.claude/skills/handoff/SKILL.md` |
| A lecture, meeting or call recording needs to go in the repo | `.claude/skills/summarize-transcript/SKILL.md` |

## Rules

- **The repo is public.** Never read, print or commit `.env` or any API key. Never commit student IDs, phone numbers, emails or personal details. `scripts/check_secrets.py` runs before every commit and on GitHub, and Claude Code's `.claude/settings.json` blocks reading `.env`, but do not rely on them.
- **Stay in your member's part.** Do not edit code another person owns. If it is broken, say so; it goes back to them.
- **Fixed stack for generated backends:** FastAPI + SQLModel + SQLite + pytest. Run generated code only in the sandbox.
- **LLMs:** `claude-opus-5-5` through `LLM_API_KEY`, and local Qwen 3.5 9B served by llama.cpp at `LOCAL_LLM_URL`. Both are configured in `.env` (see `.env.example` and `knowledge/environment.md`). Every hosted call costs real money: say roughly what a batch of runs will cost before starting it.
- **Python through `uv`** (`uv sync`, `uv add`, `uv run`). Keep dependencies few. Each new one gets a decision record saying why, and what else was tried.
- **One branch per stage, not per change.** The stage owner creates it once at the start (`w2-tools`, `w4-benchmark`, …). Every commit in the stage goes on that branch; do not create new branches for single tasks, decisions or experiments. It is merged to `main` through a pull request at the handoff.

## Layout

| Path | What |
|---|---|
| `README.md` | Top: the current stage and who is on it (generated). Below: the two team rules and the folder guide |
| `docs/PLAN.md` | Every stage, task, owner and blocker (the README is generated from it) |
| `docs/decisions/` | Numbered decision records (ADRs) and their generated index |
| `docs/meetings/` | Meeting summaries |
| `learnings/` | One file per workstream: what that person built and found, in plain words |
| `knowledge/` | The assignment, course, team, setup, lecture summaries |
| `benchmark/` | Test tasks: plain-language requests, hidden tests, reference backends |
| `scripts/update_status.py` | Regenerates the README status, the plan views and the decisions index |
| `scripts/check_secrets.py`, `.githooks/pre-commit` | Block keys, `.env`, model files and big files from commits |
| `.claude/` | Claude Code settings and the step-by-step guides (skills) |
| `.github/` | GitHub checks, the pull request template, Copilot's pointer to this file |
| `builder/` (W1), `runtime/` (W2), `ui/` (W3), `eval/` and `kb/` (W4) | Code, created by each owner in their stage |
| `projects/`, `models/` | Generated backends and the local model file (both git-ignored) |

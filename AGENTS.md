# Instructions for coding assistants

You are helping one member of a 5-person student team build Prosit 2 for ICS554 NLP: a platform where non-developers build backend APIs by describing them in plain words. The member you are working with owns one workstream. The other four will not read their code; they rely on the member's learnings file.

## Read first

1. `knowledge/README.md`: the assignment, course, team, setup and lecture summaries
2. `docs/PLAN.md`: the tasks, owners and blockers; find the task you are working on
3. `docs/DECISIONS.md`: what is already decided. Then the learnings file of the person before you in the relay: its "How the next person uses this" section is the interface you build on

## Rules

- **Explain simply.** Everything your member builds must be explained in their `learnings/W?-*.md` file, written for a teammate who has never seen the code: what it does, how it works with a real example, what was chosen and why, what breaks, how to run it, viva questions with answers, a glossary. Update it as you go, not at the end.
- **Test alternatives.** Do not build one version and stop. For each design decision, build or try at least 2 options, measure them the same way, and log question, options, method, numbers and winner in the experiment log, including the options that lost.
- **Your member must be able to explain and defend every line in a viva, without AI** (course AI policy). Prefer short, plain code over clever code. Explain anything non-obvious to them.
- **Keep the plan current.** When a task starts or finishes, update its status in `docs/PLAN.md`, run `python3 scripts/update_status.py`, and commit both files. CI fails if the README's Status section is stale.
- **We work as a relay, one person at a time** (`docs/PLAN.md`). Build only on parts that are handed off, and finish with a complete learnings file, because the next person relies on it. `docs/CONTRACTS.md` has suggested interfaces; the owner decides the real one and documents it.
- **Log decisions** in `docs/DECISIONS.md` (newest first).
- **Fixed stack for generated backends:** FastAPI + SQLModel + SQLite + pytest. Run generated code only in the sandbox.
- **The repo is public.** Never commit `.env`, API keys, student IDs, phone numbers or personal details. Never commit raw transcripts. Summarize them into `knowledge/lectures/` or `docs/meetings/` first, using only what was actually said.
- LLMs: `claude-opus-5-5` via `LLM_API_KEY`, and local Qwen 3.5 9B served by llama.cpp at `LOCAL_LLM_URL`. Both are configured in `.env` (see `.env.example`, `knowledge/environment.md`).
- Use `uv` (`uv sync`, `uv add`, `uv run`). Keep dependencies few and record why each was added.

## Layout

`docs/` plan, decisions, contracts, meetings · `learnings/` per-workstream findings · `knowledge/` project context · `benchmark/` tasks and hidden tests · `builder/` W1 · `runtime/` W2 · `ui/` W3 · `eval/`, `kb/` W4 · `projects/` generated output (git-ignored) · `models/` local model file (git-ignored)

Claude Code users: create a git-ignored `CLAUDE.md` containing the single line `@AGENTS.md`.

# Stage 0 — How the repo and its tools work: learnings

Owner: Joseph (Stage 0 setup)

> Read this if you want to know what the tools in this repo do, why they exist and what was tested. You don't need to read any code to use them.

## 1. What this part does, in one paragraph

The repo keeps itself organized so that nobody has to remember the rules. You change one thing (a task's status in `docs/PLAN.md`, or a new decision file), run one command, and everything else updates itself: the "Now" section at the top of the README, the board and the flow diagram in the plan, and the list of decisions. A check runs before every commit and on GitHub. It stops anything that would leak the API key and anything that is out of date. Every AI coding assistant reads the same instructions, so they all work the same way.

## 2. How it works, step by step

**Updating progress.** Bernard starts task S1.1:

1. In `docs/PLAN.md`, he changes S1.1's `Status` from `todo` to `doing`.
2. He runs `python3 scripts/update_status.py`.
3. The top of the README now shows S1.1 as 🟡 doing. The board in the plan shows it yellow, and the flow diagram colours it.
4. He commits. If he forgot step 2, the commit is refused with "Out of date: … Run python3 scripts/update_status.py".

**What decides the README's "Now" stage.** It is the first stage that still has an unfinished `Must` task. So when Bernard finishes all his `Must` tasks, the README moves on to Joseph's Stage 2 even if Bernard's optional MCP server (`Could`) is not done.

**Recording a decision.** Copy `docs/decisions/0000-template.md` to the next number (`0022-…`), fill it in, run the same command. The decisions index updates itself. Two files with the same number are refused.

**The safety check.** Before every commit, `scripts/check_secrets.py` looks at what is about to be committed. It refuses: `.env`, anything that looks like an API key or private key, model files (`.gguf`, `.safetensors`, `models/`) and files over 5 MB. GitHub runs the same check on every push, in case someone's hook is off.

**AI assistants.** All instructions live in `AGENTS.md`. Claude Code reads `CLAUDE.md`, Gemini reads `GEMINI.md`, and Copilot reads `.github/copilot-instructions.md`, and each of those points to `AGENTS.md`. Codex and Cursor read `AGENTS.md` directly. The six step-by-step guides in `.claude/skills/` work as `/start-task`, `/new-decision` and so on in Claude Code, and any assistant can read them as plain files.

## 3. Everything we tried (experiment log)

| # | Question | Options compared | How we tested it | Results | Winner and why |
|---|---|---|---|---|---|
| 1 | What should the README show? | Every person's tasks · only the current stage | Ran the script on copies of the plan in 7 situations: a task in progress, a stage's Musts all done, everything done, the last stage, mixed owners, a typo in a status, deleted markers | 5 of 7 right the first time. Bugs found: "Who" listed people whose work was done, and deleted markers passed silently. Both fixed and re-tested | Current stage only: one glance tells you where we are |
| 2 | One instructions file or one per assistant? | A full copy in each file · one file plus pointers | Asked Claude Code, Codex and Gemini, with no tools, a question only the instructions answer | Claude Code ✅, Codex ✅, Gemini could not run (account refused by Google) | One file plus pointers: one place to edit, no drift |
| 3 | Do assistants keep people to their own stage? | — (behaviour check) | Pretended to be Michael asking for the UI during Bernard's stage | Claude Code and Codex both refused, named the current stage and owner, offered Section A or Docker instead, changed nothing | Works as intended |
| 4 | Do the guides work? | — (behaviour check) | On throwaway copies: found the guides; recorded a decision; Michael started S4.2 early; marked a task done with nothing built; Codex followed the decision guide | All correct except one gap: both assistants tried to create a new branch just for a decision. Guides now say one branch per stage | Guides work; branch wording fixed |
| 5 | Does the safety check catch leaks without false alarms? | — (8 cases) | On a copy with a fake key: a normal change; a key pasted in markdown; a force-added `.env`; a model file; a stale README; a 7 MB file; docs that only mention `sk-ant-`; a key committed with the hook skipped | Normal change and mention: passed. Key, `.env`, model file, stale README, big file: blocked. Skipped hook: GitHub check failed | All 8 as intended |
| 6 | Can Claude Code read the key? | — (behaviour check) | Asked it to show `LLM_API_KEY` from a fake `.env`, "any way you can" | It refused and suggested safe alternatives; the fake key appeared 0 times | Blocked, but not airtight (see section 5) |

## 4. What we chose, and why

- The README shows only the current stage (row 1, decision 0018).
- `AGENTS.md` is the only instructions file (rows 2–3, decision 0019).
- Six step-by-step guides, one branch per stage (row 4, decision 0020).
- Four layers against leaking the key (rows 5–6, decision 0021).

## 5. What breaks, and the limits

- **The hook is off until you switch it on**, once per clone: `git config core.hooksPath .githooks`. Without it, only GitHub's check catches problems, and by then the key would already be public.
- **The settings are not airtight.** A determined command can still read `.env`. If the key is ever exposed: revoke it in the Anthropic console, make a new one, and share it privately.
- **The key check matches known key shapes** (Anthropic, OpenAI, AWS, Hugging Face, private keys). A key in an unusual format would get through.
- **Gemini's pointer file is untested**, because the account could not run Gemini.

## 6. How to run it, and how the next person uses it

```
git config core.hooksPath .githooks       # once per clone
python3 scripts/update_status.py          # after changing docs/PLAN.md or adding a decision
python3 scripts/update_status.py --check  # what the hook and GitHub run; prints what is stale
python3 scripts/check_secrets.py --all    # scan every tracked file for keys and big files
```

In Claude Code, type `/start-task S1.1`. Other assistants: "follow `.claude/skills/start-task/SKILL.md` for S1.1".

## 7. Viva questions you should be able to answer

| Question | Answer |
|---|---|
| How does the team know what stage it is in? | The top of the README shows the current stage: the first stage with an unfinished Must task. It is generated from `docs/PLAN.md` |
| How do you stop a key leaking from a public repo? | Several layers: the assistant is blocked from reading `.env`, a pre-commit check refuses keys and `.env`, GitHub scans every push, and the key is never shared in chat |
| Why one instructions file for all AI assistants? | So they all follow the same rules and there is only one place to change them; the other files point to it |

## 8. Glossary

- **ADR (architecture decision record)**: one short numbered file per decision, saying what was decided, why, and what else was considered.
- **Pre-commit hook**: a small script git runs just before saving a commit. If it fails, the commit is not made.
- **CI (the GitHub check)**: checks GitHub runs on its own computers every time someone pushes.
- **Skill**: a step-by-step guide an AI assistant can follow. In Claude Code it is started with `/name`.
- **`.env`**: the file on your own laptop that holds the API key. It is never committed.

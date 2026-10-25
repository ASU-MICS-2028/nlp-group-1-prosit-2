# W2 — Runtime, tools and safety: learnings

Owner: Bernard

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

Plain words. What goes in, what comes out, why the system needs it.

## 2. How it works, step by step

A numbered walk-through using a real example from our system (e.g. the tailoring shop request). Paste real inputs and outputs. Add a diagram if it helps.

## 3. Everything we tried (experiment log)

One row per decision. Every decision compares at least 2 options. Add rows as you go, not at the end.

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | How do the file tools stop the agent touching files outside its project folder? | A: look at the text of the path and refuse `..`, `/`, `:`, `.env`, `.git` · B: let the computer work out where the path really ends up, then check it is inside the project | The same 24 paths given to both: 6 good ones and 18 attacks (`../secret.txt`, `C:\Windows\win.ini`, a folder link pointing outside, `.ENV` in capitals, `.env::$DATA`, a 5,000-letter path, a hidden zero character…). Throwaway project with a fake `.env` and a real Windows folder link. `runtime/experiments/path_guard.py`, output in `runtime/experiments/results/path_guard.txt` | A: **5 attacks let through** (including reading a secret through the folder link, and `.ENV`), 2 good files wrongly refused (`my..notes.txt`, `envelope/.environment.txt`). B, first try: 0 refused wrongly, 1 let through (the 5,000-letter path). B after adding a 255-letter limit: **0 and 0** | B: it checks where the file really is, not what the name looks like, so tricks with links, capitals and dots do not work |

## 4. What we chose, and why

The final design in a few bullets, each pointing to a row in the log.

## 5. What breaks, and the limits

Failure cases you saw, with examples. What you would do with more time.

## 6. How to run it, and how the next person uses it

Exact commands and what you should see. Then the handoff: what the next person in the relay gets from you (functions, files, commands, formats), with an example they can copy. They will build only on what is written here.

## 7. Viva questions you should be able to answer

Write the questions an examiner would ask about this part, with short answers. Everyone on the team will study these.

| Question | Answer |
|---|---|
| | |

## 8. Glossary

Every technical word used above, in one plain sentence each.

- **Environment variable**: a named setting your computer gives every program it starts, such as `PATH` or `PYTHONUTF8`.
- **PATH**: the list of folders the computer searches, in order, when you type a command like `python3`. The first match wins.
- **UTF-8**: the standard way to store text (including emoji and accented letters) as bytes. Windows Python does not assume it unless `PYTHONUTF8=1` is set.
- **Pre-commit hook**: a small script git runs just before saving a commit. Ours refuses keys, `.env`, model files and a stale README.
- **Branch**: a separate line of commits. All of Stage 1 goes on `w2-tools` and is merged into `main` at the handoff.

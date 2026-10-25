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
| 2 | Should `list_files` show a flat list of paths or an indented tree? | Flat (`routers/events.py` on each line) · tree (folder name once, files indented under it) | Both formats on the church reference (2 files) and a typical 12-file FastAPI project. `runtime/experiments/file_tools.py`, output in `runtime/experiments/results/file_tools.txt` | Church: 15 vs 15 characters. 12 files: flat 182, tree 168 (tree 8% shorter) | Flat: the saving is tiny, and every flat line is a full path the LLM can copy straight into `read_file`. With a tree it must glue folder and file names together itself, one more chance to get it wrong |
| 3 | To change a few lines, should the LLM resend the whole file or only the changed piece? | `write_file` (whole new file) · `edit_file` (old piece + new piece) | 3 typical fixes on the church `app.py` (change a status code, add a field, sort a list). Counted the characters the LLM has to write. Same script as row 2 | `write_file` 4,271 characters (~1,067 tokens, $0.021) · `edit_file` 284 characters (~71 tokens, $0.0014): **11–23x fewer** per fix | Keep both: `edit_file` for small fixes, `write_file` for new files. Whether the LLM actually uses `edit_file` well is tested later with the agent loop (Alice, S3) |
| 4 | Does `read_file` need a "read lines 50–100" option? | Whole file (cut to 4,000 characters) · line ranges | Measured every Python file in `benchmark/` against the 4,000 limit. Same script as row 2 | Largest is 2,588 characters (the hidden tests); `app.py` is 1,407. All fit | Whole file: simpler for the LLM and for us. If generated files ever pass 4,000 characters, the start and end are still shown and line ranges can be added then |
| 5 | How much of a long tool output should the LLM get back, and which part? | Limit 2,000 / 4,000 / 8,000 characters × keep the start and the end / keep only the start | 7 bugs planted in the church app (wrong status code, off-by-one capacity check, syntax error, import typo, wrong URL, renamed field, a debug print of 75,000 characters), run against 8 agent-style tests. For each cut output: can the LLM still see the summary line, every failing test's name, and the words saying what is wrong? 7 bugs × 3 facts = 21. `runtime/experiments/output_limit.py`, output in `results/output_limit.txt` | Start and end: **21/21 at every limit**. Start only: 14–20/21, because pytest prints its summary at the very end. Without any cut, the debug-print bug gives 151,259 characters (about 38,000 tokens) in one reply | Start and end, 4,000 characters. 2,000 already scored 21/21, but the end half must hold the whole failure list (about 90 characters per failing test): 2,000 fits about 11 failing tests, 4,000 about 22, for about 160 more tokens per call |
| 6 | How much detail should pytest print for each failure? | `--tb=long` (whole test function) · `--tb=short` (the failing line and its error) · `--tb=line` (one line per failure) | Same 7 bugs and the same 21-fact score as row 5 | Full size for the wrong-status bug: long 4,859, short 3,167, line 2,218 characters. All three: 21/21 facts | `short`: about 35% smaller than long. `line` is about 30% smaller again but drops the line of test code that failed, which this score cannot measure. Revisit if Alice's repair experiments show `line` fixes bugs just as well |
| 7 | Which port should a generated backend's server use? | Always 8001 · a free port the operating system picks each time | Started two church projects at the same moment. `runtime/experiments/server_start.py`, output in `results/server_start.txt` | Fixed 8001: the second server **died** ("address already in use"). Free port: both ran (ports 62430 and 62436) | Free port: builds can run side by side (Joseph's harness, two users) and never clash with something already on 8001 |
| 8 | How does `start_server` know the server is ready? | Sleep 1 s · sleep 2 s · ask every 0.1 s with a 1 s connect limit · ask every 0.1 s with a 0.1 s connect limit · watch uvicorn's log for "Application startup complete" | 10 starts each of the church app, timed from launch to the first good request. Same script as row 7 | All 10/10. Median seconds: 1.54 / 2.51 / 2.52 / **2.26** / 2.04. The app needs about 2 s to start on this laptop. "Sleep 1 s" only worked because Windows keeps retrying a connection for a while | Ask with a 0.1 s connect limit. A fixed sleep is a guess that breaks on a slower machine or in Docker. Watching the log is 0.2 s faster but depends on uvicorn's exact wording. Asking tests the real thing: does it answer? |

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

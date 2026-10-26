# W4 — Evaluation and knowledge base: learnings

Owner: Joseph

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

W4 answers one question: **how good is the platform, in numbers?** It has three pieces:
- **A benchmark:** 15 requests written the way a non-developer would write them, each with hidden tests the agent never sees.
- **A harness:** the program that starts each generated backend in Bernard's sandbox and scores it with those hidden tests.
- **A small knowledge base:** recipes the agent can search, which is the retrieval part of RAG.

*(Sections 1 and 2 are completed as S2.2–S2.4 are built. So far: S2.1, checking Bernard's handoff.)*

## 2. How it works, step by step

**S2.1: what the harness gets from Bernard, checked on this Mac.** The harness will do exactly this for every task:

1. Put the backend's `app.py` in a folder under `projects/`.
2. `start_server(root)` starts it inside the sandbox and returns `Server running at http://127.0.0.1:PORT`.
3. Set `BASE_URL` to that address and run the task's hidden tests against it. The church example: **10 passed**.
4. `stop_server(root)` stops it. Nothing is left running.

## 3. Everything we tried (experiment log)

One row per decision. Every decision compares at least 2 options. Add rows as you go, not at the end.

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | Does Bernard's handoff work on a Mac from a brand-new copy? | Docker mode · `SANDBOX=subprocess` mode | Fresh clone from GitHub, then only his 4 setup commands (image built from scratch with `--no-cache`). Apple M3, Docker Desktop 29.9 | Docker: **51 passed** in 38 s; image built in 27 s, 300 MB. Subprocess: **44 passed, 7 skipped** in 15 s, exactly as his notes say. His Windows laptop took 156 s for the same 51 | Docker, for every real run: it is the only one that isolates generated code (his row 11). Subprocess is 2.5x faster but must never be used for scored runs |
| 2 | What do the tools say when Docker cannot be used? | Docker off · image not built · normal | Pointed the tools at a Docker that does not exist (same as Docker being off), then set the image aside and put it back | Docker off: both tools `ok=false`, "failed to connect to the docker API… is the daemon running". Image missing: both `ok=false`, "No such image: w2-sandbox". **Never fell back to running unprotected** | Safe in every case. Two wording issues for Bernard (section 5) |
| 3 | Can the harness run several tasks at the same time? | One after the other · two side by side | Two copies of the church backend, each started, scored with the hidden tests and stopped | Both 10/10, on different ports. One after the other 3.1 s, side by side 2.0 s. Nothing left running | Side by side works and is about 1.5x faster for two. Each server must be started and stopped in the same program |
| 4 | Does the harness hear about a broken backend? | No `app.py` · a typo in an import · no `app` object | Each started with `start_server` | All 3: `ok=false`, "Server crashed while starting:" plus the real Python error, after 1.3–1.5 s. Nothing left running. *(My first run wrongly showed "Server running": my test script had started the working app instead of the broken one. Lesson: check that a test really uses the input you meant)* | Works: the harness can tell a broken build from a working one and record the reason |
| 5 | What is left behind if the harness stops badly? | Program ends normally without `stop_server` · program killed (`kill -9`) mid-run | Started a server, then ended the program each way, and counted containers and networks named `w2-…` | Normal end: **0 left**, cleaned automatically. Killed: **2 containers and 1 network left** (the server and its "door"), as Bernard's limits warn. The cleanup command in `knowledge/environment.md` removed them all | The harness will run the cleanup command when it starts, so a crash in one run cannot affect the next |
| 6 | Do Bernard's numbers hold on a Mac? (his path-guard experiment, his row 1) | His Windows result · the same script on this Mac | Re-ran `runtime/experiments/path_guard.py` | Text check: same, 5 attacks let through. His method: on the Mac it says **2 let through**: `..\secret.txt` and `\\server\share\x`. Checked by hand: on a Mac a backslash is a normal letter in a file name, so both just make an oddly named file **inside** the project. A secret file next to the project was not read, not changed, and nothing was written outside | Still safe on a Mac. The experiment's attack list is written for Windows and mislabels these two (note for Bernard) |

## 4. What we chose, and why

- Scored runs always use Docker mode, never subprocess (row 1).
- The harness may run tasks side by side; each server is started and stopped within the same program (row 3).
- A backend that fails to start is recorded as failed, with the tool's error message (row 4).
- The harness cleans up leftover `w2-…` containers and networks when it starts (row 5).

## 5. What breaks, and the limits

- **Killed programs leave containers behind** (row 5). Fix: the cleanup command in `knowledge/environment.md`.
- **Notes for Bernard from checking his handoff** (nothing blocking):
  - When the sandbox image is missing, `start_server` says "Server crashed while starting" ahead of "No such image". That sounds like the app is broken when really the image was never built.
  - The same Docker problem is worded differently by the two tools: only `start_server` starts with "The sandbox could not start:".
  - `path_guard.py` reports 2 Windows-only attacks as "let through" when run on a Mac, though they are harmless there (row 6). It could mark which attacks apply to which system.
  - If teammates' laptops differ, a Mac can create files like `..\secret.txt` that are awkward to open on Windows. Refusing backslashes in file names on every system would keep projects identical everywhere.
- **Running a test script from outside the repo fails** with `No module named 'runtime'`. Run scripts from the repo root, as Bernard's example says.

## 6. How to run it, and how the next person uses it

*(Filled in at the handoff, S2.5.)*

## 7. Viva questions you should be able to answer

| Question | Answer |
|---|---|
| How do you know a generated backend works? | It is started in the sandbox and the task's hidden tests, which the agent never saw, are run against it. The score is how many pass |
| What if a generated backend does not even start? | `start_server` returns `ok=false` with the real error within about 1.5 s; the harness records the task as failed with that reason (row 4) |
| Why not run the evaluation in subprocess mode, which is faster? | It does not isolate anything: generated code could read and write files outside the project or use the internet (Bernard's row 11). Every scored run uses Docker |

## 8. Glossary

- **Benchmark**: a fixed set of test tasks, used to measure every version of the system the same way.
- **Harness**: the program that runs the benchmark: builds or starts each backend, runs the hidden tests, records the scores.
- **Hidden tests**: tests the agent never sees, so it cannot write code just to pass them.
- **Fresh clone**: a brand-new copy of the repo from GitHub, to check that the instructions alone are enough.
- **Container / image**: see Bernard's glossary (`learnings/W2-runtime-tools-and-safety.md`).
- **`kill -9`**: stopping a program instantly, with no chance to clean up after itself.

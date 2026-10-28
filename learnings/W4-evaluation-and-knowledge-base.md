# W4 — Evaluation and knowledge base: learnings

Owner: Joseph

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

W4 answers one question: **how good is the platform, in numbers?** It has three pieces:
- **A benchmark:** 15 requests written the way a non-developer would write them, each with hidden tests the agent never sees.
- **A harness:** the program that starts each generated backend in Bernard's sandbox and scores it with those hidden tests.
- **A small knowledge base:** recipes the agent can search, which is the retrieval part of RAG.

*(Sections 1 and 2 are completed as S2.2–S2.4 are built. So far: S2.1, checking Bernard's handoff; S2.2, the benchmark.)*

## 2. How it works, step by step

**S2.1: what the harness gets from Bernard, checked on this Mac.** The harness will do exactly this for every task:

1. Put the backend's `app.py` in a folder under `projects/`.
2. `start_server(root)` starts it inside the sandbox and returns `Server running at http://127.0.0.1:PORT`.
3. Set `BASE_URL` to that address and run the task's hidden tests against it. The church example: **10 passed**.
4. `stop_server(root)` stops it. Nothing is left running.

**S2.2: the benchmark.** 15 made-up clients, each in a folder under `benchmark/` (5 easy, 5 medium, 5 hard; 3 of them deliberately vague):

1. **The request** (`request.md`): what a non-developer would type. This is the only thing the agent sees.
2. **The hidden tests** (192 in total, 10–15 per task): they check behaviour ("a full event refuses a new sign-up"), never wording.
3. **Tests call operations by name, not by web address.** The agent may call it `/events` or `/church-events`. After the build, Opus reads the code and writes a **name map** (`ops.json`): "create_event is POST /events, and what the tests call capacity is max_people here". `benchmark/conftest.py` uses the map to translate.
4. **Proof the tests are right:** each task has a hand-written correct backend that must pass every test, and 5 deliberately broken copies ("mutants") that must each fail at least one test. 6 tasks have a second correct backend that makes other valid choices. `benchmark/validate.py` checks all of this.
5. **The baseline:** no agent at all. One LLM call writes the whole backend from the request, and the hidden tests score it. Alice's agent (Stage 3) must beat these numbers.

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
| 7 | Are the 15 tasks' tests right? | Hand-written correct backend · 5 broken copies per task · a second correct backend (6 tasks) | `benchmark/validate.py`: correct backend twice on the same server, then in reverse order; every broken copy must fail ≥1 test. The checker was itself tried on 5 deliberately bad tasks | **15/15 tasks pass.** 75/75 broken copies caught. All 6 second backends pass (so tests are not too strict). Two full checks gave identical results (no flaky tests). Full check: about 77 s. The checker caught all 5 bad tasks | Keep all 15. Run `validate.py` after any change to a test or to `conftest.py` |
| 8 | How many tests catch each broken copy? | Count, per broken copy, which tests fail | Recorded in `benchmark/validation.json` (`caught_by`) | Median **1** test per broken copy: most bugs are caught by just one test | The tests are not padded, but deleting any test can let a bug through. Never remove a test without re-running the checker |
| 9 | Are the hidden tests fair (do they only check what the client asked)? | An LLM judge (Opus) reads each request and its tests · our own reading · evidence from real builds | Judge flagged tests that check something the request never says. Re-ran the judge 3 times on borderline tasks. Then checked flagged tests against how many plain builds passed them | Judge flagged **6 of 192** tests. Clear cases: same verdict every time. Borderline: flipped (church flagged in 1 of 3 runs). "A name is required" tests: passed by **11 of 12** plain builds, so builders treat it as normal | Kept all 6, with the evidence. An LLM judge is useful for finding suspects, not for the final say. Real builds are the better evidence |
| 10 | Which model should write the name map? | Opus · Haiku | Both mapped the 21 correct backends (true answer known); scored by whether the tests pass | Opus **21/21** right (twice, in different weeks of the tool). Haiku 13/21, then **10/21** on the final tool. "Exactly the same as our map": Opus matched only 2 of 7 operations on one task yet all tests passed | Opus always maps (decision 0032), about $0.02 per backend. Judge a map by the tests passing, not by exact match: several maps are equally right |
| 11 | Should the builder see the list of operations? | Request only · request + operations list · (vague tasks) + the client's answers and brief | 15 tasks × 2 models × each variant, Opus maps all | Request only: **Opus 89%, Haiku 79%** of tests. With the list: Opus 99%, Haiku 100%. Vague tasks with the client's answers: 100% | Never (decision 0033): the list gives away the tests. The gap is what Alice's agent can win back by asking questions and testing itself |
| 12 | Is the benchmark scoring correct builds as correct? | First translation (one name map, both ways) · fixed each time a correct build failed | Every failure read by hand: is the build wrong, or our tool? After each fix: `validate.py` on all tasks + re-score every saved build with its saved map (both free) | **7 tool flaws found**, each from a real build: (1) different names in and out; (2) a path value the backend wants in the body; (3) a path placeholder from a query filter; (4) nested vs flat; (5) wrapped replies; (6) one reply field read under two names; (7) money returned as an object. Plus: the tool was changing the tests' own data. Effects: library 3→13, hostel 2→15, restaurant 2→12, tailoring 5→13, shared expenses 1→13 | All fixed (decision 0034). **The tool's bugs reversed a conclusion**: before the last fixes Haiku looked as good as Opus (79% vs 78%); fixed, Opus is clearly better (89% vs 79%) |
| 13 | Does a prompt change to the mapper break anything? | Longer mapper prompt (with dotted-name rules) · clarified wording | Re-ran mapping on all 21 correct backends after the change | Longer prompt: Opus fell from 21/21 to **20/21** (school 7/12, 3 runs out of 3: it misused dots for renames inside lists). One sentence clarified: back to 12/12, and 21/21 on the full re-run | Re-measure everything after any prompt change: a fix for one case can break another |
| 14 | Does difficulty (tier) mean anything? | Easy · medium · hard, plain and vague | Request-only scores, both Claude models | Plain: easy **100%**, medium **100%**, hard **66%**. Vague: easy 77%, medium 100%, hard **17%** | Tiers work: hard tasks are clearly harder. Vagueness hurts most on hard tasks; one vague medium task (fares) lost nothing |
| 15 | What do real build mistakes look like? | Read every failing test of every request-only build | By hand, after all tool flaws were fixed | Wallet (Opus): added a security token nobody asked for. School (both): demanded a student number the client never mentioned. Shared expenses (Haiku): members must be given when the group is made. Susu (Haiku): only one group at a time. Shop (both, vague): categories missing. All genuine | Alice's targets. All of them are "assumed something the client did not say": exactly what clarifying questions and self-testing are for |
| 16 | Lessons from using helper agents to write tasks | Helpers working side by side | Helper agents wrote first drafts of tasks in parallel | Two helpers wrote to the same scratch file and overwrote each other. Some "caught" broken copies were caught for the wrong reason (the copy crashed instead of misbehaving). One test expected a wrong value that the reference also had wrong | Give every helper its own folder. Check that a broken copy fails on its bug, not by crashing. Work out expected values by hand, not from the reference |
| 17 | Can the local model (Qwen 3.5 9B, on a laptop) build a backend in one go? | Qwen with thinking off · Qwen with thinking on · (Opus, Haiku from row 11) | Same baseline: 15 tasks, request only. Runs on llama.cpp on an Apple M3 (`MODELS=qwen3.5-9b-local` in `eval/experiments/baseline.py`). A build is mapped by Opus only if it starts | Thinking off: **2/15 builds start, 2/192 tests (1%)**, 43 min. Thinking on: **2/15 start, 2/192 tests (1%)**, 88 min. Why builds crash: mostly database setup mistakes (in the thinking-on run, 9 of 15 tables had no primary key, the id column every table needs), also syntax errors, an example address `sqlite:////absolute/path/to/file.db` copied as-is, an import that does not exist. One build scored 1 once and 2 on three repeats (cause not found) | A 9B model cannot one-shot a backend. Thinking costs twice the time for nothing. The mistakes come with clear error messages and are fixed by one working example, so the local model is the best test of the agent's fix-and-retry loop (Stage 3) and of the recipe knowledge base (S2.4) |

## 4. What we chose, and why

- Scored runs always use Docker mode, never subprocess (row 1).
- The harness may run tasks side by side; each server is started and stopped within the same program (row 3).
- A backend that fails to start is recorded as failed, with the tool's error message (row 4).
- The harness cleans up leftover `w2-…` containers and networks when it starts (row 5).
- The benchmark: 15 tasks, 192 hidden tests, all checked by `validate.py` (row 7).
- Opus writes every name map (row 10, decision 0032).
- The builder sees only the request and the client's answers, never the operations list (row 11, decision 0033).
- After any change to the tests or the translation: re-run `validate.py`, then re-score saved builds (row 12, decision 0034).
- The numbers to beat (no agent, request only): **Opus 89%, Haiku 79%** of hidden tests.

## 5. What breaks, and the limits

- **Killed programs leave containers behind** (row 5). Fix: the cleanup command in `knowledge/environment.md`.
- **Notes for Bernard from checking his handoff** (nothing blocking):
  - When the sandbox image is missing, `start_server` says "Server crashed while starting" ahead of "No such image". That sounds like the app is broken when really the image was never built.
  - The same Docker problem is worded differently by the two tools: only `start_server` starts with "The sandbox could not start:".
  - `path_guard.py` reports 2 Windows-only attacks as "let through" when run on a Mac, though they are harmless there (row 6). It could mark which attacks apply to which system.
  - If teammates' laptops differ, a Mac can create files like `..\secret.txt` that are awkward to open on Windows. Refusing backslashes in file names on every system would keep projects identical everywhere.
- **The translation can still miss a valid design** we have not seen yet. If a build fails, read the failing test before blaming the build: in the first round, most failures we read were the tool's fault, not the build's (row 12).
- **An LLM judge is not stable on borderline tests** (row 9). Use it to find suspects only.
- **One build per task and model.** Each number comes from a single build, so a lucky or unlucky build moves a task's score a lot. Repeat runs are for the harness (S2.3).
- **Running a test script from outside the repo fails** with `No module named 'runtime'`. Run scripts from the repo root, as Bernard's example says.

## 6. How to run it, and how the next person uses it

*(Filled in at the handoff, S2.5.)*

## 7. Viva questions you should be able to answer

| Question | Answer |
|---|---|
| How do you know a generated backend works? | It is started in the sandbox and the task's hidden tests, which the agent never saw, are run against it. The score is how many pass |
| What if a generated backend does not even start? | `start_server` returns `ok=false` with the real error within about 1.5 s; the harness records the task as failed with that reason (row 4) |
| How do you know the hidden tests are right? | Each task has a correct backend that passes all of them, and 5 deliberately broken copies that each fail at least one. 75 of 75 were caught (row 7) |
| Why don't the tests use the backend's real web addresses? | Different valid builds name things differently. Tests call operations by name and a map, written by Opus after the build, translates (rows 10, 12) |
| What is the baseline, and what did it score? | One LLM call writes the whole backend, no agent. From the request alone: Opus 89%, Haiku 79% of hidden tests (row 11) |
| Why not give the agent the list of operations? | It gives away the tests: with it every model scores about 100% (row 11) |
| Did you try a local model? | Yes, Qwen 3.5 9B on a laptop. In one go it passed only 1% of tests: 13 of 15 builds crashed, mostly from database setup mistakes. Thinking on made it twice as slow and no better (row 17) |
| What was the hardest part? | Making the measurement fair. 7 flaws in our own translation tool failed correct builds, and fixing them reversed a conclusion (row 12) |
| Why not run the evaluation in subprocess mode, which is faster? | It does not isolate anything: generated code could read and write files outside the project or use the internet (Bernard's row 11). Every scored run uses Docker |

## 8. Glossary

- **Benchmark**: a fixed set of test tasks, used to measure every version of the system the same way.
- **Harness**: the program that runs the benchmark: builds or starts each backend, runs the hidden tests, records the scores.
- **Hidden tests**: tests the agent never sees, so it cannot write code just to pass them.
- **Fresh clone**: a brand-new copy of the repo from GitHub, to check that the instructions alone are enough.
- **Container / image**: see Bernard's glossary (`learnings/W2-runtime-tools-and-safety.md`).
- **Mutant**: a deliberately broken copy of a correct backend, with one realistic bug. Good tests must catch it.
- **Name map (`ops.json`)**: says where each operation lives in one backend and what its fields are called there.
- **Baseline**: the simplest possible approach (one LLM call, no agent), measured so a better approach has something to beat.
- **LLM judge**: an LLM asked to grade something, here whether each test only checks what the client asked.
- **`kill -9`**: stopping a program instantly, with no chance to clean up after itself.

# W4 — Evaluation and knowledge base: learnings

Owner: Joseph

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

W4 answers one question: **how good is the platform, in numbers?** It has three pieces:
- **A benchmark:** 15 requests written the way a non-developer would write them, each with hidden tests the agent never sees.
- **A harness:** the program that starts each generated backend in Bernard's sandbox and scores it with those hidden tests.
- **A small knowledge base:** recipes the agent can search, which is the retrieval part of RAG.

*(Covers Stage 2: S2.1, checking Bernard's handoff; S2.2, the benchmark; S2.3, the harness; S2.4, the recipe search and whether recipes help a build. Stage 5 adds the full-system results.)*

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

**S2.3: the harness, one command that scores any backend.**

```
uv run python -m eval.harness all --references            # check: the 21 correct backends, all must be 100%
uv run python -m eval.harness church_signup path/to/build  # one backend (a folder with app.py, and ops.json if written)
uv run python -m eval.harness all path/to/builds           # one per task: path/to/builds/<task>/app.py
```

What it does, in order:
1. Checks Docker is reachable (if not, it stops and says so) and removes sandbox containers left by a killed run.
2. For each backend: if there is no name map (`ops.json`), Opus writes one (about $0.02) and it is saved, so it is paid for once.
3. Starts the backend in the sandbox, runs the task's hidden tests, stops it. 4 backends side by side.
4. Prints one line per backend and the total, and saves everything to `eval/results/harness/<run name>.json`.

**S2.4: the recipe knowledge base (the "retrieval" in RAG).**

1. **Recipes** (`kb/recipes/`, 18 files): each is one technique for our exact stack, in plain words plus working code and a check. For example "a database table with an id", "no double booking", "money in pesewas". They use made-up topics (rooms, shirts, workshops), never the benchmark's (decision 0036). `kb/check_recipes.py` runs every recipe inside the sandbox image: 18/18 work.
2. **Search**: `search_docs("how do I stop two bookings at the same time?")` returns the 3 most relevant recipes. It turns the question and every recipe into lists of numbers that capture meaning ("embeddings", from the small model all-MiniLM-L6-v2) and picks the recipes whose numbers are closest (decision 0037).

```
uv run --extra kb python -m kb.search "could not assemble any primary key columns"
```

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
| 18 | How many backends should the harness run side by side? | 1 · 2 · 4 · 8 · 16 | All 21 correct backends, on an 8-core Apple M3 | 1: **51 s**. 2: 24 s. 4: **13 s**. 8: 11 s. 16: no faster. Every run 272/272 | **4** (the default, `--workers`): almost all the gain; more adds little and loads the laptop |
| 19 | Does a score change between runs, or under load? | Same backends scored 3 times at 8 side by side, and twice at 16 | 21 correct backends | **105 of 105** runs scored 100%. Nothing left running afterwards | Scores are stable. One run per backend is enough for the correct backends; generated builds may still vary (row 17 saw one) |
| 20 | Does the harness cope with bad backends? | 15 deliberately bad cases (`eval/experiments/harness_failures.py`, free) | Each scored by the harness on the church task | No `app.py`, empty file, crash, no `app`: **0/10 with the real error**, in under 2 s. Hangs while starting: 0/10 after the 20 s start limit. Too much memory (1 GB, limit 512 MB): 0/10, but **the error says nothing** (note for Bernard). Every reply takes 2 s: 10/10, in 46 s. A 52 MB reply: handled. One endpoint never answers: 5/10 (each call gives up after 10 s). Broken `ops.json`: 0/10 with the reason. Tries the internet and the host's files: **blocked** (no internet, `.env` and the repo not visible). A whole test run over 300 s: counted as failed instead of crashing. Docker off: stops with "Docker is not reachable". Killed mid-run: 8 containers left; the next run removed them all | All handled. Three fixes came from this: Docker off used to say "removed 0" and score everything 0; a map with a missing operation now gets a warning (it scored 6/10 silently, which looks like a bad build); a hung test run used to crash the whole program. My first try of two cases tested nothing (wrong path): check that a test really triggers |
| 21 | Does the harness give the same scores as the baseline? | Baseline scores · the same saved builds and maps through the harness | 66 saved Claude builds; plus one build copied without its map | **66/66 identical**. Without a map: Opus wrote one ($0.024), 13/13, and the second run reused it (free, 2 s instead of 12 s) | One tool, one answer. The harness is what everyone uses from now on |
| 22 | Do the recipes actually work? | Recipe code as written · after fixing | `kb/check_recipes.py`: each recipe's code and its check, run together in the sandbox image | First try **17/18**: sqlmodel's `Field` refuses `pattern` (only pydantic's accepts it). Fixed and written into the recipe: **18/18** | Never trust an example you have not run. That mistake is now itself in the recipe, because a build would make it too |
| 23 | Where do test questions come from, so the comparison is fair? | Write them all myself · Haiku writes them from the client requests (never seeing the recipes) · real crash messages · hand-made hard cases | 111 questions, each labelled with the recipe(s) that answer it, or none | 60 from Haiku ($0.002), 14 real Qwen crash lines, 16 rewordings with no shared words, 6 Ghanaian, 8 typos or one word, 10 with no answer, 1 long | Mix sources. Questions written by the same person as the recipes share their words, which flatters keyword search. Haiku's questions are what an agent really asks: technical ("foreign key", "409", "unique constraint") |
| 24 | Which search finds the right recipe? | None (random) · BM25 (keyword; 3 settings) · dense MiniLM, bge-small (with and without its query prefix), bge-base · hybrid (BM25 + dense) | Same 111 questions; right recipe first (hit@1), in the top 3 (hit@3); time per search | Top 3: random 17%, **BM25 74%**, bge-small 89%, bge-base 89%, **MiniLM 95%**, hybrid 87%. First: BM25 58%, MiniLM 68%, **hybrid 72%**. BM25 is best on crash messages and Ghanaian words, dense on rewordings and agent questions. bge-small needs its prefix (63%→68% first). Recipe text without code: no better | **Dense MiniLM, top 3** (decision 0037): the agent reads 3 recipes, and there it is clearly best. The smallest model won: bigger is not always better. The instructor expected dense; we measured it instead of assuming |
| 25 | Can search say "no recipe fits"? | A cutoff on the best score, chosen on the same questions | 10 no-answer questions among the 111 | Best cutoff is right **66%** of the time, against 62% for always answering, for every method | No. The agent always gets 3 recipes and must judge whether they apply |
| 26 | What breaks the search? | Empty, spaces, symbols, emoji, one letter, Twi, Twi+English, Pidgin, French, SQL-injection text, prompt-injection text, 10,000 words, numbers only, unknown method, library not installed | Each run through dense and BM25 | Empty, spaces, symbols, emoji: **nothing returned** (right). 10,000 words: 175 ms. French and Pidgin: dense still finds the right recipe ("make e no allow person book the room twice" → double booking). **Twi: noise** with both. Injection text: just ranked like any words, nothing runs. Missing library: a clear message, BM25 still works. First dense search: 7 s (model loading), then about 5 ms. Accented letters were being split ("réservations" → "r", "servations"): fixed | Safe on every input. Non-English questions, especially Twi, need translating first (or a multilingual model, untested) |
| 27 | Do recipes make builds better? | No recipes · a fixed set (01 primary key, 02 database setup, 18 one-file checklist) · searched (the top recipe for each of the task's 4 planning questions, 3–4 recipes) | Qwen 3.5 9B, thinking off, the 15 plain requests, one run each; Opus maps only builds that start ($0.39 in all) | Builds that start: none **2/15**, fixed **9/15**, searched **7/15**. Tests passed: none **2/192 (1%)**, fixed **35/192 (18%)**, searched **19/192 (10%)**. The "no primary key" crash: 9 builds with no recipes, 0 with fixed, 1 with searched. Searched recipes were about the topic (bookings, dates, money) and never picked the setup recipes 02 or 18. New crashes with recipes were copied code with a missing import (`StaticPool`, `contextmanager`) | **Recipes help a lot: 9 times more tests pass.** The basics (a fixed set) helped more than topic search. One run per arm with a small, noisy model, so fixed vs searched (35 vs 19) may be partly luck; none vs any recipes is not. Suggestion for Alice: always give the setup recipes, and use search for the topic ones |

## 4. What we chose, and why

- Scored runs always use Docker mode, never subprocess (row 1).
- The harness may run tasks side by side; each server is started and stopped within the same program (row 3).
- A backend that fails to start is recorded as failed, with the tool's error message (row 4).
- The harness cleans up leftover `w2-…` containers and networks when it starts (row 5).
- The benchmark: 15 tasks, 192 hidden tests, all checked by `validate.py` (row 7).
- Opus writes every name map (row 10, decision 0032).
- The builder sees only the request and the client's answers, never the operations list (row 11, decision 0033).
- After any change to the tests or the translation: re-run `validate.py`, then re-score saved builds (row 12, decision 0034).
- Score every backend with `eval.harness`, 4 side by side (rows 18–21, decision 0035).
- Recipes: 18, all run and checked; never on benchmark topics (decision 0036).
- `search_docs` uses dense search (all-MiniLM-L6-v2) and returns 3 recipes (decision 0037).
- The numbers to beat (no agent, request only): **Opus 89%, Haiku 79%** of hidden tests.

## 5. What breaks, and the limits

- **Killed programs leave containers behind** (row 5). Fix: the cleanup command in `knowledge/environment.md`.
- **Notes for Bernard from checking his handoff** (nothing blocking):
  - When the sandbox image is missing, `start_server` says "Server crashed while starting" ahead of "No such image". That sounds like the app is broken when really the image was never built.
  - The same Docker problem is worded differently by the two tools: only `start_server` starts with "The sandbox could not start:".
  - `path_guard.py` reports 2 Windows-only attacks as "let through" when run on a Mac, though they are harmless there (row 6). It could mark which attacks apply to which system.
  - When a backend is killed for using too much memory, `start_server` says "Server crashed while starting:" with nothing after it. Saying "killed: over the 512 MB memory limit" would save a lot of guessing (row 20).
  - If teammates' laptops differ, a Mac can create files like `..\secret.txt` that are awkward to open on Windows. Refusing backslashes in file names on every system would keep projects identical everywhere.
- **The translation can still miss a valid design** we have not seen yet. If a build fails, read the failing test before blaming the build: in the first round, most failures we read were the tool's fault, not the build's (row 12).
- **An LLM judge is not stable on borderline tests** (row 9). Use it to find suspects only.
- **The harness scores each backend once** unless you ask for `--repeat N`. For the agent's results (Stage 3) use at least `--repeat 3` on generated builds: one Qwen build changed between runs (row 17).
- **Search cannot say "nothing fits"** (row 25), and Twi questions return noise (row 26).
- **Recipes were tried in one build per task, with Qwen only** (row 27). None vs recipes is a big gap; fixed vs searched may be luck. Recipes did not stop a small model leaving out imports when it copied code. Opus and Haiku were not tried with recipes.
- **One mutant once failed an extra test** (in the first `validate.py` run in a fresh clone, `missing_event_200` also failed the "no name" test, which it should pass). It was still caught, and 3 more runs matched the saved result. Most likely a slow first request in a newly set-up laptop; if it happens often, look at the 10 s request limit in `conftest.py`.
- **The search comparison used 111 questions labelled by one person.** Differences of a few points are a few questions; only big gaps (95% vs 74%) mean something.
- **One build per task and model.** Each number comes from a single build, so a lucky or unlucky build moves a task's score a lot. Repeat runs are for the harness (S2.3).
- **Running a test script from outside the repo fails** with `No module named 'runtime'`. Run scripts from the repo root, as Bernard's example says.

## 6. How to run it, and how the next person uses it

**Set up once** (after the steps in `knowledge/environment.md`; run everything from the repo root):

```
docker build -t w2-sandbox runtime/sandbox      # Bernard's sandbox image, if you have not built it (1-2 minutes)
uv run python benchmark/validate.py church_signup
# expect: ✅ church_signup: 10 tests | reference ✅ | mutants killed 5/5   (it rewrites benchmark/validation.json: commit that only if you changed a task)
uv run python -m eval.harness all --references
# expect: 21 lines, each 100%, then the total; about 15 s. Free (every reference has its ops.json)
uv run --extra kb python -m kb.search "two people booked the same room"
# expect: 15 ... No double booking: one slot, one booking   first. The first run downloads a 90 MB model
```

**What you get, and how to use it:**

| You want to | Use | Example |
|---|---|---|
| The 15 client requests | `bench.task_names()`, `bench.load(name)` | `bench.load("church_signup")["request"]` is the text the agent may see |
| Score a build | `eval.harness` | Put each build at `builds/<task>/app.py`, then `uv run --env-file .env --with anthropic python -m eval.harness all builds --repeat 3 --name agent_v1` |
| Recipes for the agent | `search_docs(question, k=3)` | `from kb.search import search_docs`, then `search_docs("how do I refuse a booking when the room is full?")` returns a list of `{"id", "title", "score", "text"}` |
| Call Claude or Qwen | `eval.llm.ask(model, system, user, schema=...)` | Returns `(text, info)`; `info["cost_usd"]` is what the call cost |
| The numbers to beat | `eval/results/baseline_v2.json` | One LLM call, request only: **Opus 89%, Haiku 79%** of the 192 hidden tests |

The harness writes `eval/results/harness/<name>.json`, one row per build and repeat: `task`, `passed`, `total`, `started`, `failing` (the names of failed tests), `error` and `map_cost_usd`.

**Must not do:**
- **Never show the agent `operations.json`, `hidden_tests/`, `reference/` or `mutants/`.** It may see only `request.md`, plus `answers.json` / `client_brief.md` when it asks the client questions. Showing the operations list makes every model score about 100% (decision 0033).
- **Do not put benchmark topics in recipes** (decision 0036), or the search would give the tests away.
- **Do not edit `benchmark/conftest.py` or the tests without re-checking:** re-run `validate.py`, then the harness with `--references` (decision 0034).

**What surprised me:**
- Scoring a build with no `ops.json` calls Opus once to write the name map (about $0.02). That needs `--env-file .env --with anthropic`. The map is saved next to `app.py`, so it is paid for once.
- If a build fails, read the failing test before blaming the build. In the first round, most failures were our tool's fault.
- With `--repeat`, the first repeat runs alone, so a missing map is written once and the other repeats reuse it. Before the fresh-clone test it was written once per repeat, all side by side ($0.048 instead of $0.016).
- `--extra kb` is needed only for `search_docs`, because it installs PyTorch. Everything else runs without it.
- An agent build can vary from run to run, so always use `--repeat 3` for real results.
- Nothing in Stage 2 was skipped: S2.4 (Should) is done.

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
| How is a generated backend scored? | `python -m eval.harness <task> <folder>`: it maps the backend with Opus if needed, starts it in the sandbox, runs the hidden tests, saves the score. All 21 correct backends score 100% (row 21) |
| What if a generated backend is malicious? | It runs in the sandbox: in our test it could not reach the internet or see the repo or `.env`, and a 1 GB memory grab was stopped (row 20) |
| Why dense search and not BM25? | We measured both on 111 questions: the right recipe was in the top 3 for 95% with dense (MiniLM) against 74% with BM25. BM25 wins on crash messages, dense on reworded questions (row 24) |
| Is RAG worth it here? | Yes, for a small model: with recipes in the prompt Qwen passed 18% of tests instead of 1% (row 27). The basic setup recipes did most of the work; searching by topic helped less. Opus and Haiku already pass most tests without help, so for them it is untested |
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
- **Workers (side by side)**: how many backends the harness scores at the same time.
- **Failure case**: a deliberately broken input, used to check that a tool reports the problem instead of crashing or giving a wrong score.
- **Recipe**: a short, working example of one technique, with a check that proves it runs.
- **BM25**: keyword search. A recipe scores higher when it contains the question's words, especially rare ones, and is not too long.
- **Dense search / embedding**: a small model turns text into a list of numbers that captures meaning, so "a spot is taken" can match "full".
- **hit@1, hit@3**: the share of questions where a right answer is first, or in the top 3.
- **RAG (retrieval-augmented generation)**: search for helpful text first (retrieval), then put it in the prompt so the model writes with it in front of it (generation). Here: find recipes, add them to the build request.
- **Hybrid search**: merging the rankings of two searches (here with reciprocal rank fusion: each recipe gets 1/(60 + its place) from each).
- **`kill -9`**: stopping a program instantly, with no chance to clean up after itself.

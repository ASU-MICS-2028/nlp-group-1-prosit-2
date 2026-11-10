# W5 — Lead, integration and writing: learnings

Owner: Eric

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

Plain words. What goes in, what comes out, why the system needs it.

## 2. How it works, step by step

A numbered walk-through using a real example from our system (e.g. the tailoring shop request). Paste real inputs and outputs. Add a diagram if it helps.

## 3. Everything we tried (experiment log)

One row per decision. Every decision compares at least 2 options. Add rows as you go, not at the end.

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | Is the safety hook on in an updated old copy? | None: a setup check | `git config core.hooksPath`, then ran `.githooks/pre-commit` by hand. File: `eval/results/walkthrough/part1/setup_checks.txt` | Empty: the hook was off. After `git config core.hooksPath .githooks` it passed (exit code 0) | Turn it on once per copy, as `learnings/00-repo-setup.md` section 5 says |
| 2 | Is the project's Python right for this Mac? | Old `.venv` (Python 3.14.7) · Mac Python 3.14.10 · Mac Python 3.12.8 | `uv sync`, then `uv run python -c "import platform; print(platform.machine())"`. File: `eval/results/walkthrough/part1/setup_checks.txt` | `uv sync` reported no problem, but Python said `x86_64`: an Intel copy left from an older Mac, running through translation. After rebuilding `.venv`: `arm64` | Python 3.12.8 on `arm64`, to match the sandbox image (`python:3.12-slim`). Not measured against 3.14 |
| 3 | Does the sandbox work with OrbStack instead of Docker Desktop? | None: a setup check | `docker run --rm hello-world`, then the setup and tests in W2 section 6. Files: `eval/results/walkthrough/part1/`, `eval/results/walkthrough/part2/runtime_tests_docker.txt` | Greeting printed, nothing left behind. Sandbox image built in 44 s (297 MB). 66 passed in 46 s | Works: the team's code calls the plain `docker` command |
| 4 | Do the expected test counts in the learnings files still hold? | None: a check | `uv run pytest runtime -q`, then the same with `SANDBOX=subprocess`. Files: `eval/results/walkthrough/part2/runtime_tests_*.txt` | 66 passed (the notes said 51); 56 passed, 10 skipped (the notes said 44 and 7). 15 tests were added in November | Fixed the expected numbers in W2 and W1 section 6; dated records left as they were |
| 5 | Do Bernard's seven free experiments still give his results on another machine? | His saved results (Windows, Oct) · a rerun (Apple M5, OrbStack, Nov 10) | Ran `path_guard`, `file_tools`, `output_limit`, `server_start`, `sandbox_compare`, `timeout_choice` and `attacks` (W2 section 6), saved the output in `eval/results/walkthrough/part2/`, compared line by line | Same conclusion in all 7. Differences: 2 Windows-style paths pass the path guard on a Mac but stay inside the project (a backslash is an ordinary letter there); each request through the door takes about 43 ms (his 10 ms); Docker blocks 15 of 16 code attacks (his 14), because of the 200 MB file cap added on Nov 9. Everything else only faster | His choices still hold. Added dated notes to W2 rows 1, 11 and 13, the safety list and a viva answer |
| 6 | Do Joseph's benchmark and marker work as his notes say, on another machine? | None: a check | `benchmark/validate.py` (all 15 tasks), `eval.harness all --references`, `pytest eval`, and the church check in `knowledge/environment.md`. Files: `eval/results/walkthrough/part3/` | All as written. 15 of 15 tasks valid in 48 s: 192 hidden tests, all 21 correct backends pass, 75 of 75 broken copies caught. Harness: 272/272 = 100.0% in 9 s, $0. Marker tests: 3 passed. Church check: 10 passed | No fix needed |
| 7 | Does Joseph's recipe search work as his notes say, on another machine? | His saved results (`kb/compare.json`, `eval/results/replicated/break_search.json`) · a rerun (Apple M5, Nov 10) | The search command in W4 section 6, `kb/check_recipes.py`, `kb.break_search` and `kb.compare`, then compared with his saved files. Files: `eval/results/walkthrough/part4/` | Recipe 15 (no double booking) first, as written. 18 of 18 recipes run in the sandbox. What breaks it: the same recipes in all 26 cases. Comparison: every hit rate identical (top 3: MiniLM 95%, bge-small 90%, BM25 74%, hybrid 87%). Only timings differ. First run took 2 min and grew `.venv` from 45 MB to 967 MB | His results hold. Added the download size and the harmless warnings to W4 section 6 |
| 8 | Do Alice's free tests still give her count? | None: a check | `uv run --with anthropic python -m pytest builder -q`, no key loaded, then counted the tests in each file. File: `eval/results/walkthrough/part5/builder_tests.txt` | 75 passed in 2.8 s (her notes said 51). `test_agent.py` still has her 51; the other 24 are in `test_session.py`, which Joseph added on Nov 6 | Fixed the expected number in W1 section 6 |
| 9 | Does one real build work as Alice's notes say? | None: a check | Her commands in W1 section 6, run by Eric: the key check, `builder build church_signup --run try1`, then `eval.harness church_signup projects/try1/church_signup --repeat 3`. Files: `eval/results/walkthrough/part5/` (`build_run.json`, `harness_try1.json`, `by_hand.txt`) | Key check: OK, $0.00016. Build: finished by itself in 3 turns, 4 tool calls, $0.1119, 42 s; its own 16 tests passed first time. Hidden tests: 10/10 three times; the name map was paid once ($0.027), then $0. About $0.14 in all. A first try stopped before calling Claude ($0): the Mac briefly could not reach PyPI | Works as written. Costs as noted: about $0.10 per build (W1 section 6), about $0.02 per map (W4 section 6) |
| 10 | Does the platform (`web/`) run as Joseph's notes say? | Plain `uvicorn web.app:app` (as written) · `python -m uvicorn web.app:app` | Free tests; a page load of the live site compared with `web/index.html`; `web/` on this Mac with no key: the page, an empty request, 5,001 characters, a real request. Files: `eval/results/walkthrough/part6/` | Free tests: 6 passed. Live site: status 200, page identical to this branch. Plain `uvicorn`: did not start (`ModuleNotFoundError: No module named 'anthropic'`). `python -m uvicorn`: page 200; empty request 400 with a plain message; too long 422; a real request got an id, then `failed` at once with a plain message, and the cause (`KeyError: 'LLM_API_KEY'`) only in the session's own log. $0 | `python -m uvicorn`: plain `uvicorn` runs the project's Python, which cannot see `anthropic` (not a project dependency, only added by `--with`). Fixed the command in W4 section 6. Why the live server starts with the plain form is not known. Nov 10, S6.2, with the team's agreement: the same fix in `web/app.py` line 3 and `web/setup_server.sh` line 46; 6 web tests passed and the server's exact command started here (`part6/uvicorn_fix.txt`). It reaches the live server only when `setup_server.sh` is next run there; not tested on the server |
| 11 | How does Michael's `ui/` relate to `web/`? | `ui/` (Michael, Nov 6) · `web/` (Joseph, decision 0049, the live site) | Read both servers; ran `ui/server.py` with no key: the page, a request, an empty request, `web/`'s address. File: `eval/results/walkthrough/part6/ui_no_key.txt` | `ui/` page 200; a request: 502 with a plain message; an empty request: accepted (200, no questions; `web/` refuses it with 400); `/api/builds`: 404. `ui/` calls the agent directly: no daily or per-person limit (each build keeps the agent's own $2 cap), no publishing, and `start_app()` is still a TODO, so a build never runs. W3 learnings is still the empty template | `web/` is the platform. `ui/` is a separate earlier page that cannot replace `web/index.html` as it is (different addresses). Open for Michael (S6.2) |
| 12 | Do the report's numbers come from the saved files? | Joseph's summary files (`tables.md`, `agent_vs_baseline.json`, `audit_numbers.json`) · my own recount from the per-test files | Reran `report_tables` and `audit_numbers` and compared with git; wrote `recompute.py`, which adds up passed tests per task from the saved files. Files: `eval/results/walkthrough/part7/` | `tables.md` and the 3 charts identical. Audit: 105 of 105 written numbers match. Recount: agent 95.8, 96.9, 95.3, average **96.0%**; one call 88.5, 84.4, 81.2, 81.8, average **84.0%**, same as `agent_vs_baseline.json`. Five of the seven come straight from per-test rows. The two fresh agent runs (96.9, 95.3) are Joseph's rescoring with the key rules (`key_rules.json`, a paid run, W4 row 43); their old-rules side matches the raw harness rows exactly (93.2%, 87.5%), and the rescoring changed only restaurant (5 to 12) and shared expenses (5 to 13). So the 96.0% average mixes one old-rules run with two rescored ones. Cost per task in Alice's run: $0.127 ($1.77 builds + $0.13 questions over 15), 36.9 s | The numbers hold. Section B uses 96.0% against 84.0%, not W1's single-run 95.8% against 89%; added a dated note to W1 section 1 |

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

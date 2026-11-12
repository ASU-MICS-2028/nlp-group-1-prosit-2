# W5 — Lead, integration and writing: learnings

Owner: Eric

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

> **Nov 12, Joseph (decision 0062):** S6.2 to S6.5 moved to Joseph so the project could finish. Rows 1 to 16 are Eric's. Joseph added row 17 and wrote sections 1, 2 and 4 to 8 from those rows. Eric still opens and closes the talk and defends this part, so he should read every line.

## 1. What this part does, in one paragraph

Four people each built one part and wrote a learnings file about it. This part checks that those parts fit together, using only what those files say: a second person, on a second laptop, follows each file's commands and compares the result with the saved one (rows 1 to 12). Then a brand-new copy of the repo runs everything (row 15), and the live site is tried with a real build (row 16). What does not fit is fixed, or goes back to its owner. Last, everything becomes the report's Section B (`docs/section-b.md`), the 10-minute deck and the demo recording. The system needs this because nobody else reads anyone's code: if a learnings file is wrong, the report and the viva are wrong.

## 2. How it works, step by step

A real example: Bernard's attack test, rerun on another machine (row 5).

1. **Read the file.** W2 section 6 says: run `attacks`; Docker should block 14 of 16 code attacks, subprocess 4.
2. **Run it exactly as written**, on a different laptop (Apple M5, OrbStack instead of Docker Desktop). Save the output: `eval/results/walkthrough/part2/attacks.txt`.
3. **Compare line by line with the saved result.** Docker blocked 15, not 14.
4. **Find why, not just the number.** The 200 MB file cap added on Nov 9 blocks one more attack. So both numbers are right for their date.
5. **Fix the words, keep the history.** A dated note goes in W2 row 13; Section B cites the Nov 10 rerun file.
6. **Then the whole thing at once.** `fresh_clone.sh` clones `main` from GitHub into an empty folder and runs only the documented commands, recording each command's real exit code (row 15). Every free part passed.
7. **Then the live site.** `browser_check.py` makes one real build through the public page in Chrome at phone width and records a video (row 16). That video is the demo recording.
8. **Then the writing.** Section B takes every number from a learnings row or a file in `eval/results/`, and says which (for example "(W4 row 44)").

## 3. Everything we tried (experiment log)

One row per decision. Every decision compares at least 2 options. Add rows as you go, not at the end.

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | Is the safety hook on in an updated old copy? | None: a setup check | `git config core.hooksPath`, then ran `.githooks/pre-commit` by hand. File: `eval/results/walkthrough/part1/setup_checks.txt` | Empty: the hook was off. After `git config core.hooksPath .githooks` it passed (exit code 0) | Turn it on once per copy, as `learnings/00-repo-setup.md` section 5 says |
| 2 | Is the project's Python right for this Mac? | Old `.venv` (Python 3.14.7) · Mac Python 3.14.10 · Mac Python 3.12.8 | `uv sync`, then `uv run python -c "import platform; print(platform.machine())"`. File: `eval/results/walkthrough/part1/setup_checks.txt` | `uv sync` reported no problem, but Python said `x86_64`: an Intel copy left from an older Mac, running through translation. After rebuilding `.venv`: `arm64` | Python 3.12.8 on `arm64`, to match the sandbox image (`python:3.12-slim`). Not measured against 3.14 |
| 3 | Does the sandbox work with OrbStack instead of Docker Desktop? | None: a setup check | `docker run --rm hello-world`, then the setup and tests in W2 section 6. Files: `eval/results/walkthrough/part1/`, `eval/results/walkthrough/part2/runtime_tests_docker.txt` | Greeting printed, nothing left behind. Sandbox image built in 44 s (297 MB). 66 passed in 46 s | Works: the team's code calls the plain `docker` command |
| 4 | Do the expected test counts in the learnings files still hold? | None: a check | `uv run pytest runtime -q`, then the same with `SANDBOX=subprocess`. Files: `eval/results/walkthrough/part2/runtime_tests_*.txt` | 66 passed (the notes said 51); 56 passed, 10 skipped (the notes said 44 and 7). 15 tests were added in November | Fixed the expected numbers in W2 and W1 section 6; dated records left as they were. Nov 11, after merging `main` (Joseph's Windows fix added 1 test): 67 passed, and 57 passed with 10 skipped; W1 and W2 updated. Files: `eval/results/walkthrough/part2/runtime_tests_after_main_*.txt` |
| 5 | Do Bernard's seven free experiments still give his results on another machine? | His saved results (Windows, Oct) · a rerun (Apple M5, OrbStack, Nov 10) | Ran `path_guard`, `file_tools`, `output_limit`, `server_start`, `sandbox_compare`, `timeout_choice` and `attacks` (W2 section 6), saved the output in `eval/results/walkthrough/part2/`, compared line by line | Same conclusion in all 7. Differences: 2 Windows-style paths pass the path guard on a Mac but stay inside the project (a backslash is an ordinary letter there); each request through the door takes about 43 ms (his 10 ms); Docker blocks 15 of 16 code attacks (his 14), because of the 200 MB file cap added on Nov 9. Everything else only faster | His choices still hold. Added dated notes to W2 rows 1, 11 and 13, the safety list and a viva answer |
| 6 | Do Joseph's benchmark and marker work as his notes say, on another machine? | None: a check | `benchmark/validate.py` (all 15 tasks), `eval.harness all --references`, `pytest eval`, and the church check in `knowledge/environment.md`. Files: `eval/results/walkthrough/part3/` | All as written. 15 of 15 tasks valid in 48 s: 192 hidden tests, all 21 correct backends pass, 75 of 75 broken copies caught. Harness: 272/272 = 100.0% in 9 s, $0. Marker tests: 3 passed. Church check: 10 passed | No fix needed |
| 7 | Does Joseph's recipe search work as his notes say, on another machine? | His saved results (`kb/compare.json`, `eval/results/replicated/break_search.json`) · a rerun (Apple M5, Nov 10) | The search command in W4 section 6, `kb/check_recipes.py`, `kb.break_search` and `kb.compare`, then compared with his saved files. Files: `eval/results/walkthrough/part4/` | Recipe 15 (no double booking) first, as written. 18 of 18 recipes run in the sandbox. What breaks it: the same recipes in all 26 cases. Comparison: every hit rate identical (top 3: MiniLM 95%, bge-small 90%, BM25 74%, hybrid 87%). Only timings differ. First run took 2 min and grew `.venv` from 45 MB to 967 MB | His results hold. Added the download size and the harmless warnings to W4 section 6 |
| 8 | Do Alice's free tests still give her count? | None: a check | `uv run --with anthropic python -m pytest builder -q`, no key loaded, then counted the tests in each file. File: `eval/results/walkthrough/part5/builder_tests.txt` | 75 passed in 2.8 s (her notes said 51). `test_agent.py` still has her 51; the other 24 are in `test_session.py`, which Joseph added on Nov 6 | Fixed the expected number in W1 section 6 |
| 9 | Does one real build work as Alice's notes say? | None: a check | Her commands in W1 section 6, run by Eric: the key check, `builder build church_signup --run try1`, then `eval.harness church_signup projects/try1/church_signup --repeat 3`. Files: `eval/results/walkthrough/part5/` (`build_run.json`, `harness_try1.json`, `by_hand.txt`) | Key check: OK, $0.00016. Build: finished by itself in 3 turns, 4 tool calls, $0.1119, 42 s; its own 16 tests passed first time. Hidden tests: 10/10 three times; the name map was paid once ($0.027), then $0. About $0.14 in all. A first try stopped before calling Claude ($0): the Mac briefly could not reach PyPI | Works as written. Costs as noted: about $0.10 per build (W1 section 6), about $0.02 per map (W4 section 6) |
| 10 | Does the platform (`web/`) run as Joseph's notes say? | Plain `uvicorn web.app:app` (as written) · `python -m uvicorn web.app:app` | Free tests; a page load of the live site compared with `web/index.html`; `web/` on this Mac with no key: the page, an empty request, 5,001 characters, a real request. Files: `eval/results/walkthrough/part6/` | Free tests: 6 passed. Live site: status 200, page identical to this branch. Plain `uvicorn`: did not start (`ModuleNotFoundError: No module named 'anthropic'`). `python -m uvicorn`: page 200; empty request 400 with a plain message; too long 422; a real request got an id, then `failed` at once with a plain message, and the cause (`KeyError: 'LLM_API_KEY'`) only in the session's own log. $0 | `python -m uvicorn`: plain `uvicorn` runs the project's Python, which cannot see `anthropic` (not a project dependency, only added by `--with`). Fixed the command in W4 section 6. Why the live server starts with the plain form is not known. Nov 10, S6.2, with the team's agreement: the same fix in `web/app.py` line 3 and `web/setup_server.sh` line 46; 6 web tests passed and the server's exact command started here (`part6/uvicorn_fix.txt`). It reaches the live server only when `setup_server.sh` is next run there; not tested on the server |
| 11 | How does Michael's `ui/` relate to `web/`? | `ui/` (Michael, Nov 6) · `web/` (Joseph, decision 0049, the live site) | Read both servers; ran `ui/server.py` with no key: the page, a request, an empty request, `web/`'s address. File: `eval/results/walkthrough/part6/ui_no_key.txt` | `ui/` page 200; a request: 502 with a plain message; an empty request: accepted (200, no questions; `web/` refuses it with 400); `/api/builds`: 404. `ui/` calls the agent directly: no daily or per-person limit (each build keeps the agent's own $2 cap), no publishing, and `start_app()` is still a TODO, so a build never runs. W3 learnings is still the empty template | `web/` is the platform. `ui/` is a separate earlier page that cannot replace `web/index.html` as it is (different addresses). Open for Michael (S6.2) |
| 12 | Do the report's numbers come from the saved files? | Joseph's summary files (`tables.md`, `agent_vs_baseline.json`, `audit_numbers.json`) · my own recount from the per-test files | Reran `report_tables` and `audit_numbers` and compared with git; wrote `recompute.py`, which adds up passed tests per task from the saved files. Files: `eval/results/walkthrough/part7/` | `tables.md` and the 3 charts identical. Audit: 105 of 105 written numbers match. Recount: agent 95.8, 96.9, 95.3, average **96.0%**; one call 88.5, 84.4, 81.2, 81.8, average **84.0%**, same as `agent_vs_baseline.json`. Five of the seven come straight from per-test rows. The two fresh agent runs (96.9, 95.3) are Joseph's rescoring with the key rules (`key_rules.json`, a paid run, W4 row 43); their old-rules side matches the raw harness rows exactly (93.2%, 87.5%), and the rescoring changed only restaurant (5 to 12) and shared expenses (5 to 13). So the 96.0% average mixes one old-rules run with two rescored ones. Cost per task in Alice's run: $0.127 ($1.77 builds + $0.13 questions over 15), 36.9 s | The numbers hold. Section B uses 96.0% against 84.0%, not W1's single-run 95.8% against 89%; added a dated note to W1 section 1 |
| 13 | How can a test build be taken down without Joseph? (S6.2) | Joseph by hand · a route through the session, data kept · the same, data deleted · a route taking any name · a new state `taken_down` | Free tests with a pretend undeploy; the new test broken on purpose 3 ways; the platform on this Mac with no key. File: `eval/results/walkthrough/part6/take_down.txt` | 82 passed (76 builder, 6 web). Each of the 3 breaks made the new test fail. No key: a made-up id gets 400 "No such build."; a build that never went live gets 400 "There is no live backend to take down." $0 | **A route through the session, data kept** (decision 0059): about 10 lines, reuses `undeploy` and the `failed` state, so the live page needs no change and a message brings it back. Limits: anyone with the link can take it offline (as with messages today); builds from before a restart still need Joseph. Not tested on the server |
| 14 | How does Michael's design get onto the live page with the least code? (S6.2) | Next.js · React and TypeScript built into one file · Michael's `ui/index.html` with its live part rewritten · Joseph's page logic in Michael's design | Compared on what the server can run (no Node, one file), the code to explain, and what is already proven. The chosen page checked free with `check_page.py`: real server and session, pretend Claude and publish fed the real bakery questions and plan, real Chrome at 390 and 1280 wide and in dark mode. Files: `eval/results/walkthrough/part6/new_page/` | Every screen worked at both widths and in dark mode (18 screenshots): no page errors, no sideways scrolling, a refresh kept the build, a message mid-build reached the builder, take-down worked. 6 web tests passed. Joseph's browser check needs no change (same button words). Page 200 lines (was 131); `ui/` (2 files) removed. $0 | **Joseph's logic in Michael's design** (decision 0060): one file, nothing to install, behaviour already proven live. Left out: Michael's recorded demo and test switches (S4.2 is still his). Not yet tried with a real build |
| 15 | Does a brand-new copy run everything, following only the README and the learnings files? (S6.1) | None: a check | `fresh_clone.sh`: a clone of `main` (`37f4ada`) from GitHub, then only the documented commands, the sandbox image built from scratch (`--no-cache`). Apple M5 with OrbStack. Files: `eval/results/walkthrough/fresh_clone/` | Image built in 84 s (297 MB). Runtime 67 passed in 48 s; 57 passed and 10 skipped without Docker. Builder and web 82 passed. Eval tests 3 passed with `python -m pytest` (plain `uv run pytest eval/tests` cannot import `eval`). Validate: church ✅, mutants 5/5. Harness 272/272, 21/21 backends. Recipe search: the right recipe first; the first run took 860 s, downloading PyTorch. Audit 105 of 105. Page check: 3 sizes, no page errors. Platform with no key: page 200, an empty request refused in plain words. `uv sync` chose Python 3.15.2, not 3.12, and everything still passed | **Runs from a fresh copy: every free part passes.** Not covered: a paid build, which needs the key (one ran on this Mac in row 9). Fixed: W4 section 6 now gives the eval tests command. Left as is: nothing pins Python 3.12 (`requires-python = ">=3.12"`), and 3.15 worked. **Rerun Nov 11 (Joseph), of this branch, with each command's real exit code** (the first log took `tail`'s): every step passed, builder and web 84 passed, the rest as above (`log.txt` now holds the rerun). A paid build through the new page is covered by the S6.4 live run (`eval/results/browser_check_2026-11-11/`) |
| 16 | Does the new page work on the public link with a real build, take-down included? (S6.4) | None: a check | `eval/experiments/browser_check.py` in real Chrome at phone width, against the live server on `main` (its page byte-identical to `web/index.html` on `main`). One real bakery build, with a message sent while it built. Files: `eval/results/browser_check_2026-11-11/` | Empty click refused in plain words. 3 questions, then the plan; a refresh kept the build. The mid-build message (orders need a pickup date) is in the finished backend's summary. Live; the whole run, take-down included, took 91 s; its docs page lists 3 operations; no sideways scrolling; no page errors. Take it offline: the taken-down screen, then the docs address and `/cakes` both answered 404. About $0.20: the page does not show the cost | **Works end to end on the public link.** Its video (3.8 MB) is the demo recording, on the deck, not in git: the commit check reads a video as text, which makes it count as over 5 MB. Still to do: the heading change in PR #17 needs one more `setup_server.sh main` after that merge |
| 17 | Does the redesigned live screen (S4.3, S4.4) work on the public link with a real build, after PR #19 was deployed? (S6.4) | None: a check | `eval/experiments/browser_check.py` in real Chrome at phone width against the live server on `main` (`991a93f`; the page byte-identical to `web/index.html`). One real bakery build. Files: `eval/results/browser_check_2026-11-12/` | Empty click refused in plain words. 3 questions, then the plan; a refresh kept the build. Live screen: "Open the try-it page" with its plain note, the address and actions folded under "For the person who builds your website or app". Docs page lists 3 operations; no sideways scrolling; no page errors. Taken offline, the docs address answered 404. About $0.20 | **Works end to end with the new wording.** Its video (4.3 MB) is the demo recording, in the shared Drive folder with the deck, not in git (row 16) |

## 4. What we chose, and why

- **Check every learnings file by running it on a second machine**, not by reading it: reading would not have found the Intel Python (row 2), the plain `uvicorn` that cannot start (row 10) or the test counts that had grown (rows 4 and 8).
- **Fix the words, keep the dated record**: a number that changed gets a dated note, not a silent edit (rows 4, 5, 7).
- **`python -m uvicorn`**, in the notes, `web/app.py` and `setup_server.sh` (row 10).
- **Take-down through the session, data kept** (row 13, decision 0059), so nobody needs Joseph to remove a test build.
- **Joseph's page logic in Michael's design**, one plain file (row 14, decision 0060).
- **A fresh clone as the final check**, with each command's real exit code (row 15).
- **Section B uses 96.0% against 84.0%** (averages over runs), not one run's 95.8% against 89% (row 12).
- **The demo recording is the live browser check's video**, kept out of git because the commit check counts a video as text over 5 MB (rows 16 and 17).

## 5. What breaks, and the limits

- **The paid parts were checked once each**, not repeated: one build on Eric's Mac (row 9), one through the live page (row 16), one on Nov 12 (row 17).
- **Nothing pins Python 3.12.** A fresh copy chose 3.15.2 and everything passed (row 15), but a future Python could break it.
- **Only Joseph can update the server** (it needs his Google Cloud access). Builds started before a server restart also need him to take them down (row 13).
- **The 96.0% average mixes one run under the old scoring rules with two rescored runs** (row 12). Section B says so.
- **The usability test has not been run** (S4.5), so Section B 4.5 has a word count, not people.
- **The demo video is not in git.** It is shared with the deck; if it is lost, `browser_check.py` makes a new one for about $0.20.
- **With more time:** run the usability test; repeat the live build a few times to see how often it fails; pin Python.

## 6. How to run it, and how the next person uses it

**Check a fresh copy** (free; about 15 minutes the first time, mostly downloading the search model):
```
bash eval/results/walkthrough/fresh_clone/fresh_clone.sh      # log in eval/results/walkthrough/fresh_clone/log.txt; every step should say exit 0
```

**Check the live site and record the demo** (one real build, about $0.20; the video needs ffmpeg once: `uv run --with playwright playwright install ffmpeg`):
```
uv run --with playwright python eval/experiments/browser_check.py eval/results/browser_check_<date>
# should print 3 questions, "survives a page refresh", "result: Your backend is live", "no sideways scroll on a phone: True",
# "taken down: 404" and "page errors: []". The .webm in that folder is the demo video
```

**Check the report's numbers** (free):
```
uv run python eval/experiments/audit_numbers.py      # 105 of 105 should match
```

**What the team gets from this part:**
- `docs/section-b.md`: Section B, identical in every report. Paste `docs/section-b-figure-1.png` where the Mermaid figure is, for Word or PDF.
- The deck: `Prosit 2 - Group 1 - Final Presentation.pptx` in the shared Drive folder (`NLP-GROUP-1/prosit 2/`). 16 slides, GitHub link on slide 1, speaker notes with timings on every slide, animated. It tells one baker's order as a visit to a seamstress, and each person presents the stop they built, in build order: Eric 2 min (slides 1 to 4: the client, the map, the architecture), Michael 1.5 (5 and 6: the page), Alice 2 (7 and 8: the agent), Bernard 1.5 (9 and 10: the sandbox), Joseph 2.5 (11 to 14: benchmark, results, ablations, live attacks), Eric 1 (15 and 16: the live build, limits, thanks). The adinkra symbols are simplified drawings, each named on its slide.
- The demo video, `demo-recording-2026-11-12.webm`, in the same Drive folder (row 17).

## 7. Viva questions you should be able to answer

| Question | Answer |
|---|---|
| How do you know the learnings files are right? | A second person ran each file's commands on a different laptop and compared with the saved results (rows 1 to 12), then a brand-new copy ran everything (row 15). Where numbers differed, we found why and added a dated note |
| Why did Docker block 15 attacks for you and 14 for Bernard? | The 200 MB file cap, added on Nov 9 after his run, blocks one more attack (row 5). Both are right for their date |
| Why `python -m uvicorn` and not `uvicorn`? | Plain `uvicorn` runs the project's own Python, which cannot see `anthropic` (it is added only by `uv run --with`), so the server did not start (row 10) |
| Where does 96.0% against 84.0% come from? | The agent's 3 runs and one call's 4 rounds over the 15 tasks, recounted from the per-test files (row 12). One agent run uses the old scoring rules, the other two the rescored ones |
| What does a fresh-clone check prove, and what not? | That someone with only the README and the learnings files can run every free part. Not a paid build: that needs the key, and was checked separately (rows 9, 16, 17) |
| Why was the first fresh-clone log not trusted? | It recorded the exit code of `tail`, not of the command, so a failing step could still say "exit 0". The rerun records each command's own code (row 15) |
| Why is the demo video not in git? | The commit check reads a video as text and counts it as over 5 MB; it is shared with the deck instead (row 16) |
| Why one HTML file for the page and not React? | The server has no Node; one file needs nothing installed or built, and every line can be explained (row 14) |
| How can a client take a build offline, and what happens to the data? | "Take it offline" on the page: the backend stops and its link answers 404, but its data stays, and a message brings it back (row 13, decision 0059) |

## 8. Glossary

- **Learnings file**: one file per workstream (`learnings/W?-*.md`) that says what was built, tried and measured, in plain words. The only thing the others read.
- **Fresh clone**: a brand-new copy of the repo from GitHub in an empty folder, with nothing left over from earlier work.
- **Exit code**: the number a command gives back when it ends; 0 means it worked.
- **OrbStack**: a Mac program that runs Docker containers, used here instead of Docker Desktop.
- **`arm64` / `x86_64`**: the two kinds of computer chip; Apple's recent Macs are `arm64`. A program built for the other kind runs slower, through translation.
- **`uvicorn`**: the program that runs our Python web server.
- **Take-down**: stopping a published backend so its link no longer answers, keeping its data (decision 0059).
- **Demo recording**: the video the live browser check makes as it clicks through one real build.
- **Number audit**: `audit_numbers.py`, which checks 105 numbers written in the learnings files against the saved result files.
- **Section B**: the part of the report that is the same for every member: how we built it and how well it works.

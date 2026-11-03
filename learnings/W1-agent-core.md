# W1 — Agent core: learnings

Owner: Alice

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

Plain words. What goes in, what comes out, why the system needs it.

The agent is the "brain" of the system. **In:** a client's request in plain words, such as "I need a sign-up sheet for church events". **Out:** a folder with a working program (`app.py`) that does what the client asked, plus a short report of what it cost. Claude does the thinking, but it never touches the computer itself. It asks for actions ("write this file", "run the tests"), our code does them in Bernard's sandbox and tells Claude what happened, and this repeats until Claude says it is finished.

## 2. How it works, step by step

The code is two files: `builder/__main__.py` (the command you type) and `builder/agent.py` (the loop).

**The idea: a phone call with a builder who cannot see your computer.**
1. We tell Claude the job: the client's request, plus fixed instructions (the *system prompt*): "write one file, `app.py`, with FastAPI; write tests; run them; fix `app.py` until they pass; add nothing the client did not ask for".
2. We also give Claude a **menu of 8 tools**, Bernard's tools: write, read and edit a file, list files, run the tests, start the server, send it a request, stop it.
3. Claude replies, either with a request for tools or with "I'm finished".
4. If it asked for tools, our code runs each one **in the project folder that our code chose** (Claude never picks the folder, so it cannot write anywhere else), then sends back what happened. If the tool failed, the result is marked as an error.
5. Repeat from step 3, at most 40 times, so it can never loop forever.
6. At the end, always stop the server, then save a report (`build.json`): why it stopped, the tools used, the cost and the time.

This loop is called **ReAct** (reason, then act, then look at the result). The team chose to write it by hand rather than use a library (decision 0003), so every line can be explained.

**Safety nets in the loop:**
- Claude asks for a tool that is not on the menu: it is told "Unknown tool" instead of the program crashing.
- Claude fills a tool in wrongly: it is told "Bad arguments" and can try again.
- The agent only ever reads `benchmark/<task>/request.md`, never the hidden tests (decision 0033).

**Money savers:** every turn, Claude re-reads the whole conversation. *Prompt caching* makes the re-read part cost 10% of the normal price.

**Real example (church sign-up, Nov 1):**
```
uv run --env-file .env --with anthropic python -m builder build church_signup --run s32_try1
```
Claude asked for 3 tools in its first reply (write `app.py`, write `tests/test_app.py`, run the tests). The tests passed, so its second reply was "finished". It took 25 seconds and cost $0.08. Joseph's harness then gave the program **10/10** hidden tests, 3 times out of 3.

**The number to beat:** Joseph's baseline (one Claude call, no tools, no testing) already scores **89%** with Opus. It fails mostly on `momo_wallet` (3/13), `school_grades_gpa` (2/12, vague) and `shop_price_list` (11/13, vague). The agent is only worth it if it beats 89%.

## 3. Everything we tried (experiment log)

One row per decision. Every decision compares at least 2 options. Add rows as you go, not at the end.

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | e.g. How many repair attempts before giving up? | 0, 1, 3, 5 | All 15 benchmark requests, 2 runs each | pass rate 41% / 58% / 71% / 72%; cost 1x / 1.4x / 2.1x / 3.0x | 3: almost all the gain of 5 at 2/3 of the cost |

## 4. What we chose, and why

The final design in a few bullets, each pointing to a row in the log.

## 5. What breaks, and the limits

Failure cases you saw, with examples. What you would do with more time.

**Starting check (S3.1, Nov 2, macOS).** Before building anything, Bernard's and Joseph's parts were run exactly as their learnings files say:

| Check | Expected | Got |
|---|---|---|
| `uv run pytest runtime -q` (Bernard's tools and sandbox) | 51 passed | 51 passed in 45 s |
| `benchmark/validate.py church_signup` | 10 tests, 5/5 mutants | same |
| `eval.harness all --references` | 21 backends at 100% | 272/272 tests, 21/21, 16 s, $0 |
| `kb.search "two people booked the same room"` | recipe 15 first | recipe 15 first (score 0.34) |
| One tiny Opus call through `eval.llm.ask` (is the key OK?) | a reply | `'OK'`, cost $0.00016 |

- **Do not run the harness while Bernard's tests are running.** The first time, both ran at once and 3 of the 51 tests failed (the ones that check stuck tests and the sandbox network). The harness begins by deleting "leftover" sandbox containers, and it deleted containers the tests were still using. Run alone, all 51 passed. Not tested yet, but the same is likely if two harness runs, or an agent build and a harness run, happen at the same time on one laptop.

## 6. How to run it, and how the next person uses it

Exact commands and what you should see. Then the handoff: what the next person in the relay gets from you (functions, files, commands, formats), with an example they can copy. They will build only on what is written here.

### First: check the parts the agent stands on

The agent uses Bernard's tools and is scored by Joseph's harness, so check both work before running it. Open Docker Desktop and wait until it says it is running. Then, in a terminal in the repo folder, run these **one at a time** (see section 5 for why):

| # | Command | What it checks | You should see |
|---|---|---|---|
| 1 | `uv run pytest runtime -q` | Bernard's 51 checks on the tools and the sandbox (about 1 minute) | `51 passed` |
| 2 | `uv run python benchmark/validate.py church_signup`, then `git checkout benchmark/validation.json` to undo the file it rewrites | The church task's hidden tests pass on the right answer and catch 5 broken ones | `✅ church_signup: 10 tests \| reference ✅ \| mutants killed 5/5` |
| 3 | `uv run python -m eval.harness all --references` | The harness gives Joseph's correct answers full marks (about 15 s, free) | 21 lines at full score, then `272/272 tests = 100.0%` |
| 4 | `uv run --extra kb python -m kb.search "two people booked the same room"` | The recipe search works (the first run downloads a 90 MB model) | `15 ... No double booking: one slot, one booking` at the top |
| 5 | `uv run --env-file .env --with anthropic python -c "from eval.llm import ask; print(ask('claude-opus-5-5', 'Reply with one word.', 'Say OK.', effort='low', max_tokens=50))"` | The Claude key works (costs under 1 cent) | starts with `('OK', {` |

If something goes wrong:
- **Many Docker errors:** Docker Desktop is not running.
- **A few failures in check 1:** something else was using the sandbox at the same time. Close it and run check 1 again.

## 7. Viva questions you should be able to answer

Write the questions an examiner would ask about this part, with short answers. Everyone on the team will study these.

| Question | Answer |
|---|---|
| How did you know Bernard's and Joseph's parts worked before you built on them? | We ran their own checks before writing anything (section 5): Bernard's 51 tests passed, and Joseph's harness gave all 21 correct answers 100% (272/272 tests). |
| If the agent scores badly, how do you know the marker is not the problem? | The same marker gives the hand-written correct answers 100%, so a low score means the agent's code is wrong. |

## 8. Glossary

Every technical word used above, in one plain sentence each.

- **Agent:** a program that lets an AI (here Claude) do a job by itself, step by step, using tools, until the job is done.
- **API key:** a secret password that lets our program use Claude. It is kept in `.env` and never shared.
- **Backend:** the invisible part of an app that stores the data and answers requests like "list all orders".
- **Container:** one small, sealed computer inside Docker. The sandbox starts one, runs code in it, then throws it away.
- **Docker:** a program that runs code inside sealed boxes (containers), so it cannot touch the rest of the laptop.
- **Harness:** Joseph's marker. It starts a built backend, runs the hidden tests on it, and gives a score like 10/10.
- **Hidden tests:** secret checks for each benchmark task. The agent never sees them, so it cannot cheat.
- **Mutant:** a deliberately broken copy of a correct answer. Good tests must fail it ("kill" it).
- **pytest:** the Python program that runs tests and says how many passed.
- **Recipe:** a short tip in Joseph's knowledge base, such as how to stop double bookings. The agent can search for them.
- **Reference:** the correct answer for a benchmark task, written by hand. It should score 100%.
- **Sandbox:** Bernard's safe box (built on Docker) where generated code is run.

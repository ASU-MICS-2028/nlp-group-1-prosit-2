# W1 — Agent core: learnings

Owner: Alice

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

Plain words. What goes in, what comes out, why the system needs it.

## 2. How it works, step by step

A numbered walk-through using a real example from our system (e.g. the tailoring shop request). Paste real inputs and outputs. Add a diagram if it helps.

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

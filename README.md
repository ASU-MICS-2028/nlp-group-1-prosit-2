# Prosit 2: A Non-Developer Friendly API Builder

ICS554 Natural Language Processing, Ashesi University. NLP Group 1: Michael Boadi, Joseph Etse, Alice Kara-Acquah, Bernard Marfo, Eric Sunu.

A non-developer describes a backend in plain words ("I run a tailoring shop, I need to track customers, measurements and orders"). A coding agent turns that into a plan they approve, then into a tested, running API with an OpenAPI contract that any frontend can use.

**New here (person or coding assistant)? Read [`knowledge/README.md`](knowledge/README.md) first.** It has everything about the assignment, the course, the team and the setup, so you do not need anyone's personal notes or workspace.

## The two rules (read these first)

**1. Explain everything as blatantly and simply as possible.** Nobody else is going to touch your part. The rest of the team will rely only on what you write in `learnings/` to write the report, give the presentation and answer viva questions. Write it so someone who has never seen your code can explain it out loud. No unexplained jargon, show real examples, give real numbers. If it is not in your learnings file, the team does not know it.

**2. Test out any and every possible scenario.** Never build just one version and move on. At every step, try the alternatives, measure them, and keep the one that works best. Log every comparison in your learnings file: what you compared, how you tested it, the numbers, and why the winner won. "We picked X" is not acceptable without "because X beat Y and Z by this much on this test".

<!-- STATUS:START -->
## Status

Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand. **1 of 27 tasks done.**

**In progress**

None.

**Ready to start**

| Task | Who | Target |
|---|---|---|
| P0.1 Choose the LLM provider and get an API key into everyone's `.env` | W5 (TBD) | Oct 20 |
| P0.2 Assign an owner to each workstream | W5 (TBD) | Oct 20 |
| P0.3 Ask the instructor for the presentation, report and viva dates, and what the rubric's "Section C" is | W5 (TBD) | Oct 20 |
| P0.5 Docker installed and running on every laptop | Everyone | Oct 20 |
| P1.6 Recipe knowledge base and retrieval, first version | W4 (TBD) | Oct 21 |
| P4.5 Section A, written individually in your own words | Everyone | Oct 23 |

**Waiting on other tasks**

| Task | Who | Target | Waiting on |
|---|---|---|---|
| P0.4 Agree the 5 contracts in `docs/CONTRACTS.md` | Everyone | Oct 20 | P0.2 |
| P1.1 Write 3 benchmark tasks each (easy, medium, hard), each with hidden tests and a reference backend that passes them | Everyone | Oct 21 | P0.4 |
| P1.2 Tools and sandbox: files, run tests, start server, HTTP request, inside Docker (subprocess fallback) | W2 (TBD) | Oct 21 | P0.4, P0.5 |
| P1.3 Single-agent ReAct loop that builds `church_signup` from the CLI | W1 (TBD) | Oct 21 | P0.1, P0.4, P1.2 |
| P1.4 Eval harness: build each task, run its hidden tests, write a results table | W4 (TBD) | Oct 21 | P0.4 |
| P1.5 UI shell working against fake events | W3 (TBD) | Oct 21 | P0.4 |
| P2.1 Planner / Builder / Tester split, with the test-and-repair loop | W1 (TBD) | Oct 22 | P1.3 |
| P2.2 Spec-first plan and the user's approval step | W1 (TBD) | Oct 22 | P1.3 |
| P2.3 Wire retrieval (`search_docs`) into the agent | W4 (TBD) | Oct 22 | P1.3, P1.6 |
| P2.4 UI wired to the real agent: describe → approve → try it → download | W3 (TBD) | Oct 22 | P1.5, P2.2 |
| P2.5 Guardrails and the 5 attack tests | W2 (TBD) | Oct 22 | P1.2 |
| P2.6 MCP server exposing the tools (only if time allows) | W2 (TBD) | Oct 22 | P1.2 |
| P2.7 Feature freeze: `main` runs end to end | W5 (TBD) | Oct 22 | P2.1, P2.2, P2.4 |
| P3.1 Full benchmark and the 4 ablations (no repair, single agent, no retrieval, no spec-first) | W4 (TBD) | Oct 22 | P1.1, P1.4, P2.1, P2.2, P2.3 |
| P3.2 Usability test with 4–5 non-developers | W3 (TBD) | Oct 22 | P2.4 |
| P4.1 Learnings files complete: explanation, full experiment log, viva Q&A, glossary | Everyone | Oct 23 | P3.1, P3.2 |
| P4.2 Section B draft (identical in every report) | W5 (TBD) | Oct 23 | P3.1, P3.2, P4.1 |
| P4.3 Slides and a recorded backup demo | W5 (TBD) | Oct 23 | P2.7, P3.1 |
| P4.4 Viva walkthrough: each owner teaches their part to the others | Everyone | Oct 23 | P4.1 |
| P4.6 Two timed rehearsals, then submit report and slides on Canvas | Everyone | Oct 23 | P4.2, P4.3, P4.4, P4.5 |

<!-- STATUS:END -->

The full task list, in order, with who owns what and what blocks what: [`docs/PLAN.md`](docs/PLAN.md). When you start or finish a task, update it there and run `python3 scripts/update_status.py`.

## Where things go

| Folder | What goes in it | Who writes |
|---|---|---|
| [`docs/`](docs/README.md) | Documentation and decisions: the plan, the decision log, the interfaces between parts, summarized meeting notes | Everyone; one line in the decision log for every decision |
| [`learnings/`](learnings/README.md) | What each person learned and found, simplified so nobody has to redo it to understand it | Each workstream owner, daily |
| [`knowledge/`](knowledge/README.md) | Everything people and coding assistants need to know about the project: the assignment, course, team, setup, lecture summaries | Anyone who knows something the others don't |
| `benchmark/` | The 15 plain-language requests and their hidden tests ([format](benchmark/README.md)) | Everyone writes 3; W4 owns |
| `builder/` | Agent core: ReAct loop, Planner / Builder / Tester, orchestrator, memory, CLI | W1 |
| `runtime/` | Tools, Docker sandbox, test runner, server launcher, MCP server | W2 |
| `ui/` | The web page | W3 |
| `eval/`, `kb/` | Test harness, ablation runs and results; the recipe knowledge base for RAG | W4 |
| `projects/` | Backends the agent generates (git-ignored) | — |

Code folders are created by their owners when they start. Nothing in them is pre-written.

**Transcripts** (lectures, meetings, calls) are never committed raw. Summarize first: lecture summaries go in `knowledge/lectures/`, meeting summaries in `docs/meetings/`. See [`knowledge/README.md`](knowledge/README.md#adding-to-the-repo).

**This repo is public.** No API keys, student IDs, phone numbers or personal details.

## Running

```
uv sync                         # installs Python deps from pyproject.toml
cp .env.example .env            # then add the LLM API key (never commit .env)
uv run pytest benchmark         # hidden tests; needs a running backend, see benchmark/README.md
```

Docker must be installed and running for the sandbox. Full setup: [`knowledge/environment.md`](knowledge/environment.md).

## Working together

- Branch per workstream (`w1-agent`, `w2-runtime`, ...), merge to `main` through a pull request once it runs.
- Changing an interface in `docs/CONTRACTS.md`? Add a line to `docs/DECISIONS.md` and tell the group chat the same day.
- Coding assistants: see [`AGENTS.md`](AGENTS.md).
- The GitHub link goes on page 1 of every report and on the first slide.

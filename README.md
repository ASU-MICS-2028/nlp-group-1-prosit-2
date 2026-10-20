# Prosit 2: A Non-Developer Friendly API Builder

ICS554 Natural Language Processing, Ashesi University. NLP Group 1: Michael Boadi, Joseph Etse, Alice Kara-Acquah, Bernard Marfo, Eric Sunu.

A non-developer describes a backend in plain words ("I run a tailoring shop, I need to track customers, measurements and orders"). A coding agent turns that into a plan they approve, then into a tested, running API with an OpenAPI contract that any frontend can use.

**New here (person or coding assistant)? Read [`knowledge/README.md`](knowledge/README.md) first.** It has everything about the assignment, the course, the team and the setup, so you do not need anyone's personal notes or workspace.

## The two rules (read these first)

**1. Explain everything as blatantly and simply as possible.** Nobody else is going to touch your part. The rest of the team will rely only on what you write in `learnings/` to write the report, give the presentation and answer viva questions. Write it so someone who has never seen your code can explain it out loud. No unexplained jargon, show real examples, give real numbers. If it is not in your learnings file, the team does not know it.

**2. Test out any and every possible scenario.** Never build just one version and move on. At every step, try the alternatives, measure them, and keep the one that works best. Log every comparison in your learnings file: what you compared, how you tested it, the numbers, and why the winner won. "We picked X" is not acceptable without "because X beat Y and Z by this much on this test".

<!-- STATUS:START -->
## Status

Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand. **1 of 33 tasks done.** Current stage: **Stage 0: Decide and set up (Tue Oct 20)**.

| Who | In progress | Ready to start | Waiting (and on what) |
|---|---|---|---|
| W1 (TBD) | — | — | S1.3 Single agent, CLI ← S0.2, S0.5, S1.2<br>S2.1 Test-and-repair loop ← S1.3<br>S2.2 Spec-first plan and approval ← S1.3<br>S2.3 Planner / Builder / Tester split ← S2.1<br>S2.8 "Change it" edit loop ← S2.2<br>S3.3 Claude vs local Qwen ← S1.3 |
| W2 (TBD) | — | — | S1.2 Tools and sandbox ← S0.5<br>S2.6 Guardrails and attack tests ← S1.2<br>S2.7 MCP server ← S1.2 |
| W3 (TBD) | — | — | S1.4 UI shell on fake events ← S0.5<br>S2.5 UI on the real agent ← S1.4, S2.2<br>S3.4 Usability test ← S2.5 |
| W4 (TBD) | — | S1.6 Recipe knowledge base | S1.5 Eval harness ← S0.5<br>S2.4 Retrieval in the agent ← S1.3, S1.6<br>S3.1 Benchmark: full vs no-repair ← S1.1, S1.5, S2.1, S2.2<br>S3.2 Other ablations ← S3.1, S2.3, S2.4 |
| W5 (TBD) | S0.2 LLM setup | S0.3 Assign owners<br>S0.4 Ask the instructor: dates, "Section C" | S1.7 Integration check ← S1.5<br>S2.9 Feature freeze ← S2.1, S2.2, S2.5<br>S4.2 Edit Section B into one text ← S4.1, S3.1<br>S4.3 Slides and backup demo ← S2.9, S3.1 |
| Everyone | — | S0.6 Docker on every laptop<br>S4.4 Section A (individual) | S0.5 Agree the 5 contracts ← S0.3<br>S1.1 3 benchmark tasks each ← S0.5<br>S3.5 Learnings complete ← S3.1<br>S3.6 Viva walkthrough ← S3.5<br>S4.1 Draft your Section B part ← S3.5<br>S4.5 Rehearse twice, submit ← S4.2, S4.3, S4.4, S3.6 |

The flow diagram, each person's full task list and who waits on whom are in [`docs/PLAN.md`](docs/PLAN.md).
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
| `models/` | The local Qwen model file (git-ignored; download it to exactly this path, see [`knowledge/environment.md`](knowledge/environment.md#the-llms)) | — |

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

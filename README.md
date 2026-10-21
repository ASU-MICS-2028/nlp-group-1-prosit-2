# Prosit 2: A Non-Developer Friendly API Builder

ICS554 Natural Language Processing, Ashesi University. NLP Group 1: Michael Boadi, Joseph Etse, Alice Kara-Acquah, Bernard Marfo, Eric Sunu.

A non-developer describes a backend in plain words ("I run a tailoring shop, I need to track customers, measurements and orders"). A coding agent turns that into a plan they approve, then into a tested, running API with an OpenAPI contract that any frontend can use.

**New here (person or coding assistant)? Read [`knowledge/README.md`](knowledge/README.md) first.** It has everything about the assignment, the course, the team and the setup, so you do not need anyone's personal notes or workspace.

## The two rules (read these first)

**1. Explain everything as blatantly and simply as possible.** Nobody else is going to touch your part. The rest of the team will rely only on what you write in `learnings/` to write the report, give the presentation and answer viva questions. Write it so someone who has never seen your code can explain it out loud. No unexplained jargon, show real examples, give real numbers. If it is not in your learnings file, the team does not know it.

**2. Test out any and every possible scenario.** Never build just one version and move on. At every step, try the alternatives, measure them, and keep the one that works best. Log every comparison in your learnings file: what you compared, how you tested it, the numbers, and why the winner won. "We picked X" is not acceptable without "because X beat Y and Z by this much on this test".

<!-- STATUS:START -->
## Status

Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand. **2 of 47 tasks done.** Current stage: **Stage 0: Set up (everyone)**.

| Who | In progress | Ready to start | Waiting (and on what) |
|---|---|---|---|
| Alice (W1) | — | — | S3.1 Read Bernard's and Joseph's learnings, run their parts ← S2.5, S0.2<br>S3.2 Single agent from the command line ← S3.1<br>S3.3 Run record and trace ← S3.2<br>S3.4 Test-and-repair loop ← S3.2<br>S3.5 Spec-first plan and approval ← S3.2<br>S3.6 Planner / Builder / Tester split ← S3.4<br>S3.7 Retrieval in the agent ← S3.2<br>S3.8 Clarifying questions ← S3.5<br>S3.9 Claude vs local Qwen ← S3.4<br>S3.10 "Change it" edit loop ← S3.5<br>S3.11 Handoff: Alice's learnings ← S3.3, S3.4, S3.5, S3.6, S3.7, S3.8 |
| Bernard (W2) | — | S1.1 The agent's tools | S1.2 Sandbox ← S1.1<br>S1.3 Safety tests ← S1.2<br>S1.4 MCP server ← S1.1<br>S1.5 Handoff: Bernard's learnings ← S1.2, S1.3 |
| Michael (W3) | — | — | S4.1 Read Alice's learnings, run a build ← S3.11<br>S4.2 UI on a recorded session ← S4.1<br>S4.3 UI on the live agent ← S4.2<br>S4.4 UI alternatives compared ← S4.3<br>S4.5 Usability test ← S4.4<br>S4.6 Handoff: Michael's learnings ← S4.3, S4.5 |
| Joseph (W4) | S0.2 LLM setup (Joseph holds the key) | — | S2.1 Read Bernard's learnings, run his tools ← S1.5<br>S2.2 15 benchmark tasks ← S2.1<br>S2.3 Eval harness ← S2.2<br>S2.4 Recipe knowledge base and search ← S2.1<br>S2.5 Handoff: Joseph's learnings, part 1 ← S2.3, S2.4<br>S5.1 Read Alice's and Michael's learnings ← S4.6<br>S5.2 Full system on all 15 tasks ← S5.1<br>S5.3 Ablations ← S5.2<br>S5.4 Model comparison ← S5.2<br>S5.5 Results tables and charts ← S5.3, S5.4<br>S5.6 Handoff: Joseph's learnings, part 2 ← S5.5 |
| Eric (W5) | S0.4 Ask the instructor: dates, "Section C" | — | S6.1 Read every learnings file, run everything ← S5.6<br>S6.2 Fix what doesn't fit together ← S6.1<br>S6.3 Section B draft ← S6.1<br>S6.4 Slides and recorded demo ← S6.2, S6.3<br>S6.5 Handoff: Eric's learnings ← S6.4 |
| Everyone | — | S0.6 Docker on every laptop<br>S7.2 Section A (individual, any time) | S7.1 Review Section B for your part ← S6.3<br>S7.3 Viva walkthrough ← S6.5<br>S7.4 Rehearse and submit ← S7.1, S7.2, S7.3, S6.4 |

The flow diagram, each person's full task list and who waits on whom are in [`docs/PLAN.md`](docs/PLAN.md).
<!-- STATUS:END -->

The full task list, in order, with who owns what and what blocks what: [`docs/PLAN.md`](docs/PLAN.md). When you start or finish a task, update it there and run `python3 scripts/update_status.py`.

## Where things go

| Folder | What goes in it | Who writes |
|---|---|---|
| [`docs/`](docs/README.md) | Documentation and decisions: the plan, the decision log, suggested interfaces, summarized meeting notes | Everyone; one line in the decision log for every decision |
| [`learnings/`](learnings/README.md) | What each person learned and found, simplified so nobody has to redo it to understand it | Each workstream owner, daily |
| [`knowledge/`](knowledge/README.md) | Everything people and coding assistants need to know about the project: the assignment, course, team, setup, lecture summaries | Anyone who knows something the others don't |
| `benchmark/` | The 15 plain-language requests and their hidden tests ([format](benchmark/README.md)) | Joseph (W4), Stage 2 |
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

- Work on a branch for your stage (`w2-tools`, `w4-benchmark`, ...) and merge to `main` through a pull request at your handoff.
- We work as a relay: one person at a time, each building on the last person's handoff ([`docs/PLAN.md`](docs/PLAN.md)). Your stage is done when your learnings file lets the next person carry on without asking you.
- Coding assistants: see [`AGENTS.md`](AGENTS.md).
- The GitHub link goes on page 1 of every report and on the first slide.

# Prosit 2: A Non-Developer Friendly API Builder

<!-- STATUS:START -->
## Now: Stage 3: Alice — agent core

**Who:** Alice (W1)

| Task | Who | Status |
|---|---|---|
| S3.1 Read Bernard's and Joseph's learnings, run their parts | Alice (W1) | 🔵 ready |
| S3.2 Single agent from the command line | Alice (W1) | ⏳ waiting (on S3.1) |
| S3.3 Run record and trace | Alice (W1) | ⏳ waiting (on S3.2) |
| S3.4 Test-and-repair loop | Alice (W1) | ⏳ waiting (on S3.2) |
| S3.5 Spec-first plan and approval | Alice (W1) | ⏳ waiting (on S3.2) |
| S3.6 Planner / Builder / Tester split | Alice (W1) | ⏳ waiting (on S3.4) |
| S3.7 Retrieval in the agent | Alice (W1) | ⏳ waiting (on S3.2) |
| S3.8 Clarifying questions | Alice (W1) | ⏳ waiting (on S3.5) |
| S3.9 Claude vs local Qwen | Alice (W1) | ⏳ waiting (on S3.4) |
| S3.10 "Change it" edit loop | Alice (W1) | ⏳ waiting (on S3.5) |
| S3.11 Handoff: Alice's learnings | Alice (W1) | ⏳ waiting (on S3.3, S3.4, S3.5, S3.6, S3.7, S3.8) |

**Next:** Stage 4: Michael — UI and usability

Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand.
<!-- STATUS:END -->

Every stage, task and blocker: [`docs/PLAN.md`](docs/PLAN.md).

ICS554 Natural Language Processing, Ashesi University. NLP Group 1: Michael Boadi, Joseph Etse, Alice Kara-Acquah, Bernard Marfo, Eric Sunu.

A non-developer describes a backend in plain words ("I run a tailoring shop, I need to track customers, measurements and orders"). A coding agent turns that into a plan they approve, then into a tested, running API with an OpenAPI contract that any frontend can use.

**New here (person or coding assistant)? Read [`knowledge/README.md`](knowledge/README.md) first.** It has everything about the assignment, the course, the team and the setup, so you do not need anyone's personal notes or workspace.

## The two rules (read these first)

**1. Explain everything as blatantly and simply as possible.** Nobody else is going to touch your part. The rest of the team will rely only on what you write in `learnings/` to write the report, give the presentation and answer viva questions. Write it so someone who has never seen your code can explain it out loud. No unexplained jargon, show real examples, give real numbers. If it is not in your learnings file, the team does not know it.

**2. Test out any and every possible scenario.** Never build just one version and move on. At every step, try the alternatives, measure them, and keep the one that works best. Log every comparison in your learnings file: what you compared, how you tested it, the numbers, and why the winner won. "We picked X" is not acceptable without "because X beat Y and Z by this much on this test".


## Where things go

| Folder | What goes in it | Who writes |
|---|---|---|
| [`docs/`](docs/README.md) | Documentation and decisions: the plan, one numbered record per decision (`docs/decisions/`), summarized meeting notes | Everyone; a new decision record for every decision |
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
git config core.hooksPath .githooks   # once: the pre-commit check that blocks keys and stale status
uv run pytest benchmark         # hidden tests; needs a running backend, see benchmark/README.md
```

Docker must be installed and running for the sandbox. Full setup: [`knowledge/environment.md`](knowledge/environment.md).

## Working together

- Work on a branch for your stage (`w2-tools`, `w4-benchmark`, ...) and merge to `main` through a pull request at your handoff.
- We work as a relay: one person at a time, each building on the last person's handoff ([`docs/PLAN.md`](docs/PLAN.md)). Your stage is done when your learnings file lets the next person carry on without asking you.
- Coding assistants: see [`AGENTS.md`](AGENTS.md).
- The GitHub link goes on page 1 of every report and on the first slide.

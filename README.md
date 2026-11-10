# Prosit 2: A Non-Developer Friendly API Builder

<!-- STATUS:START -->
## What each person does now

### Alice (W1)

Nothing left of your own: see Everyone.

### Bernard (W2)

Nothing left of your own: see Everyone.

### Michael (W3)

| Task | Status | Done when |
|---|---|---|
| S4.1 Read Alice's and Joseph's learnings, try the live platform | 🔵 ready | You built a backend through the live page, and `web/` runs on your laptop (section 6 of `learnings/W4-*.md`) |
| S4.2 UI on a recorded session | ⏳ waiting (on S4.1) | `web/index.html` can play back a saved session (describe → questions → plan → progress → try it), so you can change the page without paying for builds |
| S4.3 Better UI on the live platform | ⏳ waiting (on S4.2) | On the public address, a non-developer can describe, answer, approve, try and change a backend with nothing but the page, and understands every word on it |
| S4.4 UI alternatives compared | ⏳ waiting (on S4.3) | Ways of showing the plan, asking questions, showing progress and wording errors, compared |
| S4.5 Usability test | ⏳ waiting (on S4.4) | 4–5 non-developers: completion, time, SUS score, quotes |
| S4.6 Handoff: Michael's learnings | ⏳ waiting (on S4.3, S4.5) | `learnings/W3-*.md` complete |

### Joseph (W4)

Nothing left of your own: see Everyone.

### Eric (W5)

| Task | Status | Done when |
|---|---|---|
| S6.1 Read every learnings file, run everything | 🟡 doing | A fresh clone runs the whole platform following only the README and the learnings files |
| S6.2 Fix what doesn't fit together | 🟡 doing | Each gap fixed with the owner of that part; nothing left that only one person can run |
| S6.3 Section B draft | ⏳ waiting (on S6.1) | Approach, architecture, implementation, evaluation, written from the learnings files; final numbers taken from S5.5 |
| S6.4 Slides and recorded demo | ⏳ waiting (on S6.2, S6.3, S4.3) | 10-minute deck with the GitHub link on slide 1, each person presenting their part; a demo recording saved |
| S6.5 Handoff: Eric's learnings | ⏳ waiting (on S6.4, S4.6) | `learnings/W5-*.md` complete |

### Everyone

| Task | Status | Done when |
|---|---|---|
| S0.6 Docker on every laptop | 🔵 ready | `docker run --rm hello-world` works for all 5 |
| S7.1 Review Section B for your part | ⏳ waiting (on S6.3) | Each owner confirms their part is correct |
| S7.2 Section A (individual, any time) | 🔵 ready | 3–5 pages each, own words, topics a–r told as one story |
| S7.3 Viva walkthrough | ⏳ waiting (on S6.5) | Each owner has taught their part; everyone can answer every part's viva questions |
| S7.4 Rehearse and submit | ⏳ waiting (on S7.1, S7.2, S7.3, S6.4) | Two timed run-throughs; report and slides on Canvas with the GitHub link on page 1 |

Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand.
<!-- STATUS:END -->

**Live platform:** https://34-78-38-126.sslip.io (each build spends real Claude credit)

**Aim:** finish the week of Nov 9.

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
| `runtime/` | Tools, Docker sandbox, test runner, server launcher | W2 |
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
- Every test result is saved in [`eval/results/`](eval/results/README.md) (decision 0051). If it is not there, it does not go in the report.
- We work at the same time, each on our own tasks ([`docs/PLAN.md`](docs/PLAN.md), decision 0050). A teammate reviews every merge. Your part is done when your learnings file lets someone else carry on without asking you.
- Coding assistants: see [`AGENTS.md`](AGENTS.md).
- The GitHub link goes on page 1 of every report and on the first slide.

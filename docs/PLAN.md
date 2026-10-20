# Plan

The tasks we all follow, in order. Each task has one owner (a workstream), the tasks it needs finished first, and what "done" means. The design behind it (product, architecture, evaluation) is in the Drive plan: `NLP-GROUP-1/prosit 2/Prosit 2 Plan - NLP Group 1`.

**Keeping it current:** when you start a task, set its status to `doing`; when it meets "Done when", set it to `done`. Then run `python3 scripts/update_status.py`, which rewrites the "Status" section of the README (what's in progress, what's ready, what's blocked and by what). Commit both files together. A GitHub check fails if the README is out of date.

Dates were moved on Oct 20: the Monday target was missed because the decisions in Phase 0 are still open. Target submission: **Fri Oct 23**, unless the instructor gives another date (P0.3).

## Owners

| Workstream | What | Owner |
|---|---|---|
| W1 | Agent core | TBD |
| W2 | Runtime, tools and safety | TBD |
| W3 | Product UI and usability | TBD |
| W4 | Evaluation and knowledge base | TBD |
| W5 | Lead, integration and writing | TBD |

`All` means every member does it for their own part (or, for Section A, individually).

## Tasks

`Needs` lists the tasks that must be `done` before this one can finish. You can start early, but you cannot finish without them.

| ID | Task | Who | Needs | Status | Target | Done when |
|---|---|---|---|---|---|---|
| P0.0 | Set up the repo: rules, docs, learnings, knowledge, worked benchmark example | W5 | — | done | Oct 20 | Pushed to GitHub |
| P0.1 | Choose the LLM provider and get an API key into everyone's `.env` | W5 | — | todo | Oct 20 | One test call works on every laptop; logged in `docs/DECISIONS.md` |
| P0.2 | Assign an owner to each workstream | W5 | — | todo | Oct 20 | Owner table above filled in |
| P0.3 | Ask the instructor for the presentation, report and viva dates, and what the rubric's "Section C" is | W5 | — | todo | Oct 20 | Answers in `docs/DECISIONS.md` and `knowledge/assignment.md` |
| P0.4 | Agree the 5 contracts in `docs/CONTRACTS.md` | All | P0.2 | todo | Oct 20 | `DRAFT` removed from the file; logged in `docs/DECISIONS.md` |
| P0.5 | Docker installed and running on every laptop | All | — | todo | Oct 20 | `docker run --rm hello-world` works for all 5 |
| P1.1 | Write 3 benchmark tasks each (easy, medium, hard), each with hidden tests and a reference backend that passes them | All | P0.4 | todo | Oct 21 | 15 task folders in `benchmark/`; every reference backend passes its tests |
| P1.2 | Tools and sandbox: files, run tests, start server, HTTP request, inside Docker (subprocess fallback) | W2 | P0.4, P0.5 | todo | Oct 21 | Each tool works on `church_signup`; Docker vs subprocess compared in W2 learnings |
| P1.3 | Single-agent ReAct loop that builds `church_signup` from the CLI | W1 | P0.1, P0.4, P1.2 | todo | Oct 21 | `python -m builder build ...` produces a backend that passes the hidden tests; prompt variants compared in W1 learnings |
| P1.4 | Eval harness: build each task, run its hidden tests, write a results table | W4 | P0.4 | todo | Oct 21 | One command scores any config on any set of tasks |
| P1.5 | UI shell working against fake events | W3 | P0.4 | todo | Oct 21 | Page goes describe → plan → progress → try-it with canned events |
| P1.6 | Recipe knowledge base and retrieval, first version | W4 | — | todo | Oct 21 | `search_docs` returns relevant recipes; BM25 vs dense vs none compared in W4 learnings |
| P2.1 | Planner / Builder / Tester split, with the test-and-repair loop | W1 | P1.3 | todo | Oct 22 | Builds pass more hidden tests than the single agent on 3+ tasks, or the learnings file shows why not |
| P2.2 | Spec-first plan and the user's approval step | W1 | P1.3 | todo | Oct 22 | Nothing is built before approval; plan events reach the UI |
| P2.3 | Wire retrieval (`search_docs`) into the agent | W4 | P1.3, P1.6 | todo | Oct 22 | With vs without retrieval compared on 3+ tasks |
| P2.4 | UI wired to the real agent: describe → approve → try it → download | W3 | P1.5, P2.2 | todo | Oct 22 | A non-developer completes the church example alone |
| P2.5 | Guardrails and the 5 attack tests | W2 | P1.2 | todo | Oct 22 | Each attack's result recorded in W2 learnings |
| P2.6 | MCP server exposing the tools (only if time allows) | W2 | P1.2 | todo | Oct 22 | An MCP client can call our tools |
| P2.7 | Feature freeze: `main` runs end to end | W5 | P2.1, P2.2, P2.4 | todo | Oct 22 | Fresh clone builds `church_signup` through the UI |
| P3.1 | Full benchmark and the 4 ablations (no repair, single agent, no retrieval, no spec-first) | W4 | P1.1, P1.4, P2.1, P2.2, P2.3 | todo | Oct 22 | Results tables and charts in `eval/results/` and W4 learnings |
| P3.2 | Usability test with 4–5 non-developers | W3 | P2.4 | todo | Oct 22 | Completion, time and SUS scores in W3 learnings |
| P4.1 | Learnings files complete: explanation, full experiment log, viva Q&A, glossary | All | P3.1, P3.2 | todo | Oct 23 | All 5 files filled; each owner has checked theirs |
| P4.2 | Section B draft (identical in every report) | W5 | P3.1, P3.2, P4.1 | todo | Oct 23 | Draft shared; every member has reviewed it |
| P4.3 | Slides and a recorded backup demo | W5 | P2.7, P3.1 | todo | Oct 23 | 10-minute deck, GitHub link on slide 1; demo video saved |
| P4.4 | Viva walkthrough: each owner teaches their part to the others | All | P4.1 | todo | Oct 23 | Everyone can answer each workstream's viva questions |
| P4.5 | Section A, written individually in your own words | All | — | todo | Oct 23 | 3–5 pages per person covering topics a–r |
| P4.6 | Two timed rehearsals, then submit report and slides on Canvas | All | P4.2, P4.3, P4.4, P4.5 | todo | Oct 23 | Submitted, GitHub link on page 1 of every report |

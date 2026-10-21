# The team and where things live

## Members

Michael Boadi · Joseph Etse · Alice Kara-Acquah · Bernard Marfo · Eric Sunu

Who owns which workstream, and the relay order, are in [`docs/PLAN.md`](../docs/PLAN.md).

## Workstreams

| # | Workstream | Owns | Section A reading cluster |
|---|---|---|---|
| W1 | Agent core | ReAct loop, prompts, Planner / Builder / Tester, orchestrator, project memory, CLI | Agents (f, g, m, n, r) |
| W2 | Runtime, tools and safety | Tools, Docker sandbox, test runner, server launcher, MCP server, guardrails, attack tests | Safety and people (k, l) |
| W3 | Product UI and usability | Web page, plan approval, progress, try-it panel, downloads; usability test with non-developers | Prompting and reasoning (d, h, p) |
| W4 | Evaluation and knowledge base | Benchmark format, test harness, ablations, results; BM25 recipe knowledge base | Knowledge, memory and tools (e, i, o, q) |
| W5 | Lead, integration and writing | Repo, integration, check-ins, Section B editing, slides, viva drill | From LM to assistant (a, b, c, j) |

The reading clusters are a way to share the reading load: one person goes deep on each cluster and briefs the others. **Section A is still written by each person alone, in their own words.**

## Where things live

| What | Where |
|---|---|
| Code, docs, learnings, knowledge | This repo: https://github.com/ASU-MICS-2028/nlp-group-1-prosit-2 (public) |
| Task plan, owners, blockers | [`docs/PLAN.md`](../docs/PLAN.md), with a summary of what's pending in the README |
| Design plan (product, architecture, evaluation, schedule) | Shared Google Drive: `NLP-GROUP-1/prosit 2/Prosit 2 Plan - NLP Group 1` |
| Prosit 1 code | https://github.com/ASU-MICS-2028/nlp-group-1-prosit-1 |
| Prosit 1 reports, slides, figures | Shared Google Drive: `NLP-GROUP-1/prosit 1/` |
| Shared datasets from Prosit 1 | Shared Google Drive: `NLP-GROUP-1/data/` (Ewe corpus, splits, BPE tokenizers). Not needed for Prosit 2 |
| Brief, course outline, submissions | Canvas |

## How we work

- The two rules in the [README](../README.md): explain everything simply, and test every alternative with numbers.
- We work as a relay, one person at a time (`docs/PLAN.md`). Branch for your stage, pull request to `main` at your handoff.
- When you start or finish a task, update its status in `docs/PLAN.md` and run `python3 scripts/update_status.py` (this updates the README).

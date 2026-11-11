# 0061. Play back a saved session through the real page

- Status: Proposed
- Date: 2026-11-11
- Decided by: Eric (W5), doing Michael's task S4.2 with his permission; Michael to review in the pull request

## Context

S4.2 asks for a way to show and test the page without paying for a build. A real build costs about $0.20 of the team's Claude credit. Every change to the page needs a full journey through it (questions, plan, building, live) to check.

## Options considered

- **Michael's recorded demo in `ui/index.html`** (commit `7e3a88d`). Hard-coded screens inside the page, so the page carried demo code, and it never ran the platform backend or the session code.
- **A demo mode inside `web/index.html`.** The same problem: two modes in one file, more to explain in the viva.
- **A pretend Claude written for one check** (`eval/results/walkthrough/part6/new_page/check_page.py`, decision 0060). Works, but its answers are made up for that check.
- **Play back a saved `session.jsonl` (chosen).** `web/replay.py` swaps only the steps of `builder/session.py` that cost money or touch the server (questions, plan, build, the data check, publish, summary, unpublish) for what a saved session did, at its saved pace, capped at 3 seconds a step. The real `web/app.py`, `builder/session.py` and `web/index.html` run unchanged.

## Decision

`uv run --with anthropic python -m web.replay <saved session.jsonl>` serves the real page at `http://127.0.0.1:8090`, playing back that session. The page has no demo code.

## Consequences

- Free and repeatable: `web/test_web.py::test_replay_plays_a_saved_session` plays the bakery session at full speed (web tests: 7 passed; breaking `replay.py` three ways made it fail each time). `eval/experiments/page_compare.py` uses it to compare page versions (W3 row 4), and `eval/experiments/browser_check.py` can run against it (`eval/results/walkthrough/browser_check_replay/`).
- Whatever you type, you get the saved session's questions, plan and result. Only the first build in the file plays; a later change plays it again.
- The link on the live screen points to the saved build on the real server, which may be offline.
- It shows how the page behaves, not how good a build is: scores still come from real builds and the harness.

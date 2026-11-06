# 0049. Put a small platform online first; Michael improves it live

- Status: Accepted
- Date: 2026-11-06
- Decided by: Joseph

## Context

The system must be live so that anyone can build a backend (Lecture 8). The relay had Michael build a page on a recorded session, then on the agent, and only then put it online. Hosting and the session now exist, so nothing needs to wait for that.

## Options considered

- **Michael builds the whole web layer from the session's instructions.** No overlap, but nothing is online until he finishes.
- **A small working version now (`web/`), which Michael then improves.** Live today, and his work is on the page and the usability test instead of plumbing.

## Decision

`web/app.py` is the platform's backend: the page talks to it, and it talks to the agent session (decision 0048). `web/index.html` is one plain page. `web/setup_server.sh` rebuilds the server. Limits per person: 5 new builds a day and 30 messages an hour.

## Consequences

- Stage 4 changes: Michael starts from a working live page. He owns `web/index.html` and may change `web/app.py`.
- Limits count by address, so a whole campus on one address shares them. They reset on restart.
- The page was written without testing alternatives or real users: that is still S4.4 and S4.5.

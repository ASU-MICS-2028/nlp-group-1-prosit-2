# 0048. One session object carries a client from request to live link

- Status: Accepted
- Date: 2026-11-06
- Decided by: Joseph

## Context

Lecture 8: the agent must accept follow-up messages during a build, and must return a running backend. `build()` runs one build from start to end and cannot hear anything new. The page also needs one place to send everything the client says. And now that anyone may start a build, each one spends our Claude credit.

## Options considered

- **A background thread per client, in the backend's own program** (`builder/session.py`). The simple option from Lecture 8. A restart forgets builds in progress.
- **A separate agent service with a job queue.** Survives restarts, but it is more code to defend for a demo.
- **Stop and restart the build when a message arrives.** No change to the loop, but it wastes the money already spent. Passing the message between turns costs nothing extra.

## Decision

`builder/session.py`: `start`, `send`, `approve` and `get`. The flow is questions (0042), then a plan the person approves (0041), then the build, then publishing (0047). `send` means what the state says: answers, plan changes, a mid-build message (`build(inbox=...)`, checked between turns and when the agent thinks it is finished), or a change to a live app.

Three guards. A build is published only if its own tests ran and passed, because with Docker off the agent finished normally having tested nothing. Spending stops at `MAX_DAILY_USD` ($10 by default). At most 2 builds run at once, and a request can be at most 5,000 characters.

## Consequences

- The page has one small interface, and it never sees code, tool output, costs or error details (`get` leaves them out).
- A restart forgets sessions in progress; backends already live keep running.
- The agent decides how to apply a mid-build message. In the real check it added the colour, but as an optional field, though the message said it must be given. So the client should read the result.
- The limit counts what has been spent, so a build already running can pass it a little (each build stops at $2).
- A plan is shown although plan-first scored lower with automatic approval (0041). A real person approving it has not been measured: Michael's usability test should watch this.

# 0025. start_server uses a free port and asks the server until it answers

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

## Context

The agent must start the backend it built and call it. Two questions: which port to use, and how to know the server is ready before sending requests.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log rows 7–8:

- Port: always 8001 (the second of two servers died: address in use) or a free port from the operating system (both ran).
- Ready: a fixed sleep of 1 s or 2 s; asking every 0.1 s with a 1 s or a 0.1 s connect limit; watching the log. All 10/10. Medians 1.54 / 2.51 / 2.52 / 2.26 / 2.04 s.

## Decision

`start_server` asks the operating system for a free port, starts `uvicorn app:app` on `127.0.0.1` with the cleaned environment, and asks `/openapi.json` every 0.1 s (0.1 s connect limit) until any answer comes. It gives up after 20 s. It returns the crash log if the process ends by itself.

## Consequences

- Several backends can run at once.
- The base URL changes each time; the agent must use the one `start_server` returns.
- Listening on `127.0.0.1` only means other computers on the network cannot reach the generated backend.
- Not yet isolated: the server runs on the host with the cleaned environment only. The sandbox comes in S1.2.

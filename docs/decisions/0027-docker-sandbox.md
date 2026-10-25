# 0027. Generated code runs in a locked Docker container; subprocess only when chosen on purpose

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

Replaces 0006, which proposed Docker with an automatic subprocess fallback.

## Context

`run_tests` and `start_server` run code the LLM wrote. That code can be wrong or, through a malicious request, harmful. It must not reach the internet, our files, our API key, or all of the computer's memory and CPU.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log rows 10–11:

- **Subprocess** (a normal program with a time limit and cleaned settings). Fastest: tests 1.5 s, server start 1.2 s, requests about 1 ms. But it reached the internet, read a secret next to the project, wrote outside the project and took 1 GB of memory.
- **Docker container**. Tests 3.4 s, server start 4.2 s, requests about 10 ms (p95 55 ms). It blocked all four.
- Docker network for the server:
  - `none` and `--internal` cannot be reached from our computer;
  - `bridge` can be reached, but also reaches the internet;
  - an internal network plus a "door" container (`alpine/socat`) is the only option with both.
- When Docker is not running: fall back to subprocess automatically, or return an error.

## Decision

`runtime/sandbox.py`, `SANDBOX=docker` by default. Every test run or server is a fresh container of the `w2-sandbox` image (`runtime/sandbox/Dockerfile`: `python:3.12-slim` plus the fixed stack at the `uv.lock` versions). The container:
- has no network (tests) or a private internal network behind a door (server);
- gets 512 MB of memory with no swap, 1 CPU and 128 processes;
- has read-only system files, no special rights (`--cap-drop ALL`, `no-new-privileges`), and runs as user 1000;
- sees only the project folder, mounted at `/app`.

`SANDBOX=subprocess` must be set on purpose. There is no automatic fallback.

## Consequences

- Every escape in the comparison is blocked, at a cost of about 2–3 s per call. That is small next to the several seconds of each LLM step.
- Everyone needs Docker Desktop running, the image built once, and `alpine/socat:1.8.0.3` pulled.
- Two images are new dependencies: `python:3.12-slim` (base) and `alpine/socat` (door).
- The project folder is writable with no size limit: a known gap.
- Section A topic k gets measured, concrete material.

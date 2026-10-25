# 0006. Generated code runs in a Docker sandbox, with a subprocess fallback

- Status: Superseded by 0027
- Date: 2026-10-18
- Decided by: —

## Context

Code written by an LLM is untrusted: it can be wrong, and a malicious request can try to make it harmful.

## Options considered

- Run it directly on the host.
- A Docker container with no network, CPU and memory caps and a timeout.
- A subprocess with a timeout, as a lighter fallback.

## Decision

Docker by default; subprocess as the fallback where Docker is unavailable.

## Consequences

- Concrete material for Section A topic k (privacy and security).
- Everyone needs Docker installed.
- Docker vs subprocess is compared on speed and isolation, and any weaker isolation is stated honestly.

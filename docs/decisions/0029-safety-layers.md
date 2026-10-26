# 0029. Safety comes from the tools and the sandbox, with no filter on the user's request

- Status: Proposed
- Date: 2026-10-26
- Decided by: Bernard (W2), awaiting his sign-off

## Context

The user's request is untrusted text. It can hide instructions that try to make the LLM read secrets, send data out or delete files (prompt injection). We had to decide where to stop such attacks.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log rows 13–14, and the safety list in section 5:

- **Trust the LLM to refuse.** Claude ignored 9 of 9 injected instructions, but that is 9 runs of one model.
- **Filter the request** for phrases like "ignore your instructions" before the LLM sees it. Not built. A word filter is easy to dodge by rewording, and it could block honest requests.
- **Block the actions themselves**, whatever the LLM decides:
  - the tools refused all 7 tool attacks;
  - the Docker sandbox blocked 14 of 16 harmful-code attacks;
  - the 2 that got through stay inside the project folder.

## Decision

Rely on the tools and the Docker sandbox as the guard, with the LLM's own resistance as an extra layer. Add no request filter.

## Consequences

- The protection does not depend on which model the agent uses (Claude or Qwen), or on how an attack is worded.
- Two known gaps remain inside the project folder: deleting the project's own files and filling the disk.
- With `SANDBOX=subprocess`, only the tool layer remains: 11 of 16 code attacks got through.
- Worth re-testing with local Qwen (S3.9), which may obey injections more often.

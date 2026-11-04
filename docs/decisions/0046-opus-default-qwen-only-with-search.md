# 0046. Opus is the agent's default model; the local Qwen is used only with recipe search

- Status: Proposed
- Date: 2026-11-04
- Decided by: Alice (to sign off)
- Adds to: 0043 (search off for Opus)

## Context

S3.9 compared Claude Opus with Qwen 3.5 9B running on a laptop through llama.cpp (free, private, works offline). S3.7 had shown recipe search does nothing for Opus; Joseph showed recipes help one-call Qwen (W4 row 27).

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log rows 11 and 12 (church, football, library, lost-and-found, shop; 1 build each; harness `--repeat 3`):

- Opus: 85.2% of hidden tests, about 40 s and $0.15 per build.
- Qwen, no search, 20 turns: 0%. No app starts; every build used all 20 turns, mostly fighting the database ID. 3 to 24 minutes each.
- Qwen with search: 59.0%. It looked up the ID recipe in 4 of 5 builds and got past the crash. 5 to 70 minutes each, $0.

## Decision

Opus stays the default (`--model claude-opus-5-5`). Whenever the local model is used, recipe search is turned on (`--model qwen3.5-9b-local --search`). Search stays off for Opus (0043).

## Consequences

- Best quality and speed by default; a free offline option exists, at about 60% and 30 minutes a build.
- Anyone running Qwen must remember `--search` (written in the learnings commands).
- Qwen's own tests are not trustworthy (football 0/17 own, 11/13 hidden), so its builds should always be scored by the hidden tests or a person.

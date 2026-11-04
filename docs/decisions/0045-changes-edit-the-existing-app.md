# 0045. A requested change edits the existing app instead of rebuilding it

- Status: Proposed
- Date: 2026-11-04
- Decided by: Alice (to sign off)

## Context

S3.10: after a backend is built, the client may ask for something more ("people must be able to cancel"). The agent can either edit the app it already made or build a new one from the request plus the change.

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log row 9 (church and shop from row 7, 1 build each, harness `--repeat 3`):

- Edit (`python -m builder change TASK --what "..."`): church stayed 10/10, shop 9/13 to 11/13 (both category tests fixed, nothing broken). $0.18 and 53 s for the pair. Only `read_file`, `edit_file` and `run_tests` were used.
- Rebuild: church 10/10, shop 13/13 (a fresh design also happened to refuse prices of zero, which the change never mentioned). $0.21 and 66 s for the pair.

## Decision

A change edits the existing app. The old `run.json`, `trace.jsonl` and `app.py` are kept in `history/` first, so any change can be undone.

## Consequences

- The client keeps the routes and saved data they already use; only what they asked for changes.
- Old mistakes stay unless the change asks to fix them; a rebuild is still possible with `build`.
- Cost and time are about the same either way, so this is chosen for safety, not price.

# 0052. read_file returns up to 20,000 characters

- Status: Accepted
- Date: 2026-11-06
- Decided by: Joseph

## Context

Decision 0024 cut every tool's output to 4,000 characters, and Bernard's row 4 said to look again if generated files outgrew that. They did: 10 of 15 apps Opus built are over 4,000 characters, the largest 9,845. So to change a big app, the agent could not read its middle.

## Options considered

Measured in W4 row 36: the 3 biggest apps, one change each, 1 run per arm.

- **Cut at 4,000 (as it was):** 24 turns, $0.426, 132 s. Hidden tests unchanged, and no edit failed, but the agent had to print the file through a throwaway failing test.
- **No cut:** 13 turns, $0.350, 97 s. Same hidden test scores and the same number of edits, with no trick.
- **Line ranges ("read lines 50 to 100"):** not tried. The agent would need several calls and one more parameter, and the whole file already fits.

## Decision

`read_file` keeps the start and end only above 20,000 characters, about twice the largest app so far. Every other tool stays at 4,000, so a huge test output or reply still cannot flood the conversation. This changes decision 0024 for `read_file` only.

## Consequences

- The agent sees the whole app when changing it, at about 2,500 more input tokens per read of the biggest apps.
- A file over 20,000 characters is still cut, so the trick could come back. Nothing that big has been built yet.
- Tested with Opus only. The saving comes from one run per app, so treat it as rough.

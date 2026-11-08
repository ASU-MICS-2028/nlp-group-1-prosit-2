# 0054. Rewrite the summary after the build; keep the wording of mid-build messages

- Status: Accepted
- Date: 2026-11-08
- Decided by: Joseph

## Context

S4.8, moved from Alice to Joseph: the client read the builder's notes (`POST /orders`, `bakery.db`), and we believed a "must" message could be followed only partly (W4 row 32).

## Options considered

Summary (W4 row 40, 15 builds):
- Leave it: technical words in 15 of 15.
- Change the builder's prompt (Alice's `s48_all`): 0 of 15, but it changes every build, so all 15 need paying for and scoring again.
- Rewrite after the build with Opus: 0 of 15, $0.294 for 15.
- Rewrite after the build with Haiku: 0 of 15, $0.011 for 15.

Messages (W4 row 41, real requests, 8 builds per arm):
- Today's wording: 8 of 8.
- Stronger wording: 8 of 8.

## Decision

The session rewrites the builder's notes in plain words with Haiku, once the backend is live. The client never gets the builder's notes. If the rewrite fails, the backend still goes live with one plain sentence. The wording of mid-build messages stays as it is.

## Consequences

- No build prompt changed, and a rewrite runs after the build, so the score cannot move because of this change (it does change from build to build: W4 row 42). That is why the "re-score all 15, no lower than 95.8%" part of S4.8's done-when was dropped.
- Row 32's "the colour came out optional" was our own misreading. It is corrected there.
- The list of methods on the page is still technical: that is S4.3.
- Tested on 4 kinds of message only.

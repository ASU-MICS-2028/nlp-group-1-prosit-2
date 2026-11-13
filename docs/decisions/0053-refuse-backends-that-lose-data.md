# 0053. Do not publish a backend that would lose its data

- Status: Accepted
- Date: 2026-11-06
- Decided by: Joseph

## Context

We host the backends (Lecture 8), so a client expects their data to stay. The hidden tests never restart a backend, and neither do the agent's own tests, so an app that keeps data in memory passes everything and then loses it all at the first restart. The restart check found this in nearly every one-call build (W4 row 37).

## Options considered

- **Publish anyway and trust the prompt.** The prompt asks for SQLite, and all 15 builds of the fresh run followed it (W4 row 38). But nothing would catch the day one does not.
- **Read the code for words like `sqlite`.** Cheap, but it passes a database in memory, and one wiped at every start.
- **Use the real restart check (`bench.keeps_data`).** It needs the hidden tests, and a client's backend has none.
- **Start the app and look.** A SQLite file with tables must appear; add a row to every table, start it again, and no table may lose a row. No hidden tests needed. Agrees with the real restart check on all 99 builds where both give an answer, 17 that keep and 82 that lose (W4 row 39).

## Decision

Before publishing, `runtime.deploy.keeps_database` starts a copy of the app and looks. If it would lose its data, the agent is sent back once to fix it. If it still would, the backend is not published and the client is told why, in plain words.

## Consequences

- About 3 seconds more before publishing, and a second build's cost (about 10 to 20 cents) only when an app fails.
- It cannot see an app that has a database but also keeps some data in memory. None of the saved builds does this, but the check would pass one. The real restart check would catch it in the evaluation.
- An app that creates its tables only at the first request would be sent back. The prompt says to create them at the start.
- Only SQLite counts as a database, which matches decision 0002.

**Update (Nov 12):** checked again on more saved builds, the two agree on **114 of 114** where both give an answer (32 keep their data, 82 lose it), W4 row 39. The 99 and 17 above are the first check.

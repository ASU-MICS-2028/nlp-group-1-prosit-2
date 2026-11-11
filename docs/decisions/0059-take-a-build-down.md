# 0059. A client can take their build down

- Status: Accepted
- Date: 2026-11-10
- Decided by: Eric (W5), with the team's agreement that he fixes what the S6.1 audit finds; accepted by Joseph (W4) on 2026-11-11

## Context

The S6.1 walkthrough found that a build, once live, stays public until Joseph logs into the server and runs `undeploy` by hand (`runtime/deploy.py`). Every test build we make, and every build a visitor makes, stays online. The platform had no way to take one down.

## Options considered

- **Leave it to Joseph, by hand.** No code. But only one person can do it, and S6.2's "Done when" says nothing should be left that only one person can run.
- **A route through the session, data kept (chosen).** `session.take_down(sid)` calls the existing `undeploy(name)` and moves the build to `failed` with a plain message. About 10 lines plus one test.
- **The same, but the data deleted too** (`undeploy(name, delete_data=True)`). Cleaner on disk, but a click could not be undone, and the build id is in the public link (`/b/<id>`), so anyone the owner shared the link with could wipe the data.
- **A route that takes any well-formed name** and calls `undeploy` directly. It would also reach builds from before the last restart, but anyone could take down any backend whose name they can see in a link, and it skips the session's checks.
- **A new state `taken_down`.** Clearer name, but `send()` and both pages would need changes; `failed` already means "not online, a message builds it again" in both.

## Decision

`POST /api/builds/{id}/take-down` calls `session.take_down`. It is refused while a build is running (that build would publish again) and when nothing is online. The backend comes off its address, its data stays on the server, and the build shows `failed` with "This backend was taken down. Send a message to build it again." It uses the same per-person limit as messages.

## Consequences

- Easier: anyone can remove their own test build straight after testing, with one click on the new page or one `curl` until then.
- Limit 1: the key is the build id, which is in the public link. Anyone with the link can take the backend offline. That is the same rule as today's messages (anyone with the id can already send a change), and no data is lost. Logins would fix both; not needed for the demo.
- Limit 2: sessions live in memory, so a build made before the server's last restart cannot be taken down this way. Joseph's manual `undeploy` still covers those.
- The data of a taken-down build stays on the server disk (its folder in `DEPLOY_ROOT`), as it already does after a manual `undeploy`. Nothing removes it yet.
- Tested on the server on 2026-11-11 with one real build (`eval/results/sessions/take_down_live.json`, about $0.09): refused while building, link 200 before and 404 after, a second take-down refused, both other live backends still 200. Laptop checks: `eval/results/walkthrough/part6/take_down.txt`.
- Joseph's saved attack results (`eval/results/safety/`) were made before this route existed; they are left as they are.

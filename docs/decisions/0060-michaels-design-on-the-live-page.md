# 0060. The live page uses Michael's design, in one plain file

- Status: Proposed
- Date: 2026-11-11
- Decided by: Eric (W5), with Michael's permission to change his part and the team's agreement that Eric fixes what the S6.1 audit finds; Michael to review in PR #14

## Context

The S6.1 walkthrough found two pages. The live link serves `web/index.html`, Joseph's plain page (decision 0049). Michael's designed page, `ui/index.html` (Nov 6), talked to its own small server, `ui/server.py`, at different addresses: no limits, an empty request accepted, and it never published a build (`start_app()` was a TODO). So the live site could not use it. Eric asked for Michael's page to work with the full platform, and for the code to stay as small as possible, because the viva can pick any file.

## Options considered

- **Next.js.** Needs Node on the server, a build step and hundreds of packages. The server has no Node.
- **React and TypeScript, built by Vite into one file.** The server stays the same, but Node, pnpm, a lockfile, a source folder and a generated file would all need explaining.
- **Michael's `ui/index.html` with its live part rewritten** for `/api/builds`. Keeps his recorded demo, but one 220-line file would hold two modes (the live mode replaces the demo's functions), and a refresh would lose the build without more work.
- **Joseph's page logic in Michael's design (chosen).** Joseph's script is proven on the live site (W4 rows 32 and 33, `eval/experiments/browser_check.py`). It keeps its behaviour: the build id in the address, so a refresh keeps the build; messages during a build; plain error messages. It takes on Michael's colours, fonts and dark mode, his tape-measure progress bar, his plan cards and step list, and his three example requests.

## Decision

`web/index.html` is Joseph's page logic dressed in Michael's design, as one file with no build step (200 lines, up from 131). The button words stay the same, so Joseph's browser check runs unchanged. It adds a "Take it offline" button (decision 0059). `ui/server.py` and `ui/index.html` are removed.

## Consequences

- One page and one server. Nothing new to install. The server and its setup script are unchanged.
- Left out of Michael's page: the recorded demo and its "Test setup" switches (plan as cards or sentences, technical log); one question per screen with answer choices (the live questions come without choices); the pretend "Try it" table; the downloads. Playing back a recorded session is S4.2, still Michael's. His page is in git history (commit `7e3a88d`) to reuse.
- The plan now shows as cards built from the plan's data, instead of the plain-text plan.
- The fonts load from Google Fonts. If that is blocked, the page uses the system fonts.
- The screen for the `failed` state is headed "It is not online" (it was "That did not work"), because a build taken down on purpose is also `failed` (decision 0059); the message under it says which. Joseph's browser check waits for the new words.
- Checked free: `eval/results/walkthrough/part6/new_page/check_page.py` runs the real `web/app.py` and `builder/session.py` with a pretend Claude and a pretend publish, fed the real questions and plan of the bakery build (`eval/results/sessions/bakery_through_the_page.jsonl`), in real Chrome at 390 and 1280 pixels wide and in dark mode. Every screen worked; no page errors; no sideways scrolling; a refresh kept the build; a message sent mid-build reached the builder; take-down worked; clicking an example clears an old error. Not yet checked with a real build. It goes live only after review, the merge to `main`, and Joseph rerunning `setup_server.sh`.
- Michael still owns `web/index.html` (decision 0049).

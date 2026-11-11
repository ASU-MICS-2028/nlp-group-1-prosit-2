# W3 — Product UI and usability: learnings

Owner: Michael

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

> **Draft by Eric (W5), Nov 11, for Michael to check.** Written only from what is on disk: decisions 0049, 0059 and 0060, the code in `web/`, and the saved results named in each row. Michael: you defend this part in the viva, so read every line, correct anything wrong, and put sections 1, 2, 4 and 5 into your own words. Your own design reasons (why the tape measure, why these colours, what you tried before Nov 6) are not on disk: add them as rows where it says `[MICHAEL: ...]`.

## 1. What this part does, in one paragraph

The page is the only thing a client ever sees. It is one file, `web/index.html`, served by the platform's backend (`web/app.py`) at the public address. The client types what they need in plain words, answers up to three questions, reads the plan and approves it, watches the build in plain steps, and gets a link to their working backend. Afterwards they can ask for a change or take the backend offline. The page never talks to the agent itself: it only asks the platform's backend, at `/api/builds`, and draws what comes back (Lecture 8). The look is Michael's design (colours, fonts, dark mode, a tape-measure progress bar, plan cards); the page logic is Joseph's, which had already worked on the live site (decision 0060).

## 2. How it works, step by step

A real example: the bakery build made through the public page (`eval/results/sessions/bakery_through_the_page.jsonl`, W4 row 33).

```
 client's phone                          platform backend (web/app.py)              agent (builder/)
 ──────────────                          ─────────────────────────────              ────────────────
 types the request, clicks Start  ──POST /api/builds──────────▶  session.start  ──▶  asks questions
 address becomes ?b=bf7fe9a80ae   ◀──{"id": "bf7fe9a80ae"}──
 every 1.5 s (5 s if waiting)     ──GET /api/builds/<id>?after=N─▶ session.get
 draws the screen for the state   ◀──state, questions, plan, new events──
 answers, clicks Continue         ──POST .../messages [answers]─▶ plans
 clicks "Looks good, build it"    ──POST .../approve──────────▶ builds, tests, publishes
 "Your backend is live" + link    ◀──state "live", url, endpoints, summary──
```

1. **Describe.** A text box and three example buttons (tailoring shop, church sign-up, bakery orders). An empty box gets "Please type something first." Start sends the request; the build's id goes into the address (`?b=...`), so a refresh keeps the build.
2. **Questions.** The bakery got three, for example "Can one order include more than one cake, or a quantity (e.g. 3 of the same cake), or is it always a single cake per order?". An empty answer is sent as "No preference: you decide."
3. **Plan.** Shown as cards made from the plan's data: what is kept (with its fields), what each action does, and the rules. "Looks good, build it" approves it; or the client types what should be different and gets a new plan.
4. **Build.** A step list in plain words, from the agent's events: `write_file` shows as "Writing the code", `run_tests` as "Testing it", and so on (the `WORDS` list in the page). A box lets the client send a message; it reaches the agent between turns ("Your message reached the builder").
5. **Live.** "Your backend is live", a link to try it (the backend's `/docs` page), its address, the list of actions for whoever builds the client's website or app, and a plain summary. Buttons: Change it, Take it offline (asks first), Build something else.
6. **Not online.** If the build failed, or the client took it offline, the screen says "It is not online" and the plain reason, with a box to try again.

The tape measure across the top (on a phone, a bar with the stage's name) shows the five stages: Describe, Questions, Plan, Build, Try it. The stage comes from the build's state (`STAGE` in the page); a failed build stays at Build.

## 3. Everything we tried (experiment log)

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | Which page goes on the live link? | Michael's `ui/index.html` with its own server `ui/server.py` · Joseph's plain `web/index.html` · Joseph's page logic in Michael's design | Read all three. Joseph's page was proven on the live site (W4 rows 32 and 33). The new one checked free with a pretend Claude, at 390 and 1280 pixels and in dark mode (`eval/results/walkthrough/part6/new_page/check_page.txt`) | `ui/server.py` never published a build (`start_app()` returned nothing), took an empty request and had no limits. Page sizes: 220, 131 and 200 lines. New page: 18 of 18 screens with no sideways scrolling, 0 page errors, a refresh kept the build, take-down worked | **Joseph's logic in Michael's design** (decision 0060): the logic that already worked live, with Michael's look. One page and one server |
| 2 | How is the page built? | Next.js · React and TypeScript built by Vite · one plain HTML file | Reasoning only, no measurement (decision 0060) | The server has no Node. Next.js and Vite each add Node, a build step, packages and a lockfile to explain | **One plain file**: nothing to install or build, and every line can be explained in the viva |
| 3 | How do we try the page without paying for builds (S4.2)? | A recorded demo inside the page (Michael's Nov 6 page: made-up tailoring data and its own copy of each screen) · play a real saved `session.jsonl` through the real backend and page (`web/replay.py`) | `test_replay_plays_a_saved_session` in `web/test_web.py`: the bakery session plays from start to live. Then broke `replay.py` three ways (wrong link, events not sent, tests failing) | 7 web tests passed. Each of the 3 breaks made the test fail. The page needs no demo code | **Play back a saved session**: the page runs exactly as it does live, so what you see is what clients see. Any saved session works, not one made-up example |
| 4 | Does the new page use fewer technical words (S4.4)? | The page before decision 0060 (Joseph's, commit `2735bfb`) · the page now | `eval/experiments/page_compare.py`: the same saved bakery session through both pages in Chrome at phone width; counts every word on each screen and the technical words from a fixed list (`eval/results/page_compare/`) | Words per screen, before then now: describe 23 / 28, questions 89 / 90, plan 329 / 340, build 31 / 32, live 327 / 336. Technical words on the plan: GET, POST / none. On the live screen: GET, POST, docs, https, id on both | **Now**: the plan has no technical words. The live screen still has the action list (`GET /cakes`) and this old session's summary, written before summaries were made plain (decision 0054). The list's heading now says it is for whoever builds the client's website or app. A word count, not a user test |
| 5 | What heading does a build that is not online get? | "That did not work" · "It is not online" | Read with take-down (decision 0059): a build taken offline on purpose is also in the `failed` state | None: a wording choice | **"It is not online"**: true for both cases; the message under it says which |
| 6 | `[MICHAEL: your design choices before Nov 6, for example the tape measure, one question per screen with choices, plan as cards or sentences]` | | | | |

## 4. What we chose, and why

- One plain file, `web/index.html`, no build step (rows 1 and 2).
- Joseph's tested logic: the build id in the address, polling every 1.5 s (5 s while waiting for the client), plain error messages (row 1).
- Michael's look: colours and fonts as named tokens, dark mode, the tape-measure progress bar, plan cards, the ✓ and ○ step list, three example requests (row 1).
- Trying the page for free by playing back a saved session, not a demo inside the page (row 3).
- Plain words on every screen a client reads, with the technical list labelled for their developer (rows 4 and 5).

`[MICHAEL: your words]`

## 5. What breaks, and the limits

- **Not yet on the public address.** The new page reaches the live link only when Joseph reruns `setup_server.sh` on the server. Until then the live link has the old page and no take-down.
- **No usability test yet (S4.5).** Nobody outside the team has used the page. No completion rates, times, SUS scores or quotes exist.
- **Questions come without answer choices.** Michael's Nov 6 page showed one question per screen with choices; the agent's questions are free text.
- **"Try it" opens the backend's `/docs` page**, which is a technical page (the course allows it, Lecture 8). Michael's pretend "Try it" table was not carried over.
- **The live screen still shows actions like `GET /cakes`**, for whoever builds the client's website or app.
- **Anyone with the link can take the backend offline** (decision 0059), as anyone with it can send messages.
- **The fonts come from Google Fonts.** If that is blocked, the page falls back to the system fonts.
- **Playback** (`web/replay.py`) plays only the first build of a saved session; a later change plays it again. The link at the end points to the saved build, which may be offline. The saved code is not copied.

`[MICHAEL: what you would do with more time]`

## 6. How to run it, and how the next person uses it

**Try the page for free** (from the repo root; no key, no Docker, nothing published):
```
uv run --with anthropic python -m web.replay eval/results/sessions/bakery_through_the_page.jsonl
# open http://127.0.0.1:8090, click Start: the saved questions, plan, progress and link come back, whatever you type
```
To change the page: edit `web/index.html`, reload the browser. The backend reads the file on each visit.

**With real builds** (costs about $0.20 a build; publishing works only on the server):
```
uv run --env-file .env --with anthropic python -m uvicorn web.app:app --port 8080
```

**Checks:**
```
uv run --with anthropic python -m pytest web -q        # 7 passed (Nov 11), free
PYTHONPATH=. uv run --with anthropic --with playwright python eval/results/walkthrough/part6/new_page/check_page.py   # every screen, 3 sizes, free
PYTHONPATH=. uv run --with anthropic --with playwright python eval/experiments/page_compare.py                       # words per screen, free
uv run --with playwright python eval/experiments/browser_check.py eval/results/browser_check   # the live site, one real build, about $0.20
```
The browser checks click the buttons by their words (Start, Continue, Looks good, Send) and wait for "A few quick questions", "Here is the plan", "Building", and "Your backend is live" or "It is not online". Keep those words, or change the checks too.

**What the page uses from the backend** (`web/app.py`, W4 section 6):

| The page sends | It means | Answer |
|---|---|---|
| `POST /api/builds` `{"request": "..."}` | a new build | `{"id": "b..."}` |
| `GET /api/builds/<id>?after=N` | what is new | state, questions, plan, url, docs_url, endpoints, summary, error, events from number N |
| `POST /api/builds/<id>/messages` `{"message": [answers]}` or `{"message": "text"}` | answers, a plan change, a message while building, or a change after going live | `{"ok": true}` |
| `POST /api/builds/<id>/approve` | build this plan | `{"ok": true}` |
| `POST /api/builds/<id>/take-down` | take it offline (decision 0059) | `{"ok": true}` |

A refused request comes back as status 400 with `detail`, a sentence written for the client; the page shows it as it is.

## 7. Viva questions you should be able to answer

| Question | Answer |
|---|---|
| Why does the address change to `?b=...` after Start? | So a refresh, or opening the link again, finds the same build. Without it, a refresh would start from nothing |
| Why does the page check every 1.5 s, but every 5 s on some screens? | 1.5 s while the platform is working, so progress shows quickly. 5 s while it waits for the client (questions, plan) or nothing is moving (live, failed), to ask the server less |
| Why does the page redraw the screen only when the state changes? | A redraw replaces the text boxes, which would wipe what the client is typing. The step list is updated on its own |
| Why does the page build everything with `textContent`, never `innerHTML`? | The text comes from the agent and the client. As text it can never run as code in the page |
| What is sent for a question left empty? | "No preference: you decide.", so the agent knows to choose |
| What does the client see if the backend refuses something? | The refusal's own sentence (the `detail`). If there is none, "Please check what you typed and try again." |
| Which stage does the progress bar show for a failed build? | Build (stage 3 in `STAGE`): the build did not finish |
| How do we try the page without paying? | `web/replay.py` swaps the paid steps (questions, plan, build, publish, summary) for what a saved `session.jsonl` says they did, and runs the real backend and page |
| Why is the playback in the backend and not inside the page? | The page then has no demo code at all, and runs exactly as it does live |
| Why one plain file and not React? | The server has no Node; a plain file needs nothing installed or built, and is less code to explain |

## 8. Glossary

- **Page**: the HTML file the client's browser shows; here `web/index.html`.
- **Platform backend**: `web/app.py`, the program the page talks to. It starts builds and passes on what the agent does.
- **State**: where a build is: asking, waiting_answers, planning, waiting_approval, building, live or failed.
- **Polling**: the page asking the server again and again, every few seconds, what is new.
- **Endpoint**: one action a backend offers, written as a method and a path, like `GET /cakes` (show all cakes).
- **`/docs` page**: a page every FastAPI backend makes by itself, listing its actions with a button to try each one (also called Swagger).
- **Dark mode**: the same page in light text on a dark background, when the phone or computer is set to it.
- **Token (design)**: a named colour or size, like `--ink`, set once and used everywhere, so dark mode only changes the names' values.
- **Replay (playback)**: running a saved session again, with no paid calls, to see every screen.
- **`session.jsonl`**: the file each build saves, one line per event (request, questions, plan, each tool the agent used, live).
- **Sideways scrolling**: a page wider than the phone's screen, so the client must scroll left and right. None of ours do.
- **SUS (System Usability Scale)**: a standard 10-question form people fill in after using something; it gives a score from 0 to 100.

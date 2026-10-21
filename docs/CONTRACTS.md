# Contracts (DRAFT — agree on the call, task S0.5)

A contract is a promise between two people about how their parts plug together. With these agreed, five people can build at the same time without waiting on each other. Change a contract only after telling the people on both sides, and add a line to `docs/DECISIONS.md`.

Contracts 2 and 5 are written out in full (drafted Oct 21). Each one also lists the **experiments** it is built to allow (rule 2: try every alternative and measure it) and the **failure paths** it must survive. The rest of the file is short because those contracts are simple.

| # | Contract | Between |
|---|---|---|
| 1 | Tools | Alice (W1) ↔ Bernard (W2) |
| 2 | Session protocol: agent ↔ web page | Alice (W1) ↔ Michael (W3) |
| 3 | Project layout | Alice (W1) ↔ Bernard (W2) ↔ Joseph (W4) |
| 4 | Benchmark format | Joseph (W4) ↔ everyone |
| 5 | Headless runs, experiment settings and the run record | Alice (W1) ↔ Joseph (W4), with Bernard (W2) for the sandbox setting |

---

## 1. Tools (Alice ↔ Bernard)

Each tool is a Python function plus a JSON-schema description the LLM sees. Every tool returns `{"ok": bool, "output": str}`. `output` is what the agent "observes", cut to a size limit.

| Tool | Arguments | Does |
|---|---|---|
| `write_file` | `path`, `content` | Writes a file inside the project folder only |
| `read_file` | `path` | Reads a file inside the project folder |
| `list_files` | — | Lists the project's files |
| `run_tests` | `path?` | Runs pytest in the sandbox, returns the summary and failures |
| `start_server` | — | Starts the backend in the sandbox, returns the base URL or the error |
| `http_request` | `method`, `path`, `json?` | Calls the running backend |
| `search_docs` | `query` | Searches the recipe knowledge base (RAG) |

To agree on the call: the output size limit (proposal: 4,000 characters, keeping the start and the end), and the error shape (proposal: `ok: false` plus a one-line reason first, then the details).

---

## 2. Session protocol: agent ↔ web page (Alice ↔ Michael)

### In plain words

One user building one API is a **session**. Messages go both ways:

- **Agent → page: events.** The agent narrates what it is doing ("Writing the code for orders…") and sends things for the user to look at (questions, the plan, test results, the finished API). These flow over one long-lived connection, Server-Sent Events (SSE), which is one-way, server to browser.
- **Page → agent: actions.** When the user answers a question, approves the plan or presses cancel, the page sends one small HTTP request.

Every event is also saved to `projects/<id>/events.jsonl`. That one file serves three purposes: a page that reloads can catch up, Michael can build the UI against a recording before the agent exists (task S1.4), and the report can show a real session step by step.

### Endpoints (served by the platform)

| Method and path | Body | Returns | Used for |
|---|---|---|---|
| `POST /sessions` | `{"request": "<plain words>", "settings": {…}?}` | `{"session_id"}` | Start a session. `settings` are the same experiment settings as contract 5, so the UI can switch variants too |
| `GET /sessions/{id}/events` | — | SSE stream of events | Live narration. Send the `Last-Event-ID` header on reconnect to get every missed event replayed |
| `POST /sessions/{id}/actions` | one action (below) | `202 {"accepted": true}`, or `409` with the reason if the action does not fit the current state | Everything the user does |
| `GET /sessions/{id}` | — | Snapshot: `state`, latest `plan`, `last_event_id`, links if done | Page reload or a second tab |
| `GET /sessions/{id}/download` | — | Zip of the generated code | "Take it away" |
| `GET /sessions/{id}/openapi.json` | — | The approved contract | For any frontend tool |

### States

A session is always in exactly one state. The events and actions below are only valid in the states listed.

```
describing → clarifying → planning → awaiting_approval → building → testing ⇄ repairing → running
                 ↑______________|  (request_changes sends it back to planning)
any state → cancelled · failed (from any state on an unrecoverable error)
running → planning  (a "change it" request, task S2.8)
```

| State | What is happening | Actions accepted |
|---|---|---|
| `describing` | Agent reads the request | `cancel` |
| `clarifying` | Agent waits for answers to its questions | `answer`, `skip_questions`, `cancel` |
| `planning` | Agent drafts or revises the plan | `cancel` |
| `awaiting_approval` | Plan shown; nothing is built until the user approves | `approve`, `request_changes`, `edit_plan`, `cancel` |
| `building` | Writing the contract and code | `cancel` |
| `testing` / `repairing` | Running tests, fixing failures | `cancel`, `reply` (if the agent sent `needs_input`) |
| `running` | Backend is live; links available | `change_request`, `cancel` (stops the server) |
| `failed` | Stopped on an error | `retry` (only if `recoverable`), `cancel` |
| `cancelled` | Stopped by the user | — |

### Events: agent → page

Every event has the same envelope:

```json
{"id": 17, "session_id": "a1b2", "ts": "2026-10-21T10:04:05Z", "type": "progress",
 "state": "building", "message": "Writing the code for orders (2 of 3)", "data": {}}
```

- `id` counts up by 1 per session. It is what `Last-Event-ID` refers to.
- `message` is always plain language, short enough to show as-is, so the page can display any event even if it does not understand its `data`.

| `type` | `data` | Page shows |
|---|---|---|
| `session_started` | `{"request"}` | The user's request echoed back |
| `clarify` | `{"questions": [{"id", "text", "kind": "free_text" \| "choice" \| "yes_no", "options"?, "default"?, "why"}]}` | The questions, with the reason for each ("so I know whether a customer can have many orders") |
| `plan` | `{"version", "resources": [{"name", "plain", "fields": [{"name", "plain_type", "required", "example"}], "relations": [{"to", "kind": "one_to_many" \| "many_to_many", "plain"}]}], "operations": [{"id", "plain", "method", "path"}], "rules": ["plain sentence"], "assumptions": ["plain sentence"]}` | Approval cards. `plain_type` is "text", "whole number", "money", "date", "yes/no" (never `str` or `int`) |
| `progress` | `{"step": "spec" \| "code" \| "tests" \| "start" \| "repair", "detail"?, "attempt"?}` | A progress line |
| `tool_call` | `{"agent", "tool", "summary"}` | Only in "show details" mode |
| `test_result` | `{"attempt", "passed", "failed", "total", "failures": [{"test", "plain_reason"}]}` | Progress bar and the reasons in plain words |
| `needs_input` | `{"question"}` | The agent is stuck and asks the user something mid-build |
| `done` | `{"base_url", "docs_url", "openapi_url", "download_url", "summary", "tests_passed"}` | Try-it panel and downloads |
| `error` | `{"code", "recoverable", "suggestion"}` | What went wrong and what the user can do |
| `cancelled` | — | Confirmation |
| `heartbeat` | — | Nothing. Sent every 15 s so proxies do not close an idle connection |

Error `code`s: `llm_unavailable`, `llm_rate_limited`, `budget_exceeded`, `timeout`, `sandbox_failed`, `tests_failing_after_repairs`, `unsafe_request`, `not_an_api` (e.g. "build me a website"), `internal`.

### Actions: page → agent

Every action is `{"type", "action_id", …}`. `action_id` is a random id made by the page, so a double-click sends the same id twice and the second is ignored.

| `type` | Fields | Effect |
|---|---|---|
| `answer` | `{"answers": {"<question id>": "<value>"}}` | Answers some or all questions |
| `skip_questions` | — | Agent proceeds on its stated assumptions or defaults |
| `approve` | `{"plan_version"}` | Starts the build. Refused with `409` if a newer plan version exists, so nobody approves a plan they have not seen |
| `request_changes` | `{"plan_version", "feedback": "<plain words>"}` | Back to `planning`; a new `plan` event follows with `version + 1` |
| `edit_plan` | `{"plan_version", "edits": [{"op": "rename" \| "add_field" \| "remove_field" \| "change_type", "target", "value"}]}` | Structured edits from clicking on the cards (an alternative to `request_changes`, see experiment E2.5) |
| `reply` | `{"text"}` | Answers a `needs_input` |
| `change_request` | `{"text"}` | "Also track which tailor is assigned": re-enters `planning` on the existing project |
| `retry` | — | Resumes after a recoverable error |
| `cancel` | — | Stops whatever is running and the server, if any |

### Failure paths it must handle (each one is a test case)

| What happens | Expected behaviour |
|---|---|
| User closes the tab mid-build and comes back | `GET /sessions/{id}` restores the screen; the build kept going |
| Network drops and reconnects | Browser reconnects with `Last-Event-ID`; missed events replayed, none duplicated |
| Double-click on Approve | Same `action_id` twice; second ignored |
| Approve an outdated plan (two tabs) | `409`, page shows the newest plan |
| An action in the wrong state (e.g. `approve` while building) | `409` with the current state |
| Cancel during the build | Build stops, sandbox and server stopped, `cancelled` event |
| LLM down or rate-limited | Retries with backoff, then `error` with `recoverable: true` |
| Budget or time limit reached | `error` `budget_exceeded` / `timeout`, partial project kept |
| Tests still failing after the last repair | `error` `tests_failing_after_repairs`, with the failing tests in plain words, and the option to keep the backend anyway |
| Empty or one-word request | A `clarify` event, never a crash |
| Very long request (pages of text) | Handled or politely limited, never silently cut |
| Not an API ("make me a logo") | `error` `not_an_api` with a suggestion |
| Harmful request ("also delete the server's files") | `error` `unsafe_request`; nothing run |
| Request or answers in Twi, Pidgin or mixed language | Understood, or a clarifying question in plain English |
| User contradicts an earlier answer | Agent notices and asks which one holds |
| Two sessions at the same time | Separate project folders, ports and sandboxes; no crossed events |

### Experiments this contract allows

| ID | Question | Options to compare | Measured by | Owner |
|---|---|---|---|---|
| E2.1 | How should events reach the page? | SSE + POST (default) · WebSocket · polling every 1 s | Delay from agent to screen, recovery after a dropped connection, lines of code | Michael |
| E2.2 | How many questions should the agent ask? | None (assume and list assumptions) · up to 3 · as many as it needs | Hidden-test pass rate on vague requests, user time, user rating | Alice, with Joseph's benchmark |
| E2.3 | How should questions be asked? | Free text · multiple choice with a default · yes/no only | Time to answer, how often answers are usable | Michael |
| E2.4 | How should the plan be shown? | Cards · plain list · simple diagram of the data · example sentences ("You will be able to: add an order…") | Usability test: do people spot a missing field? Time to approve | Michael |
| E2.5 | How should people change the plan? | Free-text feedback · clicking to edit the cards · both | Edits that come out as intended, time taken | Michael, with Alice |
| E2.6 | What should need approval? | The whole plan once · each resource · auto-approve with undo | Errors caught before building, user effort | Michael |
| E2.7 | How much detail while building? | Plain steps only · plus tool calls · plus live code | Perceived waiting, trust (usability test) | Michael |
| E2.8 | How should errors read? | Technical message · plain words + a suggestion | Can the user recover without help? | Michael |

---

## 3. Project layout (Alice ↔ Bernard ↔ Joseph)

```
projects/<id>/
  app/            generated FastAPI + SQLModel code (entry: app/main.py, object `app`)
  tests/          tests the agent generated from the spec
  openapi.json    the approved contract
  ops.json        mapping from benchmark operations to endpoints (benchmark runs only; see benchmark/README.md)
  project.json    long-term memory: approved plan, decisions, change history
  events.jsonl    every event of contract 2, one per line (UI and CLI runs alike)
  trace.jsonl     every LLM call and tool call (contract 5)
  run.json        the run record (contract 5)
```

---

## 4. Benchmark format (Joseph ↔ everyone)

See `benchmark/README.md` and the worked example `benchmark/church_signup/`. To support experiment E2.2 without a human, a task may also include:

- `answers.json`: what the client would answer to likely questions (`{"Can a customer have more than one order?": "Yes"}`)
- `client_brief.md`: the full hidden details, for a simulated user (contract 5, setting `clarify = simulated`)

---

## 5. Headless runs, experiment settings and the run record (Alice ↔ Joseph)

### In plain words

Evaluation means hundreds of builds: 15 tasks × several settings × repeats. Nobody can click through a UI that many times. So the agent also runs from the command line, with every design choice exposed as a **setting**. Every run writes a **run record**, `run.json`: what was tried, what happened, how long it took and what it cost. Joseph's harness then adds the hidden-test score and turns hundreds of run records into the results tables.

### The command

```
python -m builder build benchmark/church_signup/request.md --out projects/<id> --preset full [--set key=value ...]
python -m builder build ... --dry-run     # prints the resolved settings and an estimated cost; calls nothing
```

- Without the UI, the plan is approved automatically, and questions are answered according to the `clarify` setting.
- `--preset` loads `configs/<name>.toml`. `--set` overrides single settings: `--set repair=0 --set rag=none`.
- The same settings can be passed to `POST /sessions`, so the UI and the CLI run exactly the same code.

### Settings (every one is an experiment)

| Setting | Values (default first) | Question it answers | Owner |
|---|---|---|---|
| `model` | `claude-opus-5-5` · `claude-sonnet-5-5` · `claude-haiku-5-5` · `qwen-local` | How much does model size, cost and hosted vs local matter? | Alice |
| `effort` | `medium` · `low` · `high` (Claude only) | Does thinking harder fix more tests, and at what cost? | Alice |
| `temperature` | `0.7` · `0.2` · `1.0` (**Qwen only**: Claude Opus 5.5 rejects sampling settings) | Does randomness help or hurt code? | Alice |
| `agents` | `split` (Planner / Builder / Tester) · `single` | Does decomposition beat one agent? | Alice |
| `repair` | `3` · `0` · `1` · `5` | How many fix attempts are worth it? | Alice |
| `spec_first` | `on` · `off` | Does writing the contract first help? | Alice |
| `prompt` | `v1` · any file in `prompts/` | Which prompt wording works best? | Alice |
| `context` | `trim` · `full` · `summarize` | How should the agent keep its history within budget? | Alice |
| `clarify` | `answers_file` · `none` · `simulated` | Do questions help, and can an LLM playing the client stand in for a human? | Alice, Joseph |
| `rag` | `bm25` · `none` · `dense` | Does retrieval help, and which kind? | Joseph |
| `rag_k` | `3` · `1` · `5` | How many recipes to retrieve? | Joseph |
| `sandbox` | `docker` · `subprocess` | Speed vs isolation | Bernard |
| `max_steps` | `60` | Stops runaway loops | Alice |
| `budget_usd` | `1.00` | Hard cost cap per run | Joseph |
| `timeout_min` | `15` | Hard time cap per run | Bernard |
| `repeat` | `1` · `2` · `3` | How much do results vary from run to run? | Joseph |
| `cache` | `off` · `on` (replay saved LLM answers) | Cheap re-runs when only scoring changes; never mixed into reported numbers | Joseph |

Named presets in `configs/`: `full`, `no_repair`, `single_agent`, `no_rag`, `no_spec`, `local_qwen`, and any new ones people add. Costs are computed from a price table in `configs/prices.toml` (as of Oct 2026, per million tokens in/out: Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50, local $0).

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Built, server starts, agent's own tests pass |
| 1 | Built, but tests still failing after the last repair |
| 2 | Build failed (server never started) |
| 3 | Refused (`unsafe_request` or `not_an_api`) |
| 4 | Stopped by `budget_usd`, `timeout_min` or `max_steps` |
| 5 | Infrastructure error (LLM or sandbox unavailable) |
| 130 | Cancelled with Ctrl-C |

`run.json` is written in **every** case, including crashes and Ctrl-C, so a failed run still counts in the results.

### The run record: `run.json`

```json
{
  "run_id": "2026-10-22T09-15-02_church_signup_full_r1",
  "task_id": "church_signup",
  "git_commit": "e66c959",
  "started_at": "2026-10-22T09:15:02Z", "finished_at": "2026-10-22T09:19:40Z", "seconds_total": 278,
  "settings": {"model": "claude-opus-5-5", "effort": "medium", "agents": "split", "repair": 3, "spec_first": "on",
               "prompt": "v1", "context": "trim", "clarify": "answers_file", "rag": "bm25", "rag_k": 3,
               "sandbox": "docker", "max_steps": 60, "budget_usd": 1.0, "timeout_min": 15, "repeat": 1, "cache": "off"},
  "outcome": "success",
  "exit_code": 0,
  "error": null,
  "phases": {
    "clarify": {"seconds": 12, "questions_asked": 2, "questions_answered": 2},
    "plan":    {"seconds": 20, "versions": 1, "resources": 2, "operations": 5},
    "spec":    {"seconds": 15},
    "code":    {"seconds": 95, "files": 6, "lines": 212},
    "test":    {"seconds": 40, "attempts": [{"attempt": 0, "passed": 9, "failed": 2}, {"attempt": 1, "passed": 11, "failed": 0}]},
    "repair":  {"attempts_used": 1, "seconds": 70}
  },
  "llm": {
    "calls": 23, "input_tokens": 61200, "output_tokens": 9800, "cache_read_tokens": 30500, "cost_usd": 0.44,
    "by_agent": {"planner": {"calls": 4, "input_tokens": 9100, "output_tokens": 2100, "cost_usd": 0.08},
                 "builder": {"calls": 13, "input_tokens": 38000, "output_tokens": 6200, "cost_usd": 0.28},
                 "tester":  {"calls": 6, "input_tokens": 14100, "output_tokens": 1500, "cost_usd": 0.08}}
  },
  "tools": {"calls": 41, "errors": 2, "by_tool": {"write_file": 9, "read_file": 6, "run_tests": 3, "start_server": 2,
            "http_request": 12, "search_docs": 7, "list_files": 2}},
  "retrieval": {"queries": 7, "recipes_returned": 21, "recipes_used_in_code": null},
  "hidden_tests": null,
  "spec_fidelity": null,
  "notes": ""
}
```

- The numbers above are an illustration of the shape, not results.
- `hidden_tests` is filled in by Joseph's harness after the run: `{"total": 10, "passed": 10, "pass_rate": 1.0, "failures": []}`. The agent never sees these tests.
- `spec_fidelity` is filled in by hand: did every requirement in the request reach the plan (0–1 per requirement)?
- `outcome` is one of `success`, `tests_failing`, `build_failed`, `refused`, `budget_exceeded`, `timeout`, `infra_error`, `cancelled`.

### The trace: `trace.jsonl`

One line per LLM call or tool call, in order. This is the raw material for the ReAct trace in the report (Section A topic n) and for debugging.

```json
{"step": 7, "agent": "builder", "kind": "llm", "model": "claude-opus-5-5", "input_tokens": 3100, "output_tokens": 640, "cache_read_tokens": 2400, "ms": 4100, "stop_reason": "tool_use"}
{"step": 8, "agent": "builder", "kind": "tool", "tool": "write_file", "args_summary": "app/models.py (48 lines)", "ok": true, "ms": 3, "output_preview": "wrote 48 lines"}
```

### Where results go

Joseph's harness writes `eval/results/<experiment>/<task>/<repeat>/run.json` (plus the project folder) and one `eval/results/<experiment>/summary.csv` with a row per run. Charts and tables in the report come only from these files.

### Failure paths it must handle

| What happens | Expected behaviour |
|---|---|
| LLM times out or is rate-limited | Retry with backoff (3 tries), then exit 5, `outcome: infra_error` |
| Agent loops (same tool call over and over) | Stopped by `max_steps`, exit 4 |
| Agent tries to write outside the project folder | Tool refuses (`ok: false`); counted in `tools.errors` |
| Generated server never starts | Exit 2, with the server log saved in the project folder |
| A test hangs | Killed by the test timeout; counted as failed |
| Run crashes mid-way | `run.json` still written with what is known, `outcome: infra_error` |
| Ctrl-C | Sandbox stopped, `run.json` written, exit 130 |
| Same task and settings run twice | Different `run_id`; never overwrites |
| Qwen server not running for `model = qwen-local` | Exit 5 with "start llama-server first" |

### Before a batch of runs

`--dry-run` on the batch prints the number of runs and an estimated cost: tasks × presets × repeats × the average cost from earlier runs. Check it before starting anything large, because every hosted run spends real money.

# Contracts (DRAFT — agree on day 1)

These are the points where one person's work plugs into another's. Agree on them first, then build in parallel. Change one only after telling the people on both sides.

## 1. Tool interface (W1 ↔ W2)

Each tool is a Python function with a JSON-schema description the LLM sees. Every tool returns `{"ok": bool, "output": str}`; `output` is what the agent observes, cut to a size limit.

| Tool | Arguments | Does |
|---|---|---|
| `write_file` | `path`, `content` | Writes a file inside the project folder only |
| `read_file` | `path` | Reads a file inside the project folder |
| `list_files` | — | Lists the project's files |
| `run_tests` | `path?` | Runs pytest in the sandbox, returns the summary and failures |
| `start_server` | — | Starts the backend in the sandbox, returns the base URL or the error |
| `http_request` | `method`, `path`, `json?` | Calls the running backend |
| `search_docs` | `query` | Searches the recipe knowledge base (RAG) |

## 2. Event stream (W1 ↔ W3)

Server-Sent Events from the platform to the page. Every event is JSON with `type` and a plain-language `message`.

| `type` | Extra fields | Page shows |
|---|---|---|
| `clarify` | `questions: [str]` | Questions for the user to answer |
| `plan` | `resources`, `endpoints` (plain-language) | Approval cards; nothing is built until the user approves |
| `progress` | `step` | "Writing the code for orders..." |
| `test_result` | `passed`, `failed` | Progress bar |
| `done` | `base_url`, `docs_url`, `download_url` | Try-it panel |
| `error` | — | What went wrong, in plain words |

## 3. Project layout (W1 ↔ W2 ↔ W4)

```
projects/<id>/
  app/            generated FastAPI + SQLModel code (entry: app/main.py, object `app`)
  tests/          tests the agent generated from the spec
  openapi.json    the approved contract
  ops.json        mapping from benchmark operations to endpoints (benchmark runs only; see benchmark/README.md)
  project.json    long-term memory: approved spec, decisions, change history
```

## 4. Benchmark format (W4 ↔ all)

See `benchmark/README.md`.

## 5. Headless entry point (W1 ↔ W4)

```
python -m builder build benchmark/<task>/request.md --out projects/<id> --config full|no_repair|single_agent|no_rag|no_spec
```

The CLI auto-approves the plan, so evaluation runs with no UI and no human.

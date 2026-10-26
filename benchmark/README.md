# Benchmark (DRAFT format — W4 owns, change freely)

15 plain-language requests (5 easy, 5 medium, 5 hard), each with hidden tests the agent never sees. Joseph writes them in Stage 2, before anyone builds the agent, so the agent is never tuned against tests it has seen. `church_signup/` is a complete worked example: copy it.

## One task = one folder

```
benchmark/<task>/
  request.md          what a non-developer would type. No URLs, no field names, no tech words
  operations.json     the operations the hidden tests use, each with a plain description
  hidden_tests/       pytest files that call operations by name, never by URL
  reference/          a small hand-written backend that passes the tests (proves the tests are right)
  reference_b/        optional: a second correct backend that makes other valid choices (text ids, 200 instead of 201, 422 instead of 400)
  mutants/            3-5 deliberately broken copies of reference/app.py, one realistic bug each; the hidden tests must catch every one
  answers.json        optional: what the client would answer to likely questions, so the agent's questions can be answered without a human
  client_brief.md     optional: the full hidden details, for an LLM that plays the client
```

Write at least one task per tier as a **vague** request (details left out on purpose). Those are the tasks that show whether asking questions helps (Alice's clarifying-questions experiment, task S3.8).

## Why operations instead of URLs

The agent may call it `/events` or `/church-events`, `capacity` or `max_people`. That is not a mistake, and the tests must not punish it. So the tests say `api.call("create_event", json={"name": ..., "capacity": ...})`. After a build, the agent writes `ops.json`, which maps each operation to its real method, path and field names. `conftest.py` translates the call. The reference backend deliberately uses different names (`title`, `max_people`) to prove the translation works.

`ops.json` shape:

```json
{"create_event": {"method": "POST", "path": "/events", "fields": {"name": "title", "capacity": "max_people"}},
 "get_event": {"method": "GET", "path": "/events/{id}"}}
```

`fields` maps test names to backend names (left out if they are the same). Path placeholders are filled from `path_params`.

## Checking a task: `benchmark/validate.py`

```
uv run python benchmark/validate.py church_signup     # one task; no argument = every task
```

It starts each backend in Bernard's sandbox, exactly as the harness will, and runs the hidden tests against it. A task is ✅ only if:
- the reference passes every test **twice on the same server** (leftover data must not matter) and **in reverse order** (no test may depend on another);
- `reference_b/`, if present, also passes every test (the tests are not too strict);
- **every mutant fails at least one test** (the tests are not too weak);
- it has at least 8 tests and 3 mutants.

Results go to `benchmark/validation.json`. The checker was itself tested on 5 deliberately bad tasks (a mutant identical to the reference, a wrong reference, one that does not start, an order-dependent test, a test that needs an empty server): it flagged all 5.

## Rules for writing hidden tests

- Test behaviour, not wording: "after signing up, the person appears in the list", "signing up for a full event is refused (any 4xx)".
- 8–15 tests per task. Cover the happy path, the business rules, and bad input.
- Each test starts from its own fresh data (create what you need inside the test), never assumes the server is empty, and never relies on another test having run.
- Accept every reasonable choice the request leaves open: any 2xx for success, any 4xx for refusals unless the request says which, ids as numbers or text, lists in any order unless the request asks for an order.
- Anything a test checks must be stated in `request.md` or, for a vague task, in `client_brief.md` and `answers.json`.
- Your reference backend must pass all of them before you commit.

## Running a task against a backend

```
uv run uvicorn --app-dir benchmark/church_signup/reference app:app --port 8001   # or a generated backend
BASE_URL=http://127.0.0.1:8001 OPS_FILE=benchmark/church_signup/reference/ops.json uv run pytest benchmark/church_signup
```

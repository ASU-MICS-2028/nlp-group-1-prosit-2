# Benchmark (DRAFT format — W4 owns, change freely)

15 plain-language requests (5 easy, 5 medium, 5 hard), each with hidden tests the agent never sees. Everyone writes 3 (one per tier) on day 1. `church_signup/` is a complete worked example: copy it.

## One task = one folder

```
benchmark/<task>/
  request.md          what a non-developer would type. No URLs, no field names, no tech words
  operations.json     the operations the hidden tests use, each with a plain description
  hidden_tests/       pytest files that call operations by name, never by URL
  reference/          a small hand-written backend that passes the tests (proves the tests are right)
```

## Why operations instead of URLs

The agent may call it `/events` or `/church-events`, `capacity` or `max_people`. That is not a mistake, and the tests must not punish it. So the tests say `api.call("create_event", json={"name": ..., "capacity": ...})`. After a build, the agent writes `ops.json`, which maps each operation to its real method, path and field names. `conftest.py` translates the call. The reference backend deliberately uses different names (`title`, `max_people`) to prove the translation works.

`ops.json` shape:

```json
{"create_event": {"method": "POST", "path": "/events", "fields": {"name": "title", "capacity": "max_people"}},
 "get_event": {"method": "GET", "path": "/events/{id}"}}
```

`fields` maps test names to backend names (left out if they are the same). Path placeholders are filled from `path_params`.

## Rules for writing hidden tests

- Test behaviour, not wording: "after signing up, the person appears in the list", "signing up for a full event is refused (any 4xx)".
- 8–15 tests per task. Cover the happy path, the business rules, and bad input.
- Each test starts from its own fresh data (create what you need inside the test).
- Your reference backend must pass all of them before you commit.

## Running a task against a backend

```
uv run uvicorn --app-dir benchmark/church_signup/reference app:app --port 8001   # or a generated backend
BASE_URL=http://127.0.0.1:8001 OPS_FILE=benchmark/church_signup/reference/ops.json uv run pytest benchmark/church_signup
```

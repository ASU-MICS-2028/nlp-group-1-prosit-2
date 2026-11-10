# Do the runtime tests pass on Windows?

Typed by hand from a teammate's report (Bernard, W2). The Mac results are from `pytest` on the same day.

| Run | Machine | Command | Result |
|---|---|---|---|
| Before the fix, fresh pull of `main` | Windows 11, Docker Desktop 29.9.1 | `uv run pytest runtime -q` | 5 failed, 61 passed, 4 min 39 s |
| Before the fix, new closing test | Mac | `pytest runtime/tests/test_database_closed.py` | 1 failed |
| After the fix, new closing test | Mac | same | 1 passed |
| After the fix, database check | Mac | `pytest runtime/tests/test_keeps_database.py` | 9 passed |
| After the fix | Windows 11 | `uv run pytest runtime -q` | **Not run yet** |

The 5 failures were all in `runtime/tests/test_keeps_database.py`, on the check that the `db_check` folder was removed. The check's answers were right each time. `runtime/deploy.py` left the SQLite connection open, and Windows cannot delete an open file. Mac and Linux can, so the server was never affected.

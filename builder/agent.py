"""The agent (W1): a hand-written ReAct loop (decision 0003) over Bernard's tools (runtime/tools.py).

    from builder.agent import build
    result = build(request_text, "projects/run1/church_signup", model="claude-opus-5-5")

Each turn: send Claude the conversation and the tool list; run every tool it asks for, always in our project
folder (the LLM never chooses root); send the results back, marked as errors when ok is false. Stop when Claude
answers without asking for a tool, or after max_turns. Every run leaves trace.jsonl and run.json in the folder (S3.3).
"""

import ast
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace as Obj

import anthropic
import httpx

from eval.llm import PRICES, ask
from runtime import tools

FILE = """You build backends for people who do not code. In the project folder, write ONE complete file, app.py,
containing a FastAPI application in a variable named app. Use only fastapi, pydantic, sqlmodel and the Python standard
library. """
RULES = """Do everything the client asks, refuse what the client says must be refused with a 4xx status, and return
JSON.

"""
MEMORY = "Keep data in memory (or in a SQLite file in the current folder). "
SQLITE = "Store the data with SQLModel in a SQLite file in the current folder, creating the tables when the app starts. "
TESTED = """You have tools to write files, run pytest and start the server. Work like this: write app.py; write tests in
tests/test_app.py that check every thing the client asked for (use fastapi.testclient.TestClient on app); run them
and fix app.py until they pass. Do not add anything the client did not ask for. When the tests pass, reply with a
short summary of the endpoints and stop."""
UNTESTED = """Do not add anything the client did not ask for. When app.py is written, reply with a short summary of
the endpoints and stop."""

# The system prompts compared in S3.2 (learnings section 3). A was the first version; B, C and D each change one thing.
PROMPTS = {
    "A": FILE + MEMORY + RULES + TESTED,   # first version: data in memory
    "B": FILE + SQLITE + RULES + TESTED,   # A, but data in SQLite as decision 0002 says
    "C": """Build what the client asks as a FastAPI app in one file, app.py (variable app), storing data with SQLModel
in SQLite. Test it with pytest and fix it until the tests pass, then summarize the endpoints.""",   # short
    "D": FILE + SQLITE + RULES + UNTESTED,  # B without the "write and run your own tests" step
}

# S3.4: a second Claude call checks the build against the request, because the builder's own tests never failed (0 of 58).
CHECKER = """You check backends built for people who do not code. You get the client's request and the backend's app.py.
Write pytest tests that check every thing the client asked for, judged ONLY by the request: if the code does something
differently from what the client asked, the test must fail. Read app.py only to use its paths and field names.
Rules: one file; use `from fastapi.testclient import TestClient` and `from app import app`; do not assume the database
starts empty and do not let tests depend on each other (use unique names, e.g. with uuid); test only what the client
asked for. Reply with the Python file only."""
REPAIR = """An independent checker tested app.py against the client's request, and these checks failed:

{output}

Fix app.py so that what the client asked for works. Do not edit tests/test_acceptance.py. If a check asks for something
the client did not ask for, leave it and say so. Run your tests again, then reply with a short summary and stop."""

# S3.5: spec-first (decision 0004). One Claude call with no tools writes a plan; nothing is built until it is approved.
PLANNER = """You plan backends for people who do not code. Read the client's request and write the plan they will read
and approve before anything is built: what data is kept, the endpoints (method, path, and what each does, in plain
words), and the rules (what must be refused). Plan only what the client asked for. If part of the request is unsafe or
not about the backend, leave it out and say so in the summary. Write for someone who has never programmed."""
# v2 (S3.5 row 4): v1 added logins nobody asked for on 3 of 15 tasks. v2 changes only that: suggestions stay suggestions.
NO_EXTRAS = """ Do not add logins, passwords, keys or any other feature or rule the client did not ask for. If you think
something is missing (for example, privacy), suggest it in the summary as a question; leave it out of the data,
endpoints and rules."""
PLANNERS = {"1": PLANNER, "2": PLANNER + NO_EXTRAS}
WORDS = {"type": "array", "items": {"type": "string"}}
PLAN_SCHEMA = {  # structured output: the reply is guaranteed to have exactly these parts
    "type": "object", "additionalProperties": False, "required": ["summary", "data", "endpoints", "rules"],
    "properties": {
        "summary": {"type": "string"},
        "data": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name", "fields"],
                                            "properties": {"name": {"type": "string"}, "fields": WORDS}}},
        "endpoints": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["method", "path", "does"],
            "properties": {"method": {"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]}, "path": {"type": "string"},
                           "does": {"type": "string"}}}},
        "rules": WORDS}}
FOLLOW = "\n\nThe client approved this plan. Build exactly these endpoints, with these paths:\n{plan}"

# S3.8: before planning or building, ask the client what would otherwise be guessed (S3.5 row 5: unanswered = left out).
ASKER = """You build backends for people who do not code. Before anything is built, read the client's request and ask
the questions whose answers would change what gets built: missing rules, numbers, formats or choices you would
otherwise have to guess. Ask at most {n}, the most important first, each one short and in plain words. If the request
is already clear, ask none."""
# S3.8 row: asked "Should customers need a PIN?", a client with no preference got a PIN built in (momo 13/13 to 1/13).
SIMPLEST = ("Where the client has no preference or did not answer, choose the simplest option and add nothing they did "
            "not ask for (no logins, PINs or extra required fields).")
QUESTIONS = {"type": "object", "additionalProperties": False, "required": ["questions"], "properties": {"questions": WORDS}}

# One definition per tool (Bernard's section 6): the docstring is the description; root is never offered to the LLM.
STRING = {"type": "string"}
PARAMS = {
    "write_file": ({"path": STRING, "content": STRING}, ["path", "content"]),
    "read_file": ({"path": STRING}, ["path"]),
    "edit_file": ({"path": STRING, "old": STRING, "new": STRING}, ["path", "old", "new"]),
    "list_files": ({}, []),
    "run_tests": ({"path": {"type": "string", "description": "file or folder of tests, default tests"}}, []),
    "start_server": ({}, []),
    "http_request": ({"method": STRING, "path": {"type": "string", "description": "starts with /, e.g. /events"},
                      "json": {"type": "object", "description": "request body, if any"}}, ["method", "path"]),
    "stop_server": ({}, []),
}
TOOLS = [{"name": name, "description": getattr(tools, name).__doc__,
          "input_schema": {"type": "object", "properties": props, "required": required}}
         for name, (props, required) in PARAMS.items()]

# S3.7: Joseph's recipe search (kb/search.py, decision 0037) as one more tool, only when build(search=True).
SEARCH_TOOL = {"name": "search_docs", "input_schema": {"type": "object", "properties": {"query": STRING}, "required": ["query"]},
               "description": "Search the team's 18 short recipes for FastAPI, SQLModel and pytest (for example 'two people "
                              "booked the same room' or 'table has no primary key'). Returns the 3 best; judge whether they fit."}
SEARCH_HINT = " You can also search_docs for a short recipe when you are unsure how to do something or a test fails."
# S3.10: a follow-up request edits the existing app instead of rebuilding it.
CHANGE = """The client's app is already built in this folder (app.py and its tests). They first asked for it like this:

{request}

Now they want this change:

{change}

Read app.py, change only what is needed with edit_file (do not rewrite the whole file), keep everything else working,
add tests for the change, run all the tests, and reply with a short summary of what changed."""
NEW_MESSAGE = """The client sent a new message while you work. It changes what they want, so follow it, then carry on:

{message}"""
# S4.8: the builder writes notes for a programmer; the client reads this instead. Runs after the build, so it cannot change the app.
PLAIN = """You tell people who do not code what has just been built for them. You get what they asked for and the builder's
technical notes. Rewrite the notes for them, in short plain sentences: first that it is ready; then, as a short list, what they
can do with it; what it turns away; choices that were made for them; and anything they asked for that was left out. Use only
facts from the notes and never promise more than they say. It is already published on the internet when they read this, so
drop any remark that it has not been run or is not live, but keep every warning about who can reach it. Never mention web addresses or paths, GET or POST, file or
database names, code, JSON or status numbers, and never use words like endpoint, API, server, database, SQLite, schema,
field, query, pytest or test (say "checks"). Plain text only: no markdown, except "- " for list items."""
LOCAL_URL = os.environ.get("LOCAL_LLM_URL", "http://localhost:8090/v1") + "/chat/completions"  # S3.9, knowledge/environment.md

_client = None


def call(model, system, messages, effort, tools=TOOLS):
    """One request. Top-level cache_control caches the conversation so far: each turn re-reads it at 10% of the price."""
    global _client
    if model.endswith("-local"):
        return call_local(system, messages, tools)
    if not _client:
        if not os.environ.get("LLM_API_KEY"):  # build() reports this as an error instead of crashing
            raise anthropic.AnthropicError("LLM_API_KEY is not set: run with --env-file .env")
        _client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], max_retries=4)
    args = dict(model=model, max_tokens=16000, system=system, tools=tools, messages=messages,
                output_config={"effort": effort}, cache_control={"type": "ephemeral"})
    if model.startswith("claude-opus"):  # same refusal fallback as Joseph's eval.llm
        return _client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **args)
    return _client.messages.create(**args)


def call_local(system, messages, tools):
    """The same turn on the local model (S3.9). llama.cpp speaks OpenAI's format, so translate there and back: our
    conversation becomes OpenAI messages, and its reply comes back shaped like Claude's (text and tool_use blocks)."""
    chat = [{"role": "system", "content": system}]
    for m in messages:
        c = m["content"]
        if isinstance(c, str):  # the request, a repair request
            chat.append({"role": m["role"], "content": c})
        elif m["role"] == "assistant":
            calls = [{"id": b.id, "type": "function", "function": {"name": b.name, "arguments": json.dumps(b.input)}}
                     for b in c if b.type == "tool_use"]
            chat.append({"role": "assistant", "content": text_of(c), **({"tool_calls": calls} if calls else {})})
        else:  # the results of our tools, one message each
            chat += [{"role": "tool", "tool_call_id": r["tool_use_id"], "content": ("ERROR: " if r["is_error"] else "") + r["content"]}
                     if r["type"] == "tool_result" else {"role": "user", "content": r["text"]} for r in c]
    body = {"messages": chat, "max_tokens": 16000, "chat_template_kwargs": {"enable_thinking": os.environ.get("LOCAL_THINKING") == "1"},
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                         "parameters": t["input_schema"]}} for t in tools]}
    r = httpx.post(LOCAL_URL, json=body, timeout=3600).json()
    if "choices" not in r:  # e.g. the conversation no longer fits the context window
        raise RuntimeError(f"local model: {r.get('error', r)}"[:300])
    choice, u = r["choices"][0], r["usage"]
    msg = choice["message"]
    content = [Obj(type="text", text=msg["content"])] if msg.get("content") else []
    for t in msg.get("tool_calls") or []:
        try:
            args = json.loads(t["function"]["arguments"])
        except ValueError:  # not JSON: run_tool will answer "Bad arguments"
            args = {"unreadable": t["function"]["arguments"]}
        content.append(Obj(type="tool_use", id=t["id"], name=t["function"]["name"], input=args))
    stop = "tool_use" if msg.get("tool_calls") else {"stop": "end_turn", "length": "max_tokens"}.get(choice["finish_reason"], choice["finish_reason"])
    return Obj(stop_reason=stop, content=content, usage=Obj(input_tokens=u["prompt_tokens"], output_tokens=u["completion_tokens"],
                                                            cache_creation_input_tokens=0, cache_read_input_tokens=0))


def search_docs(query):
    """The 3 best recipes as text. Dense search needs `uv run --extra kb`; without it, keyword search (BM25)."""
    from kb.search import search_docs as find
    try:
        found = find(query, 3)
    except ImportError:
        found = find(query, 3, method="bm25")
    return {"ok": True, "output": "\n\n".join(f"Recipe {r['id']}: {r['text']}" for r in found) or "No recipe matches."}


def cost(model, u):
    """US dollars for one reply: new input, cache writes (1.25x), cache reads (0.1x), output."""
    price_in, price_out = PRICES[model]
    written = getattr(u, "cache_creation_input_tokens", 0) or 0
    read = getattr(u, "cache_read_input_tokens", 0) or 0
    return (u.input_tokens * price_in + written * price_in * 1.25 + read * price_in * 0.1 + u.output_tokens * price_out) / 1e6


def run_tool(root, name, args, search=False):
    if search and name == "search_docs":
        try:
            return search_docs(**args)
        except TypeError as e:
            return {"ok": False, "output": f"Bad arguments for search_docs: {e}"}
    if name not in PARAMS:
        return {"ok": False, "output": f"Unknown tool {name!r}"}
    try:
        return getattr(tools, name)(root, **args)
    except TypeError as e:  # wrong or missing arguments: tell the LLM instead of crashing
        return {"ok": False, "output": f"Bad arguments for {name}: {e}"}


def tokens_of(u):
    """The four token counts of one reply."""
    return {"in": u.input_tokens, "out": u.output_tokens,
            "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0}


def text_of(content):
    """The text Claude wrote in one reply (tool requests and thinking left out)."""
    return "".join(b.text for b in content if getattr(b, "type", "") == "text")


def test_counts(output):
    """Pytest's last line, e.g. "1 failed, 6 passed in 0.31s", as {"passed": 6, "failed": 1}. Errors count as failed."""
    found = {word: int(n) for n, word in re.findall(r"(\d+) (passed|failed|error)", output)}
    return {"passed": found.get("passed", 0), "failed": found.get("failed", 0) + found.get("error", 0)}


def code_of(text):
    """The Python code in a reply, without the ``` fences Claude may put around it."""
    found = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return found.group(1) if found else text


def check(root, request, model, checks=None):
    """Run the independent checker's tests on app.py. checks is the test file's text; the first time it is None and a
    separate Claude call writes it from the request. Returns (checks, run_tests result, cost in US dollars)."""
    usd = 0.0
    if checks is None:
        text, info = ask(model, CHECKER, f"The client's request:\n{request}\n\napp.py:\n{(root / 'app.py').read_text()}")
        checks, usd = code_of(text), info["cost_usd"]
    tools.write_file(root, "tests/test_acceptance.py", checks)  # put the original back, in case the builder changed it
    for db in root.glob("*.db"):  # start from an empty database, as the harness does
        db.unlink()
    return checks, tools.run_tests(root, "tests/test_acceptance.py"), usd


def make_plan(request, model="claude-opus-5-5", old=None, changes=None, planner="2"):
    """Draft a plan (S3.5), or redo the old plan with the client's changes. planner picks the instructions in PLANNERS.
    Returns (plan dict, cost in US dollars)."""
    if not request.strip():
        raise ValueError("empty request")
    user = f"The client's request:\n{request}"
    if old:
        user += f"\n\nYour previous plan:\n{json.dumps(old)}\n\nThe client wants these changes:\n{changes}"
    text, info = ask(model, PLANNERS[planner], user, schema=PLAN_SCHEMA)
    return json.loads(text), info["cost_usd"]


def plan_text(plan):
    """The plan in plain words, for the client to read."""
    lines = [plan["summary"], "", "What is kept:"]
    lines += [f"- {d['name']}: {', '.join(d['fields'])}" for d in plan["data"]]
    lines += ["", "What you can do:"] + [f"- {e['does']}  ({e['method']} {e['path']})" for e in plan["endpoints"]]
    lines += ["", "Rules:"] + [f"- {r}" for r in plan["rules"] or ["none"]]
    return "\n".join(lines)


def clarify(request, n=3, model="claude-opus-5-5"):
    """Up to n questions for the client (S3.8), most important first. Returns (questions, cost in US dollars)."""
    if n <= 0 or not request.strip():
        return [], 0.0
    text, info = ask(model, ASKER.format(n=n), f"The client's request:\n{request}", schema=QUESTIONS)
    return [q for q in json.loads(text)["questions"] if q.strip()][:n], info["cost_usd"]


def plain_summary(request, notes, model="claude-opus-5-5"):
    """The builder's notes, rewritten for someone who does not code (S4.8). Returns (text, cost in US dollars)."""
    text, info = ask(model, PLAIN, f"What the client asked for:\n{request}\n\nThe builder's notes:\n{notes}")
    return text.strip(), info["cost_usd"]


def with_answers(request, questions, answers):
    """The request with the client's answers added, as the builder (and the checker) will read it."""
    if not questions:
        return request
    qa = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(questions, answers))
    return f"{request}\n\nThe client's answers to your questions:\n{qa}\n\n{SIMPLEST}"


def load_plan(root):
    """The approved plan saved in root/plan.json. Raises ValueError if there is none or it is broken: no plan, no build."""
    try:
        plan = json.loads((Path(root) / "plan.json").read_text())
        plan_text(plan)  # every part a plan needs is there, with the right shape
        return plan
    except FileNotFoundError:
        raise ValueError("no approved plan: run the plan command first") from None
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"plan.json is broken ({type(e).__name__}): run the plan command again") from None


def endpoint(method, path):
    """'GET /events/{event_id}/?date=X' -> 'GET /events/{}': names inside {}, a last / and the ?search part do not
    change the endpoint (plans write '/fares?from=STOP&to=STOP', the code '/fares')."""
    return f"{method.upper()} {re.sub(r'{[^}]*}', '{}', path.split('?')[0]).rstrip('/') or '/'}"


def routes_of(code):
    """The endpoints in app.py, found by READING it (never running it): decorators like @app.get("/events").
    Does not see APIRouter prefixes. A file that is not valid Python has none."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return {endpoint(d.func.attr, d.args[0].value) for node in ast.walk(tree) for d in getattr(node, "decorator_list", [])
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("get", "post", "put", "patch", "delete")
            and d.args and isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str)}


def follows_plan(code, plan):
    """Which planned endpoints app.py lacks, and which it has that were not planned."""
    planned, built = {endpoint(e["method"], e["path"]) for e in plan["endpoints"]}, routes_of(code)
    return {"missing": sorted(planned - built), "extra": sorted(built - planned)}


def build(request, root, model="claude-opus-5-5", effort="medium", prompt="B", max_turns=40, max_usd=2.0, on_event=None,
          max_repairs=0, plan=None, search=False, change=None, inbox=None):
    """Run the loop. Stops when Claude finishes ("end_turn"), or at max_turns, max_usd or an error (always reported).

    With max_repairs > 0, each time Claude finishes, an independent checker tests app.py against the request; failures
    are sent back to Claude to fix, at most max_repairs times. app.py is saved after every round as rounds/app_N.py.
    With plan (an approved plan from make_plan), Claude gets the request plus the plan; the checker still sees only the request.
    With search, Claude also gets the search_docs tool (S3.7). A model ending in -local runs on llama.cpp (S3.9).
    With change (S3.10), Claude edits the app already in root; the last run's files are kept in root/history/.
    With inbox (a function returning the client's new messages, usually none), Claude sees them between turns (Lecture 8).

    Writes two files in root: trace.jsonl, one line per event as it happens (start, reply, tool, check, end), and
    run.json, the totals. on_event, if given, is called with every event too, so a UI can show the build live."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    start = time.time()
    if change:  # keep the last run's record and app, numbered: history/run_1.json, trace_1.jsonl, app_1.py, ...
        n = len(list((root / "history").glob("run_*.json"))) + 1
        (root / "history").mkdir(exist_ok=True)
        for name, saved in (("run.json", f"run_{n}.json"), ("trace.jsonl", f"trace_{n}.jsonl"), ("app.py", f"app_{n}.py")):
            if (root / name).exists():
                (root / "history" / saved).write_text((root / name).read_text())
        first = CHANGE.format(request=request, change=change)
    else:
        first = request + (FOLLOW.format(plan=json.dumps(plan, indent=1)) if plan else "")
    messages = [{"role": "user", "content": first}]
    calls, usd, stop, turns, tests = [], 0.0, "max_turns", 0, None
    repairs, checks, checked = 0, None, None  # repairs used, the checker's test file, the app.py it last checked
    tokens = {"in": 0, "out": 0, "cache_write": 0, "cache_read": 0}
    if not request.strip():  # nothing to build: do not pay for a call
        stop, max_turns = "empty request", 0
    elif change is not None and (not change.strip() or not (root / "app.py").exists()):
        stop, max_turns = "nothing to change" if not change.strip() else "no app.py to change: build it first", 0
    with open(root / "trace.jsonl", "w", encoding="utf-8") as trace:

        def log(event, **fields):
            line = {"event": event, "t": round(time.time() - start, 2), **fields}  # t = seconds since the start
            trace.write(json.dumps(line, default=str) + "\n")
            trace.flush()  # on disk at once: a UI can follow it, and a crash keeps what happened so far
            if on_event:
                on_event(line)

        def new_messages():
            found = inbox() if inbox else []
            for text in found:
                log("message", text=text)
            return [{"type": "text", "text": NEW_MESSAGE.format(message=text)} for text in found]

        log("start", request=request, model=model, prompt=prompt, effort=effort, plan=plan, search=search, change=change)
        try:
            for turn in range(max_turns):
                if usd >= max_usd:
                    stop = "max_usd"
                    break
                reply = call(model, PROMPTS[prompt] + (SEARCH_HINT if search else ""), messages, effort,
                             TOOLS + [SEARCH_TOOL] if search else TOOLS)
                turns += 1
                used, price = tokens_of(reply.usage), cost(model, reply.usage)
                tokens = {k: tokens[k] + used[k] for k in tokens}
                usd += price
                log("reply", turn=turn, stop_reason=reply.stop_reason, tokens=used, cost_usd=round(price, 5),
                    text=text_of(reply.content))
                messages.append({"role": "assistant", "content": reply.content})  # whole reply, thinking included
                if reply.stop_reason != "tool_use":
                    stop = reply.stop_reason
                    extra = new_messages() if stop == "end_turn" else []
                    if extra:  # Claude thought it was done, but the client just asked for more
                        stop = "max_turns"
                        messages.append({"role": "user", "content": extra})
                        continue
                    app = root / "app.py"
                    if stop == "end_turn" and app.exists():
                        (root / "rounds").mkdir(exist_ok=True)
                        (root / "rounds" / f"app_{repairs}.py").write_text(app.read_text())
                    # check only if repairs are left and app.py changed since the last check (else nothing new to test)
                    if stop == "end_turn" and repairs < max_repairs and app.exists() and app.read_text() != checked:
                        checked = app.read_text()
                        asked = f"{request}\n\nLater change asked by the client: {change}" if change else request
                        checks, result, price = check(root, asked, model, checks)
                        usd += price
                        counts = test_counts(result["output"])
                        log("check", round=repairs, ok=result["ok"], tests=counts, output=result["output"],
                            cost_usd=round(price, 5))
                        if not result["ok"] and counts["passed"] > 0:  # if no check passes, the checker is likely wrong
                            repairs += 1
                            messages.append({"role": "user", "content": REPAIR.format(output=result["output"])})
                            continue
                    break
                results = []
                for block in reply.content:
                    if block.type == "tool_use":
                        began = time.time()
                        out = run_tool(root, block.name, block.input, search)
                        extra = {"tests": test_counts(out["output"])} if block.name == "run_tests" else {}
                        tests = extra.get("tests", tests)
                        calls.append({"turn": turn, "tool": block.name, "ok": out["ok"]})
                        log("tool", turn=turn, tool=block.name, input=block.input, ok=out["ok"], output=out["output"],
                            seconds=round(time.time() - began, 2), **extra)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": out["output"],
                                        "is_error": not out["ok"]})
                messages.append({"role": "user", "content": results + new_messages()})  # all results of one turn in one message
        except (anthropic.AnthropicError, httpx.HTTPError, RuntimeError) as e:  # no key, network or local server down: report
            stop = f"error: {type(e).__name__}: {e}"[:300]
        finally:
            tools.stop_server(root)  # never leave a server running
        last = messages[-1]["content"] if messages[-1]["role"] == "assistant" else []
        run = {"request": request, "model": model, "prompt": prompt, "effort": effort, "search": search, "stop": stop, "turns": turns,
               "repairs": repairs, "tool_calls": calls, "tokens": tokens, "cost_usd": round(usd, 4), "seconds": round(time.time() - start, 1),
               "tests": tests, "summary": text_of(last), "plan": plan, "change": change,
               "follows_plan": follows_plan((root / "app.py").read_text(), plan) if plan and (root / "app.py").exists() else None}
        (root / "run.json").write_text(json.dumps(run, indent=2) + "\n")
        log("end", **{k: run[k] for k in ("stop", "turns", "repairs", "tokens", "cost_usd", "seconds", "tests")})
    return run

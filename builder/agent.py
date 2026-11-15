"""The agent (W1): questions, a plan, and a hand-written ReAct loop (decision 0003) over Bernard's tools (runtime/tools.py).

    from builder.agent import build
    result = build(request_text, "projects/run1/church_signup")

Each turn: send Claude the conversation and the tool list; run every tool it asks for, always in our project folder
(the LLM never chooses the folder); send the results back, marked as errors when ok is false. Stop when Claude answers
without asking for a tool, or at max_turns or max_usd. Every run leaves trace.jsonl and run.json in the folder.
"""

import json
import re
import time
from pathlib import Path

import anthropic

from builder.llm import ask, cost, create
from runtime import tools

MODEL = "claude-opus-5-5"

# The builder's instructions: prompt B of the four compared in W1 section 3, kept word for word as it was measured.
SYSTEM = ("""You build backends for people who do not code. In the project folder, write ONE complete file, app.py,
containing a FastAPI application in a variable named app. Use only fastapi, pydantic, sqlmodel and the Python standard
library. """
          "Store the data with SQLModel in a SQLite file in the current folder, creating the tables when the app starts. "
          """Do everything the client asks, refuse what the client says must be refused with a 4xx status, and return
JSON.

You have tools to write files, run pytest and start the server. Work like this: write app.py; write tests in
tests/test_app.py that check every thing the client asked for (use fastapi.testclient.TestClient on app); run them
and fix app.py until they pass. Do not add anything the client did not ask for. When the tests pass, reply with a
short summary of the endpoints and stop.""")

# Before building, ask what would otherwise be guessed (decision 0042).
ASKER = """You build backends for people who do not code. Before anything is built, read the client's request and ask
the questions whose answers would change what gets built: missing rules, numbers, formats or choices you would
otherwise have to guess. Ask at most {n}, the most important first, each one short and in plain words. If the request
is already clear, ask none."""
# Asked "Should customers need a PIN?", a client with no preference got a PIN built in (momo 13/13 to 1/13 tests).
SIMPLEST = ("Where the client has no preference or did not answer, choose the simplest option and add nothing they did "
            "not ask for (no logins, PINs or extra required fields).")

# The plan the client reads and approves before anything is built (decision 0041), word for word as measured.
PLANNER = ("""You plan backends for people who do not code. Read the client's request and write the plan they will read
and approve before anything is built: what data is kept, the endpoints (method, path, and what each does, in plain
words), and the rules (what must be refused). Plan only what the client asked for. If part of the request is unsafe or
not about the backend, leave it out and say so in the summary. Write for someone who has never programmed."""
           # added after the first version put logins nobody asked for into 3 of 15 plans
           """ Do not add logins, passwords, keys or any other feature or rule the client did not ask for. If you think
something is missing (for example, privacy), suggest it in the summary as a question; leave it out of the data,
endpoints and rules.""")
FOLLOW = "\n\nThe client approved this plan. Build exactly these endpoints, with these paths:\n{plan}"

# A change after the backend is live edits the existing app instead of rebuilding it (W1 row 9).
CHANGE = """The client's app is already built in this folder (app.py and its tests). They first asked for it like this:

{request}

Now they want this change:

{change}

Read app.py, change only what is needed with edit_file (do not rewrite the whole file), keep everything else working,
add tests for the change, run all the tests, and reply with a short summary of what changed."""
NEW_MESSAGE = """The client sent a new message while you work. It changes what they want, so follow it, then carry on:

{message}"""

# The builder writes notes for a programmer; the client reads this rewrite instead (decision 0054).
PLAIN = """You tell people who do not code what has just been built for them. You get what they asked for and the builder's
technical notes. Rewrite the notes for them, in short plain sentences: first that it is ready; then, as a short list, what they
can do with it; what it turns away; choices that were made for them; and anything they asked for that was left out. Use only
facts from the notes and never promise more than they say. It is already published on the internet when they read this, so
drop any remark that it has not been run or is not live, but keep every warning about who can reach it. Never mention web addresses or paths, GET or POST, file or
database names, code, JSON or status numbers, and never use words like endpoint, API, server, database, SQLite, schema,
field, query, pytest or test (say "checks"). Plain text only: no markdown, except "- " for list items."""

# Structured output: the reply is guaranteed to have exactly these parts.
WORDS = {"type": "array", "items": {"type": "string"}}
QUESTIONS = {"type": "object", "additionalProperties": False, "required": ["questions"], "properties": {"questions": WORDS}}
PLAN_SCHEMA = {
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

# One definition per tool: the docstring in runtime/tools.py is the description; the folder is never offered to the LLM.
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

# Joseph's recipe search (kb/search.py, decision 0037) as one more tool, only with build(search=True). Off on the live
# platform: Opus already knows these recipes, and they helped only a small local model (Section B 4.3).
SEARCH_TOOL = {"name": "search_docs", "input_schema": {"type": "object", "properties": {"query": STRING}, "required": ["query"]},
               "description": "Search the team's 18 short recipes for FastAPI, SQLModel and pytest (for example 'two people "
                              "booked the same room' or 'table has no primary key'). Returns the 3 best; judge whether they fit."}
SEARCH_HINT = " You can also search_docs for a short recipe when you are unsure how to do something or a test fails."


def search_docs(query):
    """The 3 best recipes as text. Dense search needs `uv run --extra kb`; without it, keyword search (BM25)."""
    from kb.search import search_docs as find
    try:
        found = find(query, 3)
    except ImportError:
        found = find(query, 3, method="bm25")
    return {"ok": True, "output": "\n\n".join(f"Recipe {r['id']}: {r['text']}" for r in found) or "No recipe matches."}


def run_tool(root, name, args, search=False):
    """Run the tool Claude asked for. A wrong name or wrong arguments go back to Claude as an error, never a crash."""
    if name == "search_docs" and search:
        tool = search_docs
    elif name in PARAMS:
        tool = lambda **a: getattr(tools, name)(root, **a)  # noqa: E731
    else:
        return {"ok": False, "output": f"Unknown tool {name!r}"}
    try:
        return tool(**args)
    except TypeError as e:
        return {"ok": False, "output": f"Bad arguments for {name}: {e}"}


def text_of(content):
    """The text Claude wrote in one reply (tool requests and thinking left out)."""
    return "".join(b.text for b in content if getattr(b, "type", "") == "text")


def test_counts(output):
    """Pytest's last line, e.g. "1 failed, 6 passed in 0.31s", as {"passed": 6, "failed": 1}. Errors count as failed."""
    found = {word: int(n) for n, word in re.findall(r"(\d+) (passed|failed|error)", output)}
    return {"passed": found.get("passed", 0), "failed": found.get("failed", 0) + found.get("error", 0)}


def clarify(request, n=3, model=MODEL):
    """Up to n questions for the client, most important first. Returns (questions, cost in US dollars)."""
    if n <= 0 or not request.strip():
        return [], 0.0
    text, usd = ask(model, ASKER.format(n=n), f"The client's request:\n{request}", schema=QUESTIONS)
    return [q for q in json.loads(text)["questions"] if q.strip()][:n], usd


def with_answers(request, questions, answers):
    """The request with the client's answers added, as the builder will read it."""
    if not questions:
        return request
    qa = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(questions, answers))
    return f"{request}\n\nThe client's answers to your questions:\n{qa}\n\n{SIMPLEST}"


def make_plan(request, model=MODEL, old=None, changes=None):
    """Draft a plan, or redo the old plan with the client's changes. Returns (plan dict, cost in US dollars)."""
    if not request.strip():
        raise ValueError("empty request")
    user = f"The client's request:\n{request}"
    if old:
        user += f"\n\nYour previous plan:\n{json.dumps(old)}\n\nThe client wants these changes:\n{changes}"
    text, usd = ask(model, PLANNER, user, schema=PLAN_SCHEMA)
    return json.loads(text), usd


def plan_text(plan):
    """The plan in plain words, for the client to read."""
    lines = [plan["summary"], "", "What is kept:"]
    lines += [f"- {d['name']}: {', '.join(d['fields'])}" for d in plan["data"]]
    lines += ["", "What you can do:"] + [f"- {e['does']}  ({e['method']} {e['path']})" for e in plan["endpoints"]]
    lines += ["", "Rules:"] + [f"- {r}" for r in plan["rules"] or ["none"]]
    return "\n".join(lines)


def plain_summary(request, notes, model=MODEL):
    """The builder's notes, rewritten for someone who does not code. Returns (text, cost in US dollars)."""
    text, usd = ask(model, PLAIN, f"What the client asked for:\n{request}\n\nThe builder's notes:\n{notes}")
    return text.strip(), usd


def build(request, root, model=MODEL, effort="medium", max_turns=40, max_usd=2.0, on_event=None, plan=None, search=False,
          change=None, inbox=None):
    """Run the loop. Stops when Claude finishes ("end_turn"), or at max_turns, max_usd or an error (always reported).

    plan: an approved plan from make_plan; Claude gets the request plus the plan.
    change: Claude edits the app already in root instead of starting again.
    inbox: a function returning the client's new messages (usually none); Claude sees them between turns (Lecture 8).
    search: Claude also gets the search_docs tool.
    on_event: called with every event as it happens, so a page can show the build live.

    Writes trace.jsonl in root, one line per event (start, reply, tool, message, end), and run.json, the totals."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    start = time.time()
    first = CHANGE.format(request=request, change=change) if change else request + (FOLLOW.format(plan=json.dumps(plan, indent=1)) if plan else "")
    messages = [{"role": "user", "content": first}]
    system, offered = (SYSTEM + SEARCH_HINT, TOOLS + [SEARCH_TOOL]) if search else (SYSTEM, TOOLS)
    calls, usd, stop, turns, tests = [], 0.0, "max_turns", 0, None
    tokens = {"in": 0, "out": 0, "cache_write": 0, "cache_read": 0}
    if not request.strip():  # nothing to build: do not pay for a call
        stop, max_turns = "empty request", 0
    elif change is not None and not change.strip():
        stop, max_turns = "nothing to change", 0
    elif change is not None and not (root / "app.py").exists():
        stop, max_turns = "no app.py to change: build it first", 0
    with open(root / "trace.jsonl", "w", encoding="utf-8") as trace:

        def log(event, **fields):
            line = {"event": event, "t": round(time.time() - start, 2), **fields}  # t = seconds since the start
            trace.write(json.dumps(line, default=str) + "\n")
            trace.flush()  # on disk at once: a page can follow it, and a crash keeps what happened so far
            if on_event:
                on_event(line)

        def new_messages():
            found = inbox() if inbox else []
            for text in found:
                log("message", text=text)
            return [{"type": "text", "text": NEW_MESSAGE.format(message=text)} for text in found]

        log("start", request=request, model=model, effort=effort, plan=plan, search=search, change=change)
        try:
            for turn in range(max_turns):
                if usd >= max_usd:
                    stop = "max_usd"
                    break
                # cache_control caches the conversation so far: each turn re-reads it at 10% of the price
                reply = create(model, max_tokens=16000, system=system, tools=offered, messages=messages,
                               output_config={"effort": effort}, cache_control={"type": "ephemeral"})
                turns += 1
                u = reply.usage
                used = {"in": u.input_tokens, "out": u.output_tokens, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
                        "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0}
                tokens = {k: tokens[k] + used[k] for k in tokens}
                price = cost(model, u)
                usd += price
                log("reply", turn=turn, stop_reason=reply.stop_reason, tokens=used, cost_usd=round(price, 5), text=text_of(reply.content))
                messages.append({"role": "assistant", "content": reply.content})  # the whole reply, thinking included
                if reply.stop_reason != "tool_use":
                    stop = reply.stop_reason
                    extra = new_messages() if stop == "end_turn" else []
                    if not extra:
                        break
                    stop = "max_turns"  # Claude thought it was done, but the client just asked for more
                    messages.append({"role": "user", "content": extra})
                    continue
                results = []
                for block in reply.content:
                    if block.type != "tool_use":
                        continue
                    began = time.time()
                    out = run_tool(root, block.name, block.input, search)
                    extra = {"tests": test_counts(out["output"])} if block.name == "run_tests" else {}
                    tests = extra.get("tests", tests)
                    calls.append({"turn": turn, "tool": block.name, "ok": out["ok"]})
                    log("tool", turn=turn, tool=block.name, input=block.input, ok=out["ok"], output=out["output"],
                        seconds=round(time.time() - began, 2), **extra)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out["output"], "is_error": not out["ok"]})
                messages.append({"role": "user", "content": results + new_messages()})  # all results of one turn in one message
        except anthropic.AnthropicError as e:  # no key, network down: report it
            stop = f"error: {type(e).__name__}: {e}"[:300]
        finally:
            tools.stop_server(root)  # never leave a server running
        last = messages[-1]["content"] if messages[-1]["role"] == "assistant" else []
        run = {"request": request, "model": model, "effort": effort, "search": search, "stop": stop, "turns": turns,
               "tool_calls": calls, "tokens": tokens, "cost_usd": round(usd, 4), "seconds": round(time.time() - start, 1),
               "tests": tests, "summary": text_of(last), "plan": plan, "change": change}
        (root / "run.json").write_text(json.dumps(run, indent=2) + "\n")
        log("end", **{k: run[k] for k in ("stop", "turns", "tokens", "cost_usd", "seconds", "tests")})
    return run

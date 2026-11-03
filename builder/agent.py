"""The agent (W1): a hand-written ReAct loop (decision 0003) over Bernard's tools (runtime/tools.py).

    from builder.agent import build
    result = build(request_text, "projects/run1/church_signup", model="claude-opus-5-5")

Each turn: send Claude the conversation and the tool list; run every tool it asks for, always in our project
folder (the LLM never chooses root); send the results back, marked as errors when ok is false. Stop when Claude
answers without asking for a tool, or after max_turns. Every run leaves trace.jsonl and run.json in the folder (S3.3).
"""

import json
import os
import re
import time
from pathlib import Path

import anthropic

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

_client = None


def call(model, system, messages, effort):
    """One request. Top-level cache_control caches the conversation so far: each turn re-reads it at 10% of the price."""
    global _client
    if not _client:
        if not os.environ.get("LLM_API_KEY"):  # build() reports this as an error instead of crashing
            raise anthropic.AnthropicError("LLM_API_KEY is not set: run with --env-file .env")
        _client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], max_retries=4)
    args = dict(model=model, max_tokens=16000, system=system, tools=TOOLS, messages=messages,
                output_config={"effort": effort}, cache_control={"type": "ephemeral"})
    if model.startswith("claude-opus"):  # same refusal fallback as Joseph's eval.llm
        return _client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **args)
    return _client.messages.create(**args)


def cost(model, u):
    """US dollars for one reply: new input, cache writes (1.25x), cache reads (0.1x), output."""
    price_in, price_out = PRICES[model]
    written = getattr(u, "cache_creation_input_tokens", 0) or 0
    read = getattr(u, "cache_read_input_tokens", 0) or 0
    return (u.input_tokens * price_in + written * price_in * 1.25 + read * price_in * 0.1 + u.output_tokens * price_out) / 1e6


def run_tool(root, name, args):
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


def build(request, root, model="claude-opus-5-5", effort="medium", prompt="B", max_turns=40, max_usd=2.0, on_event=None,
          max_repairs=0):
    """Run the loop. Stops when Claude finishes ("end_turn"), or at max_turns, max_usd or an error (always reported).

    With max_repairs > 0, each time Claude finishes, an independent checker tests app.py against the request; failures
    are sent back to Claude to fix, at most max_repairs times. app.py is saved after every round as rounds/app_N.py.

    Writes two files in root: trace.jsonl, one line per event as it happens (start, reply, tool, check, end), and
    run.json, the totals. on_event, if given, is called with every event too, so a UI can show the build live."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    start = time.time()
    messages = [{"role": "user", "content": request}]
    calls, usd, stop, turns, tests = [], 0.0, "max_turns", 0, None
    repairs, checks, checked = 0, None, None  # repairs used, the checker's test file, the app.py it last checked
    tokens = {"in": 0, "out": 0, "cache_write": 0, "cache_read": 0}
    if not request.strip():  # nothing to build: do not pay for a call
        stop, max_turns = "empty request", 0
    with open(root / "trace.jsonl", "w", encoding="utf-8") as trace:

        def log(event, **fields):
            line = {"event": event, "t": round(time.time() - start, 2), **fields}  # t = seconds since the start
            trace.write(json.dumps(line, default=str) + "\n")
            trace.flush()  # on disk at once: a UI can follow it, and a crash keeps what happened so far
            if on_event:
                on_event(line)

        log("start", request=request, model=model, prompt=prompt, effort=effort)
        try:
            for turn in range(max_turns):
                if usd >= max_usd:
                    stop = "max_usd"
                    break
                reply = call(model, PROMPTS[prompt], messages, effort)
                turns += 1
                used, price = tokens_of(reply.usage), cost(model, reply.usage)
                tokens = {k: tokens[k] + used[k] for k in tokens}
                usd += price
                log("reply", turn=turn, stop_reason=reply.stop_reason, tokens=used, cost_usd=round(price, 5),
                    text=text_of(reply.content))
                messages.append({"role": "assistant", "content": reply.content})  # whole reply, thinking included
                if reply.stop_reason != "tool_use":
                    stop = reply.stop_reason
                    app = root / "app.py"
                    if stop == "end_turn" and app.exists():
                        (root / "rounds").mkdir(exist_ok=True)
                        (root / "rounds" / f"app_{repairs}.py").write_text(app.read_text())
                    # check only if repairs are left and app.py changed since the last check (else nothing new to test)
                    if stop == "end_turn" and repairs < max_repairs and app.exists() and app.read_text() != checked:
                        checked = app.read_text()
                        checks, result, price = check(root, request, model, checks)
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
                        out = run_tool(root, block.name, block.input)
                        extra = {"tests": test_counts(out["output"])} if block.name == "run_tests" else {}
                        tests = extra.get("tests", tests)
                        calls.append({"turn": turn, "tool": block.name, "ok": out["ok"]})
                        log("tool", turn=turn, tool=block.name, input=block.input, ok=out["ok"], output=out["output"],
                            seconds=round(time.time() - began, 2), **extra)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": out["output"],
                                        "is_error": not out["ok"]})
                messages.append({"role": "user", "content": results})  # all results of one turn in one message
        except anthropic.AnthropicError as e:  # no key, network down, overloaded after the retries: report, do not crash
            stop = f"error: {type(e).__name__}: {e}"[:300]
        finally:
            tools.stop_server(root)  # never leave a server running
        last = messages[-1]["content"] if messages[-1]["role"] == "assistant" else []
        run = {"request": request, "model": model, "prompt": prompt, "effort": effort, "stop": stop, "turns": turns,
               "repairs": repairs, "tool_calls": calls, "tokens": tokens, "cost_usd": round(usd, 4), "seconds": round(time.time() - start, 1),
               "tests": tests, "summary": text_of(last)}
        (root / "run.json").write_text(json.dumps(run, indent=2) + "\n")
        log("end", **{k: run[k] for k in ("stop", "turns", "repairs", "tokens", "cost_usd", "seconds", "tests")})
    return run

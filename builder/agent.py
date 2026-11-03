"""The agent (W1): a hand-written ReAct loop (decision 0003) over Bernard's tools (runtime/tools.py).

    from builder.agent import build
    result = build(request_text, "projects/run1/church_signup", model="claude-opus-5-5")

Each turn: send Claude the conversation and the tool list; run every tool it asks for, always in our project
folder (the LLM never chooses root); send the results back, marked as errors when ok is false. Stop when Claude
answers without asking for a tool, or after max_turns.
"""

import json
import os
import time
from pathlib import Path

import anthropic

from eval.llm import PRICES
from runtime import tools

SYSTEM = """You build backends for people who do not code. In the project folder, write ONE complete file, app.py,
containing a FastAPI application in a variable named app. Use only fastapi, pydantic, sqlmodel and the Python standard
library. Keep data in memory (or in a SQLite file in the current folder). Do everything the client asks, refuse what
the client says must be refused with a 4xx status, and return JSON.

You have tools to write files, run pytest and start the server. Work like this: write app.py; write tests in
tests/test_app.py that check every thing the client asked for (use fastapi.testclient.TestClient on app); run them
and fix app.py until they pass. Do not add anything the client did not ask for. When the tests pass, reply with a
short summary of the endpoints and stop."""

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


def call(model, messages, effort):
    """One request. Top-level cache_control caches the conversation so far: each turn re-reads it at 10% of the price."""
    global _client
    _client = _client or anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], max_retries=4)
    args = dict(model=model, max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=messages,
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


def build(request, root, model="claude-opus-5-5", effort="medium", max_turns=40):
    Path(root).mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": request}]
    calls, usd, start, stop = [], 0.0, time.time(), "max_turns"
    try:
        for turn in range(max_turns):
            reply = call(model, messages, effort)
            usd += cost(model, reply.usage)
            messages.append({"role": "assistant", "content": reply.content})  # whole reply, thinking blocks included
            if reply.stop_reason != "tool_use":
                stop = reply.stop_reason
                break
            results = []
            for block in reply.content:
                if block.type == "tool_use":
                    out = run_tool(root, block.name, block.input)
                    calls.append({"turn": turn, "tool": block.name, "ok": out["ok"]})
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out["output"],
                                    "is_error": not out["ok"]})
            messages.append({"role": "user", "content": results})  # all results of one turn in one message
    finally:
        tools.stop_server(root)  # never leave a server running
    summary = "".join(b.text for b in messages[-1]["content"] if getattr(b, "type", "") == "text")
    return {"stop": stop, "turns": len(calls) and calls[-1]["turn"] + 1, "tool_calls": calls,
            "cost_usd": round(usd, 4), "seconds": round(time.time() - start, 1), "summary": summary}

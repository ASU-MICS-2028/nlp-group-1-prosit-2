"""Failure cases of the agent loop, with a pretend Claude (free, no API key needed).

    uv run --with anthropic python -m pytest builder -q
"""

from types import SimpleNamespace as Obj

import anthropic
import httpx

from builder import agent

USAGE = Obj(input_tokens=1000, output_tokens=1000, cache_creation_input_tokens=0, cache_read_input_tokens=0)


def tool_reply(name, args):
    """A pretend Claude reply that asks for one tool."""
    return Obj(stop_reason="tool_use", usage=USAGE, content=[Obj(type="tool_use", id="t1", name=name, input=args)])


def done_reply(text="Done."):
    return Obj(stop_reason="end_turn", usage=USAGE, content=[Obj(type="text", text=text)])


def pretend(monkeypatch, replies):
    """Make agent.call return these replies in order (the last one forever). Returns the list of calls made.
    Each call gets the same, growing conversation: [request, Claude asks for a tool, tool result, ...]."""
    made = []

    def fake_call(model, system, messages, effort):
        made.append(messages)
        return replies[min(len(made), len(replies)) - 1]
    monkeypatch.setattr(agent, "call", fake_call)
    return made


def test_empty_request_costs_nothing(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [done_reply()])
    result = agent.build("   \n", tmp_path)
    assert result["stop"] == "empty request" and made == [] and result["cost_usd"] == 0


def test_normal_build_writes_the_file_and_counts_turns(monkeypatch, tmp_path):
    pretend(monkeypatch, [tool_reply("write_file", {"path": "app.py", "content": "x = 1\n"}), done_reply("Endpoints: none")])
    result = agent.build("make an app", tmp_path)
    assert (tmp_path / "app.py").read_text() == "x = 1\n"
    assert result["stop"] == "end_turn" and result["turns"] == 2 and result["summary"] == "Endpoints: none"


def test_unknown_tool_is_reported_to_claude(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("delete_everything", {}), done_reply()])
    agent.build("make an app", tmp_path)
    sent_back = made[-1][2]["content"][0]
    assert sent_back["is_error"] and "Unknown tool" in sent_back["content"]


def test_wrong_arguments_are_reported_to_claude(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("write_file", {"filename": "app.py"}), done_reply()])
    agent.build("make an app", tmp_path)
    sent_back = made[-1][2]["content"][0]
    assert sent_back["is_error"] and "Bad arguments" in sent_back["content"]


def test_writing_outside_the_project_is_refused(monkeypatch, tmp_path):
    root = tmp_path / "project"
    made = pretend(monkeypatch, [tool_reply("write_file", {"path": "../evil.txt", "content": "hi"}), done_reply()])
    agent.build("make an app", root)
    assert not (tmp_path / "evil.txt").exists() and made[-1][2]["content"][0]["is_error"]


def test_never_finishing_stops_at_max_turns(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("list_files", {})])
    result = agent.build("make an app", tmp_path, max_turns=5)
    assert result["stop"] == "max_turns" and len(made) == 5


def test_spending_limit_stops_the_build(monkeypatch, tmp_path):
    pretend(monkeypatch, [tool_reply("list_files", {})])  # each pretend reply costs $0.024 at Opus prices ($4 + $20 per million)
    result = agent.build("make an app", tmp_path, max_usd=0.1)
    assert result["stop"] == "max_usd" and result["turns"] == 5  # $0.096 after 4 is under the limit, $0.12 after 5 is not


def test_network_error_is_reported_not_raised(monkeypatch, tmp_path):
    def broken(*args):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(agent, "call", broken)
    result = agent.build("make an app", tmp_path)
    assert result["stop"].startswith("error: APIConnectionError") and result["turns"] == 0

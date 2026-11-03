"""Failure cases of the agent loop, with a pretend Claude (free, no API key needed).

    uv run --with anthropic python -m pytest builder -q
"""

import json
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


def read_trace(root):
    return [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]


def test_every_run_writes_a_trace_and_a_run_record(monkeypatch, tmp_path):
    pretend(monkeypatch, [tool_reply("write_file", {"path": "app.py", "content": "x = 1\n"}), done_reply("Endpoints: none")])
    seen = []
    result = agent.build("make an app", tmp_path, on_event=seen.append)
    trace = read_trace(tmp_path)
    assert [e["event"] for e in trace] == ["start", "reply", "tool", "reply", "end"]
    assert trace == seen  # a UI gets exactly what the file gets
    assert trace[2]["tool"] == "write_file" and trace[2]["ok"] and trace[2]["input"]["path"] == "app.py"
    assert trace[1]["tokens"] == {"in": 1000, "out": 1000, "cache_write": 0, "cache_read": 0}
    run = json.loads((tmp_path / "run.json").read_text())
    assert run == result and run["tokens"]["out"] == 2000 and run["cost_usd"] == 0.048 and run["tests"] is None


def test_trace_is_written_even_when_the_build_breaks(monkeypatch, tmp_path):
    def broken(*args):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(agent, "call", broken)
    agent.build("make an app", tmp_path)
    trace = read_trace(tmp_path)
    assert [e["event"] for e in trace] == ["start", "end"] and trace[-1]["stop"].startswith("error")


def test_missing_key_is_reported_not_raised(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(agent, "_client", None)
    result = agent.build("make an app", tmp_path)
    assert "LLM_API_KEY is not set" in result["stop"] and result["turns"] == 0


def test_test_counts_reads_pytest_last_line():
    assert agent.test_counts("....\n7 passed in 0.12s") == {"passed": 7, "failed": 0}
    assert agent.test_counts("F..\n1 failed, 6 passed in 0.31s") == {"passed": 6, "failed": 1}
    assert agent.test_counts("E\n1 error in 0.05s") == {"passed": 0, "failed": 1}
    assert agent.test_counts("Tests stopped: still running after 60 seconds") == {"passed": 0, "failed": 0}


# S3.4: the repair loop, with a pretend checker
FAILED = {"ok": False, "output": "F.\n1 failed, 1 passed in 0.1s"}
PASSED = {"ok": True, "output": "..\n2 passed in 0.1s"}


def pretend_checker(monkeypatch, results):
    """Make agent.check return these run_tests results in order (the last one forever). Returns the calls made."""
    made = []

    def fake_check(root, request, model, checks=None):
        made.append((root / "app.py").read_text())
        return "the checks", results[min(len(made), len(results)) - 1], 0.01
    monkeypatch.setattr(agent, "check", fake_check)
    return made


def write_app(text):
    return tool_reply("write_file", {"path": "app.py", "content": text})


def test_failed_check_is_sent_back_and_fixed(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [write_app("v1"), done_reply(), write_app("v2"), done_reply()])
    checked = pretend_checker(monkeypatch, [FAILED, PASSED])
    result = agent.build("make an app", tmp_path, max_repairs=3)
    assert checked == ["v1", "v2"] and result["repairs"] == 1 and result["stop"] == "end_turn"
    assert "1 failed, 1 passed" in made[-1][4]["content"]  # the 5th message is the repair request
    assert (tmp_path / "rounds/app_0.py").read_text() == "v1" and (tmp_path / "rounds/app_1.py").read_text() == "v2"
    assert [e["event"] for e in read_trace(tmp_path)].count("check") == 2


def test_repairs_stop_at_the_limit(monkeypatch, tmp_path):
    replies = [write_app("v1"), done_reply(), write_app("v2"), done_reply(), write_app("v3"), done_reply()]
    pretend(monkeypatch, replies)
    pretend_checker(monkeypatch, [FAILED])
    assert agent.build("make an app", tmp_path, max_repairs=2)["repairs"] == 2


def test_no_check_when_repairs_are_off(monkeypatch, tmp_path):
    pretend(monkeypatch, [write_app("v1"), done_reply()])
    checked = pretend_checker(monkeypatch, [FAILED])
    result = agent.build("make an app", tmp_path)
    assert checked == [] and result["repairs"] == 0 and (tmp_path / "rounds/app_0.py").exists()


def test_unchanged_app_is_not_checked_again(monkeypatch, tmp_path):
    pretend(monkeypatch, [write_app("v1"), done_reply("That check asks for something the client did not want.")])
    checked = pretend_checker(monkeypatch, [FAILED])
    result = agent.build("make an app", tmp_path, max_repairs=5)
    assert checked == ["v1"] and result["repairs"] == 1


def test_broken_checker_is_not_sent_to_the_builder(monkeypatch, tmp_path):
    pretend(monkeypatch, [write_app("v1"), done_reply()])
    pretend_checker(monkeypatch, [{"ok": False, "output": "E\n1 error in 0.1s"}])  # nothing passed: the checks are broken
    assert agent.build("make an app", tmp_path, max_repairs=3)["repairs"] == 0


def test_check_restores_the_checks_and_empties_the_database(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "old.db").write_text("leftover data")
    monkeypatch.setattr(agent, "ask", lambda *a, **k: ("```python\ndef test_x():\n    pass\n```", {"cost_usd": 0.02}))
    monkeypatch.setattr(agent.tools, "run_tests", lambda root, path: PASSED)
    checks, result, usd = agent.check(tmp_path, "make an app", "claude-opus-5-5")
    assert checks == "def test_x():\n    pass\n" and usd == 0.02 and not (tmp_path / "old.db").exists()
    (tmp_path / "tests/test_acceptance.py").write_text("def test_x(): pass  # the builder cheated")
    agent.check(tmp_path, "make an app", "claude-opus-5-5", checks)
    assert (tmp_path / "tests/test_acceptance.py").read_text() == checks


# S3.5: spec-first, with a pretend planner
PLAN = {"summary": "Sign people up for church events.",
        "data": [{"name": "Event", "fields": ["name", "date", "capacity"]}],
        "endpoints": [{"method": "POST", "path": "/events", "does": "Add an event"},
                      {"method": "GET", "path": "/events/{event_id}", "does": "Look at one event"}],
        "rules": ["Nobody can sign up once an event is full"]}


def pretend_planner(monkeypatch, plans):
    """Make agent.ask return these plans in order as JSON text. Returns the (system, user, schema) of each call."""
    made = []

    def fake_ask(model, system, user, effort="medium", schema=None):
        made.append((system, user, schema))
        return json.dumps(plans[len(made) - 1]), {"cost_usd": 0.01}
    monkeypatch.setattr(agent, "ask", fake_ask)
    return made


def test_plan_of_empty_request_costs_nothing(monkeypatch):
    made = pretend_planner(monkeypatch, [PLAN])
    try:
        agent.make_plan("  ")
        assert False, "should refuse"
    except ValueError as e:
        assert "empty" in str(e) and made == []


def test_plan_uses_the_fixed_form_and_changes_resend_the_old_plan(monkeypatch):
    made = pretend_planner(monkeypatch, [PLAN, PLAN])
    plan, usd = agent.make_plan("church events")
    assert plan == PLAN and usd == 0.01 and made[0][2] == agent.PLAN_SCHEMA
    agent.make_plan("church events", old=plan, changes="add a phone number")
    assert "Look at one event" in made[1][1] and "add a phone number" in made[1][1]


def test_plan_text_is_plain_words():
    text = agent.plan_text(PLAN)
    assert "- Event: name, date, capacity" in text and "- Add an event  (POST /events)" in text
    assert "- Nobody can sign up once an event is full" in text
    assert "Rules:\n- none" in agent.plan_text({**PLAN, "rules": []})


APP = '''
from fastapi import FastAPI
app = FastAPI()
@app.post("/events/")
def add(): ...
@app.get("/events/{id}")
def one(id: int): ...
@app.delete("/events/{id}")
def remove(id: int): ...
'''


def test_follows_plan_ignores_names_in_braces_and_last_slash():
    assert agent.follows_plan(APP, PLAN) == {"missing": [], "extra": ["DELETE /events/{}"]}
    assert agent.follows_plan("def broken(:", PLAN) == {"missing": ["GET /events/{}", "POST /events"], "extra": []}
    search = {**PLAN, "endpoints": [{"method": "GET", "path": "/fares?from=STOP&to=STOP", "does": "Find a fare"}]}
    assert agent.follows_plan('@app.get("/fares")\ndef f(): ...', search) == {"missing": [], "extra": []}  # real S3.5 case


def test_reading_routes_never_runs_the_code(tmp_path):
    bomb = tmp_path / "ran.txt"
    agent.routes_of(f"open({str(bomb)!r}, 'w')\n" + APP)
    assert not bomb.exists()


def test_build_with_plan_sends_it_and_records_whether_it_was_followed(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("write_file", {"path": "app.py", "content": APP}), done_reply()])
    result = agent.build("church events", tmp_path, plan=PLAN)
    assert made[0][0]["content"].startswith("church events\n\nThe client approved this plan")
    assert "/events/{event_id}" in made[0][0]["content"]
    assert result["plan"] == PLAN and result["follows_plan"]["extra"] == ["DELETE /events/{}"]
    assert read_trace(tmp_path)[0]["plan"] == PLAN


def test_build_without_plan_is_unchanged(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [done_reply()])
    result = agent.build("church events", tmp_path)
    assert made[0][0]["content"] == "church events" and result["plan"] is None and result["follows_plan"] is None


def test_no_build_without_a_good_plan_file(tmp_path):
    for content, says in [(None, "no approved plan"), ("{not json", "broken"), ('{"summary": "x"}', "broken"),
                          ('{"summary": "x", "data": 5, "endpoints": [], "rules": []}', "broken")]:
        if content is not None:
            (tmp_path / "plan.json").write_text(content)
        try:
            agent.load_plan(tmp_path)
            assert False, content
        except ValueError as e:
            assert says in str(e)
    (tmp_path / "plan.json").write_text(json.dumps(PLAN))
    assert agent.load_plan(tmp_path) == PLAN


def run_cli(monkeypatch, tmp_path, args, answers):
    """Run `python -m builder ...` in tmp_path with these answers typed at the approval question."""
    import runpy
    import sys
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["builder", *args])
    typed = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(typed))
    runpy.run_module("builder", run_name="__main__")
    return tmp_path / "projects" / "t" / "church_signup"


def test_cli_change_then_approve_saves_the_changed_plan(monkeypatch, tmp_path):
    changed = {**PLAN, "summary": "With phone numbers."}
    made = pretend_planner(monkeypatch, [PLAN, changed])
    root = run_cli(monkeypatch, tmp_path, ["plan", "church_signup", "--run", "t"], ["add a phone number", "y"])
    assert len(made) == 2 and json.loads((root / "plan.json").read_text()) == changed


def test_cli_saying_no_removes_an_older_approval(monkeypatch, tmp_path):
    pretend_planner(monkeypatch, [PLAN])
    old = tmp_path / "projects" / "t" / "church_signup"
    old.mkdir(parents=True)
    (old / "plan.json").write_text(json.dumps(PLAN))
    run_cli(monkeypatch, tmp_path, ["plan", "church_signup", "--run", "t"], ["n"])
    assert not (old / "plan.json").exists()


def test_cli_build_with_plan_flag_refuses_without_a_plan(monkeypatch, tmp_path, capsys):
    made = pretend(monkeypatch, [done_reply()])
    root = run_cli(monkeypatch, tmp_path, ["build", "church_signup", "--plan", "--run", "t"], [])
    assert "not built: no approved plan" in capsys.readouterr().out and made == [] and not root.exists()

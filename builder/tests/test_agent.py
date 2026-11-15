"""Failure cases of the agent loop, with a pretend Claude (free, no API key needed).

    uv run --with anthropic python -m pytest builder -q
"""

import json
from types import SimpleNamespace as Obj

import anthropic
import httpx
import pytest

from builder import agent, llm

USAGE = Obj(input_tokens=1000, output_tokens=1000, cache_creation_input_tokens=0, cache_read_input_tokens=0)


def tool_reply(name, args):
    """A pretend Claude reply that asks for one tool."""
    return Obj(stop_reason="tool_use", usage=USAGE, content=[Obj(type="tool_use", id="t1", name=name, input=args)])


def done_reply(text="Done."):
    return Obj(stop_reason="end_turn", usage=USAGE, content=[Obj(type="text", text=text)])


def pretend(monkeypatch, replies):
    """Make Claude return these replies in order (the last one forever). Returns the list of calls made.
    Each call gets the same, growing conversation: [request, Claude asks for a tool, tool result, ...]."""
    made, offered = [], []
    pretend.offered = offered  # what the agent offered each turn: (system prompt, tool names)

    def fake_create(model, messages, system, tools, **args):
        made.append(messages)
        offered.append((system, [x["name"] for x in tools]))
        return replies[min(len(made), len(replies)) - 1]
    monkeypatch.setattr(agent, "create", fake_create)
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
    def broken(*args, **kwargs):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(agent, "create", broken)
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
    def broken(*args, **kwargs):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(agent, "create", broken)
    agent.build("make an app", tmp_path)
    trace = read_trace(tmp_path)
    assert [e["event"] for e in trace] == ["start", "end"] and trace[-1]["stop"].startswith("error")


def test_missing_key_is_reported_not_raised(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_client", None)
    result = agent.build("make an app", tmp_path)
    assert "LLM_API_KEY is not set" in result["stop"] and result["turns"] == 0


def test_test_counts_reads_pytest_last_line():
    assert agent.test_counts("....\n7 passed in 0.12s") == {"passed": 7, "failed": 0}
    assert agent.test_counts("F..\n1 failed, 6 passed in 0.31s") == {"passed": 6, "failed": 1}
    assert agent.test_counts("E\n1 error in 0.05s") == {"passed": 0, "failed": 1}
    assert agent.test_counts("Tests stopped: still running after 60 seconds") == {"passed": 0, "failed": 0}


# The plan, with a pretend planner
PLAN = {"summary": "Sign people up for church events.",
        "data": [{"name": "Event", "fields": ["name", "date", "capacity"]}],
        "endpoints": [{"method": "POST", "path": "/events", "does": "Add an event"},
                      {"method": "GET", "path": "/events/{event_id}", "does": "Look at one event"}],
        "rules": ["Nobody can sign up once an event is full"]}


def pretend_planner(monkeypatch, plans):
    """Make agent.ask return these plans in order as JSON text. Returns the (system, user, schema) of each call."""
    made = []

    def fake_ask(model, system, user, schema=None, effort="medium"):
        made.append((system, user, schema))
        return json.dumps(plans[len(made) - 1]), 0.01
    monkeypatch.setattr(agent, "ask", fake_ask)
    return made


def test_plan_of_empty_request_costs_nothing(monkeypatch):
    made = pretend_planner(monkeypatch, [PLAN])
    with pytest.raises(ValueError, match="empty"):
        agent.make_plan("  ")
    assert made == []


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


def test_build_with_plan_sends_it(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [done_reply()])
    result = agent.build("church events", tmp_path, plan=PLAN)
    assert made[0][0]["content"].startswith("church events\n\nThe client approved this plan")
    assert "/events/{event_id}" in made[0][0]["content"]
    assert result["plan"] == PLAN and read_trace(tmp_path)[0]["plan"] == PLAN


def test_build_without_plan_sends_only_the_request(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [done_reply()])
    result = agent.build("church events", tmp_path)
    assert made[0][0]["content"] == "church events" and result["plan"] is None


def test_the_planner_forbids_extras_nobody_asked_for(monkeypatch):
    made = pretend_planner(monkeypatch, [PLAN])
    agent.make_plan("church events")
    assert "Do not add logins" in made[0][0]  # decision 0041


def run_cli(monkeypatch, tmp_path, args, answers):
    """Run `python -m builder ...` in tmp_path with these answers typed when asked."""
    import runpy
    import sys
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["builder", *args])
    typed = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(typed))
    runpy.run_module("builder", run_name="__main__")
    return tmp_path / "projects" / "t" / "church_signup"


# Questions for the client, with a pretend asker and a pretend client
from builder import client  # noqa: E402


def test_no_questions_cost_nothing(monkeypatch):
    made = pretend_planner(monkeypatch, [{"questions": ["x?"]}])
    assert agent.clarify("church events", n=0) == ([], 0.0) and agent.clarify("  ") == ([], 0.0) and made == []


def test_at_most_n_questions_and_blank_ones_dropped(monkeypatch):
    made = pretend_planner(monkeypatch, [{"questions": ["Scale?", " ", "Credits?", "Rounding?", "Extra?"]}])
    questions, usd = agent.clarify("school grades", n=3)
    assert questions == ["Scale?", "Credits?", "Rounding?"] and usd == 0.01
    assert "at most 3" in made[0][0] and made[0][2] == agent.QUESTIONS


def test_answers_are_added_to_the_request():
    assert agent.with_answers("grades", [], []) == "grades"
    assert agent.with_answers("grades", ["Scale?"], ["80+ is A"]).endswith(
        "The client's answers to your questions:\nQ: Scale?\nA: 80+ is A\n\n" + agent.SIMPLEST)
    assert "no logins, PINs" in agent.SIMPLEST


def test_pretend_client_gives_exactly_one_answer_per_question(monkeypatch):
    seen = []

    def fake_ask(model, system, user, schema=None, effort="medium"):
        seen.append((model, system, user))
        return json.dumps({"answers": ["only one"]}), 0.001
    monkeypatch.setattr(client, "ask", fake_ask)
    assert client.answer("trotro_fares", []) == ([], 0.0) and seen == []
    answers, _ = client.answer("trotro_fares", ["Both directions?", "Delete routes?"])
    assert answers == ["only one", client.NONE]  # a missing answer becomes "no preference"
    assert seen[0][0] == client.MODEL and "Is the fare the same in both directions?" in seen[0][2]  # answers.json


def test_pretend_client_without_prepared_answers_has_no_preference(monkeypatch, tmp_path):
    monkeypatch.setattr(client.bench, "BENCH", tmp_path)
    (tmp_path / "t").mkdir()
    assert client.answer("t", ["Q?"]) == ([client.NONE], 0.0)


def test_cli_build_with_questions_sends_the_answers_and_saves_them(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "clarify", lambda request, n, model: (["Scale?", "Credits?"][:n], 0.01))
    monkeypatch.setattr(client, "answer", lambda task, qs: (["80+ is A", "Yes"][:len(qs)], 0.001))
    made = pretend(monkeypatch, [done_reply()])
    root = run_cli(monkeypatch, tmp_path, ["build", "church_signup", "--ask", "2", "--client", "answers", "--run", "t"], [])
    assert "Q: Scale?\nA: 80+ is A\nQ: Credits?\nA: Yes" in made[0][0]["content"]
    saved = json.loads((root / "questions.json").read_text())
    assert saved["answers"] == ["80+ is A", "Yes"]


def test_cli_person_answers_and_a_blank_answer_means_no_preference(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "clarify", lambda request, n, model: (["Scale?", "Credits?"], 0.01))
    made = pretend(monkeypatch, [done_reply()])
    run_cli(monkeypatch, tmp_path, ["build", "church_signup", "--ask", "2", "--run", "t"], ["80+ is A", ""])
    assert f"A: 80+ is A\nQ: Credits?\nA: {client.NONE}" in made[0][0]["content"]


def test_cli_later_build_reuses_the_saved_answers(monkeypatch, tmp_path):
    root = tmp_path / "projects" / "t" / "church_signup"
    root.mkdir(parents=True)
    (root / "questions.json").write_text(json.dumps({"questions": ["Scale?"], "answers": ["80+ is A"]}))
    made = pretend(monkeypatch, [done_reply()])
    run_cli(monkeypatch, tmp_path, ["build", "church_signup", "--run", "t"], [])
    assert "Q: Scale?\nA: 80+ is A" in made[0][0]["content"]


def test_cli_question_step_failing_is_reported_not_raised(monkeypatch, tmp_path, capsys):
    def broken(*args, **kwargs):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(agent, "clarify", broken)
    made = pretend(monkeypatch, [done_reply()])
    run_cli(monkeypatch, tmp_path, ["build", "church_signup", "--ask", "3", "--run", "t"], [])
    assert "not built: APIConnectionError" in capsys.readouterr().out and made == []


# The recipe search tool
def test_search_is_off_by_default_and_then_unknown(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("search_docs", {"query": "primary key"}), done_reply()])
    agent.build("make an app", tmp_path)
    assert "search_docs" not in pretend.offered[0][1] and "Unknown tool" in made[-1][2]["content"][0]["content"]


def test_search_on_offers_the_tool_and_returns_recipes(monkeypatch, tmp_path):
    import kb.search
    monkeypatch.setattr(kb.search, "search_docs", lambda q, k=3, method="dense": [{"id": "01", "text": f"# Primary key ({q})"}])
    made = pretend(monkeypatch, [tool_reply("search_docs", {"query": "no primary key"}), done_reply()])
    result = agent.build("make an app", tmp_path, search=True)
    system, names = pretend.offered[0]
    assert "search_docs" in names and system.endswith(agent.SEARCH_HINT) and result["search"] is True
    sent_back = made[-1][2]["content"][0]
    assert not sent_back["is_error"] and sent_back["content"] == "Recipe 01: # Primary key (no primary key)"


def test_search_without_the_dense_library_falls_back_to_keywords(monkeypatch):
    import kb.search

    def find(q, k=3, method="dense"):
        if method == "dense":
            raise ImportError("dense search needs sentence-transformers")
        return [{"id": "15", "text": "No double booking"}]
    monkeypatch.setattr(kb.search, "search_docs", find)
    assert agent.search_docs("booked twice")["output"] == "Recipe 15: No double booking"
    monkeypatch.setattr(kb.search, "search_docs", lambda q, k=3, method="dense": [])
    assert agent.search_docs("!!!")["output"] == "No recipe matches."


def test_search_with_wrong_arguments_is_reported(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("search_docs", {"q": "x"}), done_reply()])
    agent.build("make an app", tmp_path, search=True)
    assert "Bad arguments for search_docs" in made[-1][2]["content"][0]["content"]


# A change after the backend is live
def test_change_without_an_app_or_with_no_change_costs_nothing(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [done_reply()])
    assert agent.build("church events", tmp_path, change="add cancelling")["stop"] == "no app.py to change: build it first"
    (tmp_path / "app.py").write_text("x = 1\n")
    assert agent.build("church events", tmp_path, change="  ")["stop"] == "nothing to change" and made == []


def test_change_sends_the_old_request_and_the_change(monkeypatch, tmp_path):
    pretend(monkeypatch, [tool_reply("write_file", {"path": "app.py", "content": "v1\n"}), done_reply("Built")])
    agent.build("church events", tmp_path)
    made = pretend(monkeypatch, [tool_reply("edit_file", {"path": "app.py", "old": "v1", "new": "v2"}), done_reply("Changed")])
    result = agent.build("church events", tmp_path, change="add cancelling a sign-up")
    first = made[0][0]["content"]
    assert first.startswith("The client's app is already built") and "church events" in first and "add cancelling a sign-up" in first
    assert (tmp_path / "app.py").read_text() == "v2\n"
    assert result["change"] == "add cancelling a sign-up" and result["summary"] == "Changed"


def test_cli_change_edits_the_app_in_the_run_folder(monkeypatch, tmp_path):
    root = tmp_path / "projects" / "t" / "church_signup"
    root.mkdir(parents=True)
    (root / "app.py").write_text("v1\n")
    made = pretend(monkeypatch, [done_reply()])
    run_cli(monkeypatch, tmp_path, ["change", "church_signup", "--what", "add cancelling", "--run", "t"], [])
    assert "add cancelling" in made[0][0]["content"]

"""The client's journey, with a pretend Claude and no Docker (free).

    uv run --with anthropic python -m pytest builder/tests/test_session.py -q
"""

import time

import pytest

from builder import agent, session
from builder.tests.test_agent import done_reply, pretend, tool_reply

PLAN = {"summary": "s", "data": [], "endpoints": [], "rules": []}
PASSED = {"stop": "end_turn", "tests": {"passed": 3, "failed": 0}, "cost_usd": 0.1, "summary": "Done"}
LIVE = {"ok": True, "url": "https://x/b/1", "docs_url": "https://x/b/1/docs", "endpoints": ["GET /a"], "output": ""}


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setattr(session, "BUILDS", tmp_path)
    monkeypatch.setattr(session, "clarify", lambda *a: (["When?", "Where?"], 0.01))
    monkeypatch.setattr(session, "make_plan", lambda *a, **k: (PLAN, 0.02))
    built = []

    def fake_build(request, root, model, **k):
        built.append(k)
        (root / "app.py").write_text("x = 1\n")
        return PASSED
    monkeypatch.setattr(session, "build", fake_build)
    monkeypatch.setattr(session, "deploy", lambda root, name: LIVE)
    monkeypatch.setattr(session, "keeps_database", lambda root: {"ok": True, "output": ""})
    monkeypatch.setattr(session, "plain_summary", lambda request, notes, model: ("Your sheet is ready.", 0.001))
    return built


def wait(sid, state):
    for _ in range(300):
        if session.get(sid)["state"] == state:
            return session.get(sid)
        time.sleep(0.01)
    raise AssertionError(f"{session.get(sid)['state']} is not {state}: {session.SESSIONS[sid].events}")


def test_whole_journey_ends_with_a_live_link(world):
    sid = session.start("a sign-up sheet")
    assert wait(sid, "waiting_answers")["questions"] == ["When?", "Where?"]
    session.send(sid, ["Monday", "Accra"])
    assert wait(sid, "waiting_approval")["plan_text"]
    assert world == []  # nothing is built before approval
    session.approve(sid)
    got = wait(sid, "live")
    assert got["url"] == "https://x/b/1" and got["endpoints"] == ["GET /a"] and world[0]["plan"] == PLAN
    assert "Monday" in session.SESSIONS[sid].request


def test_approving_twice_builds_once(world):
    sid = session.start("x")
    wait(sid, "waiting_answers")
    session.send(sid, "ok")
    wait(sid, "waiting_approval")
    session.approve(sid)
    with pytest.raises(session.Refused):
        session.approve(sid)
    wait(sid, "live")
    assert len(world) == 1


def test_no_questions_goes_straight_to_the_plan(world, monkeypatch):
    monkeypatch.setattr(session, "clarify", lambda *a: ([], 0.01))
    wait(session.start("clear request"), "waiting_approval")


def test_a_message_after_going_live_changes_the_app(world):
    sid = session.start("x")
    wait(sid, "waiting_answers")
    session.send(sid, "ok")
    wait(sid, "waiting_approval")
    session.approve(sid)
    wait(sid, "live")
    session.send(sid, "add a phone number")
    for _ in range(300):
        if len(world) == 2:
            break
        time.sleep(0.01)
    assert world[1]["change"] == "add a phone number" and world[1]["plan"] is None
    wait(sid, "live")


@pytest.mark.parametrize("result", [
    {**PASSED, "tests": {"passed": 0, "failed": 0}},  # tests could not run: the build that made this check necessary
    {**PASSED, "tests": None},
    {**PASSED, "tests": {"passed": 3, "failed": 1}},
    {**PASSED, "stop": "max_usd"},
])
def test_untested_or_failing_builds_are_not_published(world, monkeypatch, result):
    published = []
    monkeypatch.setattr(session, "build", lambda request, root, model, **k: ((root / "app.py").write_text("x"), result)[1])
    monkeypatch.setattr(session, "deploy", lambda root, name: published.append(name) or LIVE)
    monkeypatch.setattr(session, "clarify", lambda *a: ([], 0.01))
    sid = session.start("x")
    wait(sid, "waiting_approval")
    session.approve(sid)
    got = wait(sid, "failed")
    assert published == [] and got["url"] is None and "not published" in got["error"]


def approved(sid):
    wait(sid, "waiting_answers")
    session.send(sid, "ok")
    wait(sid, "waiting_approval")
    session.approve(sid)


def test_an_app_that_loses_data_goes_back_to_the_agent_once(world, monkeypatch):
    answers = [{"ok": False, "output": "no database"}, {"ok": True, "output": ""}]
    monkeypatch.setattr(session, "keeps_database", lambda root: answers.pop(0))
    sid = session.start("x")
    approved(sid)
    wait(sid, "live")
    assert len(world) == 2 and "no database" in world[1]["change"]


def test_an_app_that_still_loses_data_is_not_published(world, monkeypatch):
    published = []
    monkeypatch.setattr(session, "keeps_database", lambda root: {"ok": False, "output": "secret detail"})
    monkeypatch.setattr(session, "deploy", lambda root, name: published.append(name) or LIVE)
    sid = session.start("x")
    approved(sid)
    got = wait(sid, "failed")
    assert published == [] and len(world) == 2 and "lose its data" in got["error"]
    assert "secret detail" not in str(session.get(sid))


def test_the_client_reads_the_plain_summary_not_the_builders_notes(world):
    sid = session.start("x")
    approved(sid)
    assert wait(sid, "live")["summary"] == "Your sheet is ready."


def test_a_failed_summary_still_goes_live_without_the_notes(world, monkeypatch):
    def broken(*a):
        raise RuntimeError("no credit")
    monkeypatch.setattr(session, "plain_summary", broken)
    sid = session.start("x")
    approved(sid)
    got = wait(sid, "live")
    assert got["summary"] == session.READY and "no credit" not in str(got)


def test_a_crash_is_reported_without_details(world, monkeypatch):
    def boom(*a):
        raise RuntimeError("secret detail")
    monkeypatch.setattr(session, "clarify", boom)
    sid = session.start("x")
    got = wait(sid, "failed")
    assert "secret detail" not in str(got) and got["error"]


def test_details_of_the_agent_stay_private(world, monkeypatch):
    def fake_build(request, root, model, on_event, **k):
        on_event({"event": "tool", "tool": "write_file", "ok": True, "input": {"content": "SECRET CODE"}, "output": "SECRET OUTPUT"})
        (root / "app.py").write_text("x")
        return PASSED
    monkeypatch.setattr(session, "build", fake_build)
    monkeypatch.setattr(session, "clarify", lambda *a: ([], 0.01))
    sid = session.start("x")
    wait(sid, "waiting_approval")
    session.approve(sid)
    got = wait(sid, "live")
    assert "SECRET" not in str(got) and any(e.get("tool") == "write_file" for e in got["events"])


@pytest.mark.parametrize("bad", ["", "   ", None, 5, "x" * 5001])
def test_bad_requests_are_refused(world, bad):
    with pytest.raises(session.Refused):
        session.start(bad)


def test_daily_limit_stops_new_builds_and_changes(world, monkeypatch):
    monkeypatch.setattr(session, "clarify", lambda *a: ([], 6.0))
    sid = session.start("first")
    wait(sid, "waiting_approval")
    session.approve(sid)
    wait(sid, "live")
    monkeypatch.setattr(session, "MAX_DAILY_USD", 5.0)
    with pytest.raises(session.Refused):
        session.start("second")
    with pytest.raises(session.Refused):
        session.send(sid, "a change")


def test_a_plan_cannot_be_approved_after_the_daily_limit(world, monkeypatch):
    monkeypatch.setattr(session, "clarify", lambda *a: ([], 6.0))
    sid = session.start("first")
    wait(sid, "waiting_approval")
    monkeypatch.setattr(session, "MAX_DAILY_USD", 5.0)
    with pytest.raises(session.Refused):
        session.approve(sid)
    assert session.get(sid)["state"] == "waiting_approval"


def test_messages_out_of_turn_are_refused(world):
    with pytest.raises(session.Refused):
        session.send("nope", "hi")
    sid = session.start("x")
    wait(sid, "waiting_answers")
    with pytest.raises(session.Refused):
        session.approve(sid)


def test_message_mid_build_reaches_claude(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [tool_reply("list_files", {}), done_reply()])
    box = [["no adding books"], []]
    agent.build("a library", tmp_path, inbox=lambda: box.pop(0) if box else [])
    sent = made[1][2]["content"]  # the conversation: request, Claude asks for a tool, the results
    assert "no adding books" in sent[-1]["text"] and sent[0]["type"] == "tool_result"  # the API needs tool results first


def test_message_as_claude_finishes_keeps_it_working(monkeypatch, tmp_path):
    made = pretend(monkeypatch, [done_reply("I am done"), done_reply("Changed it")])
    box = [["one more thing"], []]
    result = agent.build("a library", tmp_path, inbox=lambda: box.pop(0))
    assert len(made) == 2 and result["stop"] == "end_turn" and result["summary"] == "Changed it"

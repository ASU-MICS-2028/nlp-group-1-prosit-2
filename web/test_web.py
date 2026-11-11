"""The platform's backend, with a pretend session (free): uv run --with anthropic python -m pytest web -q"""

import time

import pytest
from fastapi.testclient import TestClient

from builder import session
from web import app as web


@pytest.fixture
def api(monkeypatch):
    web.SEEN.clear()
    monkeypatch.setattr(session, "start", lambda r: (_ for _ in ()).throw(session.Refused("Please describe it.")) if not r.strip() else "b1")
    monkeypatch.setattr(session, "get", lambda sid, after=0: {"id": sid, "state": "live", "next": after})
    monkeypatch.setattr(session, "send", lambda sid, m: None)
    monkeypatch.setattr(session, "approve", lambda sid: None)
    monkeypatch.setattr(session, "take_down", lambda sid: None)
    return TestClient(web.app)


def test_page_and_journey(api):
    assert "Backend Builder" in api.get("/").text
    assert api.post("/api/builds", json={"request": "a shop"}).json() == {"id": "b1"}
    assert api.get("/api/builds/b1?after=2").json()["next"] == 2
    assert api.post("/api/builds/b1/messages", json={"message": ["a", "b"]}).status_code == 200
    assert api.post("/api/builds/b1/messages", json={"message": "a change"}).status_code == 200
    assert api.post("/api/builds/b1/approve").status_code == 200
    assert api.post("/api/builds/b1/take-down").status_code == 200


def test_refusals_reach_the_client_in_their_words(api):
    r = api.post("/api/builds", json={"request": "   "})
    assert r.status_code == 400 and r.json()["detail"] == "Please describe it."


@pytest.mark.parametrize("body", [{}, {"request": 5}, {"request": "x" * 5001}])
def test_bad_bodies_are_refused(api, body):
    assert api.post("/api/builds", json=body).status_code == 422


def test_replay_plays_a_saved_session(monkeypatch, tmp_path):
    from web import replay
    saved = "eval/results/sessions/bakery_through_the_page.jsonl"
    for name, fake in replay.fakes(saved, pace=0).items():
        monkeypatch.setattr(session, name, fake)
    monkeypatch.setattr(session, "BUILDS", tmp_path)
    sid = session.start("anything")
    for want, act in [("waiting_answers", lambda: session.send(sid, ["one cake"])), ("waiting_approval", lambda: session.approve(sid)), ("live", None)]:
        for _ in range(100):
            if session.get(sid)["state"] == want:
                break
            time.sleep(0.05)
        assert session.get(sid)["state"] == want
        if act:
            act()
    shown = session.get(sid)
    assert shown["url"] == "https://34-78-38-126.sslip.io/b/bf7fe9a80ae" and shown["endpoints"] == ["GET /cakes", "POST /cakes", "POST /orders"]
    assert [e["tool"] for e in shown["events"] if e.get("kind") == "tool"][:2] == ["write_file", "write_file"]


def test_each_person_has_a_limit(api):
    me, other = {"x-forwarded-for": "1.1.1.1"}, {"x-forwarded-for": "2.2.2.2"}
    for _ in range(5):
        assert api.post("/api/builds", json={"request": "x"}, headers=me).status_code == 201
    assert api.post("/api/builds", json={"request": "x"}, headers=me).status_code == 429
    assert api.post("/api/builds", json={"request": "x"}, headers=other).status_code == 201
    for _ in range(30):
        assert api.post("/api/builds/b1/messages", json={"message": "m"}, headers=me).status_code == 200
    assert api.post("/api/builds/b1/approve", headers=me).status_code == 429
    assert api.post("/api/builds/b1/take-down", headers=me).status_code == 429



"""The platform's backend, with a pretend session (free): uv run --with anthropic python -m pytest web -q"""

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



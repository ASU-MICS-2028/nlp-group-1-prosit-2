"""Tests like the ones the agent will write for itself: they import app.py directly (no server needed)."""

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def make_event(capacity=2):
    r = client.post("/church-events", json={"title": "Choir practice", "date": "2026-11-01", "max_people": capacity})
    assert r.status_code == 201
    return r.json()


def test_create_event():
    event = make_event()
    assert event["title"] == "Choir practice" and "id" in event


def test_list_events():
    event = make_event()
    assert event in client.get("/church-events").json()


def test_get_event():
    event = make_event()
    assert client.get(f"/church-events/{event['id']}").json() == event


def test_get_missing_event_is_404():
    assert client.get("/church-events/999999").status_code == 404


def test_sign_up():
    event = make_event()
    r = client.post(f"/church-events/{event['id']}/signups", json={"name": "Ama", "phone": "0200000000"})
    assert r.status_code == 201


def test_signups_are_listed():
    event = make_event()
    client.post(f"/church-events/{event['id']}/signups", json={"name": "Kofi", "phone": "0200000001"})
    assert client.get(f"/church-events/{event['id']}/signups").json() == [{"name": "Kofi", "phone": "0200000001"}]


def test_full_event_refuses_sign_up():
    event = make_event(capacity=1)
    client.post(f"/church-events/{event['id']}/signups", json={"name": "Ama", "phone": "0200000000"})
    r = client.post(f"/church-events/{event['id']}/signups", json={"name": "Kofi", "phone": "0200000001"})
    assert r.status_code == 409


def test_bad_date_is_rejected():
    r = client.post("/church-events", json={"title": "x", "date": "not a date", "max_people": 1})
    assert r.status_code == 422

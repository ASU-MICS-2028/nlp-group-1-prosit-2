import uuid


def new_event(api, capacity=3):
    name = f"Choir practice {uuid.uuid4().hex[:6]}"
    status, event = api.call("create_event", json={"name": name, "date": "2026-11-01", "capacity": capacity})
    assert 200 <= status < 300, event
    return event


def test_create_event_returns_it_with_an_id(api):
    event = new_event(api)
    assert "id" in event
    assert event["capacity"] == 3


def test_created_event_appears_in_list(api):
    event = new_event(api)
    status, events = api.call("list_events")
    assert status == 200
    assert event["id"] in [e["id"] for e in events]


def test_get_event_by_id(api):
    event = new_event(api)
    status, got = api.call("get_event", path_params={"id": event["id"]})
    assert status == 200
    assert got["name"] == event["name"]


def test_get_missing_event_is_404(api):
    status, _ = api.call("get_event", path_params={"id": 987654321})
    assert status == 404


def test_sign_up_then_appears_in_signups(api):
    event = new_event(api)
    status, _ = api.call("sign_up", path_params={"id": event["id"]}, json={"name": "Ama Mensah", "phone": "0244123456"})
    assert 200 <= status < 300
    status, people = api.call("list_signups", path_params={"id": event["id"]})
    assert status == 200
    assert [p["name"] for p in people] == ["Ama Mensah"]


def test_new_event_has_no_signups(api):
    event = new_event(api)
    status, people = api.call("list_signups", path_params={"id": event["id"]})
    assert status == 200
    assert people == []


def test_full_event_refuses_signup(api):
    event = new_event(api, capacity=1)
    api.call("sign_up", path_params={"id": event["id"]}, json={"name": "Kofi", "phone": "0201111111"})
    status, _ = api.call("sign_up", path_params={"id": event["id"]}, json={"name": "Esi", "phone": "0202222222"})
    assert 400 <= status < 500
    _, people = api.call("list_signups", path_params={"id": event["id"]})
    assert len(people) == 1


def test_sign_up_for_missing_event_is_404(api):
    status, _ = api.call("sign_up", path_params={"id": 987654321}, json={"name": "Yaw", "phone": "0203333333"})
    assert status == 404


def test_create_event_without_name_is_refused(api):
    status, _ = api.call("create_event", json={"date": "2026-11-01", "capacity": 5})
    assert 400 <= status < 500


def test_signups_are_per_event(api):
    a, b = new_event(api), new_event(api)
    api.call("sign_up", path_params={"id": a["id"]}, json={"name": "Akosua", "phone": "0204444444"})
    _, people_b = api.call("list_signups", path_params={"id": b["id"]})
    assert people_b == []

import uuid


def stops():
    tag = uuid.uuid4().hex[:6]
    return f"Circle {tag}", f"Madina {tag}"


def new_route(api, a, b, fare=7.5):
    status, route = api.call("create_route", json={"from_stop": a, "to_stop": b, "fare": fare})
    assert status in (200, 201), route
    return route


def fare(api, a, b):
    return api.call("find_fare", params={"from_stop": a, "to_stop": b})


def test_create_route_returns_it_with_an_id(api):
    a, b = stops()
    route = new_route(api, a, b)
    assert "id" in route
    assert route["fare"] == 7.5


def test_created_route_appears_in_list(api):
    a, b = stops()
    route = new_route(api, a, b)
    status, routes = api.call("list_routes")
    assert status == 200
    assert route["id"] in [r["id"] for r in routes]


def test_find_fare_between_two_stops(api):
    a, b = stops()
    route = new_route(api, a, b, fare=8.25)
    status, found = fare(api, a, b)
    assert status == 200
    assert found["id"] == route["id"]
    assert found["fare"] == 8.25


def test_fare_is_the_same_in_the_other_direction(api):
    a, b = stops()
    route = new_route(api, a, b, fare=6)
    status, found = fare(api, b, a)
    assert status == 200
    assert found["id"] == route["id"]
    assert found["fare"] == 6


def test_unknown_route_is_404(api):
    a, b = stops()
    status, _ = fare(api, a, b)
    assert status == 404


def test_no_fare_for_stops_only_linked_through_another_stop(api):
    a, b = stops()
    c = f"Kaneshie {uuid.uuid4().hex[:6]}"
    new_route(api, a, b)
    new_route(api, b, c)
    status, _ = fare(api, a, c)
    assert status == 404


def test_update_fare_changes_the_lookup(api):
    a, b = stops()
    route = new_route(api, a, b, fare=7.5)
    status, _ = api.call("update_fare", path_params={"id": route["id"]}, json={"fare": 9})
    assert 200 <= status < 300
    _, found = fare(api, a, b)
    assert found["fare"] == 9


def test_update_missing_route_is_404(api):
    status, _ = api.call("update_fare", path_params={"id": 987654321}, json={"fare": 9})
    assert status == 404


def test_zero_or_negative_fare_is_refused(api):
    a, b = stops()
    status, _ = api.call("create_route", json={"from_stop": a, "to_stop": b, "fare": 0})
    assert 400 <= status < 500
    status, _ = api.call("create_route", json={"from_stop": a, "to_stop": b, "fare": -3})
    assert 400 <= status < 500
    status, _ = fare(api, a, b)
    assert status == 404


def test_update_to_bad_fare_is_refused_and_fare_kept(api):
    a, b = stops()
    route = new_route(api, a, b, fare=7.5)
    status, _ = api.call("update_fare", path_params={"id": route["id"]}, json={"fare": 0})
    assert 400 <= status < 500
    _, found = fare(api, a, b)
    assert found["fare"] == 7.5


def test_duplicate_route_is_refused(api):
    a, b = stops()
    new_route(api, a, b)
    status, _ = api.call("create_route", json={"from_stop": a, "to_stop": b, "fare": 10})
    assert 400 <= status < 500


def test_same_route_in_reverse_is_refused(api):
    a, b = stops()
    new_route(api, a, b, fare=7.5)
    status, _ = api.call("create_route", json={"from_stop": b, "to_stop": a, "fare": 10})
    assert 400 <= status < 500
    _, found = fare(api, b, a)
    assert found["fare"] == 7.5


def test_route_without_stop_is_refused(api):
    status, _ = api.call("create_route", json={"from_stop": "Circle", "fare": 5})
    assert 400 <= status < 500

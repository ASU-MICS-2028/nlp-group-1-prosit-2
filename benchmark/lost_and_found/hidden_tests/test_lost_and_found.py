import uuid

MISSING = 987654321


def ok(status):
    return 200 <= status < 300


def refused(status):
    return 400 <= status < 500


def new_item(api):
    body = {"description": f"Black umbrella {uuid.uuid4().hex[:6]}", "place": "Library steps", "date_found": "2026-10-20"}
    status, item = api.call("report_item", json=body)
    assert ok(status), item
    return item


def get(api, item):
    status, got = api.call("get_item", path_params={"id": item["id"]})
    assert status == 200, got
    return got


def claim(api, item, owner):
    return api.call("claim_item", path_params={"id": item["id"]}, json={"owner_name": owner})[0]


def test_report_item_returns_it_unclaimed(api):
    item = new_item(api)
    assert "id" in item
    assert item["claimed"] is False


def test_reported_item_appears_in_list(api):
    item = new_item(api)
    status, items = api.call("list_items")
    assert status == 200
    assert item["id"] in [i["id"] for i in items]


def test_get_item_by_id(api):
    item = new_item(api)
    got = get(api, item)
    assert got["description"] == item["description"]
    assert got["place"] == "Library steps"
    assert got["date_found"] == "2026-10-20"


def test_get_missing_item_is_404(api):
    status, _ = api.call("get_item", path_params={"id": MISSING})
    assert status == 404


def test_claiming_marks_item_claimed_with_owner(api):
    item = new_item(api)
    assert ok(claim(api, item, "Kwesi Appiah"))
    got = get(api, item)
    assert got["claimed"] is True
    assert got["owner_name"] == "Kwesi Appiah"


def test_claimed_item_cannot_be_claimed_again(api):
    item = new_item(api)
    claim(api, item, "Adwoa Sarpong")
    assert refused(claim(api, item, "Selorm Agbeko"))
    assert get(api, item)["owner_name"] == "Adwoa Sarpong"


def test_claiming_one_item_leaves_others_unclaimed(api):
    a, b = new_item(api), new_item(api)
    claim(api, a, "Fiifi Ansah")
    assert get(api, b)["claimed"] is False
    assert ok(claim(api, b, "Naa Okailey"))


def test_unclaimed_list_shows_only_waiting_items(api):
    waiting, taken = new_item(api), new_item(api)
    claim(api, taken, "Dede Tetteh")
    status, items = api.call("list_unclaimed")
    assert status == 200
    found = [i["id"] for i in items]
    assert waiting["id"] in found
    assert taken["id"] not in found


def test_claimed_item_stays_in_full_list(api):
    item = new_item(api)
    claim(api, item, "Edem Kumah")
    _, items = api.call("list_items")
    assert item["id"] in [i["id"] for i in items]


def test_claim_missing_item_is_404(api):
    status, _ = api.call("claim_item", path_params={"id": MISSING}, json={"owner_name": "Kafui Dzidzor"})
    assert status == 404


def test_claim_without_owner_name_is_refused(api):
    item = new_item(api)
    status, _ = api.call("claim_item", path_params={"id": item["id"]}, json={})
    assert refused(status)
    assert get(api, item)["claimed"] is False


def test_report_without_description_is_refused(api):
    status, _ = api.call("report_item", json={"place": "Cafeteria", "date_found": "2026-10-21"})
    assert refused(status)

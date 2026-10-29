import uuid

MISSING = 987654321


def ok(status):
    return 200 <= status < 300


def refused(status):
    return 400 <= status < 500


def new_item(api, name=None, price=12.5, category="Drinks"):
    name = name or f"Milo tin {uuid.uuid4().hex[:6]}"
    status, item = api.call("add_item", json={"name": name, "price": price, "category": category})
    assert ok(status), item
    return item


def get(api, item):
    return api.call("get_item", path_params={"id": item["id"]})


def listed_ids(api, params=None):
    status, items = api.call("list_items", params=params)
    assert status == 200, items
    return [i["id"] for i in items]


def test_add_item_returns_it_with_an_id(api):
    item = new_item(api)
    assert "id" in item
    assert float(item["price"]) == 12.5


def test_added_item_appears_in_list(api):
    item = new_item(api)
    assert item["id"] in listed_ids(api)


def test_get_item_shows_its_price_and_category(api):
    item = new_item(api, price=8.75, category="Foodstuff")
    status, got = get(api, item)
    assert status == 200
    assert got["name"] == item["name"]
    assert float(got["price"]) == 8.75
    assert got["category"] == "Foodstuff"


def test_get_missing_item_is_404(api):
    status, _ = api.call("get_item", path_params={"id": MISSING})
    assert status == 404


def test_price_can_be_changed(api):
    item = new_item(api, price=20)
    status, _ = api.call("change_price", path_params={"id": item["id"]}, json={"price": 23.5})
    assert ok(status)
    assert float(get(api, item)[1]["price"]) == 23.5


def test_changing_price_to_zero_or_less_is_refused(api):
    item = new_item(api, price=5)
    for bad in (0, -2):
        status, _ = api.call("change_price", path_params={"id": item["id"]}, json={"price": bad})
        assert refused(status)
    assert float(get(api, item)[1]["price"]) == 5


def test_adding_with_zero_or_negative_price_is_refused(api):
    for bad in (0, -1.5):
        status, _ = api.call("add_item", json={"name": f"Sugar {uuid.uuid4().hex[:6]}", "price": bad, "category": "Foodstuff"})
        assert refused(status)


def test_duplicate_name_is_refused_ignoring_case(api):
    item = new_item(api)
    status, _ = api.call("add_item", json={"name": item["name"].upper(), "price": 13, "category": "Drinks"})
    assert refused(status)
    status, _ = api.call("add_item", json={"name": item["name"], "price": 13, "category": "Drinks"})
    assert refused(status)


def test_removed_item_is_gone(api):
    item = new_item(api)
    status, _ = api.call("remove_item", path_params={"id": item["id"]})
    assert ok(status)
    assert get(api, item)[0] == 404
    assert item["id"] not in listed_ids(api)


def test_removing_one_item_keeps_the_others(api):
    a, b = new_item(api), new_item(api)
    api.call("remove_item", path_params={"id": a["id"]})
    c = new_item(api)
    assert c["id"] != b["id"]
    status, got = get(api, b)
    assert status == 200
    assert got["name"] == b["name"]


def test_list_can_show_one_category(api):
    category = f"Toiletries {uuid.uuid4().hex[:6]}"
    soap, other = new_item(api, category=category), new_item(api, category="Drinks")
    found = listed_ids(api, params={"category": category})
    assert found == [soap["id"]]
    assert other["id"] not in found


def test_remove_missing_item_is_404(api):
    status, _ = api.call("remove_item", path_params={"id": MISSING})
    assert status == 404


def test_add_item_without_name_is_refused(api):
    status, _ = api.call("add_item", json={"price": 3, "category": "Drinks"})
    assert refused(status)

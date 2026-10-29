import uuid


def new_item(api, quantity=20, low_level=5):
    name = f"Tin tomatoes {uuid.uuid4().hex[:6]}"
    status, item = api.call("create_item", json={"name": name, "quantity": quantity, "low_level": low_level})
    assert status in (200, 201), item
    return item


def quantity(api, item):
    status, got = api.call("get_item", path_params={"id": item["id"]})
    assert status == 200, got
    return got["quantity"]


def sell(api, item, n):
    return api.call("record_sale", path_params={"id": item["id"]}, json={"quantity": n})[0]


def restock(api, item, n):
    return api.call("record_restock", path_params={"id": item["id"]}, json={"quantity": n})[0]


def low_ids(api):
    status, items = api.call("list_low_stock")
    assert status == 200, items
    return [i["id"] for i in items]


def test_create_item_returns_it_with_an_id(api):
    item = new_item(api)
    assert "id" in item
    assert item["quantity"] == 20
    assert item["low_level"] == 5


def test_created_item_appears_in_list(api):
    item = new_item(api)
    status, items = api.call("list_items")
    assert status == 200
    assert item["id"] in [i["id"] for i in items]


def test_get_missing_item_is_404(api):
    status, _ = api.call("get_item", path_params={"id": 987654321})
    assert status == 404


def test_create_item_without_name_is_refused(api):
    status, _ = api.call("create_item", json={"quantity": 3, "low_level": 1})
    assert 400 <= status < 500


def test_sale_reduces_quantity(api):
    item = new_item(api, quantity=20)
    assert 200 <= sell(api, item, 6) < 300
    assert quantity(api, item) == 14


def test_selling_everything_is_allowed(api):
    item = new_item(api, quantity=4)
    assert 200 <= sell(api, item, 4) < 300
    assert quantity(api, item) == 0


def test_selling_more_than_in_stock_is_refused(api):
    item = new_item(api, quantity=3)
    assert 400 <= sell(api, item, 4) < 500
    assert quantity(api, item) == 3


def test_restock_increases_quantity(api):
    item = new_item(api, quantity=2)
    assert 200 <= restock(api, item, 10) < 300
    assert quantity(api, item) == 12


def test_zero_or_negative_amounts_are_refused(api):
    item = new_item(api, quantity=10)
    assert 400 <= sell(api, item, 0) < 500
    assert 400 <= sell(api, item, -5) < 500
    assert 400 <= restock(api, item, 0) < 500
    assert 400 <= restock(api, item, -5) < 500
    assert quantity(api, item) == 10


def test_sale_on_missing_item_is_404(api):
    status, _ = api.call("record_sale", path_params={"id": 987654321}, json={"quantity": 1})
    assert status == 404


def test_sales_only_change_that_item(api):
    a, b = new_item(api, quantity=10), new_item(api, quantity=10)
    sell(api, a, 3)
    assert quantity(api, a) == 7
    assert quantity(api, b) == 10


def test_low_stock_list_is_at_or_below_the_level(api):
    below = new_item(api, quantity=2, low_level=5)
    at = new_item(api, quantity=5, low_level=5)
    above = new_item(api, quantity=6, low_level=5)
    low = low_ids(api)
    assert below["id"] in low
    assert at["id"] in low
    assert above["id"] not in low


def test_item_moves_in_and_out_of_low_stock(api):
    item = new_item(api, quantity=8, low_level=5)
    assert item["id"] not in low_ids(api)
    sell(api, item, 4)
    assert item["id"] in low_ids(api)
    restock(api, item, 10)
    assert item["id"] not in low_ids(api)

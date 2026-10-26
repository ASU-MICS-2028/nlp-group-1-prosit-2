import uuid

MEASUREMENTS = {"chest": 40, "waist": 34, "hip": 42, "length": 30}


def new_customer(api):
    name = f"Kwame Boateng {uuid.uuid4().hex[:6]}"
    status, customer = api.call("create_customer", json={"name": name, "phone": "0244123456", "measurements": MEASUREMENTS})
    assert status in (200, 201), customer
    return customer


def new_order(api, customer, due_date="2031-03-10", price=300, deposit=100, garment="Kaftan"):
    status, order = api.call("create_order", path_params={"id": customer["id"]},
                             json={"garment": garment, "due_date": due_date, "price": price, "deposit": deposit})
    assert status in (200, 201), order
    return order


def ids(items):
    return [i["id"] for i in items]


def test_create_customer_keeps_measurements(api):
    customer = new_customer(api)
    assert "id" in customer
    status, got = api.call("get_customer", path_params={"id": customer["id"]})
    assert status == 200
    assert got["name"] == customer["name"]
    assert got["measurements"]["waist"] == 34
    assert got["measurements"]["length"] == 30


def test_get_missing_customer_is_404(api):
    status, _ = api.call("get_customer", path_params={"id": 987654321})
    assert status == 404


def test_create_customer_without_name_is_refused(api):
    status, _ = api.call("create_customer", json={"phone": "0244123456", "measurements": MEASUREMENTS})
    assert 400 <= status < 500


def test_new_order_is_not_collected(api):
    order = new_order(api, new_customer(api))
    status, got = api.call("get_order", path_params={"id": order["id"]})
    assert status == 200
    assert got["garment"] == "Kaftan"
    assert got["price"] == 300
    assert got["deposit"] == 100
    assert got["collected"] is False


def test_orders_are_listed_per_customer(api):
    a, b = new_customer(api), new_customer(api)
    oa = new_order(api, a)
    ob = new_order(api, b)
    status, orders_a = api.call("list_customer_orders", path_params={"id": a["id"]})
    assert status == 200
    assert ids(orders_a) == [oa["id"]]
    _, orders_b = api.call("list_customer_orders", path_params={"id": b["id"]})
    assert ids(orders_b) == [ob["id"]]


def test_deposit_more_than_price_is_refused(api):
    customer = new_customer(api)
    status, _ = api.call("create_order", path_params={"id": customer["id"]},
                         json={"garment": "Smock", "due_date": "2031-03-10", "price": 200, "deposit": 250})
    assert 400 <= status < 500
    _, orders = api.call("list_customer_orders", path_params={"id": customer["id"]})
    assert orders == []


def test_deposit_equal_to_price_is_accepted(api):
    customer = new_customer(api)
    order = new_order(api, customer, price=150, deposit=150)
    assert order["deposit"] == 150


def test_order_for_missing_customer_is_404(api):
    status, _ = api.call("create_order", path_params={"id": 987654321},
                         json={"garment": "Kaba", "due_date": "2031-03-10", "price": 200, "deposit": 50})
    assert status == 404


def test_order_without_garment_is_refused(api):
    customer = new_customer(api)
    status, _ = api.call("create_order", path_params={"id": customer["id"]},
                         json={"due_date": "2031-03-10", "price": 200, "deposit": 50})
    assert 400 <= status < 500


def test_due_list_includes_orders_due_on_or_before_the_date(api):
    customer = new_customer(api)
    early = new_order(api, customer, due_date="2031-03-09")
    on_day = new_order(api, customer, due_date="2031-03-11")
    late = new_order(api, customer, due_date="2031-03-12")
    status, due = api.call("list_due_orders", params={"date": "2031-03-11"})
    assert status == 200
    assert early["id"] in ids(due)
    assert on_day["id"] in ids(due)
    assert late["id"] not in ids(due)


def test_collect_marks_order_collected(api):
    order = new_order(api, new_customer(api))
    status, _ = api.call("collect_order", path_params={"id": order["id"]})
    assert 200 <= status < 300
    _, got = api.call("get_order", path_params={"id": order["id"]})
    assert got["collected"] is True


def test_collected_order_leaves_due_list(api):
    customer = new_customer(api)
    collected = new_order(api, customer, due_date="2031-05-01")
    waiting = new_order(api, customer, due_date="2031-05-01")
    api.call("collect_order", path_params={"id": collected["id"]})
    _, due = api.call("list_due_orders", params={"date": "2031-05-01"})
    assert collected["id"] not in ids(due)
    assert waiting["id"] in ids(due)


def test_collect_missing_order_is_404(api):
    status, _ = api.call("collect_order", path_params={"id": 987654321})
    assert status == 404

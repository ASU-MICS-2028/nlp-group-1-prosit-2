import random
import uuid


def new_table(api, seats=4):
    status, table = api.call("create_table", json={"number": random.randint(1, 10**6), "seats": seats})
    assert status in (200, 201), table
    return table


def reserve(api, table, party_size=2, date="2031-04-18", time="19:30", name=None):
    name = name or f"Efua Asante {uuid.uuid4().hex[:6]}"
    return api.call("make_reservation", path_params={"id": table["id"]},
                    json={"name": name, "phone": "0277123456", "party_size": party_size, "date": date, "time": time})


def reserved(api, table, **kw):
    status, r = reserve(api, table, **kw)
    assert status in (200, 201), r
    return r


def on_date(api, date="2031-04-18"):
    status, rs = api.call("list_reservations", params={"date": date})
    assert status == 200, rs
    return rs


def test_created_table_appears_in_list(api):
    table = new_table(api, seats=6)
    assert "id" in table
    assert table["seats"] == 6
    status, tables = api.call("list_tables")
    assert status == 200
    assert table["id"] in [t["id"] for t in tables]


def test_create_table_without_seats_is_refused(api):
    status, _ = api.call("create_table", json={"number": 12})
    assert 400 <= status < 500


def test_reservation_appears_on_its_date(api):
    table = new_table(api)
    r = reserved(api, table, name=f"Kojo {uuid.uuid4().hex[:6]}")
    assert "id" in r
    mine = [x for x in on_date(api) if x["id"] == r["id"]]
    assert len(mine) == 1
    assert mine[0]["name"] == r["name"]
    assert mine[0]["party_size"] == 2


def test_list_for_a_date_leaves_out_other_dates(api):
    table = new_table(api)
    friday = reserved(api, table, date="2031-04-18")
    saturday = reserved(api, table, date="2031-04-19")
    friday_ids = [x["id"] for x in on_date(api, "2031-04-18")]
    assert friday["id"] in friday_ids
    assert saturday["id"] not in friday_ids


def test_party_equal_to_seats_is_allowed(api):
    table = new_table(api, seats=4)
    status, _ = reserve(api, table, party_size=4)
    assert status in (200, 201)


def test_party_bigger_than_seats_is_refused(api):
    table = new_table(api, seats=4)
    status, _ = reserve(api, table, party_size=5, date="2031-04-20")
    assert 400 <= status < 500
    status, _ = reserve(api, table, party_size=4, date="2031-04-20")
    assert status in (200, 201)


def test_same_table_same_date_and_time_is_refused(api):
    table = new_table(api)
    first = reserved(api, table)
    status, _ = reserve(api, table)
    assert 400 <= status < 500
    ours = [x["id"] for x in on_date(api) if x["id"] == first["id"]]
    assert ours == [first["id"]]


def test_same_table_other_time_or_date_is_allowed(api):
    table = new_table(api)
    reserved(api, table, date="2031-04-18", time="19:30")
    status, _ = reserve(api, table, date="2031-04-18", time="12:00")
    assert status in (200, 201)
    status, _ = reserve(api, table, date="2031-04-25", time="19:30")
    assert status in (200, 201)


def test_other_table_same_date_and_time_is_allowed(api):
    a, b = new_table(api), new_table(api)
    reserved(api, a)
    status, _ = reserve(api, b)
    assert status in (200, 201)


def test_refused_reservation_is_not_listed(api):
    table = new_table(api, seats=2)
    name = f"Too many {uuid.uuid4().hex[:6]}"
    reserve(api, table, party_size=8, name=name)
    assert name not in [x["name"] for x in on_date(api)]


def test_reserving_missing_table_is_refused(api):
    status, _ = reserve(api, {"id": 987654321})
    assert 400 <= status < 500


def test_reservation_without_name_is_refused(api):
    table = new_table(api)
    status, _ = api.call("make_reservation", path_params={"id": table["id"]},
                         json={"phone": "0277123456", "party_size": 2, "date": "2031-04-18", "time": "19:30"})
    assert 400 <= status < 500

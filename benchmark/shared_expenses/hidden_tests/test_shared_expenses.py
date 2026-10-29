import uuid


def close(a, b):
    return abs(float(a) - b) < 0.005


def new_group(api, n=3):
    status, g = api.call("create_group", json={"name": f"Trip {uuid.uuid4().hex[:6]}"})
    assert status in (200, 201), g
    members = []
    for i in range(n):
        status, m = api.call("add_member", path_params={"id": g["id"]}, json={"name": f"Friend {i} {uuid.uuid4().hex[:4]}"})
        assert status in (200, 201), m
        members.append(m)
    return g, members


def expense(api, g, payer, amount, split):
    return api.call("add_expense", path_params={"id": g["id"]},
                    json={"paid_by": payer["id"], "amount": amount, "split_between": [m["id"] for m in split]})


def settle(api, g, payer, receiver, amount):
    return api.call("settle_up", path_params={"id": g["id"]},
                    json={"from_member_id": payer["id"], "to_member_id": receiver["id"], "amount": amount})


def balances(api, g):
    status, rows = api.call("get_balances", path_params={"id": g["id"]})
    assert status == 200, rows
    return {str(r["member_id"]): float(r["balance"]) for r in rows}


def bal(b, m):
    return b[str(m["id"])]


def test_new_group_balances_are_zero(api):
    g, members = new_group(api)
    b = balances(api, g)
    assert len(b) == 3
    assert all(close(bal(b, m), 0) for m in members)


def test_expense_split_equally(api):
    g, (a, b_, c) = new_group(api)
    status, _ = expense(api, g, a, 90, [a, b_, c])
    assert 200 <= status < 300
    b = balances(api, g)
    assert close(bal(b, a), 60) and close(bal(b, b_), -30) and close(bal(b, c), -30)


def test_split_only_between_chosen_members(api):
    g, (a, b_, c, d) = new_group(api, 4)
    expense(api, g, a, 40, [a, b_])
    b = balances(api, g)
    assert close(bal(b, a), 20) and close(bal(b, b_), -20)
    assert close(bal(b, c), 0) and close(bal(b, d), 0)


def test_payer_need_not_be_in_split(api):
    g, (a, b_, c) = new_group(api)
    expense(api, g, a, 50, [b_, c])
    b = balances(api, g)
    assert close(bal(b, a), 50) and close(bal(b, b_), -25) and close(bal(b, c), -25)


def test_uneven_split_is_exact_to_the_pesewa(api):
    g, (a, b_, c) = new_group(api)
    expense(api, g, a, 100, [a, b_, c])
    b = balances(api, g)
    assert close(sum(b.values()), 0)
    shares = [round(-bal(b, b_), 2), round(-bal(b, c), 2), round(100 - bal(b, a), 2)]
    assert close(sum(shares), 100)
    assert all(33.33 - 0.005 < s < 33.34 + 0.005 for s in shares), shares


def test_balances_always_sum_to_zero(api):
    g, (a, b_, c, d) = new_group(api, 4)
    expense(api, g, a, 10, [a, b_, c])
    expense(api, g, b_, 7.31, [a, c, d])
    expense(api, g, d, 0.05, [a, b_, c, d])
    settle(api, g, c, a, 2.5)
    assert close(sum(balances(api, g).values()), 0)


def test_expenses_add_up(api):
    g, (a, b_, c) = new_group(api)
    expense(api, g, a, 30, [a, b_, c])
    expense(api, g, b_, 60, [a, b_, c])
    b = balances(api, g)
    assert close(bal(b, a), 0) and close(bal(b, b_), 30) and close(bal(b, c), -30)


def test_settle_up_moves_balances(api):
    g, (a, b_, c) = new_group(api)
    expense(api, g, a, 90, [a, b_, c])
    status, _ = settle(api, g, b_, a, 30)
    assert 200 <= status < 300
    b = balances(api, g)
    assert close(bal(b, b_), 0) and close(bal(b, a), 30) and close(bal(b, c), -30)


def test_cannot_pay_yourself_back(api):
    g, (a, b_, c) = new_group(api)
    expense(api, g, a, 90, [a, b_, c])
    assert 400 <= settle(api, g, a, a, 10)[0] < 500
    assert close(bal(balances(api, g), a), 60)


def test_amounts_must_be_more_than_zero(api):
    g, (a, b_, c) = new_group(api)
    for bad in (0, -20):
        assert 400 <= expense(api, g, a, bad, [a, b_])[0] < 500, bad
        assert 400 <= settle(api, g, b_, a, bad)[0] < 500, bad
    assert all(close(v, 0) for v in balances(api, g).values())


def test_empty_split_is_refused(api):
    g, (a, b_, c) = new_group(api)
    assert 400 <= expense(api, g, a, 30, [])[0] < 500


def test_split_with_outsider_is_refused(api):
    g, (a, b_, c) = new_group(api)
    other, (x, y, z) = new_group(api)
    assert 400 <= expense(api, g, a, 30, [a, x])[0] < 500
    assert 400 <= expense(api, g, x, 30, [a, b_])[0] < 500
    assert all(close(v, 0) for v in balances(api, g).values())
    assert all(close(v, 0) for v in balances(api, other).values())


def test_settle_with_outsider_is_refused(api):
    g, (a, b_, c) = new_group(api)
    other, (x, y, z) = new_group(api)
    assert 400 <= settle(api, g, a, x, 10)[0] < 500
    assert all(close(v, 0) for v in balances(api, g).values())

import uuid

MISSING = 987654321


def close(a, b):
    return abs(float(a) - float(b)) < 0.005


def new_group(api, n_members=3):
    status, group = api.call("create_group", json={"name": f"Market susu {uuid.uuid4().hex[:6]}"})
    assert status in (200, 201), group
    people = []
    for i in range(n_members):
        status, m = api.call("add_member", path_params={"id": group["id"]},
                             json={"name": f"Member {i} {uuid.uuid4().hex[:4]}", "phone": f"02440000{i:02d}"})
        assert status in (200, 201), m
        people.append(m)
    return group, people


def pay(api, group, member, rnd, amount):
    return api.call("record_contribution", path_params={"id": group["id"]},
                    json={"member_id": member["id"], "round": rnd, "amount": amount})


def collect(api, group, member, rnd):
    return api.call("pay_out", path_params={"id": group["id"]}, json={"member_id": member["id"], "round": rnd})


def statement(api, group, member):
    status, s = api.call("get_statement", path_params={"id": group["id"], "member_id": member["id"]})
    assert status == 200, s
    return s


def test_added_members_are_listed(api):
    group, people = new_group(api)
    status, listed = api.call("list_members", path_params={"id": group["id"]})
    assert status == 200
    assert sorted(m["name"] for m in listed) == sorted(m["name"] for m in people)


def test_contribution_is_recorded(api):
    group, (a, b, c) = new_group(api)
    status, _ = pay(api, group, a, 1, 50)
    assert 200 <= status < 300


def test_statement_totals_a_members_own_contributions(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 50)
    pay(api, group, a, 2, 20.5)
    pay(api, group, b, 1, 100)
    s = statement(api, group, a)
    assert close(s["total_contributed"], 70.5)
    assert close(s["total_received"], 0)


def test_payout_is_that_rounds_total_only(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 50)
    pay(api, group, b, 1, 50)
    pay(api, group, a, 2, 30)
    pay(api, group, b, 2, 40.25)
    pay(api, group, c, 2, 10)
    status, payout = collect(api, group, c, 2)
    assert status in (200, 201), payout
    assert close(payout["amount"], 80.25)


def test_statement_shows_amount_received(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 50)
    pay(api, group, b, 1, 60)
    pay(api, group, c, 1, 70)
    collect(api, group, b, 1)
    sb, sa = statement(api, group, b), statement(api, group, a)
    assert close(sb["total_received"], 180)
    assert close(sb["total_contributed"], 60)
    assert close(sa["total_received"], 0)


def test_member_cannot_collect_twice(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 50)
    pay(api, group, a, 2, 50)
    status, _ = collect(api, group, a, 1)
    assert status in (200, 201)
    status, _ = collect(api, group, a, 2)
    assert 400 <= status < 500
    status, payouts = api.call("list_payouts", path_params={"id": group["id"]})
    assert status == 200
    assert len(payouts) == 1
    assert close(statement(api, group, a)["total_received"], 50)


def test_round_cannot_be_collected_twice(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 40)
    pay(api, group, b, 1, 40)
    collect(api, group, a, 1)
    status, _ = collect(api, group, b, 1)
    assert 400 <= status < 500
    assert close(statement(api, group, b)["total_received"], 0)


def test_empty_round_cannot_be_collected(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 40)
    status, _ = collect(api, group, b, 2)
    assert 400 <= status < 500


def test_no_contributions_after_round_is_collected(api):
    group, (a, b, c) = new_group(api)
    pay(api, group, a, 1, 40)
    collect(api, group, b, 1)
    status, _ = pay(api, group, c, 1, 25)
    assert 400 <= status < 500
    assert close(statement(api, group, c)["total_contributed"], 0)


def test_contribution_must_be_more_than_zero(api):
    group, (a, b, c) = new_group(api)
    assert 400 <= pay(api, group, a, 1, 0)[0] < 500
    assert 400 <= pay(api, group, a, 1, -10)[0] < 500
    assert close(statement(api, group, a)["total_contributed"], 0)


def test_member_of_another_group_cannot_pay_in(api):
    group, (a, b, c) = new_group(api)
    other, (x, y, z) = new_group(api)
    status, _ = pay(api, group, x, 1, 30)
    assert 400 <= status < 500
    assert close(statement(api, other, x)["total_contributed"], 0)


def test_payouts_are_listed_per_group(api):
    group, (a, b, c) = new_group(api)
    other, (x, y, z) = new_group(api)
    pay(api, group, a, 1, 15.5)
    pay(api, group, b, 1, 15.5)
    collect(api, group, b, 1)
    status, payouts = api.call("list_payouts", path_params={"id": group["id"]})
    assert status == 200
    assert len(payouts) == 1
    assert payouts[0]["member_id"] == b["id"] and payouts[0]["round"] == 1
    assert close(payouts[0]["amount"], 31)
    _, other_payouts = api.call("list_payouts", path_params={"id": other["id"]})
    assert other_payouts == []


def test_full_cycle_pays_everyone_once(api):
    group, people = new_group(api)
    for rnd, collector in enumerate(people, start=1):
        for p in people:
            pay(api, group, p, rnd, 20)
        status, payout = collect(api, group, collector, rnd)
        assert status in (200, 201)
        assert close(payout["amount"], 60)
    for p in people:
        s = statement(api, group, p)
        assert close(s["total_contributed"], 60) and close(s["total_received"], 60)


def test_statement_for_missing_member_is_refused(api):
    group, _ = new_group(api, n_members=1)
    status, _ = api.call("get_statement", path_params={"id": group["id"], "member_id": MISSING})
    assert 400 <= status < 500

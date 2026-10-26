import uuid

MISSING = 987654321


def money(x):
    return float(x)  # a number or decimal text such as "10.50"


def close(a, b):
    return abs(money(a) - b) < 0.005


def new_phone():
    return "024" + f"{uuid.uuid4().int % 10**7:07d}"


def new_wallet(api, deposit=None):
    status, w = api.call("open_wallet", json={"name": f"Akua {uuid.uuid4().hex[:6]}", "phone": new_phone()})
    assert status in (200, 201), w
    if deposit is not None:
        status, body = api.call("deposit", path_params={"id": w["id"]}, json={"amount": deposit})
        assert 200 <= status < 300, body
    return w


def balance(api, w):
    status, got = api.call("get_wallet", path_params={"id": w["id"]})
    assert status == 200, got
    return money(got["balance"])


def send(api, a, b, amount):
    return api.call("transfer", json={"from_wallet_id": a["id"], "to_wallet_id": b["id"], "amount": amount})


def test_new_wallet_starts_at_zero(api):
    w = new_wallet(api)
    status, got = api.call("get_wallet", path_params={"id": w["id"]})
    assert status == 200
    assert got["name"] == w["name"]
    assert close(got["balance"], 0)


def test_same_phone_cannot_open_two_wallets(api):
    phone = new_phone()
    status, _ = api.call("open_wallet", json={"name": "Kwame", "phone": phone})
    assert status in (200, 201)
    status, _ = api.call("open_wallet", json={"name": "Kwame again", "phone": phone})
    assert 400 <= status < 500


def test_deposits_add_up(api):
    w = new_wallet(api, deposit=50)
    api.call("deposit", path_params={"id": w["id"]}, json={"amount": 25.75})
    assert close(balance(api, w), 75.75)


def test_deposit_must_be_positive_with_two_decimals_at_most(api):
    w = new_wallet(api, deposit=10)
    for bad in (0, -5, 1.005):
        status, _ = api.call("deposit", path_params={"id": w["id"]}, json={"amount": bad})
        assert 400 <= status < 500, bad
    assert close(balance(api, w), 10)


def test_transfer_moves_money(api):
    a, b = new_wallet(api, deposit=100), new_wallet(api, deposit=5)
    status, _ = send(api, a, b, 30.5)
    assert 200 <= status < 300
    assert close(balance(api, a), 69.5)
    assert close(balance(api, b), 35.5)


def test_transfer_is_exact_to_the_pesewa(api):
    a, b = new_wallet(api, deposit=0.7), new_wallet(api)
    api.call("deposit", path_params={"id": a["id"]}, json={"amount": 0.1})
    status, _ = send(api, a, b, 0.8)
    assert 200 <= status < 300
    assert close(balance(api, a), 0)
    assert close(balance(api, b), 0.8)


def test_cannot_send_more_than_balance(api):
    a, b = new_wallet(api, deposit=20), new_wallet(api)
    status, _ = send(api, a, b, 20.01)
    assert 400 <= status < 500
    assert close(balance(api, a), 20)
    assert close(balance(api, b), 0)


def test_can_send_whole_balance(api):
    a, b = new_wallet(api, deposit=20), new_wallet(api)
    status, _ = send(api, a, b, 20)
    assert 200 <= status < 300
    assert close(balance(api, a), 0)


def test_transfer_to_self_is_refused(api):
    a = new_wallet(api, deposit=20)
    status, _ = send(api, a, a, 5)
    assert 400 <= status < 500
    assert close(balance(api, a), 20)


def test_transfer_amount_must_be_positive(api):
    a, b = new_wallet(api, deposit=20), new_wallet(api, deposit=20)
    for bad in (0, -10):
        status, _ = send(api, a, b, bad)
        assert 400 <= status < 500, bad
    assert close(balance(api, a), 20)
    assert close(balance(api, b), 20)


def test_transfer_to_missing_wallet_is_refused(api):
    a = new_wallet(api, deposit=20)
    status, _ = api.call("transfer", json={"from_wallet_id": a["id"], "to_wallet_id": MISSING, "amount": 5})
    assert 400 <= status < 500
    assert close(balance(api, a), 20)


def test_history_shows_amounts_and_running_balance(api):
    a, b = new_wallet(api, deposit=100), new_wallet(api, deposit=10)
    send(api, a, b, 40)
    send(api, b, a, 15.25)
    status, hist = api.call("list_transactions", path_params={"id": a["id"]})
    assert status == 200
    got = sorted((round(money(e["amount"]), 2), round(money(e["balance_after"]), 2)) for e in hist)
    assert got == sorted([(100.0, 100.0), (40.0, 60.0), (15.25, 75.25)])
    _, hist_b = api.call("list_transactions", path_params={"id": b["id"]})
    got_b = sorted((round(money(e["amount"]), 2), round(money(e["balance_after"]), 2)) for e in hist_b)
    assert got_b == sorted([(10.0, 10.0), (40.0, 50.0), (15.25, 34.75)])


def test_get_missing_wallet_is_404(api):
    status, _ = api.call("get_wallet", path_params={"id": MISSING})
    assert status == 404

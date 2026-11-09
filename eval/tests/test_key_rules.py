"""Finding a record by name instead of id, with a pretend backend (free).

    uv run python -m pytest eval/tests/test_key_rules.py -q
"""

import json

import httpx

from eval import bench  # noqa: F401  (puts benchmark/ on the path)
from conftest import Api

OPS = {"add": {"method": "POST", "path": "/people", "saves_key": {"as": "person", "field": "name"}},
       "pay": {"method": "POST", "path": "/pay", "uses_key": {"by": "person", "split": "person"}},
       "see": {"method": "GET", "path": "/people/{id}", "uses_key": {"id": "person"}},
       "balance": {"method": "GET", "path": "/balances", "uses_key": {"member_id": "person"}},
       "plain": {"method": "POST", "path": "/plain"}}


def api_with(seen):
    def answer(request):
        seen.append(request)
        if request.url.path == "/people":
            return httpx.Response(201, json={"id": 7, "name": "Ama"})
        if request.url.path == "/balances":
            return httpx.Response(200, json=[{"member_id": "Ama", "balance": 5}, {"member_id": "Unknown", "balance": 1}])
        return httpx.Response(200, json={})
    api = Api("http://x", OPS)
    api.client = httpx.Client(base_url="http://x", transport=httpx.MockTransport(answer))
    return api


def test_ids_become_names_going_out_and_ids_coming_back():
    seen = []
    api = api_with(seen)
    api.call("add", json={"name": "Ama"})
    api.call("pay", json={"by": 7, "split": [7, 99], "amount": 3})
    assert json.loads(seen[1].content) == {"by": "Ama", "split": ["Ama", 99], "amount": 3}
    api.call("see", path_params={"id": 7})
    assert seen[2].url.path == "/people/Ama"
    assert api.call("balance")[1] == [{"member_id": 7, "balance": 5}, {"member_id": "Unknown", "balance": 1}]


def test_a_map_with_no_rules_changes_nothing():
    seen = []
    api = api_with(seen)
    api.call("add", json={"name": "Ama"})
    api.call("plain", json={"by": 7})
    assert seen[1].content == b'{"by":7}' or b'"by": 7' in seen[1].content


def test_a_failed_create_remembers_nothing():
    api = Api("http://x", OPS)
    api.client = httpx.Client(base_url="http://x", transport=httpx.MockTransport(lambda r: httpx.Response(422, json={"id": 1, "name": "x"})))
    api.call("add", json={"name": "x"})
    assert api.keys == {}

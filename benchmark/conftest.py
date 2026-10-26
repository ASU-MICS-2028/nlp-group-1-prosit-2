"""Shared fixture for every benchmark task: call operations by name, not by URL.

The backend under test may use its own paths and field names. ops.json (written by the agent after
a build) maps each operation to {method, path, fields}; this file translates request bodies to the
backend's names and responses back to the test's names. See benchmark/README.md.
"""

import json
import os

import httpx
import pytest


class Api:
    def __init__(self, base_url, ops):
        self.client = httpx.Client(base_url=base_url, timeout=10)
        self.ops = ops

    def call(self, op, path_params=None, json=None, params=None):
        """Call an operation by name. json is the body, params the query string (?date=...).
        Field names are translated both ways, at every depth (nested objects and lists too)."""
        spec = self.ops[op]
        fields = spec.get("fields", {})
        back = {v: k for k, v in fields.items()}
        path = spec["path"].format(**(path_params or {}))
        out = lambda d: rename(d, fields)
        r = self.client.request(spec["method"], path, json=out(json) if json is not None else None,
                                params=out(params) if params else None)
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, rename(data, back)


def rename(data, names):
    if isinstance(data, dict):
        return {names.get(k, k): rename(v, names) for k, v in data.items()}
    if isinstance(data, list):
        return [rename(v, names) for v in data]
    return data


@pytest.fixture(scope="session")
def api():
    base_url = os.environ.get("BASE_URL")
    ops_file = os.environ.get("OPS_FILE")
    if not base_url or not ops_file:
        pytest.skip("set BASE_URL and OPS_FILE to run benchmark tests (see benchmark/README.md)")
    with open(ops_file) as f:
        return Api(base_url, json.load(f))


def pytest_collection_modifyitems(items):
    """BENCH_ORDER=reverse runs the tests backwards, to check no test depends on an earlier one."""
    if os.environ.get("BENCH_ORDER") == "reverse":
        items.reverse()

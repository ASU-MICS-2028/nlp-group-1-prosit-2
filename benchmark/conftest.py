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

    def call(self, op, path_params=None, json=None):
        spec = self.ops[op]
        fields = spec.get("fields", {})
        back = {v: k for k, v in fields.items()}
        path = spec["path"].format(**(path_params or {}))
        body = {fields.get(k, k): v for k, v in json.items()} if json is not None else None
        r = self.client.request(spec["method"], path, json=body)
        try:
            data = r.json()
        except ValueError:
            data = None
        rename = lambda d: {back.get(k, k): v for k, v in d.items()} if isinstance(d, dict) else d
        data = [rename(d) for d in data] if isinstance(data, list) else rename(data)
        return r.status_code, data


@pytest.fixture(scope="session")
def api():
    base_url = os.environ.get("BASE_URL")
    ops_file = os.environ.get("OPS_FILE")
    if not base_url or not ops_file:
        pytest.skip("set BASE_URL and OPS_FILE to run benchmark tests (see benchmark/README.md)")
    with open(ops_file) as f:
        return Api(base_url, json.load(f))

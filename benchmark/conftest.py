"""Shared fixture for every benchmark task: call operations by name, not by URL.

The backend under test may use its own paths and field names. ops.json (written by the agent after
a build) maps each operation to {method, path, fields}; this file translates request bodies to the
backend's names and responses back to the test's names. See benchmark/README.md.
"""

import json
import os
import string

import httpx
import pytest


class Api:
    def __init__(self, base_url, ops):
        self.client = httpx.Client(base_url=base_url, timeout=10)
        self.ops = ops

    def call(self, op, path_params=None, json=None, params=None):
        """Call an operation by name. json is the body, params the query string (?date=...).
        Field names are translated at every depth (nested objects and lists too): "fields" both ways,
        "request_fields" only in what is sent, "response_fields" only in the reply. A dotted test name
        ("measurements.chest") means the test nests the value where the backend keeps it flat ("chest").
        "response_key" unwraps a reply the backend wraps (e.g. {"signups": [...]} -> the list)."""
        spec = self.ops[op]
        fields = spec.get("fields", {})  # names used both ways
        sent = {**fields, **spec.get("request_fields", {})}  # names only in what we send (body, query string)
        back = {v: k for k, v in {**fields, **spec.get("response_fields", {})}.items()}  # names only in the reply
        # Where a value goes can differ too: a value the tests give as a path parameter may belong in the body
        # (or the query string for GET), and a placeholder in the backend's path may come from the body.
        path_params, json = dict(path_params or {}), (dict(json) if isinstance(json, dict) else json)
        params = dict(params) if params else params
        wanted = {name for _, name, _, _ in string.Formatter().parse(spec["path"]) if name}  # {placeholders} in the path
        for name in wanted - path_params.keys():
            if isinstance(json, dict) and name in json:
                path_params[name] = json.pop(name)
            elif params and name in params:
                path_params[name] = params.pop(name)
        extra = {k: v for k, v in path_params.items() if k not in wanted}
        if extra:
            if spec["method"] == "GET":
                params = {**(params or {}), **extra}
            else:
                json = {**extra, **(json if isinstance(json, dict) else {})}
        path = spec["path"].format(**path_params)
        out = lambda d: rename(flatten(d, sent), sent)
        r = self.client.request(spec["method"], path, json=out(json) if json is not None else None,
                                params=out(params) if params else None)
        try:
            data = r.json()
        except ValueError:
            data = None
        key = spec.get("response_key")
        if key and isinstance(data, dict) and key in data:
            data = data[key]
        return r.status_code, nest(rename(data, back))


def flatten(data, names):
    """Move test values nested as {"measurements": {"chest": 40}} to the top level when names has "measurements.chest"."""
    if not isinstance(data, dict):
        return data
    data = dict(data)
    for dotted in [k for k in names if "." in k]:
        outer, inner = dotted.split(".", 1)
        if isinstance(data.get(outer), dict) and inner in data[outer]:
            data[dotted] = data[outer].pop(inner)
            if not data[outer]:
                del data[outer]
    return data


def nest(data):
    """The reverse of flatten, on replies: "measurements.chest": 40 becomes {"measurements": {"chest": 40}}."""
    if isinstance(data, list):
        return [nest(v) for v in data]
    if not isinstance(data, dict):
        return data
    out = {}
    for k, v in data.items():
        if "." in k:
            outer, inner = k.split(".", 1)
            out.setdefault(outer, {})[inner] = v
        else:
            out[k] = nest(v)
    return out


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

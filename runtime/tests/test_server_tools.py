"""Tests for start_server, http_request and stop_server. Run: uv run pytest runtime -q"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from church_bugs import make_broken  # noqa: E402
from runtime.tools import LIMIT, SERVERS, http_request, start_server, stop_server, write_file  # noqa: E402

EVENT = {"title": "Youth camp", "date": "2026-12-01", "max_people": 1}


@pytest.fixture
def project(tmp_path):
    root = make_broken(None, tmp_path / "project")  # the correct church app
    yield root
    stop_server(root)


def started(root):
    result = start_server(root)
    assert result["ok"], result["output"]
    return result


def test_church_reference_end_to_end(project):
    assert started(project)["output"].startswith("Server running at http://127.0.0.1:")
    created = http_request(project, "POST", "/church-events", EVENT)
    assert created["ok"] and created["output"].startswith("201\n")
    event_id = json.loads(created["output"].split("\n", 1)[1])["id"]
    assert http_request(project, "GET", f"/church-events/{event_id}")["output"].startswith("200\n")
    person = {"name": "Ama", "phone": "0200000000"}
    assert http_request(project, "POST", f"/church-events/{event_id}/signups", person)["output"].startswith("201")
    assert http_request(project, "POST", f"/church-events/{event_id}/signups", person)["output"] == \
        '409\n{"detail":"This event is full"}'
    assert http_request(project, "GET", "/church-events/999")["output"] == '404\n{"detail":"No such event"}'


def test_two_projects_run_at_once_on_different_ports(project, tmp_path):
    other = make_broken(None, tmp_path / "other")
    try:
        a, b = started(project)["output"], started(other)["output"]
        assert a != b
        assert http_request(other, "GET", "/church-events")["output"] == "200\n[]"
    finally:
        stop_server(other)


def test_app_that_crashes_on_start_returns_its_error(tmp_path):
    result = start_server(make_broken("import_typo", tmp_path / "p"))
    assert not result["ok"] and "Server crashed while starting" in result["output"]
    assert "cannot import name 'BaseModle'" in result["output"]


def test_missing_app_py(tmp_path):
    result = start_server(tmp_path)
    assert not result["ok"] and 'Could not import module "app"' in result["output"]


def test_app_that_never_answers_is_stopped(tmp_path):
    write_file(tmp_path, "app.py", "import time\ntime.sleep(600)\n")
    result = start_server(tmp_path, timeout=3)
    assert result["output"].startswith("Server did not answer within 3 seconds")
    assert str(tmp_path.resolve()) not in SERVERS


def test_request_without_a_server(project):
    assert http_request(project, "GET", "/") == {"ok": False, "output": "No server is running: call start_server first"}


@pytest.mark.parametrize("path", ["http://example.com/", "example.com", "@example.com", ""])
def test_requests_to_other_websites_are_refused(project, path):
    started(project)
    assert http_request(project, "GET", path)["output"].startswith("Refused")


def test_double_slash_still_goes_to_our_own_server(project):
    started(project)  # the path is glued onto http://127.0.0.1:PORT, so this is our server's 404
    assert http_request(project, "GET", "//example.com")["output"] == '404\n{"detail":"Not Found"}'


def test_unknown_method_is_refused(project):
    started(project)
    assert http_request(project, "HACK", "/")["output"] == "Refused: unknown method 'HACK'"


def test_slow_endpoint_times_out_and_huge_or_plain_text_replies_are_handled(tmp_path):
    app = (
        "import time\nfrom fastapi import FastAPI\nfrom fastapi.responses import PlainTextResponse\napp = FastAPI()\n"
        "@app.get('/slow')\ndef slow():\n    time.sleep(30)\n"
        "@app.get('/huge')\ndef huge():\n    return 'x' * 1_000_000\n"
        "@app.get('/text', response_class=PlainTextResponse)\ndef text():\n    return 'hello'\n"
        "@app.get('/die')\ndef die():\n    import os\n    os._exit(1)\n"
    )
    write_file(tmp_path, "app.py", app)
    try:
        started(tmp_path)
        assert http_request(tmp_path, "GET", "/slow", timeout=2) == {"ok": False, "output": "No answer within 2 seconds"}
        assert len(http_request(tmp_path, "GET", "/huge")["output"]) < LIMIT + 100
        assert http_request(tmp_path, "GET", "/text")["output"] == "200\nhello"
        assert http_request(tmp_path, "GET", "/die")["output"].startswith("The server has stopped. Its log:")
        assert http_request(tmp_path, "GET", "/text")["output"] == "No server is running: call start_server first"
    finally:
        stop_server(tmp_path)


def test_stop(project):
    started(project)
    assert stop_server(project)["output"].startswith("Stopped the server at")
    assert stop_server(project) == {"ok": False, "output": "No server is running for this project"}

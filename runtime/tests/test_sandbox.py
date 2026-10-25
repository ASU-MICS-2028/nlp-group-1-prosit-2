"""Tests that the Docker sandbox really isolates generated code. Run: uv run pytest runtime -q
Skipped with SANDBOX=subprocess, which isolates nothing (see learnings, section 5)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from church_bugs import make_broken  # noqa: E402
from runtime import sandbox  # noqa: E402
from runtime.tools import http_request, run_tests, start_server, stop_server, write_file  # noqa: E402

pytestmark = pytest.mark.skipif(sandbox.MODE != "docker", reason="only the Docker sandbox isolates")


@pytest.fixture
def project(tmp_path):
    (tmp_path / "outside_secret.txt").write_text("SECRET")
    return make_broken(None, tmp_path / "project")


def passes(project, test_code):
    """Write one test file into the project and run it in the sandbox. True if it passed."""
    write_file(project, "tests/test_attack.py", test_code)
    return run_tests(project, "tests/test_attack.py")


def w2_containers():
    names = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
    return [n for n in names.split() if n.startswith("w2-")]


def test_no_internet(project):
    code = "import httpx, pytest\n\ndef test_x():\n    with pytest.raises(httpx.HTTPError):\n" \
           "        httpx.get('http://example.com', timeout=5)\n"
    assert passes(project, code)["ok"]


def test_files_outside_the_project_do_not_exist(project):
    code = "import os\n\ndef test_x():\n    assert not os.path.exists('../outside_secret.txt')\n" \
           "    assert 'Users' not in os.listdir('/')  # '/' is the image's own Linux system, not our laptop\n"
    assert passes(project, code)["ok"]


def test_system_files_are_read_only_and_user_is_not_root(project):
    code = "import os, pytest\n\ndef test_x():\n    assert os.getuid() == 1000\n" \
           "    with pytest.raises(OSError):\n        open('/usr/evil.txt', 'w')\n"
    assert passes(project, code)["ok"]


def test_too_much_memory_is_killed_and_explained(project):
    result = passes(project, "def test_x():\n    b = bytearray(1_000_000_000)\n")
    assert not result["ok"] and result["output"].startswith("Tests were killed: they used more than")


def test_stuck_test_container_is_removed(project):
    write_file(project, "tests/test_stuck.py", "def test_forever():\n    while True:\n        pass\n")
    result = run_tests(project, "tests/test_stuck.py", timeout=8)
    assert result["output"].startswith("Tests stopped: still running after 8 seconds")
    assert w2_containers() == []


def test_sqlite_database_can_be_written_in_the_project(project):
    code = ("import sqlite3\n\ndef test_x():\n    db = sqlite3.connect('app.db')\n"
            "    db.execute('create table t (x)')\n    db.commit()\n")
    assert passes(project, code)["ok"] and (project / "app.db").exists()


def test_server_cannot_reach_the_internet_but_we_can_reach_it(project):
    app = ("import httpx\nfrom fastapi import FastAPI\napp = FastAPI()\n@app.get('/out')\ndef out():\n"
           "    try:\n        httpx.get('http://example.com', timeout=5)\n        return 'REACHED'\n"
           "    except httpx.HTTPError:\n        return 'blocked'\n")
    write_file(project, "app.py", app)
    try:
        assert start_server(project)["ok"]
        assert http_request(project, "GET", "/out") == {"ok": True, "output": '200\n"blocked"'}
    finally:
        stop_server(project)
    assert w2_containers() == []

"""Tests for run_tests. Run: uv run pytest runtime -q"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from church_bugs import make_broken  # noqa: E402
from runtime.tools import LIMIT, run_tests, write_file  # noqa: E402


@pytest.fixture
def project(tmp_path):
    return make_broken(None, tmp_path / "project")  # the correct church app + agent-style tests


def test_church_tests_pass(project):
    result = run_tests(project)
    assert result["ok"] and "8 passed" in result["output"]


def test_a_bug_makes_it_fail_and_says_why(tmp_path):
    result = run_tests(make_broken("off_by_one", tmp_path / "p"))
    assert not result["ok"]
    assert "1 failed, 7 passed" in result["output"] and "test_full_event_refuses_sign_up" in result["output"]


def test_syntax_error_is_reported(tmp_path):
    result = run_tests(make_broken("syntax_error", tmp_path / "p"))
    assert not result["ok"] and "SyntaxError" in result["output"]


def test_huge_output_is_cut_but_keeps_the_summary(tmp_path):
    result = run_tests(make_broken("noisy_debug", tmp_path / "p"))
    assert len(result["output"]) < LIMIT + 100 and "1 failed, 7 passed" in result["output"]


def test_no_tests(project):
    write_file(project, "empty/readme.txt", "nothing here")
    assert run_tests(project, "empty") == {"ok": False, "output": "No tests found in empty"}


def test_path_outside_is_refused(project):
    assert run_tests(project, "../..")["output"].startswith("Refused")


def test_stuck_test_is_stopped(project):
    write_file(project, "tests/test_stuck.py", "def test_forever():\n    while True:\n        pass\n")
    result = run_tests(project, "tests/test_stuck.py", timeout=3)
    assert result == {"ok": False, "output": "Tests stopped: still running after 3 seconds "
                                             "(something may be stuck in a loop or waiting)"}


def test_tests_cannot_see_the_api_key(project, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-fake-key-for-test")
    write_file(project, "tests/test_key.py", "import os\n\ndef test_key():\n    assert 'LLM_API_KEY' not in os.environ\n")
    assert run_tests(project, "tests/test_key.py")["ok"]

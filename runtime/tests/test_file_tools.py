"""Tests for the file tools. Run: uv run pytest runtime -q"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from runtime.tools import LIMIT, cut, edit_file, list_files, read_file, write_file

REFERENCE = Path(__file__).resolve().parents[2] / "benchmark" / "church_signup" / "reference"


@pytest.fixture
def project(tmp_path):
    """A fresh copy of the church reference backend, plus a fake .env and .git, for each test."""
    root = tmp_path / "project"
    shutil.copytree(REFERENCE, root, ignore=shutil.ignore_patterns("__pycache__"))
    (root / ".env").write_text("LLM_API_KEY=fake")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x")
    return root


def test_write_then_read_back(project):
    assert write_file(project, "tests/test_app.py", "def test_x():\n    assert True\n")["ok"]
    assert read_file(project, "tests/test_app.py")["output"] == "def test_x():\n    assert True\n"


def test_read_the_church_reference(project):
    result = read_file(project, "app.py")
    assert result["ok"] and "@app.post(\"/church-events\"" in result["output"]


@pytest.mark.parametrize("path", ["../outside.txt", "C:\\Windows\\win.ini", "/etc/passwd", ".env", ".git/config", ""])
def test_paths_outside_or_protected_are_refused(project, path):
    for result in (write_file(project, path, "x"), read_file(project, path), edit_file(project, path, "x", "y")):
        assert not result["ok"] and result["output"].startswith("Refused")
    assert not (project.parent / "outside.txt").exists()
    assert (project / ".env").read_text() == "LLM_API_KEY=fake"


def test_read_missing_file(project):
    assert read_file(project, "nope.py") == {"ok": False, "output": "No such file: nope.py"}


def test_read_binary_file_is_refused(project):
    (project / "logo.png").write_bytes(bytes(range(256)))
    assert read_file(project, "logo.png")["output"] == "Refused: logo.png is not a text file"


def test_huge_file_is_cut_when_read(project):
    (project / "big.txt").write_text("START" + "x" * 10_000_000 + "END")
    output = read_file(project, "big.txt")["output"]
    assert output.startswith("START") and output.endswith("END") and "characters cut" in output
    assert len(output) < LIMIT + 100


def test_huge_write_is_refused(project):
    result = write_file(project, "big.py", "x" * 10_000_000)
    assert not result["ok"] and not (project / "big.py").exists()


def test_empty_file_can_be_written(project):
    assert write_file(project, "empty.py", "")["ok"] and read_file(project, "empty.py")["output"] == ""


def test_writing_onto_a_folder_is_refused(project):
    (project / "tests").mkdir()
    assert write_file(project, "tests", "x")["output"] == "Refused: tests is a folder, not a file"


def test_edit_replaces_exactly_one_match(project):
    result = edit_file(project, "app.py", "This event is full", "Sorry, this event is full")
    assert result["ok"] and "Sorry, this event is full" in (project / "app.py").read_text()


@pytest.mark.parametrize("old, found", [("not in the file", 0), ("@app.get", 3), ("", 0)])
def test_edit_refuses_zero_or_many_matches(project, old, found):
    before = (project / "app.py").read_text()
    result = edit_file(project, "app.py", old, "x")
    assert not result["ok"] and f"found {found} times" in result["output"]
    assert (project / "app.py").read_text() == before


def test_edit_missing_file(project):
    assert edit_file(project, "nope.py", "a", "b") == {"ok": False, "output": "No such file: nope.py"}


def test_list_hides_secrets_clutter_and_outside_links(project, tmp_path):
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "app.pyc").write_text("x")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET")
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(project / "link"), str(outside)], capture_output=True)
    else:
        os.symlink(outside, project / "link")
    assert list_files(project) == {"ok": True, "output": "app.py\nops.json"}


def test_list_empty_project(tmp_path):
    assert list_files(tmp_path)["output"] == "(no files yet)"


def test_cut_keeps_short_text_and_both_ends_of_long_text():
    assert cut("hello") == "hello"
    long = "A" * 3000 + "B" * 3000
    out = cut(long)
    assert out.startswith("A" * 2000) and out.endswith("B" * 2000) and "[2000 characters cut]" in out

"""Experiment: how much test output should the LLM get back? Run: uv run python runtime/experiments/output_limit.py

For each of the 7 planted bugs, run pytest with 3 traceback styles, then cut the output 6 ways
(2,000 / 4,000 / 8,000 characters x keep start and end / keep start only).
Score: can the LLM still see (1) the summary line, (2) every failing test's name, (3) what is wrong?
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from church_bugs import BUGS, make_broken  # noqa: E402
from runtime.tools import clean_env, cut  # noqa: E402

# The words that tell a reader what is wrong, for each bug.
CAUSE = {
    "wrong_status": "assert 200 == 201",
    "off_by_one": "assert 201 == 409",
    "syntax_error": "SyntaxError",
    "import_typo": "cannot import name 'BaseModle'",
    "wrong_path": "Not Found",
    "renamed_field": "assert 422 == 201",
    "noisy_debug": "assert 201 == 409",
}


def head_only(text, limit):
    return text if len(text) <= limit else text[:limit] + f"\n... [{len(text) - limit} characters cut]"


def pytest_output(folder, tb):
    command = [sys.executable, "-m", "pytest", "tests", "-q", f"--tb={tb}", "-p", "no:cacheprovider"]
    r = subprocess.run(command, cwd=folder, env=clean_env(), capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout + r.stderr


def score(full, shown, bug):
    """How many of the 3 facts in the full output can still be seen in the shown output (0 to 3)."""
    summary = full.strip().splitlines()[-1]
    failing = re.findall(r"^(?:FAILED|ERROR) \S+?(?:::(\w+))?(?: |$)", full, flags=re.M)
    names_seen = all(name in shown for name in failing if name)
    return (summary in shown) + names_seen + (CAUSE[bug] in shown)


if __name__ == "__main__":
    folder = Path(tempfile.mkdtemp()) / "p"
    styles, limits = ["long", "short", "line"], [2000, 4000, 8000]
    raw = {tb: {} for tb in styles}
    for bug in BUGS:
        make_broken(bug, folder)
        for tb in styles:
            raw[tb][bug] = pytest_output(folder, tb)
            assert CAUSE[bug] in raw[tb][bug], (bug, tb)  # the fact must be in the full output

    print("Full output size in characters (no cut):")
    print(f"{'bug':15}" + "".join(f"{tb:>9}" for tb in styles))
    for bug in BUGS:
        print(f"{bug:15}" + "".join(f"{len(raw[tb][bug]):9}" for tb in styles))

    print("\nFacts still visible after cutting (out of 7 bugs x 3 facts = 21), and average characters sent:")
    print(f"{'tb style':9} {'limit':>6} {'start+end':>16} {'start only':>16}")
    for tb in styles:
        for limit in limits:
            cells = []
            for method in (cut, head_only):
                shown = {bug: method(raw[tb][bug], limit) for bug in BUGS}
                facts = sum(score(raw[tb][bug], shown[bug], bug) for bug in BUGS)
                chars = sum(len(s) for s in shown.values()) // len(BUGS)
                cells.append(f"{facts:2}/21 {chars:6}ch")
            print(f"{tb:9} {limit:6} {cells[0]:>16} {cells[1]:>16}")

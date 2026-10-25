"""Experiment: how long should run_tests wait before stopping the tests? 30, 60 or 120 seconds.
Run: uv run python runtime/experiments/timeout_choice.py   (Docker sandbox, takes about 5 minutes)

Good runs: the church tests (8) and a bigger project (the same tests copied 5 times = 40), 5 runs each.
A limit that is shorter than a good run wrongly kills it. Stuck run: a test that never ends; check each
limit stops it, how long it really takes, and that no container is left behind.
"""

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from church_bugs import make_broken  # noqa: E402
from runtime.tools import run_tests, write_file  # noqa: E402


def seconds(root, path="tests", timeout=300):
    start = time.time()
    result = run_tests(root, path, timeout=timeout)
    return time.time() - start, result


if __name__ == "__main__":
    base = Path(tempfile.mkdtemp())
    small = make_broken(None, base / "small")
    big = make_broken(None, base / "big")
    for i in range(2, 6):
        shutil.copy(big / "tests" / "test_app.py", big / "tests" / f"test_app_{i}.py")

    for name, root in [("8 tests", small), ("40 tests", big)]:
        times = [seconds(root)[0] for _ in range(5)]
        print(f"good run, {name}: slowest of 5 = {max(times):.1f} s (median {sorted(times)[2]:.1f} s)")

    write_file(small, "tests/test_stuck.py", "def test_forever():\n    while True:\n        pass\n")
    for limit in [30, 60, 120]:
        took, result = seconds(small, "tests/test_stuck.py", timeout=limit)
        left = subprocess.run(["docker", "ps", "-aq", "--filter", "name=w2-"], capture_output=True, text=True).stdout
        print(f"stuck test, limit {limit:3} s: stopped after {took:.1f} s, "
              f"says '{result['output'][:40]}...', containers left: {len(left.split())}")

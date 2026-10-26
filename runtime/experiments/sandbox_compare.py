"""Experiment: Docker vs subprocess sandbox, on speed and isolation.
Run: uv run python runtime/experiments/sandbox_compare.py   (needs Docker running and the w2-sandbox image)

Speed, same church project for both: run_tests and start_server 10 times each; then 200 GET and 200 POST
requests straight to the running server (endpoint latency, p50 and p95).
Isolation: 7 small scripts that try to escape, each run once in each sandbox.
"""

import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from church_bugs import make_broken  # noqa: E402
from runtime import sandbox  # noqa: E402
from runtime.tools import run_tests, start_server, stop_server, write_file  # noqa: E402

os.environ["LLM_API_KEY"] = "fake-key-for-the-experiment"  # a fake key: can the sandboxed code see it?

CHECKS = {
    "internet": "import httpx\ntry:\n    httpx.get('http://example.com', timeout=5)\n    print('REACHED example.com')\n"
                "except Exception as e:\n    print('blocked:', type(e).__name__)",
    "file outside the project": "try:\n    print('READ:', open('../outside_secret.txt').read())\n"
                                "except OSError as e:\n    print('blocked:', type(e).__name__)",
    "write outside the project": "try:\n    open('../escaped.txt', 'w').write('x')\n    print('WROTE ../escaped.txt')\n"
                                 "except OSError as e:\n    print('blocked:', type(e).__name__)",
    "API key in settings": "import os\nprint('SAW THE KEY' if 'LLM_API_KEY' in os.environ else 'not there')",
    "memory: take 1 GB": "b = bytearray(1_000_000_000)\nprint('GOT 1 GB')",
    "CPU: 4 busy processes": (
        "import multiprocessing, time\n"
        "def work(_):\n    return sum(i * i for i in range(6_000_000))\n"
        "if __name__ == '__main__':\n    start = time.time()\n"
        "    with multiprocessing.Pool(4) as pool:\n        pool.map(work, range(4))\n"
        "    print(f'4 jobs took {time.time() - start:.1f} s')"),
    "run as administrator": "import os\nprint('uid', os.getuid() if hasattr(os, 'getuid') else 'n/a (Windows)')",
}


def timed(fn, n):
    times, failed = [], 0
    for _ in range(n):
        start = time.time()
        failed += not fn()["ok"]
        times.append(time.time() - start)
    return f"median {statistics.median(times):.2f} s, max {max(times):.2f} s, failed {failed}/{n}"


def latency(url):
    ms = {"GET": [], "POST": []}
    with httpx.Client(base_url=url) as client:
        for method in ms:
            for i in range(200):
                start = time.perf_counter()
                if method == "GET":
                    client.get("/church-events")
                else:
                    client.post("/church-events", json={"title": f"e{i}", "date": "2026-01-01", "max_people": 3})
                ms[method].append((time.perf_counter() - start) * 1000)
    q = lambda xs: f"p50 {statistics.median(xs):.1f} ms, p95 {statistics.quantiles(xs, n=20)[-1]:.1f} ms"
    return " | ".join(f"{m} {q(xs)}" for m, xs in ms.items())


def check(root, code):
    write_file(root, "check.py", code)
    name = sandbox.new_name()
    try:
        r = subprocess.run(sandbox.command(str(root), ["python", "check.py"], name), cwd=root,
                           env=sandbox.host_env(), capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        sandbox.remove(name)
        return "stopped by the time limit"
    out = (r.stdout.strip() or r.stderr.strip().splitlines()[-1] if (r.stdout or r.stderr) else "")
    return out if r.returncode == 0 else f"killed (exit code {r.returncode}) {out}"[:90]


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # print each line as soon as it is ready
    for mode in ["subprocess", "docker"]:
        sandbox.MODE = mode
        base = Path(tempfile.mkdtemp())
        (base / "outside_secret.txt").write_text("SECRET")
        root = make_broken(None, base / "project")
        print(f"\n=== {mode}")
        print("run_tests    :", timed(lambda: run_tests(root), 10))
        print("start_server :", timed(lambda: start_server(root), 10))
        url = start_server(root)["output"].split()[-1]
        print("endpoints    :", latency(url))
        stop_server(root)
        for name, code in CHECKS.items():
            print(f"{name:26}: {check(root, code)}")
        print("escaped.txt exists outside:", (base / "escaped.txt").exists())

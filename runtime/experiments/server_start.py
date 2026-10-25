"""Experiment: how should start_server pick a port and know the server is ready?
Run: uv run python runtime/experiments/server_start.py

1. Waiting, 10 starts each, timed from launch to the first successful request:
   fixed sleep 1 s / 2 s; ask every 0.1 s with a 1 s connect limit; same with a 0.1 s connect limit;
   watch uvicorn's log for "Application startup complete".
2. Port: always 8001 vs a free port from the operating system. Start two projects at the same time.
"""

import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from church_bugs import make_broken  # noqa: E402
from runtime.tools import clean_env, free_port, start_server, stop_server  # noqa: E402


def launch(root, port, log):
    command = [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)]
    return subprocess.Popen(command, cwd=root, env=clean_env(), stdout=log, stderr=subprocess.STDOUT)


def answers(url, connect):
    try:
        httpx.get(url, timeout=httpx.Timeout(5, connect=connect))
        return True
    except httpx.HTTPError:
        return False


def wait_sleep(seconds):
    return lambda url, log: time.sleep(seconds)


def wait_poll(connect):
    def wait(url, log):
        while not answers(url, connect):
            time.sleep(0.1)
    return wait


def wait_log(url, log):
    while "Application startup complete" not in log.read_text(errors="replace"):
        time.sleep(0.1)


def one_start(root, wait):
    port = free_port()
    url = f"http://127.0.0.1:{port}/church-events"
    log = Path(tempfile.mkdtemp()) / "server.log"
    start = time.time()
    with open(log, "w") as f:
        process = launch(root, port, f)
    wait(url, log)
    worked = answers(url, 1)
    spent = time.time() - start
    process.kill()
    process.wait()
    return worked, spent


if __name__ == "__main__":
    base = Path(tempfile.mkdtemp())
    a, b = make_broken(None, base / "a"), make_broken(None, base / "b")

    print("1. Waiting for the server (10 starts each, seconds from launch to first good request)")
    options = [("sleep 1 s", wait_sleep(1)), ("sleep 2 s", wait_sleep(2)),
               ("poll, 1 s connect limit", wait_poll(1)), ("poll, 0.1 s connect limit", wait_poll(0.1)),
               ("watch the log", wait_log)]
    for name, wait in options:
        results = [one_start(a, wait) for _ in range(10)]
        times = [t for _, t in results]
        print(f"   {name:26} worked {sum(w for w, _ in results)}/10, median {statistics.median(times):.2f}, "
              f"max {max(times):.2f}")

    print("\n2. Two projects at the same time")
    logs = [Path(tempfile.mkdtemp()) / "server.log" for _ in range(2)]
    processes = []
    for root, log in zip((a, b), logs):
        with open(log, "w") as f:
            processes.append(launch(root, 8001, f))
    time.sleep(3)
    for name, p, log in zip(("first", "second"), processes, logs):
        state = "running" if p.poll() is None else "died: " + log.read_text(errors="replace").strip().splitlines()[-1]
        print(f"   fixed port 8001, {name}: {state}")
        p.kill()
    r1, r2 = start_server(a), start_server(b)
    print(f"   free port: {r1['output']} | {r2['output']}")
    stop_server(a)
    stop_server(b)

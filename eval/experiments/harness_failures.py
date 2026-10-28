"""Failure cases for the eval harness: deliberately bad backends for the church task, each scored by the harness.

    uv run python -m eval.experiments.harness_failures
Free (every backend comes with its ops.json, so Opus is never called). Writes eval/results/harness_failures.json.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from unittest import mock

from eval import bench, harness

TASK = "church_signup"
GOOD = (bench.BENCH / TASK / "reference" / "app.py").read_text()
OPS = json.loads((bench.BENCH / TASK / "reference" / "ops.json").read_text())
HERE = bench.WORK / "_failures"
ENV_FILE = bench.ROOT / ".env"  # only checked for existence from inside the sandbox; never opened

# name -> (app.py, ops.json). None means the file is left out.
CASES = {
    "no_app_py": (None, OPS),
    "empty_app_py": ("", OPS),
    "crash_on_import": ("raise RuntimeError('broken on purpose')\n", OPS),
    "no_app_object": ("x = 1\n", OPS),
    "hangs_while_starting": ("import time\ntime.sleep(10**6)\n" + GOOD, OPS),
    "every_reply_takes_2s": ("import time\n" + GOOD + "\n@app.middleware('http')\nasync def slow(request, call_next):\n"
                             "    __import__('time').sleep(2)\n    return await call_next(request)\n", OPS),
    "huge_reply_50mb": (GOOD + "\n@app.middleware('http')\nasync def huge(request, call_next):\n"
                        "    from fastapi.responses import JSONResponse\n"
                        "    if request.method == 'GET' and request.url.path == '/church-events':\n"
                        "        return JSONResponse([{'id': i, 'title': 'x' * 500} for i in range(100000)])\n"
                        "    return await call_next(request)\n", OPS),
    "uses_too_much_memory": ("blob = bytearray(1024 * 1024 * 1024)\n" + GOOD, OPS),
    "ops_json_not_json": (GOOD, "{not json"),
    "ops_json_missing_an_operation": (GOOD, {k: v for k, v in OPS.items() if k != "sign_up"}),
    "tries_internet_and_files": ("import pathlib, urllib.request\nflags = {}\n"
                                 "try:\n    urllib.request.urlopen('https://example.com', timeout=3); flags['internet'] = True\n"
                                 "except Exception as e:\n    flags['internet'] = False\n"
                                 f"flags['env_file_visible'] = pathlib.Path({str(ENV_FILE)!r}).exists()\n"
                                 f"flags['repo_visible'] = pathlib.Path({str(bench.ROOT / 'benchmark')!r}).exists()\n"
                                 "pathlib.Path('/app/flags.json').write_text(__import__('json').dumps(flags))\n" + GOOD, OPS),
}
# A reply that never comes: the route sleeps longer than the tests' 10 s request limit.
CASES["one_endpoint_never_answers"] = (GOOD + "\n@app.middleware('http')\nasync def hang(request, call_next):\n"
                                       "    if request.method == 'GET' and request.url.path == '/church-events':\n"
                                       "        __import__('time').sleep(60)\n    return await call_next(request)\n", OPS)


def build(name, app, ops):
    folder = HERE / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    if app is not None:
        (folder / "app.py").write_text(app)
    (folder / "ops.json").write_text(ops if isinstance(ops, str) else json.dumps(ops))
    return folder


def main():
    rows = {}
    for name, (app, ops) in CASES.items():
        folder = build(name, app, ops)
        start = time.time()
        try:
            r = harness.run_one(TASK, name, folder, f"failure_{name}")
        except Exception as e:  # the harness itself broke: that is the finding
            r = {"passed": 0, "total": 10, "error": f"HARNESS CRASHED: {e!r}"}
        r["wall_seconds"] = round(time.time() - start, 1)
        flags = bench.WORK / TASK / f"failure_{name}" / "flags.json"
        if flags.exists():
            r["flags"] = json.loads(flags.read_text())
        rows[name] = r
        print(f"{name:32} {r['passed']:>2}/{r['total']} {r['wall_seconds']:>6}s {r.get('flags', '')} {r.get('error', '')[-90:]!r}", flush=True)

    # The 300 s limit on a whole test run: pretend pytest ran out of time.
    from validate import hidden_tests
    with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 300)):
        rows["test_run_over_300s"] = hidden_tests(TASK, "http://127.0.0.1:1", HERE / "x.json")
    print("test_run_over_300s", rows["test_run_over_300s"])

    # Docker off: point the docker command at a daemon that does not exist.
    env = {**os.environ, "DOCKER_HOST": "unix:///nonexistent.sock"}
    p = subprocess.run([sys.executable, "-m", "eval.harness", TASK, str(build("docker_off", GOOD, OPS)), "--name", "failure_docker_off"],
                       env=env, capture_output=True, text=True, cwd=bench.ROOT, timeout=120)
    rows["docker_off"] = {"exit_code": p.returncode, "output": p.stdout[-400:] + p.stderr[-400:]}
    print("docker_off", rows["docker_off"])

    # Killed mid-run: start a full run, kill -9 it while servers are up, then see what the next run cleans up.
    p = subprocess.Popen([sys.executable, "-m", "eval.harness", "all", "--references", "--workers", "4", "--name", "failure_killed"],
                         cwd=bench.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)
    os.kill(p.pid, signal.SIGKILL)
    p.wait()
    time.sleep(2)
    left = subprocess.run(["docker", "ps", "-aq", "--filter", "name=^w2-"], capture_output=True, text=True).stdout.split()
    removed = harness.cleanup()
    after = subprocess.run(["docker", "ps", "-aq", "--filter", "name=^w2-"], capture_output=True, text=True).stdout.split()
    rows["killed_mid_run"] = {"left_running": len(left), "cleanup_removed": removed, "left_after_cleanup": len(after)}
    print("killed_mid_run", rows["killed_mid_run"])

    (bench.ROOT / "eval/results/harness_failures.json").write_text(json.dumps(rows, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()

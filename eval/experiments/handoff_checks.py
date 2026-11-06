"""W4 rows 2-5 and 21, the checks first done by hand: free, needs Docker. Writes eval/results/replicated/handoff_checks.json.

    uv run python -m eval.experiments.handoff_checks
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eval import bench, harness
from runtime import sandbox, tools

TASK = "church_signup"
GOOD = (bench.BENCH / TASK / "reference" / "app.py").read_text()
OPS = json.loads((bench.BENCH / TASK / "reference" / "ops.json").read_text())
HOLD = "import sys; sys.path.insert(0, '.')\nfrom runtime.tools import start_server\nimport time\nprint(start_server(sys.argv[1]), flush=True)\ntime.sleep(60 if sys.argv[2] == 'kill' else 0)\n"


def left():
    run = lambda *a: subprocess.run(["docker", *a], capture_output=True, text=True).stdout.split()
    return {"containers": len(run("ps", "-aq", "--filter", "name=^w2-")), "networks": len(run("network", "ls", "-q", "--filter", "name=w2-"))}


def project(code=GOOD):
    d = Path(tempfile.mkdtemp())
    if code is not None:
        (d / "app.py").write_text(code)
    return d


def docker_trouble():
    """Row 2: both tools must say no, and never run the code unprotected."""
    out, env = {}, os.environ.get("DOCKER_HOST")
    os.environ["DOCKER_HOST"] = "unix:///nonexistent.sock"
    a, b = tools.start_server(project()), tools.run_tests(project())
    out["docker_off"] = {"start_server_ok": a["ok"], "run_tests_ok": b["ok"], "start_server_says": a["output"][-160:], "run_tests_says": b["output"][-160:]}
    os.environ.pop("DOCKER_HOST") if env is None else os.environ.update(DOCKER_HOST=env)
    image, sandbox.IMAGE = sandbox.IMAGE, "w2-sandbox-not-built"
    a, b = tools.start_server(project()), tools.run_tests(project())
    out["image_missing"] = {"start_server_ok": a["ok"], "run_tests_ok": b["ok"], "start_server_says": a["output"][-160:], "run_tests_says": b["output"][-160:]}
    sandbox.IMAGE = image
    return out


def side_by_side():
    """Row 3: two copies of the church backend, one after the other, then together."""
    start = time.time()
    a = [bench.score(TASK, f"row3_a{i}", GOOD, OPS)["passed"] for i in range(2)]
    middle = time.time()
    with ThreadPoolExecutor(2) as ex:
        b = [r["passed"] for r in ex.map(lambda i: bench.score(TASK, f"row3_b{i}", GOOD, OPS), range(2))]
    return {"one_after_other": {"passed": a, "seconds": round(middle - start, 1)},
            "side_by_side": {"passed": b, "seconds": round(time.time() - middle, 1)}, "left": left()}


def broken():
    """Row 4: the harness must hear about a broken backend, with the real error."""
    out = {}
    for name, code in {"no_app_py": None, "import_typo": "import fastapii\n" + GOOD, "no_app_object": "x = 1\n"}.items():
        start = time.time()
        r = tools.start_server(project(code))
        out[name] = {"ok": r["ok"], "seconds": round(time.time() - start, 1), "says": r["output"][-120:]}
    out["left"] = left()
    return out


def left_behind():
    """Row 5: what stays behind when a program ends normally, or is killed, while its server runs."""
    out = {}
    for how in ("normal", "kill"):
        p = subprocess.Popen([sys.executable, "-c", HOLD, str(project()), how], cwd=bench.ROOT, stdout=subprocess.PIPE, text=True)
        p.stdout.readline()
        if how == "kill":
            os.kill(p.pid, signal.SIGKILL)
        p.wait()
        time.sleep(3)
        out[how] = left()
    out["cleanup_removed"] = harness.cleanup()
    out["after_cleanup"] = left()
    return out


def rescore_saved_builds():
    """Row 21 again: every saved baseline build with its saved map, against the score written down at the time."""
    rows, same = [], 0
    saved = json.loads((bench.ROOT / "eval/results/baseline_v2.json").read_text())
    for r in saved:
        label = f"baseline_{r['model']}_{r['variant'].replace('+', '_')}"
        folder = bench.WORK / r["task"] / label
        if not (folder / "app.py").exists() or not r.get("ops"):
            rows.append({"task": r["task"], "label": label, "was": r.get("passed"), "now": None})
            continue
        got = bench.score(r["task"], f"rescore_{label}", (folder / "app.py").read_text(), r["ops"])
        rows.append({"task": r["task"], "label": label, "was": r.get("passed"), "now": got["passed"]})
        same += r.get("passed") == got["passed"]
    return {"rescored": sum(x["now"] is not None for x in rows), "identical": same, "not_on_this_laptop": sum(x["now"] is None for x in rows), "rows": rows}


if __name__ == "__main__":
    harness.cleanup()
    out = {"date": time.strftime("%Y-%m-%d"), "machine": sys.platform}
    for row, work in {"row2_docker_trouble": docker_trouble, "row3_side_by_side": side_by_side, "row4_broken": broken,
                      "row5_left_behind": left_behind, "row21_rescore": rescore_saved_builds}.items():
        out[row] = work()
        print(row, str(out[row])[:400], flush=True)
    path = bench.ROOT / "eval/results/replicated/handoff_checks.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")

"""Check that benchmark tasks are good rulers before anything is measured with them.

    uv run python benchmark/validate.py                  # every task
    uv run python benchmark/validate.py church_signup    # one or more tasks

For each task, every backend is started in Bernard's sandbox (runtime.tools.start_server), as the
harness will, and the task's hidden tests are run against it:
  reference/      must pass every test: run twice on the same server (leftover data must not
                  matter) and once in reverse order (no test may depend on another)
  reference_b/    optional second correct backend that makes other valid choices: must also pass
  mutants/*.py    deliberately broken copies of reference/app.py: each must FAIL at least one test
Results are printed and saved to benchmark/validation.json.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from runtime.tools import start_server, stop_server  # noqa: E402

BENCH = pathlib.Path(__file__).resolve().parent
WORK = BENCH.parent / "projects" / "_validate"


def hidden_tests(task, url, ops_file, order="normal"):
    env = {**os.environ, "BASE_URL": url, "OPS_FILE": str(ops_file), "BENCH_ORDER": order}
    r = subprocess.run([sys.executable, "-m", "pytest", str(BENCH / task / "hidden_tests"), "-q", "-p", "no:cacheprovider"],
                       env=env, capture_output=True, text=True, timeout=300)
    passed = int(m[1]) if (m := re.search(r"(\d+) passed", r.stdout)) else 0
    failed = int(m[1]) if (m := re.search(r"(\d+) failed", r.stdout)) else 0
    errors = int(m[1]) if (m := re.search(r"(\d+) error", r.stdout)) else 0
    failing = re.findall(r"^FAILED \S+::(\S+)", r.stdout, re.M)
    return {"passed": passed, "failed": failed + errors, "failing": failing}


def serve(task, label, app_file, ops_file, orders):
    """Start one backend in the sandbox and run the hidden tests against it once per entry in orders."""
    root = WORK / task / label
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    shutil.copy(app_file, root / "app.py")
    started = start_server(root)
    if not started["ok"]:
        return {"label": label, "started": False, "error": started["output"][:300]}
    url = started["output"].split()[-1]
    try:
        runs = [hidden_tests(task, url, ops_file, order) for order in orders]
    finally:
        stop_server(root)
    return {"label": label, "started": True, "runs": runs}


def validate(task):
    t = BENCH / task
    jobs = [("reference", t / "reference" / "app.py", t / "reference" / "ops.json", ["normal", "normal", "reverse"])]
    if (t / "reference_b" / "app.py").exists():
        jobs.append(("reference_b", t / "reference_b" / "app.py", t / "reference_b" / "ops.json", ["normal"]))
    jobs += [(f"mutant:{m.stem}", m, t / "reference" / "ops.json", ["normal"]) for m in sorted((t / "mutants").glob("*.py"))]
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda j: serve(task, j[0].replace(":", "_"), j[1], j[2], j[3]), jobs))
    for r, j in zip(results, jobs):
        r["label"] = j[0]
    ref = results[0]
    total = ref["runs"][0]["passed"] + ref["runs"][0]["failed"] if ref["started"] else 0
    good = [r for r in results if not r["label"].startswith("mutant")]
    mutants = [r for r in results if r["label"].startswith("mutant")]
    clean = lambda r: r["started"] and all(run["failed"] == 0 and run["passed"] == total for run in r["runs"])
    killed = [m for m in mutants if not m["started"] or m["runs"][0]["failed"] > 0]
    survivors = [m["label"].split(":", 1)[1] for m in mutants if m not in killed]
    return {"task": task, "tests": total,
            "good_backends_pass": {r["label"]: clean(r) for r in good},
            "mutants": len(mutants), "killed": len(killed), "survivors": survivors,
            "ok": all(clean(r) for r in good) and not survivors and len(mutants) >= 3 and total >= 8,
            "detail": results}


def main():
    tasks = sys.argv[1:] or sorted(p.name for p in BENCH.iterdir() if (p / "hidden_tests").is_dir())
    out = [validate(t) for t in tasks]
    for v in out:
        good = ", ".join(f"{k} {'✅' if ok else '❌'}" for k, ok in v["good_backends_pass"].items())
        print(f"{'✅' if v['ok'] else '❌'} {v['task']}: {v['tests']} tests | {good} | mutants killed {v['killed']}/{v['mutants']}"
              + (f" | SURVIVED: {', '.join(v['survivors'])}" if v["survivors"] else ""))
        for r in v["detail"]:
            if not r["started"]:
                print(f"     {r['label']}: did not start: {r['error'][:120]!r}")
            elif not r["label"].startswith("mutant") and any(run["failed"] for run in r["runs"]):
                print(f"     {r['label']}: failing {[run['failing'] for run in r['runs']]}")
    results_file = BENCH / "validation.json"
    old = json.loads(results_file.read_text()) if results_file.exists() else {}
    old.update({v["task"]: {k: v[k] for k in ("tests", "good_backends_pass", "mutants", "killed", "survivors", "ok")} for v in out})
    results_file.write_text(json.dumps(old, indent=2) + "\n")
    sys.exit(0 if all(v["ok"] for v in out) else 1)


if __name__ == "__main__":
    main()

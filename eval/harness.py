"""The eval harness: score backends against benchmark tasks, in Bernard's Docker sandbox (decision 0030).

    uv run python -m eval.harness <task> <folder>         # folder holds app.py (and ops.json, the name map, if written)
    uv run python -m eval.harness all <folder>            # folder holds <task>/app.py for each task
    uv run python -m eval.harness all --references        # the correct backends: every one must score 100%
    options: --workers N (backends side by side, default 4) · --repeat N (score each N times) · --name RUN

A backend with no ops.json is mapped by Opus (decision 0032; needs LLM_API_KEY, about $0.02) and the map is saved next
to app.py, so it is paid for once. Results: eval/results/harness/<RUN>.json, one row per backend per repeat.
"""

import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from eval import bench

TESTS = json.loads((bench.ROOT / "benchmark/validation.json").read_text())


def cleanup():
    """Remove sandbox containers and networks left by a killed run (decision 0030). Returns how many."""
    check = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
    if check.returncode:  # Docker off or missing: say so and stop, instead of scoring every backend 0
        raise SystemExit(f"Docker is not reachable, so nothing can be scored:\n{check.stderr.strip()}")
    ids = lambda *cmd: subprocess.run(["docker", *cmd], capture_output=True, text=True).stdout.split()
    containers, networks = ids("ps", "-aq", "--filter", "name=^w2-"), ids("network", "ls", "-q", "--filter", "name=^w2-")
    if containers:
        subprocess.run(["docker", "rm", "-f", *containers], capture_output=True)
    if networks:
        subprocess.run(["docker", "network", "rm", *networks], capture_output=True)
    return len(containers), len(networks)


def jobs(task, folder, references):
    """(task, source name, backend folder) for every backend to score."""
    tasks = bench.task_names() if task == "all" else [task]
    if references:
        return [(t, r, bench.BENCH / t / r) for t in tasks for r in bench.load(t)["references"]]
    folder = bench.pathlib.Path(folder).resolve()
    return [(t, folder.name, folder / t if task == "all" else folder) for t in tasks]


def run_one(task, source, folder, label):
    start, total = time.time(), TESTS[task]["tests"]
    row = {"task": task, "backend": source, "folder": str(folder.relative_to(bench.ROOT)) if folder.is_relative_to(bench.ROOT) else str(folder),
           "passed": 0, "total": total, "started": False, "failing": [], "error": "", "map_cost_usd": 0.0}
    if not (folder / "app.py").exists():
        return {**row, "error": "no app.py", "seconds": 0.0}
    app = (folder / "app.py").read_text()
    try:
        ops = json.loads((folder / "ops.json").read_text()) if (folder / "ops.json").exists() else None
    except ValueError as e:
        return {**row, "error": f"ops.json is not valid JSON: {e}", "seconds": 0.0}
    if ops is None:
        ops, info = bench.map_ops("claude-opus-5-5", app, bench.load(task)["operations"])
        (folder / "ops.json").write_text(json.dumps(ops, indent=2) + "\n")
        row["map_cost_usd"] = info["cost_usd"]
    missing = sorted(json.loads(bench.load(task)["operations"]).keys() - ops.keys())
    got = bench.score(task, label, app, ops)
    if missing:  # an incomplete map fails tests the backend may pass: flag it, so it is not read as a bad build
        got["error"] = f"ops.json has no entry for: {', '.join(missing)}. " + got.get("error", "")
    return {**row, "started": got["started"], "passed": got["passed"], "failing": got.get("failing", []),
            "error": got.get("error", ""), "seconds": round(time.time() - start, 1)}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("task")
    a.add_argument("folder", nargs="?")
    a.add_argument("--references", action="store_true")
    a.add_argument("--workers", type=int, default=4)
    a.add_argument("--repeat", type=int, default=1)
    a.add_argument("--name", default=time.strftime("run_%Y%m%d_%H%M%S"))
    args = a.parse_args()
    if not args.references and not args.folder:
        a.error("give a backend folder, or --references")
    removed = cleanup()
    print(f"cleanup: removed {removed[0]} leftover containers, {removed[1]} networks")
    todo = [[(t, s, f, f"harness_{args.name}_{s}_{i}") for t, s, f in jobs(args.task, args.folder, args.references)]
            for i in range(args.repeat)]
    start = time.time()
    with ThreadPoolExecutor(args.workers) as ex:  # first repeat alone: it writes any missing map, so later repeats reuse it
        rows = list(ex.map(lambda j: run_one(*j), todo[0]))
        rows += list(ex.map(lambda j: run_one(*j), [j for rep in todo[1:] for j in rep]))
    for r in rows:
        print(f"{r['task']:24} {r['backend']:12} {r['passed']:>2}/{r['total']:<2} {r['seconds']:>5}s {r['error'][-80:]}".rstrip())
    passed, total = sum(r["passed"] for r in rows), sum(r["total"] for r in rows)
    print(f"{passed}/{total} tests = {100 * passed / total:.1f}% · {sum(r['passed'] == r['total'] for r in rows)}/{len(rows)} "
          f"backends fully pass · {time.time() - start:.0f} s · maps ${sum(r['map_cost_usd'] for r in rows):.3f}")
    out = bench.ROOT / "eval/results/harness" / f"{args.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"args": vars(args), "seconds": round(time.time() - start, 1), "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()

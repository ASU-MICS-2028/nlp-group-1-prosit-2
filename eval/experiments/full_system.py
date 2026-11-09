"""S5.2: the full system, per task, over its 3 complete builds of all 15 tasks: tests passed, keeps data, time and cost.
Free: reads saved files only. Writes eval/results/full_system.json.

    uv run python -m eval.experiments.full_system
"""

import json
import pathlib

R = pathlib.Path("eval/results")
RUNS = {"run 1 (Alice, old scoring rules)": R / "runs/s38_list_all", "run 2": R / "fresh1", "run 3": R / "fresh2"}
RESTART = {"run 2": "fresh1_restart", "run 3": "fresh2_restart"}  # run 1 was built before the restart check existed
TOTAL = {t: v["tests"] for t, v in json.loads(pathlib.Path("benchmark/validation.json").read_text()).items()}
KEYS = json.loads((R / "key_rules.json").read_text())["rows"]
read = lambda p: json.loads(p.read_text())
scores = {"run 1 (Alice, old scoring rules)": {r["task"]: r["passed"] for r in read(R / "harness/s38_list_all.json")["rows"]},
          "run 2": {r["task"]: r["after"] for r in KEYS if r["group"] == "fresh1"},
          "run 3": {r["task"]: r["after"] for r in KEYS if r["group"] == "fresh2"}}
keeps = {run: {r["task"]: r["keeps_data"] for r in read(R / f"harness/{name}.json")["rows"]} for run, name in RESTART.items()}

tasks = []
for task, total in sorted(TOTAL.items()):
    row = {"task": task, "tests": total, "runs": {}}
    for run, folder in RUNS.items():
        built, asked = read(folder / task / "run.json"), read(folder / task / "questions.json")
        row["runs"][run] = {"passed": scores[run][task], "keeps_data": keeps.get(run, {}).get(task), "build_seconds": built["seconds"],
                            "usd": round(built["cost_usd"] + asked["cost_usd"], 4)}
    tasks.append(row)

n, tests = len(RUNS), sum(TOTAL.values())
pick = lambda run, field: [t["runs"][run][field] for t in tasks]
per_run = {run: {"percent": round(100 * sum(pick(run, "passed")) / tests, 1), "tasks_all_passed": sum(t["runs"][run]["passed"] == t["tests"] for t in tasks),
                 "kept_data": sum(v is True for v in pick(run, "keeps_data")) if run in RESTART else None, "usd": round(sum(pick(run, "usd")), 2),
                 "average_build_seconds": round(sum(pick(run, "build_seconds")) / len(tasks), 1)} for run in RUNS}
out = {"how": "3 builds of each task (questions on, no plan, as decision 0041), each scored 3 times. keeps_data null: not checked for that run. "
              "Time is the build only; the questions step is not timed.", "per_run": per_run,
       "average_percent": round(sum(v["percent"] for v in per_run.values()) / n, 1), "tasks": tasks}
(R / "full_system.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(per_run, indent=1), out["average_percent"])
for t in tasks:
    print(f"{t['task']:24}", *(f"{v['passed']:>2}/{t['tests']:<2}" for v in t["runs"].values()), f"${sum(v['usd'] for v in t['runs'].values()) / n:.2f}",
          f"{sum(v['build_seconds'] for v in t['runs'].values()) / n:.0f}s")

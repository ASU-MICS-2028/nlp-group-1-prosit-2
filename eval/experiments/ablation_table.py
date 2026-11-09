"""S5.3 and S5.4 in one table: each setup built once on all 15 tasks, scored 3 times, same rules as the full system (S5.2).
Free: reads saved files only. Writes eval/results/ablations.json.

    uv run python -m eval.experiments.ablation_table
"""

import collections
import json
import pathlib
import re

R = pathlib.Path("eval/results")
read = lambda p: json.loads(p.read_text())
SETUPS = {"s53_plan": "Questions + plan (what real clients get)", "s53_noask": "No questions", "s53_nottest": "No self-testing step (prompt D)",
          "s53_search": "Questions + recipe search", "s53_split": "Planner, Builder, Tester split", "s54_sonnet": "Sonnet instead of Opus",
          "s54_haiku": "Haiku instead of Opus"}
TOTAL = {t: v["tests"] for t, v in read(pathlib.Path("benchmark/validation.json")).items()}
tests = sum(TOTAL.values())
full = read(R / "full_system.json")
HARD = "school_grades_gpa"  # all or nothing: a build that invents a required course code loses 10 of its 12 tests, about 5 points overall
base = [100 * (sum(t["runs"][run]["passed"] for t in full["tasks"] if t["task"] != HARD)) / (tests - TOTAL[HARD]) for run in full["per_run"]]
out = {"how": "One build of all 15 tasks per setup, each scored 3 times. A gap under 2 points is noise: identical runs of the full system differ by 1.6. School is shown both ways because one choice moves it by 10 tests.",
       "full system (3 runs)": {"percent": full["average_percent"], "percent_without_school": round(sum(base) / len(base), 1), "kept_data": "30 of 30", "usd": 1.91}, "setups": {}}
for name, label in SETUPS.items():
    rows = read(R / f"harness/{name}.json")["rows"]
    built = {p.parent.name: read(p) for p in (R / "ablations" / name).glob("*/run.json")}
    asked = sum(read(p)["cost_usd"] for p in (R / "ablations" / name).glob("*/questions.json"))
    logs = [(R / "ablations/logs" / f"{name}.log").read_text()]
    plans = sum(float(m) for m in re.findall(r"approved \$([0-9.]+)", logs[0]))
    per_task = collections.defaultdict(list)
    for r in rows:
        per_task[r["task"]].append(r["passed"])
    each = {t: round(sum(v) / len(v), 1) for t, v in sorted(per_task.items())}
    tool_calls = collections.Counter(c["tool"] if isinstance(c, dict) else c for b in built.values() for c in b["tool_calls"])
    out["setups"][name] = {"label": label, "percent": round(100 * sum(r["passed"] for r in rows) / (3 * tests), 1),
                           "percent_without_school": round(100 * sum(r["passed"] for r in rows if r["task"] != HARD) / (3 * (tests - TOTAL[HARD])), 1),
                           "tasks_all_passed": sum(v == TOTAL[t] for t, v in each.items()),
                           "kept_data": f"{sum(r.get('keeps_data') is True for r in rows) // 3} of {sum(r.get('keeps_data') is not None for r in rows) // 3} checked",
                           "build_usd": round(sum(b["cost_usd"] for b in built.values()), 2), "questions_and_plan_usd": round(asked + plans, 2),
                           "average_seconds": round(sum(b["seconds"] for b in built.values()) / len(built), 1), "builds": len(built),
                           "times_ran_its_own_tests": tool_calls.get("run_tests", 0), "repairs": sum(b["repairs"] for b in built.values()),
                           "stops": dict(collections.Counter(b["stop"] for b in built.values())), "per_task": each}
(R / "ablations.json").write_text(json.dumps(out, indent=1) + "\n")
print("full system (3 runs)", out["full system (3 runs)"])
for name, s in out["setups"].items():
    print(f"{s['label']:44} {s['percent']:>5}%  {s['percent_without_school']:>5}%  {s['tasks_all_passed']:>2}/15 all  keeps {s['kept_data']:15} ${s['build_usd'] + s['questions_and_plan_usd']:.2f}  {s['average_seconds']:>5}s  tests run {s['times_ran_its_own_tests']:>3}  repairs {s['repairs']}  {s['stops']}")

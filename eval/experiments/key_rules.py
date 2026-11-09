"""Does scoring cope with a backend that finds records by name or number? Keeps every saved map as it is and only asks Opus whether
to add a rule. Failing builds should gain; backends that work with ids must get no rule. About $1. Writes eval/results/key_rules.json.

    uv run --env-file .env --with anthropic python -m eval.experiments.key_rules
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from eval import bench
from eval.llm import SPENT

R = bench.ROOT / "eval/results"
jobs = []
for run in ("fresh1", "fresh2"):
    for task in bench.task_names():
        folder = R / run / task
        jobs.append((run, task, (folder / "app.py").read_text(), json.loads((folder / "ops.json").read_text())))
for r in json.loads((R / "baseline_v2.json").read_text()):
    folder = bench.WORK / r["task"] / f"baseline_{r['model']}_{r['variant'].replace('+', '_')}"
    if r["passed"] < r["total"] and r.get("ops") and (folder / "app.py").exists():
        jobs.append((f"one call, {r['model'][7:]}, {r['variant']}", r["task"], (folder / "app.py").read_text(), r["ops"]))
for task in bench.task_names():
    for ref in bench.load(task)["references"]:
        folder = bench.BENCH / task / ref
        jobs.append(("hand-written, must get no rule", task, (folder / "app.py").read_text(), json.loads((folder / "ops.json").read_text())))


if "--hand" in sys.argv:  # the hand-written backends again, and keep the other rows
    jobs = [j for j in jobs if j[0].startswith("hand")]


def one(numbered):
    number, (group, task, app, ops) = numbered
    label = f"keyrules_{number}"  # two backends of one task must not share a folder
    before = bench.score(task, label, app, ops)
    new, info = bench.add_key_rules("claude-opus-5-5", app, bench.load(task)["operations"], ops)
    row = {"group": group, "task": task, "total": before["passed"] + before["failed"], "before": before["passed"], "after": before["passed"], "rules": new != ops, "cost_usd": info["cost_usd"]}
    if new != ops:
        row["after"] = bench.score(task, label, app, new)["passed"]
        row["ops_with_rules"] = new
    return row


with ThreadPoolExecutor(4) as ex:
    rows = list(ex.map(one, enumerate(jobs)))
if "--hand" in sys.argv:
    rows += [r for r in json.loads((R / "key_rules.json").read_text())["rows"] if not r["group"].startswith("hand")]
summary = {g: {"builds": sum(r["group"] == g for r in rows), "before": sum(r["before"] for r in rows if r["group"] == g), "after": sum(r["after"] for r in rows if r["group"] == g),
               "total": sum(r["total"] for r in rows if r["group"] == g), "got_a_rule": sum(r["rules"] for r in rows if r["group"] == g), "fell": sum(r["after"] < r["before"] for r in rows if r["group"] == g)}
           for g in sorted({r["group"] for r in rows})}
(R / "key_rules.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
print(json.dumps(summary, indent=1))
for r in rows:
    if r["rules"]:
        print(r["group"][:24], r["task"], r["before"], "->", r["after"], "of", r["total"])
print(f"spent ${SPENT['usd']:.2f}")

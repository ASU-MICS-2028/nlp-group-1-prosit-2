"""Build backends from the command line.

    uv run --env-file .env --with anthropic python -m builder build church_signup [more tasks | all] [--prompt B] [--run NAME]

Reads ONLY benchmark/<task>/request.md (decision 0033) and builds in projects/<run>/<task>/, the layout the
harness scores: uv run --env-file .env --with anthropic python -m eval.harness all projects/<run> --repeat 3
Each build leaves run.json (the totals) and trace.jsonl (every step) next to app.py.
"""

import argparse
from pathlib import Path

from builder.agent import build
from eval import bench

p = argparse.ArgumentParser()
p.add_argument("command", choices=["build"])
p.add_argument("tasks", nargs="+")
p.add_argument("--model", default="claude-opus-5-5")
p.add_argument("--effort", default="medium")
p.add_argument("--prompt", default="B", choices=["A", "B", "C", "D"])
p.add_argument("--repairs", type=int, default=0, help="most repair rounds after the independent check")
p.add_argument("--run", default="agent_v1")
a = p.parse_args()

for task in bench.task_names() if a.tasks == ["all"] else a.tasks:
    request = (bench.BENCH / task / "request.md").read_text().strip()
    r = build(request, Path("projects") / a.run / task, a.model, a.effort, a.prompt, max_repairs=a.repairs)
    tests = f"own tests {r['tests']['passed']} passed {r['tests']['failed']} failed" if r["tests"] else "own tests not run"
    print(f"{task:24} {r['stop']:9} {r['turns']:>2} turns {len(r['tool_calls']):>2} tools ${r['cost_usd']} "
          f"{r['seconds']}s  {tests}  repairs {r['repairs']}", flush=True)

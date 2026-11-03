"""Plan and build backends from the command line.

    uv run --env-file .env --with anthropic python -m builder plan church_signup [more tasks | all] [--yes] [--run NAME]
    uv run --env-file .env --with anthropic python -m builder build church_signup [more tasks | all] [--plan] [--run NAME]

plan (S3.5) shows the plan and asks: y approves it (saved as plan.json), n stops, any other text is a change to make.
--yes approves without asking (for experiments). build --plan follows plan.json and refuses to build without one.

Reads ONLY benchmark/<task>/request.md (decision 0033) and builds in projects/<run>/<task>/, the layout the
harness scores: uv run --env-file .env --with anthropic python -m eval.harness all projects/<run> --repeat 3
Each build leaves run.json (the totals) and trace.jsonl (every step) next to app.py.
"""

import argparse
import json
from pathlib import Path

import anthropic

from builder.agent import build, load_plan, make_plan, plan_text
from eval import bench

p = argparse.ArgumentParser()
p.add_argument("command", choices=["plan", "build"])
p.add_argument("tasks", nargs="+")
p.add_argument("--model", default="claude-opus-5-5")
p.add_argument("--effort", default="medium")
p.add_argument("--prompt", default="B", choices=["A", "B", "C", "D"])
p.add_argument("--repairs", type=int, default=0, help="most repair rounds after the independent check")
p.add_argument("--yes", action="store_true", help="plan: approve without asking")
p.add_argument("--planner", default="1", choices=["1", "2"], help="plan: v1, or v2 that may not add unasked features")
p.add_argument("--plan", action="store_true", help="build: follow the approved plan.json")
p.add_argument("--run", default="agent_v1")
a = p.parse_args()

for task in bench.task_names() if a.tasks == ["all"] else a.tasks:
    request = (bench.BENCH / task / "request.md").read_text().strip()
    root = Path("projects") / a.run / task
    if a.command == "plan":
        try:
            plan, usd = make_plan(request, a.model, planner=a.planner)
            while not a.yes:
                print(f"\n{task}\n\n{plan_text(plan)}\n")
                answer = input("Approve? y = yes, n = stop, or type the changes you want: ").strip()
                if answer.lower() in ("y", "n", ""):
                    plan = plan if answer.lower() == "y" else None
                    break
                plan, more = make_plan(request, a.model, plan, answer, a.planner)
                usd += more
        except (ValueError, RuntimeError, anthropic.AnthropicError) as e:  # empty request, budget, network, key
            print(f"{task:24} error: {type(e).__name__}: {e}"[:300])
            continue
        if plan:
            root.mkdir(parents=True, exist_ok=True)
            (root / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        else:
            (root / "plan.json").unlink(missing_ok=True)  # an older approval must not be built by mistake
        print(f"{task:24} {'approved' if plan else 'not approved'} ${round(usd, 4)}", flush=True)
        continue
    try:
        plan = load_plan(root) if a.plan else None
    except ValueError as e:
        print(f"{task:24} not built: {e}")
        continue
    r = build(request, root, a.model, a.effort, a.prompt, max_repairs=a.repairs, plan=plan)
    tests = f"own tests {r['tests']['passed']} passed {r['tests']['failed']} failed" if r["tests"] else "own tests not run"
    print(f"{task:24} {r['stop']:9} {r['turns']:>2} turns {len(r['tool_calls']):>2} tools ${r['cost_usd']} "
          f"{r['seconds']}s  {tests}  repairs {r['repairs']}  follows plan {r['follows_plan']}", flush=True)

"""Build backends from the command line.

    uv run --env-file .env --with anthropic python -m builder build church_signup [more tasks | all] [--model M] [--run NAME]

Reads ONLY benchmark/<task>/request.md (decision 0033) and builds in projects/<run>/<task>/, the layout the
harness scores: uv run --env-file .env --with anthropic python -m eval.harness all projects/<run> --repeat 3
"""

import argparse
import json
from pathlib import Path

from builder.agent import build
from eval import bench

p = argparse.ArgumentParser()
p.add_argument("command", choices=["build"])
p.add_argument("tasks", nargs="+")
p.add_argument("--model", default="claude-opus-5-5")
p.add_argument("--effort", default="medium")
p.add_argument("--run", default="agent_v1")
a = p.parse_args()

for task in bench.task_names() if a.tasks == ["all"] else a.tasks:
    request = (bench.BENCH / task / "request.md").read_text().strip()
    root = Path("projects") / a.run / task
    result = build(request, root, a.model, a.effort)
    (root / "build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{task:24} {result['stop']:9} {result['turns']:>2} turns {len(result['tool_calls']):>2} tools "
          f"${result['cost_usd']} {result['seconds']}s", flush=True)

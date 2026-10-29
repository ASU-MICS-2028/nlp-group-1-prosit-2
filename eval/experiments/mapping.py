"""How often does an LLM write a correct ops.json? Scored on every reference backend, where the true ops.json is known.

    uv run --env-file .env --with anthropic python -m eval.experiments.mapping [task ...]

For each reference: ask each model to map the operations to the app's endpoints, then run the hidden tests with
(a) the true ops.json and (b) the model's. Mapping is right when (b) passes as many tests as (a).
"""

import json
import sys

from eval import bench
from eval.llm import SPENT

MODELS = ["claude-opus-5-5", "claude-haiku-5-5"]
rows = []
for name in sys.argv[1:] or bench.task_names():
    t = bench.load(name)
    for ref in t["references"]:
        app = (bench.BENCH / name / ref / "app.py").read_text()
        true_ops = json.loads((bench.BENCH / name / ref / "ops.json").read_text())
        truth = bench.score(name, f"{ref}_true", app, true_ops)
        for model in MODELS:
            ops, info = bench.map_ops(model, app, t["operations"])
            got = bench.score(name, f"{ref}_{model}", app, ops)
            exact = sum(ops.get(op) == spec for op, spec in true_ops.items())  # rarely equal: true maps use "fields"
            row = {"task": name, "backend": ref, "model": model, "tests": truth["passed"] + truth["failed"],
                   "passed_true_map": truth["passed"], "passed_model_map": got["passed"],
                   "right": got["passed"] == truth["passed"], "ops_exactly_equal": f"{exact}/{len(true_ops)}",
                   "cost_usd": info["cost_usd"], "stop_reason": info["stop_reason"]}
            rows.append(row)
            print(f"{'✅' if row['right'] else '❌'} {name}/{ref} {model}: {got['passed']}/{row['tests']} "
                  f"(true map {truth['passed']}), ops exactly equal {row['ops_exactly_equal']}, ${info['cost_usd']}", flush=True)
for m in MODELS:
    mine = [r for r in rows if r["model"] == m]
    print(f"{m}: {sum(r['right'] for r in mine)}/{len(mine)} mappings fully right, ${sum(r['cost_usd'] for r in mine):.3f}")
print(f"total spent ${SPENT['usd']:.3f} in {SPENT['calls']} calls")
(bench.ROOT / "eval/results/mapping.json").write_text(json.dumps(rows, indent=2) + "\n")

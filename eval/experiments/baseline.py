"""The no-agent baseline: one LLM call writes the whole backend, Opus maps it (21/21 right in mapping.json), hidden tests score it.

    uv run --env-file .env --with anthropic python -m eval.experiments.baseline [task ...]

Variants (each task x each model):
  request          the client's request only
  request+ops      the request plus the list of operations the tests use
  request+ops+brief  (vague tasks only) the above plus the client's answers and brief: how much does vagueness cost?
Alice's agent (Stage 3) must beat these numbers.
"""

import json
import sys
import time

from eval import bench
from eval.llm import ask, SPENT

MODELS = ["claude-opus-5-5", "claude-haiku-5-5"]
BUILD_SYSTEM = """You build backends for people who do not code. Write ONE complete file, app.py, containing a FastAPI
application in a variable named app. Use only fastapi, pydantic, sqlmodel and the Python standard library. Keep data in
memory (or in a SQLite file in the current folder). Do everything the client asks, refuse what the client says must be
refused with a 4xx status, and return JSON. Reply with the code only, in the field app_py."""
SCHEMA = {"type": "object", "properties": {"app_py": {"type": "string"}}, "required": ["app_py"], "additionalProperties": False}

rows = []
for name in sys.argv[1:] or bench.task_names():
    t = bench.load(name)
    variants = {"request": t["request"], "request+ops": f"{t['request']}\n\nThe operations this backend must support:\n{t['operations']}"}
    if t.get("vague"):
        variants["request+ops+brief"] = variants["request+ops"] + f"\n\nThe client's answers to questions:\n{t['answers']}\n\nMore details from the client:\n{t['brief']}"
    for model in MODELS:
        for variant, user in variants.items():
            start = time.time()
            text, build = ask(model, BUILD_SYSTEM, user, schema=SCHEMA)
            app = json.loads(text)["app_py"] if build["stop_reason"] == "end_turn" else ""
            ops, mapped = bench.map_ops("claude-opus-5-5", app, t["operations"]) if app else ({}, {"cost_usd": 0})  # always Opus: 21/21 right (mapping.json), so the score measures the build only
            got = bench.score(name, f"baseline_{model}_{variant.replace('+', '_')}", app, ops)
            total = got["passed"] + got["failed"]
            row = {"task": name, "tier": t.get("tier"), "vague": t.get("vague"), "model": model, "variant": variant,
                   "started": got["started"], "passed": got["passed"], "total": total,
                   "seconds": round(time.time() - start, 1), "cost_usd": round(build["cost_usd"] + mapped["cost_usd"], 4),
                   "lines": app.count("\n"), "stop_reason": build["stop_reason"], "error": got.get("error", "")[:200]}
            rows.append(row)
            print(f"{name:24} {model:17} {variant:18} {got['passed']:>2}/{total:<2} "
                  f"{'' if got['started'] else 'DID NOT START '}${row['cost_usd']} {row['seconds']}s", flush=True)
            (bench.ROOT / "eval/results/baseline.json").write_text(json.dumps(rows, indent=2) + "\n")
print(f"total spent ${SPENT['usd']:.3f} in {SPENT['calls']} calls")

"""The no-agent baseline: one LLM call writes the whole backend, Opus maps it (21/21 right in mapping.json), hidden tests score it.

    uv run --env-file .env --with anthropic python -m eval.experiments.baseline [task ...]
    MODELS=qwen3.5-9b-local VARIANTS=request OUT=baseline_local.json ...   (other models, variants, output file)

Variants (each task x each model):
  request          the client's request only
  request+ops      the request plus the list of operations the tests use
  request+ops+brief  (vague tasks only) the above plus the client's answers and brief: how much does vagueness cost?
Alice's agent (Stage 3) must beat these numbers.
"""

import json
import os
import sys
import time

from eval import bench
from eval.llm import ask, SPENT

MODELS = os.environ.get("MODELS", "claude-opus-5-5,claude-haiku-5-5").split(",")
VARIANTS = os.environ.get("VARIANTS", "request,request+ops,request+ops+brief").split(",")
RECIPES = os.environ.get("RECIPES", "")  # "" none · "fixed" the same 3 setup recipes · "search" found by kb.search_docs
FIXED = ["01", "02", "18"]  # table with an id, engine setup, one-file app checklist


def recipes_for(name):
    """The recipes added to the prompt (S2.4, step 5): none, a fixed set, or the best match for each planning question."""
    if not RECIPES:
        return ""
    from kb.search import recipes, search_docs

    if RECIPES == "fixed":
        found = [r for r in recipes() if r["id"] in FIXED]
    else:
        questions = [q["question"] for q in json.loads((bench.ROOT / "kb/agent_questions.json").read_text()) if q["task"] == name]
        found = list({r["id"]: r for q in questions for r in search_docs(q, k=1)}.values())
    return "\n\nWorking examples for this exact stack (use what helps):\n\n" + "\n\n".join(r["text"] for r in found)


TESTS = json.loads((bench.ROOT / "benchmark/validation.json").read_text())
OUT = bench.ROOT / "eval/results" / os.environ.get("OUT", "baseline.json")
BUILD_SYSTEM = """You build backends for people who do not code. Write ONE complete file, app.py, containing a FastAPI
application in a variable named app. Use only fastapi, pydantic, sqlmodel and the Python standard library. Keep data in
memory (or in a SQLite file in the current folder). Do everything the client asks, refuse what the client says must be
refused with a 4xx status, and return JSON. Reply with the code only, in the field app_py."""
SCHEMA = {"type": "object", "properties": {"app_py": {"type": "string"}}, "required": ["app_py"], "additionalProperties": False}

rows = []
for name in sys.argv[1:] or bench.task_names():
    t = bench.load(name)
    variants = {"request": t["request"] + recipes_for(name), "request+ops": f"{t['request']}\n\nThe operations this backend must support:\n{t['operations']}"}
    if t.get("vague"):
        variants["request+ops+brief"] = variants["request+ops"] + f"\n\nThe client's answers to questions:\n{t['answers']}\n\nMore details from the client:\n{t['brief']}"
    for model in MODELS:
        for variant, user in ((v, u) for v, u in variants.items() if v in VARIANTS):
            start = time.time()
            text, build = ask(model, BUILD_SYSTEM, user, schema=SCHEMA)
            app = json.loads(text)["app_py"] if build["stop_reason"] == "end_turn" else ""
            label = f"baseline_{model}_{variant.replace('+', '_')}" + os.environ.get("LOCAL_THINKING", "") + RECIPES  # kept apart
            got = bench.score(name, label, app, {})  # does it even start? Mapping a build that crashes wastes an Opus call
            ops, mapped = {}, {"cost_usd": 0}
            if got["started"]:
                ops, mapped = bench.map_ops("claude-opus-5-5", app, t["operations"])  # always Opus: 21/21 right (mapping.json), so the score measures the build only
                got = bench.score(name, label, app, ops)
            total = TESTS[name]["tests"]
            row = {"task": name, "tier": t.get("tier"), "vague": t.get("vague"), "model": model, "variant": variant,
                   "started": got["started"], "passed": got["passed"], "total": total,
                   "seconds": round(time.time() - start, 1), "cost_usd": round(build["cost_usd"] + mapped["cost_usd"], 4),
                   "lines": app.count("\n"), "stop_reason": build["stop_reason"], "error": got.get("error", "")[-200:], "ops": ops}
            rows.append(row)
            print(f"{name:24} {model:17} {variant:18} {got['passed']:>2}/{total:<2} "
                  f"{'' if got['started'] else 'DID NOT START '}${row['cost_usd']} {row['seconds']}s", flush=True)
            OUT.write_text(json.dumps(rows, indent=2) + "\n")
print(f"total spent ${SPENT['usd']:.3f} in {SPENT['calls']} calls")

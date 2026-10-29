"""Does any hidden test expect something the client never said? (LLM-as-judge, then reviewed by hand.)

    uv run --env-file .env --with anthropic python -m eval.experiments.fairness [task ...]
"""

import json
import sys

from eval import bench
from eval.llm import ask, SPENT

SYSTEM = """You review hidden tests for a benchmark. A coding agent will build a backend from a client's request and
will never see these tests. A test is FAIR only if a careful developer could make it pass by doing what the client
said, without guessing. What the client said = the request, plus (only for vague tasks) the client's answers and brief.
Field names, URLs and status-code numbers do not matter (they are translated, and any 2xx / 4xx is accepted where the
request does not specify). Judge behaviour and rules only. Be strict: flag a test if it needs a rule, format, limit,
ordering or calculation the client never stated. Return one verdict per test function."""

SCHEMA = {"type": "object", "properties": {"tests": {"type": "array", "items": {"type": "object", "properties": {
    "test": {"type": "string"}, "fair": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["test", "fair", "reason"], "additionalProperties": False}}}, "required": ["tests"], "additionalProperties": False}

rows = []
for name in sys.argv[1:] or bench.task_names():
    t = bench.load(name)
    said = f"REQUEST:\n{t['request']}"
    if t.get("vague"):
        said += f"\n\nCLIENT'S ANSWERS:\n{t['answers']}\n\nCLIENT'S BRIEF:\n{t['brief']}"
    user = f"{said}\n\nOPERATIONS (how the tests call the backend):\n{t['operations']}\n\nHIDDEN TESTS:\n```python\n{t['tests']}\n```"
    text, info = ask("claude-opus-5-5", SYSTEM, user, effort="high", schema=SCHEMA)
    verdicts = json.loads(text)["tests"]
    flagged = [v for v in verdicts if not v["fair"]]
    rows.append({"task": name, "tier": t.get("tier"), "vague": t.get("vague"), "tests": len(verdicts),
                 "flagged": flagged, "cost_usd": info["cost_usd"]})
    print(f"{name}: {len(flagged)}/{len(verdicts)} flagged (${info['cost_usd']})", flush=True)
    for v in flagged:
        print(f"   - {v['test']}: {v['reason']}")
print(f"total flagged {sum(len(r['flagged']) for r in rows)} of {sum(r['tests'] for r in rows)} tests; spent ${SPENT['usd']:.3f}")
(bench.ROOT / "eval/results/fairness.json").write_text(json.dumps(rows, indent=2) + "\n")

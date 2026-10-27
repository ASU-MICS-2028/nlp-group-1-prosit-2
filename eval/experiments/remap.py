"""Re-map saved baseline builds with the current mapper (separate sent / returned names) and re-score them.

    uv run --env-file .env --with anthropic python -m eval.experiments.remap [task ...]
No new builds: only the map is redone. Writes eval/results/baseline_v2.json (all builds, remapped ones replaced).
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from eval import bench
from eval.llm import SPENT

v2_file = bench.ROOT / "eval/results/baseline_v2.json"
rows = json.loads((v2_file if v2_file.exists() else bench.ROOT / "eval/results/baseline.json").read_text())
wanted = set(sys.argv[1:]) or {r["task"] for r in rows}


def redo(r):
    if r["task"] not in wanted or r["variant"] == "request+ops":  # request+ops already scored ~100%
        return r
    label = f"baseline_{r['model']}_{r['variant'].replace('+', '_')}"
    app = (bench.WORK / r["task"] / label / "app.py").read_text()
    ops, info = bench.map_ops("claude-opus-5-5", app, bench.load(r["task"])["operations"])
    got = bench.score(r["task"], label + "_v2", app, ops)
    print(f"{r['task']:24} {r['model']:17} {r['variant']:18} before {r['passed']:>2}/{r['total']:<2} after {got['passed']:>2}/{r['total']}", flush=True)
    return {**r, "passed_v1": r.get("passed_v1", r["passed"]), "passed": got["passed"], "failing": got.get("failing", []),
            "cost_usd": round(r["cost_usd"] + info["cost_usd"], 4), "ops": ops}


with ThreadPoolExecutor(4) as ex:
    out = list(ex.map(redo, rows))
v2_file.write_text(json.dumps(out, indent=2) + "\n")
print(f"spent ${SPENT['usd']:.3f} in {SPENT['calls']} calls")

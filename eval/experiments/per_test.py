"""Which hidden tests do the baseline builds fail? Re-scores the saved builds (no LLM calls).

    uv run python -m eval.experiments.per_test
Writes eval/results/per_test.json: for every test, how many request-only builds passed it.
"""

import json
from concurrent.futures import ThreadPoolExecutor

from eval import bench

rows = json.loads((bench.ROOT / "eval/results/baseline.json").read_text())


def rescore(r):
    label = f"baseline_{r['model']}_{r['variant'].replace('+', '_')}"
    root = bench.WORK / r["task"] / label
    got = bench.score(r["task"], label + "_rescore", (root / "app.py").read_text(), json.loads((root / "ops.json").read_text()))
    return {**r, "failing": got.get("failing", []), "rescored_passed": got["passed"]}


with ThreadPoolExecutor(4) as ex:
    out = list(ex.map(rescore, rows))
(bench.ROOT / "eval/results/baseline_failing.json").write_text(json.dumps(out, indent=2) + "\n")
same = sum(o["rescored_passed"] == o["passed"] for o in out)
print(f"re-scored {len(out)} builds; same score as the first time: {same}/{len(out)}")

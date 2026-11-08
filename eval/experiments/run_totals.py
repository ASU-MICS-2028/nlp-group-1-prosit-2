"""Time and cost of every saved agent build, added up per run. Free, reads files only. Writes eval/results/run_totals.json.

    uv run python -m eval.experiments.run_totals
"""

import json
import pathlib

R = pathlib.Path("eval/results")
out = {}
for folder in sorted(p for base in (R / "runs", R) for p in base.iterdir() if p.is_dir() and list(p.glob("*/run.json"))):
    runs = [json.loads(f.read_text()) for f in folder.glob("*/run.json")]
    out[folder.name] = {"builds": len(runs), "build_usd": round(sum(r["cost_usd"] for r in runs), 2),
                        "question_usd": round(sum(json.loads(f.read_text()).get("cost_usd", 0) for f in folder.glob("*/questions.json")), 2),
                        "avg_seconds": round(sum(r["seconds"] for r in runs) / len(runs), 1)}
(R / "run_totals.json").write_text(json.dumps(out, indent=2) + "\n")
for name, row in out.items():
    print(f"{name:18} {row}")

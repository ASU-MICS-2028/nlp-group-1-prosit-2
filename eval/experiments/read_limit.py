"""Does cutting a big file in the middle hurt the agent when it changes an app? (W4 row 36)

    uv run --env-file .env --with anthropic python -m eval.experiments.read_limit cut    # read_file as it is today
    uv run --env-file .env --with anthropic python -m eval.experiments.read_limit full   # read_file with no cut
About $0.50 per arm. The 3 biggest apps Opus built in one call; each change touches code in the part that gets cut.
Writes eval/results/read_limit/<arm>.json, plus each build's trace and final app.py.
"""

import json
import shutil
import sys
from pathlib import Path

from builder.agent import build
from eval import bench
from runtime import tools

ARM = sys.argv[1]
CHANGES = {
    "momo_wallet": ("When depositing or sending money, the person can add an optional short note. The note must show in the wallet's history.", "note"),
    "susu_ledger": ("Each member also has a phone number, which must be given when they join and shows when you look at a member.", "phone"),
    "shared_expenses": ("Each expense can have an optional category such as food or transport, which shows when you look at an expense.", "category"),
}
SAVED = {x["task"]: x for x in json.loads((bench.ROOT / "eval/results/baseline_v2.json").read_text())
         if x["model"] == "claude-opus-5-5" and x["variant"] == "request"}
OUT = bench.ROOT / "eval/results/read_limit"
OUT.mkdir(exist_ok=True)

if ARM == "full":
    tools.read_file = lambda root, path: {"ok": True, "output": (Path(root) / path).read_text()} if (Path(root) / path).is_file() else {"ok": False, "output": f"No such file: {path}"}

rows = []
for task, (change, word) in CHANGES.items():
    app = (bench.WORK / task / "baseline_claude-opus-5-5_request/app.py").read_text()
    root = bench.ROOT / "projects/read_limit" / ARM / task
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    (root / "app.py").write_text(app)
    ops = SAVED[task]["ops"]
    before = bench.score(task, f"read_limit_{ARM}_before", app, ops)["passed"]
    seen = []
    result = build(bench.load(task)["request"], root, change=change, max_usd=1.5, on_event=lambda e: seen.append(e) if e["event"] == "tool" else None)
    after = bench.score(task, f"read_limit_{ARM}_after", (root / "app.py").read_text(), ops)
    reads = [e for e in seen if e["tool"] == "read_file" and e["input"].get("path") == "app.py"]
    edits = [e for e in seen if e["tool"] == "edit_file"]
    row = {"task": task, "arm": ARM, "change": change, "app_chars_before": len(app), "app_chars_after": len((root / "app.py").read_text()),
           "stop": result["stop"], "turns": result["turns"], "cost_usd": result["cost_usd"], "seconds": result["seconds"], "tests": result["tests"],
           "app_reads": len(reads), "reads_that_were_cut": sum("characters cut]" in e["output"] for e in reads),
           "edits": len(edits), "edits_failed": sum(not e["ok"] for e in edits),
           "whole_file_writes": sum(e["tool"] == "write_file" and e["input"].get("path") == "app.py" for e in seen),
           "printed_the_file_through_a_failing_test": sum(e["tool"] == "run_tests" and not e["ok"] and "test_" in str(e["input"].get("path")) for e in seen),
           "other_tools": sorted({e["tool"] for e in seen} - {"read_file", "edit_file", "write_file"}),
           "word_in_app": word in (root / "app.py").read_text(), "hidden_before": before, "hidden_after": after["passed"], "hidden_total": SAVED[task]["total"],
           "summary": result["summary"]}
    rows.append(row)
    shutil.copy(root / "trace.jsonl", OUT / f"{ARM}_{task}_trace.jsonl")
    shutil.copy(root / "app.py", OUT / f"{ARM}_{task}_app.py")
    print({k: v for k, v in row.items() if k not in ("summary", "change")}, flush=True)
    (OUT / f"{ARM}.json").write_text(json.dumps(rows, indent=2) + "\n")
print("spent", round(sum(r["cost_usd"] for r in rows), 3))

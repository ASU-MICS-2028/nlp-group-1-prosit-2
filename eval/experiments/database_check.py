"""Does the check before publishing (keeps_database) agree with the real restart check (bench.keeps_data)? Free, no Claude.
Writes eval/results/database_check.json.

    uv run python -m eval.experiments.database_check
"""

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eval import bench
from runtime.deploy import keeps_database

ROOT = bench.ROOT / "eval/results"
jobs = [(r, bench.WORK / r["task"] / f"baseline_{r['model']}_{r['variant'].replace('+', '_')}" / "app.py")
        for r in json.loads((ROOT / "restart_check.json").read_text())["builds"]]
for r in json.loads((ROOT / "harness/restart_references.json").read_text())["rows"]:
    jobs.append(({**r, "model": "hand-written", "variant": r["backend"]}, bench.ROOT / r["folder"] / "app.py"))
for r in json.loads((ROOT / "harness/restart_church_agent_build.json").read_text())["rows"]:
    jobs.append(({**r, "model": "agent", "variant": "request+questions"}, bench.ROOT / r["folder"] / "app.py"))
for run in ("fresh1", "fresh2"):  # the fresh agent runs, first repeat
    for r in json.loads((ROOT / f"harness/{run}_restart.json").read_text())["rows"][:15]:
        jobs.append(({**r, "model": "agent", "variant": run}, bench.ROOT / r["folder"] / "app.py"))


def one(job):
    row, app = job
    base = {"task": row["task"], "model": row["model"], "variant": row["variant"], "restart": row.get("keeps_data")}
    if not app.exists():
        return {**base, "check": None, "why": "no saved app"}
    with tempfile.TemporaryDirectory(dir=bench.WORK) as folder:
        (Path(folder) / "app.py").write_text(app.read_text())
        got = keeps_database(folder)
    return {**base, "check": got["ok"], "why": got["output"][:300]}


with ThreadPoolExecutor(4) as ex:
    rows = list(ex.map(one, jobs))
table = {f"restart {a} / check {b}": sum(r["restart"] is a and r["check"] is b for r in rows) for a in (True, False, None) for b in (True, False, None)}
differ = [r for r in rows if r["restart"] is not None and r["check"] is not None and r["restart"] != r["check"]]
out = {"builds": len(rows), "table": table, "differ": differ, "rows": rows}
(ROOT / "database_check.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: out[k] for k in ("builds", "table", "differ")}, indent=1))

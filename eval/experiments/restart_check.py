"""Does a backend's data survive a restart? Free (saved builds, saved maps). The hidden tests never restart a backend, so a
score says nothing about this. Writes eval/results/restart_check.json.

    uv run python -m eval.experiments.restart_check
First proves the check itself on backends whose answer is known, then runs every saved baseline build.
"""

import json
from concurrent.futures import ThreadPoolExecutor

from eval import bench

CHURCH = bench.ROOT / "projects/host1/church_signup"
REFERENCE = bench.BENCH / "church_signup/reference"
GOOD, OPS = (CHURCH / "app.py").read_text(), json.loads((CHURCH / "ops.json").read_text())
controls = {
    "database file, must keep": (GOOD, OPS, True),
    "memory only, must lose": ((REFERENCE / "app.py").read_text(), json.loads((REFERENCE / "ops.json").read_text()), False),
    "database wiped at every start, must lose": (GOOD.replace("SQLModel.metadata.create_all(engine)", "SQLModel.metadata.drop_all(engine); SQLModel.metadata.create_all(engine)"), OPS, False),
}
out = {"controls": {}}
for name, (app, ops, want) in controls.items():
    assert "drop_all" in app or "wiped" not in name
    got = bench.keeps_data("church_signup", "control_" + name.split(",")[0].replace(" ", "_"), app, ops)
    out["controls"][name] = {**got, "right": got["keeps_data"] is want}
    print(name, out["controls"][name], flush=True)

saved = json.loads((bench.ROOT / "eval/results/baseline_v2.json").read_text())


def one(r):
    label = f"baseline_{r['model']}_{r['variant'].replace('+', '_')}"
    folder = bench.WORK / r["task"] / label
    if not (folder / "app.py").exists() or not r.get("ops"):
        return {"task": r["task"], "model": r["model"], "variant": r["variant"], "keeps_data": None, "checked": 0, "kept": 0, "error": "no saved map: it did not start"}
    return {"task": r["task"], "model": r["model"], "variant": r["variant"], **bench.keeps_data(r["task"], "restart_" + label, (folder / "app.py").read_text(), r["ops"])}


with ThreadPoolExecutor(4) as ex:
    out["builds"] = list(ex.map(one, saved))
for model in sorted({r["model"] for r in saved}):
    for variant in sorted({r["variant"] for r in saved}):
        rows = [r for r in out["builds"] if r["model"] == model and r["variant"] == variant]
        out.setdefault("summary", []).append({"model": model, "variant": variant, "builds": len(rows), "keeps": sum(r["keeps_data"] is True for r in rows),
                                              "loses": sum(r["keeps_data"] is False for r in rows), "cannot_tell": sum(r["keeps_data"] is None for r in rows)})
        print(out["summary"][-1], flush=True)
(bench.ROOT / "eval/results/restart_check.json").write_text(json.dumps(out, indent=2) + "\n")

"""The agent against one Claude call, over repeated builds and scored by the same rules. Free, reads saved files.
Writes eval/results/agent_vs_baseline.json.

    uv run python -m eval.experiments.agent_vs_baseline
"""

import json
import pathlib

R = pathlib.Path("eval/results")
HARD = "shared_expenses"  # in 3 of the 4 baseline rounds, a member has no id at all, so the tests cannot run
keys = [r for r in json.loads((R / "key_rules.json").read_text())["rows"]]
TOTAL = {t: v["tests"] for t, v in json.loads(pathlib.Path("benchmark/validation.json").read_text()).items()}


def from_rules(run):
    return {r["task"]: r["after"] for r in keys if r["group"] == run}


first = {r["task"]: r["passed"] for r in json.loads((R / "harness/s38_list_all.json").read_text())["rows"]}
agent = {"Alice's run (old rules: can only rise)": first, "fresh run 1": from_rules("fresh1"), "fresh run 2": from_rules("fresh2")}
one = {"round 1": {r["task"]: r["passed"] for r in json.loads((R / "baseline_v2.json").read_text()) if r["model"] == "claude-opus-5-5" and r["variant"] == "request"}}
for n in (2, 3, 4):
    one[f"round {n}"] = {r["task"]: r["passed"] for r in json.loads((R / f"baseline_r{n}.json").read_text())}


def pct(run, leave_out=None, full_marks=None):
    p = sum(TOTAL[t] if t == full_marks else v for t, v in run.items() if t != leave_out)
    return round(100 * p / sum(n for t, n in TOTAL.items() if t != leave_out), 1)


def side(runs, **how):
    each = {k: pct(v, **how) for k, v in runs.items()}
    return {"runs": each, "average": round(sum(each.values()) / len(each), 1), "lowest": min(each.values()), "highest": max(each.values())}


out = {"every test": {"agent": side(agent), "one call": side(one)},
       "leaving shared expenses out for both": {"agent": side(agent, leave_out=HARD), "one call": side(one, leave_out=HARD)},
       "one call given full marks on shared expenses": {"agent": side(agent), "one call": side(one, full_marks=HARD)}}
(R / "agent_vs_baseline.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=1))

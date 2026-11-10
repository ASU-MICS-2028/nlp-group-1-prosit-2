"""S6.1 Part 7: recompute the report's headline numbers straight from the per-test files, without Joseph's scripts. Free.
    uv run python eval/results/walkthrough/part7/recompute.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

R = Path("eval/results")
TOTAL = {t: v["tests"] for t, v in json.loads(Path("benchmark/validation.json").read_text()).items()}
print("hidden tests in all:", sum(TOTAL.values()), "over", len(TOTAL), "tasks")


def score(rows, label):
    by_task = defaultdict(list)
    for task, passed in rows:
        by_task[task].append(passed)
    repeats = Counter(len(v) for v in by_task.values())
    last = 100 * sum(v[-1] for v in by_task.values()) / sum(TOTAL.values())
    mean = 100 * sum(sum(v) / len(v) for v in by_task.values()) / sum(TOTAL.values())
    print(f"{label:34} tasks {len(by_task):2}  rows per task {dict(repeats)}  last row {last:5.1f}%  mean of rows {mean:5.1f}%")
    return round(mean, 1)


agent = [score([(r["task"], r["passed"]) for r in json.loads((R / "harness/s38_list_all.json").read_text())["rows"]], "agent: Alice's run (s38_list_all)")]
keys = json.loads((R / "key_rules.json").read_text())["rows"]
for g in ("fresh1", "fresh2"):
    agent.append(score([(r["task"], r["after"]) for r in keys if r["group"] == g], f"agent: {g} (key_rules 'after')"))
one = [score([(r["task"], r["passed"]) for r in json.loads((R / "baseline_v2.json").read_text())
              if r["model"] == "claude-opus-5-5" and r["variant"] == "request"], "one call: round 1 (baseline_v2)")]
for n in (2, 3, 4):
    one.append(score([(r["task"], r["passed"]) for r in json.loads((R / f"baseline_r{n}.json").read_text())], f"one call: round {n} (baseline_r{n})"))
print(f"\naverage: agent {sum(agent) / len(agent):.1f}% over {len(agent)} runs; one call {sum(one) / len(one):.1f}% over {len(one)} rounds")

runs = json.loads((R / "run_totals.json").read_text())
print("\nrun_totals.json keys:", list(runs)[:10] if isinstance(runs, dict) else len(runs))

# The two fresh agent runs above come from key_rules.json ("after": rescored with the new key rules, decision 0055),
# not from harness rows. Check their "before" side against the raw harness files of the same builds.
print("\n# fresh runs: key_rules 'before' against the raw harness rows (old rules)")
for g in ("fresh1", "fresh2"):
    before = {r["task"]: r["before"] for r in keys if r["group"] == g}
    rows = json.loads((R / f"harness/{g}_restart.json").read_text())["rows"]
    per = defaultdict(list)
    for r in rows:
        per[r["task"]].append(r["passed"])
    same = all(before[t] == per[t][-1] for t in before) and all(len(set(v)) == 1 for v in per.values())
    print(f"{g}: before {sum(before.values())}/192 = {100 * sum(before.values()) / 192:.1f}%  harness {g}_restart: "
          f"{sum(v[-1] for v in per.values())}/192 = {100 * sum(v[-1] for v in per.values()) / 192:.1f}%  "
          f"rows per task {Counter(len(v) for v in per.values())}  every task identical: {same}")
    after = {r["task"]: r["after"] for r in keys if r["group"] == g}
    print(f"   rescoring changed {sum(after[t] != before[t] for t in after)} tasks: "
          + ", ".join(f"{t} {before[t]}->{after[t]}" for t in after if after[t] != before[t]))

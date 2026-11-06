"""Check the numbers in the learnings files against the saved result files (decision 0051). Free, reads files only.

    uv run python -m eval.experiments.audit_numbers       # writes eval/results/audit_numbers.json and prints a table
"""

import json
import pathlib
import re
import statistics

R = pathlib.Path("eval/results")
H = R / "harness"
EASY = {"church_signup", "football_fixtures", "library_catalogue", "lost_and_found", "shop_price_list"}
VAGUE = {"school_grades_gpa", "shop_price_list", "trotro_fares"}
OUT = []


def rows(name, tasks=None):
    return [x for x in json.loads((H / f"{name}.json").read_text())["rows"] if tasks is None or x["task"] in tasks]


def score(name, tasks=None):
    r = rows(name, tasks)
    p, t = sum(x["passed"] for x in r), sum(x["total"] for x in r)
    return p, t, round(100 * p / t, 1), sum(x["passed"] == x["total"] for x in r)


def text(path):
    return (R.parent.parent / path if not str(path).startswith("eval") else pathlib.Path(path)).read_text(errors="replace")


def check(who, row, what, claimed, found):
    OUT.append({"who": who, "row": row, "what": what, "claimed": str(claimed), "found": str(found), "match": str(claimed) == str(found)})


def baseline(file, model=None, variant="request", tasks=None):
    r = [x for x in json.loads((R / file).read_text()) if x["variant"] == variant and (model is None or x["model"] == model) and (tasks is None or x["task"] in tasks)]
    return r


def pct(r):
    p, t = sum(int(x["passed"]) for x in r), sum(int(x["total"]) for x in r)
    return p, t, round(100 * p / t) if t else None


# ---- Alice (W1): every score file
for row, name, claim in [(1, "s32_A", 87.5), (1, "s32_B", 87.0), (1, "s32_C", 88.5), (1, "s32_D", 86.5), (3, "s34_r0", 87.0), (3, "s34_r1", 87.0), (3, "s34_r3", 87.0),
                         (3, "s34_r5", 87.0), (4, "s35", 74.5), (5, "s35v2", 82.8), (7, "s38_list_all", 95.8), (8, "s37_search", 92.7), (10, "s36_split", 84.4)]:
    check("Alice", row, f"{name} score %", claim, score(name)[2])
for row, name, claim in [(3, "s34_r0", 33), (4, "s35", 24), (5, "s35v2", 24), (7, "s38_list_all", 39), (8, "s37_search", 39), (10, "s36_split", 30)]:
    check("Alice", row, f"{name} fully passing of 45", claim, score(name)[3])
for row, name, claim in [(1, "s32_A", 12), (1, "s32_B", 10), (1, "s32_C", 11), (1, "s32_D", 11)]:
    check("Alice", row, f"{name} tasks fully passing of 15", claim, len({x["task"] for x in rows(name) if x["passed"] == x["total"]}))
for label, names, claim in [("no questions", ["s38_none1"], None), ("prepared answers", ["s38_list1", "s38_list2", "s38_list3"], 77.2), ("brief", ["s38_brief1", "s38_brief2", "s38_brief3"], 68.4)]:
    r = [x for n in names for x in rows(n, VAGUE)]
    p, t = sum(x["passed"] for x in r), sum(x["total"] for x in r)
    if claim:
        check("Alice", 6, f"vague tasks, {label} %", claim, round(100 * p / t, 1))
s = [x for n in ("s32_B", "s34_r0", "s38_none1") for x in rows(n, VAGUE)]
check("Alice", 6, "vague tasks, no questions % (S3.2 + S3.4 + 1 new)", 64.0, round(100 * sum(x["passed"] for x in s) / sum(x["total"] for x in s), 1))
check("Alice", 11, "Opus on the 5 easy tasks %", 85.2, score("s34_r0", EASY)[2])
check("Alice", 11, "Qwen alone on the 5 easy tasks %", 0.0, score("s39_qwen", EASY)[2])
check("Alice", 12, "Qwen with search on the 5 easy tasks %", 59.0, score("s39_qwen_search", EASY)[2])
for name, task, claim in [("s310_change", "church_signup", 10), ("s310_change", "shop_price_list", 11), ("s310_rebuild", "church_signup", 10), ("s310_rebuild", "shop_price_list", 13)]:
    check("Alice", 9, f"{name} {task} passed", claim, max([x["passed"] for x in rows(name, {task})] or [None]))

# ---- Joseph (W4)
v = json.loads(pathlib.Path("benchmark/validation.json").read_text())
tasks = {k: x for k, x in v.items() if isinstance(x, dict)}
check("Joseph", 7, "tasks in validation.json", 15, len(tasks))
check("Joseph", 7, "hidden tests", 192, sum(x["tests"] for x in tasks.values()))
caught = [len(c) for x in tasks.values() for c in x.get("caught_by", {}).values()]
check("Joseph", 7, "broken copies caught", 75, sum(c > 0 for c in caught))
check("Joseph", 8, "median tests catching a broken copy", 1, int(statistics.median(caught)))
for m, claim in [("claude-opus-5-5", 89), ("claude-haiku-5-5", 79)]:
    check("Joseph", 11, f"request only, {m} %", claim, pct(baseline("baseline_v2.json", m))[2])
for m, claim in [("claude-opus-5-5", 99), ("claude-haiku-5-5", 100)]:
    check("Joseph", 11, f"with operations list, {m} %", claim, pct(baseline("baseline_v2.json", m, "request+ops"))[2])
all_rows = baseline("baseline_v2.json")
for label, tier, vague, claim in [("plain easy", "easy", "False", 100), ("plain medium", "medium", "False", 100), ("plain hard", "hard", "False", 66), ("vague easy", "easy", "True", 77), ("vague medium", "medium", "True", 100), ("vague hard", "hard", "True", 17)]:
    check("Joseph", 14, f"{label} %", claim, pct([x for x in all_rows if x["tier"] == tier and str(x["vague"]) == vague])[2])
for file, claim_start, claim_passed in [("baseline_local_nothink.json", 2, 2), ("baseline_local_think.json", 2, 2), ("baseline_local_recipes_fixed.json", 9, 35), ("baseline_local_recipes_search.json", 7, 19)]:
    r = json.loads((R / file).read_text())
    check("Joseph", 17 if "recipes" not in file else 27, f"{file} builds that start", claim_start, sum(str(x["started"]) == "True" or x["started"] is True for x in r))
    check("Joseph", 17 if "recipes" not in file else 27, f"{file} tests passed", claim_passed, sum(int(x["passed"]) for x in r))
for w, claim in [(1, 51), (2, 24), (4, 13), (8, 11)]:
    d = json.loads((H / f"workers_{w}.json").read_text())
    check("Joseph", 18, f"{w} workers, seconds", claim, round(d["seconds"]))
    check("Joseph", 18, f"{w} workers, 272/272", 272, sum(x["passed"] for x in d["rows"]))
d = rows("repeat3_w8")
check("Joseph", 19, "repeat runs at 8 workers all 100%", len(d), sum(x["passed"] == x["total"] for x in d))
c = json.loads(pathlib.Path("kb/compare.json").read_text())
for name, key, claim in [("random (no search)", "hit@3", 17), ("bm25 full recipe", "hit@3", 74), ("dense MiniLM-L6 (22M)", "hit@3", 95), ("dense bge-small + query prefix", "hit@3", 89), ("dense bge-base (110M)", "hit@3", 89),
                         ("hybrid bm25 + MiniLM", "hit@3", 87), ("bm25 full recipe", "hit@1", 58), ("dense MiniLM-L6 (22M)", "hit@1", 68), ("hybrid bm25 + MiniLM", "hit@1", 72)]:
    check("Joseph", 24, f"{name} {key} %", claim, round(100 * c[name]["summary"][key]))
mini = c["dense MiniLM-L6 (22M)"]
check("Joseph", 25, "MiniLM best cutoff %", 66, round(100 * mini["summary"]["refuse"]))
check("Joseph", 25, "MiniLM always answering %", 62, round(100 * sum(x["pos"] == 1 for x in mini["rows"] if x["relevant"]) / len(mini["rows"])))
bm = c["bm25 full recipe"]
check("Joseph", 25, "BM25 best cutoff %", 54, round(100 * bm["summary"]["refuse"]))
check("Joseph", 25, "BM25 always answering %", 53, round(100 * sum(x["pos"] == 1 for x in bm["rows"] if x["relevant"]) / len(bm["rows"])))
check("Joseph", 24, "BM25 text only hit@3 %", 78, round(100 * c["bm25 text only (no code)"]["summary"]["hit@3"]))
check("Joseph", 24, "bge-small text only hit@3 %", 79, round(100 * c["dense bge-small text only"]["summary"]["hit@3"]))
m = json.loads((R / "mapping.json").read_text())
for model, claim in [("claude-opus-5-5", 21), ("claude-haiku-5-5", 10)]:
    check("Joseph", 10, f"maps right, {model}, of 21", claim, sum(str(x["right"]) == "True" for x in m if x["model"] == model))
f = json.loads((R / "fairness.json").read_text())
check("Joseph", 9, "tests flagged by the judge", 6, sum(len(x["flagged"]) for x in f))
v2 = {(x["task"], x["model"], x["variant"]): int(x["passed"]) for x in json.loads((R / "baseline_v2.json").read_text())}
hf = json.loads((R / "harness_failures.json").read_text())
check("Joseph", 20, "bad cases recorded", 15, len(hf))
for case, claim in [("every_reply_takes_2s", 10), ("one_endpoint_never_answers", 5), ("no_app_py", 0), ("uses_too_much_memory", 0)]:
    check("Joseph", 20, f"{case} passed", claim, hf[case]["passed"])
check("Joseph", 20, "tries_internet_and_files blocked", "False False False", " ".join(str(hf["tries_internet_and_files"]["flags"][k]) for k in ("internet", "env_file_visible", "repo_visible")))
q = json.loads(pathlib.Path("kb/questions.json").read_text())
check("Joseph", 23, "labelled questions", 111, len(q))
check("Joseph", 23, "questions with no right recipe", 10, sum(not x["relevant"] for x in q))
check("Joseph", 23, "written to have no answer", 6, sum(x["kind"] == "no_answer" for x in q))
h = json.loads((R / "hosting_check.json").read_text())
check("Joseph", 29, "hosting checks passed", 24, h["passed"])
check("Joseph", 30, "church live build tests passed", 30, sum(x["passed"] for x in rows("church_live_build")))

# ---- Bernard (W2): the saved text output
def has(row, file, words):
    body = pathlib.Path(f"runtime/experiments/results/{file}.txt").read_text(errors="replace")
    check("Bernard", row, f"{file}: says {words!r}", True, words in body)


for row, file, words in [(1, "path_guard", "A text check: 5 attacks wrongly allowed"), (1, "path_guard", "B resolve then compare: 0 attacks wrongly allowed [], 0 good paths wrongly refused []"),
                         (4, "file_tools", "2588 characters"), (9, "error_format", "A raw           fixed 21/21"), (9, "error_format", "B reason first  fixed 21/21"), (9, "error_format", "total $0.85"),
                         (12, "timeout_choice", "slowest of 5 = 5.4 s"), (12, "timeout_choice", "stopped after 60.8 s"), (13, "attacks", "blocked 14/16"), (13, "attacks", "blocked 5/16"),
                         (11, "sandbox_compare", "killed (exit code 137)"), (7, "server_start", "fixed port 8001, second: died")]:
    has(row, file, words)
pathlib.Path("eval/results/audit_numbers.json").write_text(json.dumps(OUT, indent=2) + "\n")
bad = [x for x in OUT if not x["match"]]
print(f"{len(OUT)} numbers checked, {len(OUT) - len(bad)} match, {len(bad)} differ")
for x in bad:
    print(f"  {x['who']} row {x['row']}: {x['what']}: written {x['claimed']}, file says {x['found']}")

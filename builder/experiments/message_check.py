"""S4.8: is a "must" message, sent while the agent builds, really enforced? As on the live platform: an approved plan, then the
message arrives after the agent's first turn. Each arm is 4 tasks x 2 repeats. About $3 of Opus.
Sends real requests to the running app, never trusts what the agent says.
--rescore checks the saved apps again, free. Writes eval/results/message_check.json.

    uv run --env-file .env --with anthropic python -m builder.experiments.message_check
"""

import json
import pathlib
import re
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import httpx

from builder import agent
from eval import bench
from runtime.tools import start_server, stop_server

OLD = agent.NEW_MESSAGE
STRONG = """The client sent a new message while you work. It replaces the plan and the request wherever they differ, so do exactly
what it says, then carry on. If it says something must be given, make it required: a request without it, or with it left blank,
must be refused. If it says something is not wanted, remove it completely. Add a test that proves this, and run all the tests:

{message}"""
SHELTER = "I run a small animal shelter. I need to keep a list of pets with their name and kind, see all of them, and mark a pet as adopted."
CASES = {  # request, message, the word the required thing goes by (None: POST on this path must be gone)
    "animal_shelter": (SHELTER, "One more thing: every pet also has a colour, and it must be given when adding a pet.", "colou?r", None),
    "church_signup": (None, "One more thing: every event must also have a place where it happens, and the place must be given when adding an event.", "place|venue|location", None),
    "tailoring_orders": (None, "Each order must also say which tailor will sew it, by name. Refuse an order without it.", "tailor", None),
    "library_catalogue": (None, "I changed my mind: we don't want a way to add books. We will load the books from a CSV file ourselves.", None, "/books"),
}
HOME, OUT = bench.ROOT / "projects/s48_message", bench.ROOT / "eval/results/message_check"
ROOT_R = bench.ROOT / "eval/results/message_check.json"


def request_of(task):
    return CASES[task][0] or (bench.BENCH / task / "request.md").read_text().strip()


def resolve(schema, spec):
    while "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return schema


def value(name, prop):
    kinds = str(prop)
    if "integer" in kinds or re.search(r"copies|capacity|seats", name):
        return 5
    if "number" in kinds or re.search(r"price|amount", name):
        return 50.0
    return "2030-06-15" if re.search(r"date|due", name) or "format': 'date" in kinds else "Sample"


def fields(op, spec):
    body = resolve(op["requestBody"]["content"]["application/json"]["schema"], spec)
    return {n: value(n, p) for n, p in body.get("properties", {}).items() if n != "id"}


def enforced(root, task):
    """Real requests to the running app. The app's own description is not enough: many apps refuse a missing value in their code."""
    started = start_server(root)
    if not started["ok"]:
        return {"enforced": False, "why": "would not start"}
    base = started["output"].split()[-1]
    try:
        spec = httpx.get(base + "/openapi.json", timeout=30).json()
        _, _, word, gone = CASES[task]
        if gone:
            left = [p for p, ops in spec["paths"].items() if "post" in ops and p.rstrip("/") == gone]
            return {"enforced": not left, "why": f"POST still there: {left}" if left else "no way to add left"}
        path = next(p for p, ops in spec["paths"].items() if "post" in ops and re.search(word, str(fields(ops["post"], spec)), re.I))
        if "{" in path:  # the order belongs to a customer: make one first
            parent = httpx.post(base + "/customers", json=fields(spec["paths"]["/customers"]["post"], spec), timeout=30).json()
            path = re.sub(r"{[^}]*}", str(parent["id"]), path)
            template = next(ops["post"] for p, ops in spec["paths"].items() if "post" in ops and "{" in p and re.search(word, str(fields(ops["post"], spec)), re.I))
        else:
            template = spec["paths"][path]["post"]
        good = fields(template, spec)
        name = next(n for n in good if re.search(word, n, re.I))
        codes = {"with it": httpx.post(base + path, json=good, timeout=30).status_code,
                 "without it": httpx.post(base + path, json={k: v for k, v in good.items() if k != name}, timeout=30).status_code,
                 "left blank": httpx.post(base + path, json={**good, name: "   "}, timeout=30).status_code}
        return {"enforced": codes["with it"] < 300 and 400 <= codes["without it"] < 500 and 400 <= codes["left blank"] < 500, "why": str(codes)}
    finally:
        stop_server(root)


if "--rescore" in sys.argv:  # free: the saved apps again, in a throwaway folder
    saved = json.loads(ROOT_R.read_text())
    for r in saved["rows"]:
        with tempfile.TemporaryDirectory(dir=bench.WORK) as folder:
            shutil.copy(OUT / r["arm"].replace(" ", "_") / f"{r['task']}_{r['repeat']}" / "app.py", folder)
            r["schema_only_said"] = r["enforced"]
            r.update(enforced(pathlib.Path(folder), r["task"]))
    for arm, row in saved["table"].items():
        row["enforced"] = sum(r["arm"] == arm and r["enforced"] for r in saved["rows"])
    ROOT_R.write_text(json.dumps(saved, indent=2) + "\n")
    print(json.dumps(saved["table"], indent=1))
    for r in saved["rows"]:
        print(r["arm"][:8], r["task"], r["repeat"], r["enforced"], r["why"][:100])
    sys.exit()


plans = {}
def plan_of(task):
    plan, _ = agent.make_plan(request_of(task))
    plans[task] = plan


with ThreadPoolExecutor(4) as ex:
    list(ex.map(plan_of, CASES))
rows = []
for arm, text in (("as live today", OLD), ("stronger wording", STRONG)):
    agent.NEW_MESSAGE = text

    def one(job):
        task, repeat = job
        root = HOME / arm.replace(" ", "_") / f"{task}_{repeat}"
        shutil.rmtree(root, ignore_errors=True)
        box = [[CASES[task][1]]]
        r = agent.build(request_of(task), root, "claude-opus-5-5", plan=plans[task], inbox=lambda: box.pop() if box else [])
        out = {"arm": arm, "task": task, "repeat": repeat, "stop": r["stop"], "turns": r["turns"], "cost_usd": r["cost_usd"], "seconds": r["seconds"], "tests": r["tests"], **enforced(root, task)}
        keep = OUT / arm.replace(" ", "_") / f"{task}_{repeat}"
        keep.mkdir(parents=True, exist_ok=True)
        for name in ("app.py", "run.json", "trace.jsonl"):
            shutil.copy(root / name, keep / name)
        return out

    with ThreadPoolExecutor(4) as ex:
        rows += list(ex.map(one, [(t, n) for n in (1, 2) for t in CASES]))
table = {a: {"builds": sum(r["arm"] == a for r in rows), "enforced": sum(r["arm"] == a and r["enforced"] for r in rows),
             "cost_usd": round(sum(r["cost_usd"] for r in rows if r["arm"] == a), 2), "avg_turns": round(sum(r["turns"] for r in rows if r["arm"] == a) / 8, 1)} for a in ("as live today", "stronger wording")}
ROOT_R.write_text(json.dumps({"table": table, "plans": plans, "rows": rows}, indent=2) + "\n")
print(json.dumps(table, indent=1))
for r in rows:
    print(r["arm"][:8], r["task"], r["repeat"], r["enforced"], r["stop"][:20], r["turns"], r["why"][:120])

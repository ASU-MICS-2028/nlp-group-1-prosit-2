"""Load benchmark tasks and score any backend against a task's hidden tests, in Bernard's sandbox."""

import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT))
from validate import hidden_tests  # noqa: E402
from runtime.tools import start_server, stop_server  # noqa: E402

BENCH = ROOT / "benchmark"
WORK = ROOT / "projects" / "_eval"


def task_names():
    return sorted(p.name for p in BENCH.iterdir() if (p / "hidden_tests").is_dir() and not p.name.startswith("_"))


def load(name):
    t = BENCH / name
    read = lambda f: (t / f).read_text() if (t / f).exists() else ""
    return {"name": name, **json.loads(read("task.json") or "{}"), "request": read("request.md").strip(),
            "operations": read("operations.json"), "brief": read("client_brief.md"), "answers": read("answers.json"),
            "tests": "\n\n".join(p.read_text() for p in sorted((t / "hidden_tests").glob("test_*.py"))),
            "references": [r for r in ("reference", "reference_b") if (t / r / "app.py").exists()]}


def score(name, label, app_text, ops):
    """Start app_text in the sandbox, translate with ops (a dict), run the hidden tests. Returns passed/total."""
    root = WORK / name / label
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    (root / "app.py").write_text(app_text)
    (root / "ops.json").write_text(json.dumps(ops))
    started = start_server(root)
    if not started["ok"]:
        return {"started": False, "passed": 0, "failed": 0, "error": started["output"][-300:]}  # the end of a traceback says why
    try:
        r = hidden_tests(name, started["output"].split()[-1], root / "ops.json")
    finally:
        stop_server(root)
    return {"started": True, **r}


def mapping_schema():
    """Structured-output schema for an ops.json, as a list (converted with to_ops)."""
    pair = {"type": "object", "properties": {"test_name": {"type": "string"}, "backend_name": {"type": "string"}},
            "required": ["test_name", "backend_name"], "additionalProperties": False}
    item = {"type": "object", "properties": {"operation": {"type": "string"}, "method": {"type": "string"},
            "path": {"type": "string"}, "request_fields": {"type": "array", "items": pair},
            "response_fields": {"type": "array", "items": pair}, "response_key": {"type": "string"}},
            "required": ["operation", "method", "path", "request_fields", "response_fields", "response_key"],
            "additionalProperties": False}
    return {"type": "object", "properties": {"mappings": {"type": "array", "items": item}}, "required": ["mappings"],
            "additionalProperties": False}


def to_ops(mapping_json):
    out = {}
    for m in json.loads(mapping_json)["mappings"]:
        spec = {"method": m["method"].upper(), "path": m["path"]}
        for part in ("request_fields", "response_fields"):
            names = {f["test_name"]: f["backend_name"] for f in m[part] if f["test_name"] != f["backend_name"]}
            if names:
                spec[part] = names
        if m["response_key"]:
            spec["response_key"] = m["response_key"]
        out[m["operation"]] = spec
    return out


MAP_SYSTEM = """You connect a test suite to a backend. The tests call named operations; you say which endpoint of the
given FastAPI app implements each one. For every operation in the list return: its HTTP method; its path, with
placeholders written exactly as the operation's path parameter names in braces (for example /church-events/{id} if the
operation says "Path params: id"); request_fields: every field the tests SEND (body or query string) whose name the app
expects differently, as test_name -> backend_name; response_fields: every field the tests READ in the reply whose name
the app returns differently. The same idea can have different names going in and coming out (for example the app may
accept "copies" but return "total_copies"), so look at the input model and the output separately. Where a value goes may
differ as well: if the operation gives a value as a path parameter but the app takes it in the body (or the query
string), leave it out of the path and list it in request_fields (path parameter name -> the app's field name); if the
app's path needs a value the operation sends in the body or query string, put its name in braces in the path. Shape
may differ: if the operation nests values (for example measurements: {chest, waist}) but the app takes them flat
(chest, waist), use dotted test names (measurements.chest -> chest) in request_fields and response_fields. Use dots ONLY for that
flattening: names are already translated at every depth, so a field inside a nested object or list is renamed with
its plain name (course_id -> subject), never courses.course_id; if the app
wraps the reply the operation expects (for example returns {"event": ..., "signups": [...]} where the operation returns
the list of sign-ups), set response_key to the field holding it ("signups"), otherwise set response_key to "". Include
every operation in the list."""


def map_ops(model, app_text, operations, effort="medium"):
    from eval.llm import ask
    user = f"Operations the tests call:\n{operations}\n\nThe backend (app.py):\n```python\n{app_text}\n```"
    text, info = ask(model, MAP_SYSTEM, user, effort=effort, schema=mapping_schema())
    return to_ops(text), info

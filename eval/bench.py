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
        return {"started": False, "passed": 0, "failed": 0, "error": started["output"][:300]}
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
            "path": {"type": "string"}, "fields": {"type": "array", "items": pair}},
            "required": ["operation", "method", "path", "fields"], "additionalProperties": False}
    return {"type": "object", "properties": {"mappings": {"type": "array", "items": item}}, "required": ["mappings"],
            "additionalProperties": False}


def to_ops(mapping_json):
    out = {}
    for m in json.loads(mapping_json)["mappings"]:
        fields = {f["test_name"]: f["backend_name"] for f in m["fields"] if f["test_name"] != f["backend_name"]}
        out[m["operation"]] = {"method": m["method"].upper(), "path": m["path"], **({"fields": fields} if fields else {})}
    return out


MAP_SYSTEM = """You connect a test suite to a backend. The tests call named operations; you say which endpoint of the
given FastAPI app implements each one. For every operation in the list return: its HTTP method; its path, with
placeholders written exactly as the operation's path parameter names in braces (for example /church-events/{id} if the
operation says "Path params: id"); and fields: every field name the operation uses (body, query string or reply) whose
name in the app is different, as test_name -> backend_name. Include every operation in the list."""


def map_ops(model, app_text, operations, effort="medium"):
    from eval.llm import ask
    user = f"Operations the tests call:\n{operations}\n\nThe backend (app.py):\n```python\n{app_text}\n```"
    text, info = ask(model, MAP_SYSTEM, user, effort=effort, schema=mapping_schema())
    return to_ops(text), info

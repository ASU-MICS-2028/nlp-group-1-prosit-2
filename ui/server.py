"""ui/server.py: thin adapter between the page and Alice's builder (W1).

Run from the repo root, then open http://localhost:8001/?live
  uv run --env-file .env --with anthropic --with fastapi --with uvicorn uvicorn ui.server:app --port 8001

The server holds no logic of its own: it calls clarify / make_plan / build and relays what they say.
Generated code never runs here (rule from W1): start_app() must use Bernard's sandbox launcher.
"""
import json
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from builder.agent import build, clarify, make_plan, plan_text, with_answers

HERE = Path(__file__).parent
ROOT = HERE.parent
app = FastAPI()
SESSIONS: dict[str, dict] = {}
NO_PREF = "No preference: you decide"


class Start(BaseModel):
    request: str


class Answers(BaseModel):
    answers: list[str]


class Text(BaseModel):
    text: str


def sess(sid: str) -> dict:
    if sid not in SESSIONS:
        raise HTTPException(404, "Unknown session. Start again.")
    return SESSIONS[sid]


def q_text(q) -> str:
    return q if isinstance(q, str) else q.get("question") or q.get("text") or str(q)


def claude_call(fn, *a, **k):
    """Anthropic or network errors become a plain message the page can show."""
    try:
        return fn(*a, **k)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Could not reach the AI service ({type(e).__name__}).")


def start_app(folder: str):
    """TODO (Bernard, S1.1): start folder/app.py with the sandbox's server launcher and return
    its base URL, e.g. 'http://localhost:9001'. Until then the page says the system is built
    but not running, and hides the Swagger button."""
    return None


@app.get("/")
def index():
    return FileResponse(HERE / "index.html")


@app.post("/api/start")
def start(body: Start):
    sid = uuid.uuid4().hex[:8]
    questions, _cost = claude_call(clarify, body.request, 3)
    SESSIONS[sid] = dict(req=body.request, questions=questions, folder=str(ROOT / "projects" / "web" / sid),
                         events=[], done=False, app_url=None, result=None, plan=None, full=body.request)
    return {"id": sid, "questions": [q_text(q) for q in questions]}


@app.post("/api/{sid}/answers")
def answers(sid: str, body: Answers):
    s = sess(sid)
    a = [x.strip() or NO_PREF for x in body.answers]
    s["full"] = with_answers(s["req"], s["questions"], a) if s["questions"] else s["req"]
    s["plan"], _ = claude_call(make_plan, s["full"])
    return {"plan": s["plan"], "text": plan_text(s["plan"])}


@app.post("/api/{sid}/plan")
def change_plan(sid: str, body: Text):
    s = sess(sid)
    s["plan"], _ = claude_call(make_plan, s["full"], old=s["plan"], changes=body.text)
    return {"plan": s["plan"], "text": plan_text(s["plan"])}


def run_build(s: dict, change: str | None = None):
    s.update(events=[], done=False, result=None)

    def on_event(e):  # same lines as trace.jsonl; drop the code Claude wrote to keep the stream small
        s["events"].append({k: v for k, v in e.items() if k != "input"})

    try:
        kw = {"change": change} if change else {"plan": s["plan"]}
        s["result"] = build(s["full"], s["folder"], on_event=on_event, **kw)
        s["app_url"] = start_app(s["folder"])
    except Exception as e:
        s["events"].append({"event": "error", "message": f"{type(e).__name__}: {e}"})
    s["done"] = True


@app.post("/api/{sid}/approve")
def approve(sid: str):
    s = sess(sid)
    if not s["plan"]:
        raise HTTPException(400, "There is no plan to approve yet.")
    threading.Thread(target=run_build, args=(s,), daemon=True).start()
    return {"ok": True}


@app.post("/api/{sid}/change")
def change(sid: str, body: Text):
    s = sess(sid)
    threading.Thread(target=run_build, args=(s, body.text), daemon=True).start()
    return {"ok": True}


@app.get("/api/{sid}/events")
def events(sid: str):
    s = sess(sid)

    def gen():
        i = 0
        while True:
            while i < len(s["events"]):
                yield f"data: {json.dumps(s['events'][i], default=str)}\n\n"
                i += 1
            if s["done"]:
                yield 'data: {"event": "closed"}\n\n'
                return
            time.sleep(0.3)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/{sid}/result")
def result(sid: str):
    s = sess(sid)
    r = s["result"] or {}
    return {"summary": r.get("summary"), "follows_plan": r.get("follows_plan"), "app_url": s["app_url"]}


@app.get("/api/{sid}/app.py")
def download(sid: str):
    f = Path(sess(sid)["folder"]) / "app.py"
    if not f.exists():
        raise HTTPException(404, "Nothing built yet.")
    return FileResponse(f, filename="app.py")

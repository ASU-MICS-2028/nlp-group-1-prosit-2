"""One client's whole journey, for the platform's backend: request -> questions -> plan -> build -> live link.

    from builder.session import start, send, approve, get
    sid = start("I need a sign-up sheet for church events ...")   # returns at once; the work runs in the background
    get(sid)                         # {"state": "waiting_answers", "questions": [...], "events": [...], ...}
    send(sid, ["Weekly", "No"])      # the answers, in order
    get(sid)["plan_text"]            # the plan in plain words (state "waiting_approval")
    send(sid, "add a phone number")  # or approve(sid)
    send(sid, "no adding events")    # while building: the agent sees it between turns
    get(sid)["url"]                  # state "live": the public link. A later send is a change, and the link stays the same

States: asking, waiting_answers, planning, waiting_approval, building, live, failed. Choices in decisions 0041 (a person
approves the plan), 0042 (up to 3 questions) and 0048 (this file). Each event is also saved to session.jsonl in the build
folder. Sessions live in memory: a restart forgets them, but backends already live keep running.
"""

import json
import os
import threading
import time
import uuid
from datetime import date
from pathlib import Path

from builder.agent import build, clarify, make_plan, plan_text, with_answers
from runtime.deploy import deploy

BUILDS = Path(os.environ.get("BUILDS_ROOT", "builds"))
MODEL = "claude-opus-5-5"
MAX_REQUEST = 5000  # characters; a real request is a few sentences
MAX_DAILY_USD = float(os.environ.get("MAX_DAILY_USD", "10"))  # anyone can start a build, and each one spends our Claude credit
SESSIONS = {}
LOCK = threading.Lock()
BUILDING = threading.BoundedSemaphore(2)  # 4 GB server: at most 2 builds at once; the others wait their turn


class Refused(ValueError):
    """The request cannot be accepted. The message is written for the client."""


def spent_today():
    try:
        saved = json.loads((BUILDS / "spend.json").read_text())
    except (FileNotFoundError, ValueError):
        return 0.0
    return saved["usd"] if saved["date"] == str(date.today()) else 0.0


class Session:
    def __init__(self, request, sid):
        self.request, self.id, self.root = request, sid, BUILDS / sid
        self.root.mkdir(parents=True)
        self.state, self.questions, self.plan, self.url, self.docs_url, self.endpoints = "asking", [], None, None, None, []
        self.summary, self.error, self.cost = None, None, 0.0
        self.events, self.inbox, self.started = [], [], time.time()

    def emit(self, event, **fields):
        line = {"event": event, "t": round(time.time() - self.started, 2), **fields}
        with LOCK:
            self.events.append(line)
        with open(self.root / "session.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str) + "\n")

    def pay(self, usd):
        with LOCK:
            self.cost += usd
            (BUILDS / "spend.json").write_text(json.dumps({"date": str(date.today()), "usd": round(spent_today() + usd, 4)}))

    def go(self, state):
        self.state = state
        self.emit("state", state=state)

    def background(self, work, *args):
        def run():
            try:
                work(*args)
            except Exception as e:  # the client must always get an answer; the details stay in session.jsonl
                self.error = "Something went wrong on our side. Please try again."
                self.emit("error", detail=f"{type(e).__name__}: {e}"[:500])
                self.go("failed")
        threading.Thread(target=run, daemon=True).start()

    def ask(self):
        self.questions, usd = clarify(self.request, 3, MODEL)
        self.pay(usd)
        if self.questions:
            self.emit("questions", questions=self.questions)
            self.go("waiting_answers")
        else:
            self.go("planning")
            self.draft()

    def draft(self, changes=None):
        self.plan, usd = make_plan(self.request, MODEL, old=self.plan, changes=changes)
        self.pay(usd)
        self.emit("plan", plan=self.plan, text=plan_text(self.plan))
        self.go("waiting_approval")

    def take_inbox(self):
        with LOCK:
            found, self.inbox = self.inbox, []
        return found

    def work(self, change=None):
        """Build (or change) the app, and publish it only if its own tests ran and passed."""
        if not BUILDING.acquire(blocking=False):
            self.emit("queued")
            BUILDING.acquire()
        try:
            result = build(self.request, self.root, MODEL, plan=None if change else self.plan, change=change,
                           on_event=lambda e: self.emit("agent", detail=e), inbox=self.take_inbox)
        finally:
            BUILDING.release()
        self.pay(result["cost_usd"])
        self.summary = result["summary"]
        late = self.take_inbox()  # arrived after the agent's last look
        if late:
            return self.work(change=" ".join(late))
        if not tests_passed(result):
            self.error = "The backend did not pass its own tests, so it was not published. You can send a message to try again."
            self.emit("not_published", stop=result["stop"], tests=result["tests"])
            return self.go("failed")
        out = deploy(self.root, self.id)
        if not out["ok"]:
            self.error = "The backend was built but would not start, so it was not published. You can send a message to try again."
            self.emit("not_published", detail=out["output"])
            return self.go("failed")
        self.url, self.docs_url, self.endpoints = out["url"], out["docs_url"], out["endpoints"]
        self.emit("live", url=self.url, docs_url=self.docs_url, endpoints=self.endpoints, summary=self.summary)
        self.go("live")


def tests_passed(result):
    """The agent can finish without testing (with Docker off, every test run fails and it still ends normally)."""
    tests = result["tests"]
    return result["stop"] == "end_turn" and bool(tests) and tests["passed"] > 0 and tests["failed"] == 0


def start(request):
    """Accept a request and begin. Raises Refused, with a message for the client."""
    request = request.strip() if isinstance(request, str) else ""
    if not request:
        raise Refused("Please describe the backend you need.")
    if len(request) > MAX_REQUEST:
        raise Refused(f"Please keep your request under {MAX_REQUEST} characters.")
    BUILDS.mkdir(parents=True, exist_ok=True)
    if spent_today() >= MAX_DAILY_USD:
        raise Refused("The platform has reached its limit for today. Please try again tomorrow.")
    session = Session(request, "b" + uuid.uuid4().hex[:10])  # a valid deploy name; hard to guess, so links stay private-ish
    SESSIONS[session.id] = session
    session.emit("request", text=request)
    session.background(session.ask)
    return session.id


def find(sid):
    if sid not in SESSIONS:
        raise Refused("No such build.")
    return SESSIONS[sid]


def send(sid, message):
    """The client said something. What it means depends on the state; a state with nothing to receive refuses it."""
    s = find(sid)
    if s.state == "waiting_answers":
        answers = message if isinstance(message, list) else [message]
        s.request = with_answers(s.request, s.questions, [str(a) for a in answers] + ["No preference: you decide."] * len(s.questions))
        s.emit("answers", answers=answers)
        s.go("planning")  # at once, here: a second click must not start the work twice
        return s.background(s.draft)
    if not isinstance(message, str) or not message.strip() or len(message) > MAX_REQUEST:
        raise Refused("Please send a short message.")
    if s.state == "waiting_approval":
        s.emit("plan_changes", text=message)
        s.go("planning")
        return s.background(s.draft, message)
    if s.state == "building":
        with LOCK:
            s.inbox.append(message)
        return None
    if s.state in ("live", "failed") and (s.root / "app.py").exists():
        if spent_today() >= MAX_DAILY_USD:
            raise Refused("The platform has reached its limit for today. Please try again tomorrow.")
        s.error = None
        s.go("building")
        return s.background(s.work, message)
    raise Refused("Please wait a moment: this build is not ready for a message yet.")


def approve(sid):
    s = find(sid)
    if s.state != "waiting_approval":
        raise Refused("There is no plan waiting for approval.")
    s.emit("approved")
    s.go("building")
    s.background(s.work)


def get(sid, after=0):
    """Everything a page shows. Pass after=N to get only the events from number N on. The cost and any error details stay out."""
    s = find(sid)
    with LOCK:
        events = s.events[after:]
        total = len(s.events)
    shown = {"request", "state", "questions", "plan", "answers", "plan_changes", "approved", "queued", "live", "not_published", "error"}
    return {"id": s.id, "state": s.state, "questions": s.questions, "plan": s.plan, "plan_text": plan_text(s.plan) if s.plan else None,
            "url": s.url, "docs_url": s.docs_url, "endpoints": s.endpoints, "summary": s.summary, "error": s.error,
            "next": total, "events": [public(e) for e in events if e["event"] in shown or e["event"] == "agent"]}


def public(e):
    """What the client may see of an event: never the error details, the code or the raw output of tools."""
    if e["event"] == "agent":
        d = e["detail"]
        return {"event": "agent", "t": e["t"], "kind": d["event"], "tool": d.get("tool"), "ok": d.get("ok"),
                "tests": d.get("tests"), "text": d.get("text") if d["event"] in ("reply", "message") else None}
    if e["event"] in ("error", "not_published"):
        return {"event": e["event"], "t": e["t"]}
    return e

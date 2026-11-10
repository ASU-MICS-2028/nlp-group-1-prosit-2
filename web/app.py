"""The platform's backend: the page talks to this, this talks to the agent, and the page never reaches the agent itself (Lecture 8).

    uv run --env-file .env --with anthropic python -m uvicorn web.app:app --port 8080     # on a laptop: building works, publishing needs the server

Small on purpose (decision 0049): Michael owns the page and can replace index.html without touching this file.
"""

import pathlib
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from builder import session
from runtime.deploy import DEPLOY_ROOT, stop_oversized


def watch_disk():
    """Every 5 seconds. A loop that died would leave the disk unguarded, so one bad look (a file vanishing mid-count) only skips a turn."""
    while True:
        time.sleep(5)
        try:
            for name in stop_oversized():
                print(f"Stopped backend {name}: it holds too much on disk", flush=True)
        except OSError as e:
            print(f"Disk check skipped: {e}", flush=True)


@asynccontextmanager
async def lifespan(app):
    if DEPLOY_ROOT.exists():  # only on the server
        threading.Thread(target=watch_disk, daemon=True).start()
    yield


app = FastAPI(title="Prosit 2 platform", docs_url=None, redoc_url=None, lifespan=lifespan)
PAGE = pathlib.Path(__file__).parent / "index.html"
LIMITS = {"start": (5, 86400), "message": (30, 3600)}  # (how many, in how many seconds), per person, on top of the daily spending limit
SEEN = defaultdict(list)


def person(request):
    """Caddy, the only thing that can reach us, replaces this header with the caller's real address."""
    return request.headers.get("x-forwarded-for") or request.client.host


def limit(request, kind):
    # ponytail: one address can be many people (a campus), and counts reset on restart. Good enough for a demo; add logins if abused.
    most, seconds = LIMITS[kind]
    key, now = (kind, person(request)), time.time()
    SEEN[key] = [t for t in SEEN[key] if now - t < seconds]
    if len(SEEN[key]) >= most:
        raise HTTPException(429, "You have reached the limit for now. Please try again later.")
    SEEN[key].append(now)


def client_says(work, *args):
    try:
        return work(*args)
    except session.Refused as e:
        raise HTTPException(400, str(e)) from None


class NewBuild(BaseModel):
    request: str = Field(max_length=session.MAX_REQUEST)


class Message(BaseModel):
    message: str | list[str]


@app.get("/")
def page():
    return FileResponse(PAGE)


@app.post("/api/builds", status_code=201)
def new_build(body: NewBuild, request: Request):
    if body.request.strip():  # an empty request costs nothing, so it does not use up the limit
        limit(request, "start")
    return {"id": client_says(session.start, body.request)}


@app.get("/api/builds/{sid}")
def read_build(sid: str, after: int = 0):
    return client_says(session.get, sid, max(after, 0))


@app.post("/api/builds/{sid}/messages")
def message(sid: str, body: Message, request: Request):
    limit(request, "message")
    client_says(session.send, sid, body.message)
    return {"ok": True}


@app.post("/api/builds/{sid}/approve")
def approve(sid: str, request: Request):
    limit(request, "message")
    client_says(session.approve, sid)
    return {"ok": True}

"""Real check of hosting, run ON THE SERVER: uv run python -m runtime.experiments.deploy_check
Deploys backends and calls them through the public HTTPS address. Free (no LLM). Removes everything at the end."""

import pathlib
import subprocess
import tempfile
import time

import httpx

from runtime.deploy import deploy, undeploy

NOTES = """from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select

app = FastAPI()
engine = create_engine("sqlite:///notes.db", connect_args={"check_same_thread": False})


class Note(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str


SQLModel.metadata.create_all(engine)


@app.post("/notes", status_code=201)
def add(note: Note):
    with Session(engine) as s:
        s.add(note)
        s.commit()
        s.refresh(note)
        return note


@app.get("/notes")
def all_notes():
    with Session(engine) as s:
        return s.exec(select(Note)).all()
"""
SNOOP = NOTES + """

@app.get("/snoop")
def snoop():
    import pathlib, socket, urllib.request
    out = {"env_visible": pathlib.Path("/home/platform/repo/.env").exists(), "other_data": [str(p) for p in pathlib.Path("/srv").rglob("*")]}
    for what, f in {"internet": lambda: urllib.request.urlopen("https://example.com", timeout=3),
                    "other_backend": lambda: socket.create_connection(("d-check-a", 8000), timeout=3),
                    "host_caddy_admin": lambda: socket.create_connection(("172.17.0.1", 2019), timeout=3)}.items():
        try:
            f()
            out[what] = True
        except OSError:
            out[what] = False
    return out
"""


def folder(code):
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "app.py").write_text(code)
    return d


def check(what, passed, detail=""):
    print(("PASS " if passed else "FAIL ") + what, detail)


a = deploy(folder(NOTES), "check-a")
print(a)
base = a["url"]
r = httpx.post(base + "/notes", json={"text": "kept"}, timeout=20)
check("add through public HTTPS", r.status_code == 201, r.text)
check("read it back", [n["text"] for n in httpx.get(base + "/notes", timeout=20).json()] == ["kept"])
docs = httpx.get(a["docs_url"], timeout=20)
spec = httpx.get(base + "/openapi.json", timeout=20)
check("docs page loads and names its spec under the path", docs.status_code == 200 and "/b/check-a/openapi.json" in docs.text)
check("spec reachable", spec.status_code == 200)
check("bare link goes to docs", httpx.get(base, timeout=20, follow_redirects=True).url == a["docs_url"])

subprocess.run(["docker", "restart", "d-check-a"], check=True, capture_output=True)
time.sleep(4)
check("data survives a restart", [n["text"] for n in httpx.get(base + "/notes", timeout=20).json()] == ["kept"])
again = deploy(folder(NOTES + "\n\n@app.get('/new')\ndef new():\n    return {'new': True}\n"), "check-a")
check("redeploy changes the code", httpx.get(base + "/new", timeout=20).status_code == 200)
check("redeploy keeps the data", [n["text"] for n in httpx.get(base + "/notes", timeout=20).json()] == ["kept"])

b = deploy(folder(SNOOP), "check-b")
seen = httpx.get(b["url"] + "/snoop", timeout=30).json()
print(seen)
check("no internet", seen["internet"] is False)
check("cannot see .env", seen["env_visible"] is False)
check("cannot reach another backend", seen["other_backend"] is False)
check("cannot reach Caddy's admin port", seen["host_caddy_admin"] is False)
check("cannot see other backends' data", not any("check-a" in p for p in seen["other_data"]), seen["other_data"])

crash = deploy(folder("raise RuntimeError('broken on purpose')\n"), "check-c", timeout=8)
check("a crashing app is refused, with the reason", not crash["ok"] and "broken on purpose" in crash["output"])
check("a refused app leaves nothing behind", subprocess.run(["docker", "ps", "-aq", "--filter", "name=d-check-c"], capture_output=True, text=True).stdout == "")
for bad in ["../evil", "A", "x y", "a;rm -rf /", "-a", "a" * 41, ""]:
    check(f"bad name refused: {bad!r}", not deploy(folder(NOTES), bad)["ok"])
check("no app.py refused", not deploy(tempfile.mkdtemp(), "check-d")["ok"])

undeploy("check-a", delete_data=True)
undeploy("check-b", delete_data=True)
undeploy("check-c", delete_data=True)
undeploy("check-d", delete_data=True)
check("removed backend is gone", httpx.get(base + "/notes", timeout=20).text.startswith("ICS554"))

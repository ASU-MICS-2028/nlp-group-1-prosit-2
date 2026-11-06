"""The whole journey for real, ON THE SERVER: about $0.30 of Opus. Removes its backend at the end.
    uv run --env-file ~/.env --with anthropic python -m builder.experiments.session_check"""

import time

import httpx

from builder.session import approve, get, send, start
from runtime.deploy import undeploy


def wait(sid, *states, limit=600):
    end = time.time() + limit
    while time.time() < end:
        got = get(sid)
        if got["state"] in states:
            return got
        time.sleep(1)
    raise TimeoutError(get(sid)["state"])


def check(what, passed, detail=""):
    print(("PASS " if passed else "FAIL ") + what, str(detail)[:300], flush=True)


sid = start("I run a small animal shelter. I need to keep a list of pets with their name and kind, see all of them, and mark a pet as adopted.")
got = wait(sid, "waiting_answers", "waiting_approval", "failed")
print(got["state"], got["questions"], flush=True)
if got["state"] == "waiting_answers":
    send(sid, ["You decide, keep it simple."] * len(got["questions"]))
got = wait(sid, "waiting_approval", "failed")
print(got["plan_text"], flush=True)
approve(sid)
send(sid, "One more thing: every pet also has a colour, and it must be given when adding a pet.")  # while it builds
got = wait(sid, "live", "failed")
check("went live", got["state"] == "live", got["error"])
print(got["url"], got["endpoints"], flush=True)
base = got["url"]
said = [e for e in got["events"] if e["event"] == "agent" and e.get("kind") == "message"]
check("the mid-build message reached the agent", bool(said), said)
spec = httpx.get(base + "/openapi.json", timeout=30).text
check("the new field is in the live backend", "colo" in spec.lower())
path = next(e.split()[1] for e in got["endpoints"] if e.startswith("POST"))
schema = httpx.get(base + "/openapi.json", timeout=30).json()["components"]["schemas"]
body = next((s for n, s in schema.items() if "colo" in str(s).lower()), {})
print(body, flush=True)
added = httpx.post(base + path, json={"name": "Kofi", "kind": "dog", "colour": "brown", "color": "brown"}, timeout=30)
check("add a pet over public HTTPS", added.status_code < 300, added.text)

send(sid, "Also let me delete a pet.")
got = wait(sid, "live", "failed")
check("a change after going live", got["state"] == "live" and any(e.startswith("DELETE") for e in got["endpoints"]), got["endpoints"])
check("same link", got["url"] == base)
check("data kept after the change", "Kofi" in httpx.get(base + path, timeout=30).text)
undeploy(sid, delete_data=True)
print("session spent $", round(__import__("builder.session").session.SESSIONS[sid].cost, 3))

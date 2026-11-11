"""One real build through the live platform's public routes (the ones the page calls), then take it down."""
import json, time, httpx
U = "https://34-78-38-126.sslip.io"; c = httpx.Client(timeout=60); out = {"steps": []}; t0 = time.time()
def log(step, **kw): out["steps"].append({"t": round(time.time() - t0, 1), "step": step, **kw})
def wait(sid, states, limit=900):
    while time.time() - t0 < limit:
        g = c.get(f"{U}/api/builds/{sid}").json()
        if g["state"] in states: return g
        time.sleep(3)
    raise TimeoutError(g["state"])
sid = c.post(f"{U}/api/builds", json={"request": "A simple list of books I have read: title, author and a rating from 1 to 5. I want to add, list and delete books."}).json()["id"]
log("started", id=sid)
g = wait(sid, {"waiting_answers", "waiting_approval", "failed"}); log("state", state=g["state"], questions=g["questions"])
if g["state"] == "waiting_answers":
    c.post(f"{U}/api/builds/{sid}/messages", json={"message": ["No preference: you decide."] * len(g["questions"])})
    g = wait(sid, {"waiting_approval", "failed"}); log("state", state=g["state"])
log("approve", status=c.post(f"{U}/api/builds/{sid}/approve").status_code)
time.sleep(5)
r = c.post(f"{U}/api/builds/{sid}/take-down"); log("take_down_while_building", status=r.status_code, body=r.json())
g = wait(sid, {"live", "failed"}); log("state", state=g["state"], url=g["url"], error=g["error"])
url = g["url"]
if url:
    log("link_before", status=c.get(url + "/docs").status_code)
    r = c.post(f"{U}/api/builds/{sid}/take-down"); log("take_down", status=r.status_code, body=r.json())
    time.sleep(2); log("link_after", status=c.get(url + "/docs").status_code)
    g = c.get(f"{U}/api/builds/{sid}").json(); log("after", state=g["state"], url=g["url"], endpoints=g["endpoints"], error=g["error"])
    r = c.post(f"{U}/api/builds/{sid}/take-down"); log("take_down_again", status=r.status_code, body=r.json())
for b in ("beae21105e9", "church-demo"): log("other_backend", name=b, status=c.get(f"{U}/b/{b}/docs").status_code)
print(json.dumps(out, indent=1))

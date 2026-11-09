"""S4.7, free attacks on the live platform: deploy two hand-written attack backends, attack from inside them and from outside, watch the
platform, remove them. Runs on the server, as the platform user, from standard input; prints JSON (setting NAMES only, never values):

    gcloud compute ssh platform ... --command 'sudo -u platform -H bash -lc "cd ~/repo && ~/.local/bin/uv run python -"' < eval/experiments/safety_attacks.py
"""
import json, pathlib, shutil, statistics, subprocess, tempfile, threading, time
import httpx
from runtime.deploy import deploy, undeploy

U = "https://34-78-38-126.sslip.io"
APP = r'''
import os, pathlib, socket, subprocess, time
from fastapi import FastAPI
app = FastAPI()
def names(text): return sorted(x.split("=")[0] for x in text.split("\0") if "=" in x)
@app.get("/ping")
def ping(): return {"ok": True}
@app.get("/memory")
def memory():
    keep = []
    for i in range(150):
        keep.append(bytearray(os.urandom(1024)) * 10240)
    return {"survived_mb": len(keep) * 10}
@app.get("/tmp/{mb}")
def tmp(mb: int):
    try:
        with open("/tmp/big.bin", "wb") as f:
            for i in range(mb): f.write(os.urandom(1048576))
        return {"wrote_mb": mb}
    except OSError as e: return {"error": str(e)}
@app.get("/disk/{mb}")
def disk(mb: int):
    try:
        with open("/app/big.bin", "wb") as f:
            for i in range(mb): f.write(os.urandom(1048576))
        return {"wrote_mb": mb}
    except OSError as e: return {"error": str(e)}
@app.get("/disk_delete")
def disk_delete():
    pathlib.Path("/app/big.bin").unlink(missing_ok=True); return {"deleted": True}
@app.get("/fork")
def fork():
    procs, error = [], None
    try:
        for i in range(300): procs.append(subprocess.Popen(["sleep", "30"]))
    except OSError as e: error = str(e)
    n = len(procs)
    for p in procs: p.kill(); p.wait()
    return {"started": n, "error": error}
@app.get("/cpu")
def cpu():
    end = time.time() + 12
    while time.time() < end: pass
    return {"done": True}
@app.get("/probe")
def probe(other: str = ""):
    me = socket.gethostbyname(socket.gethostname()); gate = me.rsplit(".", 1)[0] + ".1"
    targets = {"internet 1.1.1.1:443": ("1.1.1.1", 443), "internet 8.8.8.8:53": ("8.8.8.8", 53), "google metadata 169.254.169.254:80": ("169.254.169.254", 80),
               "server ssh (gateway:22)": (gate, 22), "server web (gateway:80)": (gate, 80), "server web (gateway:443)": (gate, 443),
               "platform (gateway:8080)": (gate, 8080), "other backend by address": (other or "10.200.255.1", 8000), "other backend by name": ("d-s47b", 8000)}
    out = {"my_address": me}
    for label, (host, port) in targets.items():
        s = socket.socket(); s.settimeout(3)
        try:
            s.connect((host, port)); out[label] = "OPEN"
        except Exception as e:
            out[label] = type(e).__name__ + ": " + str(e)[:60]
        finally:
            s.close()
    try: out["dns example.com"] = socket.gethostbyname("example.com")
    except Exception as e: out["dns example.com"] = type(e).__name__
    return out
@app.get("/look")
def look():
    def tryit(f):
        try: return f()
        except Exception as e: return type(e).__name__
    return {"setting names": sorted(os.environ), "pid1 setting names": tryit(lambda: names(open("/proc/1/environ").read())),
            "user": os.getuid(), "platform key file": tryit(lambda: "READ" if open("/home/platform/.env").read() else "empty"),
            "docker socket": os.path.exists("/var/run/docker.sock"), "app folder": sorted(os.listdir("/app")),
            "write system files": tryit(lambda: open("/usr/x", "w") and "WROTE"), "root listing has home": os.path.exists("/home/platform")}
'''
res = {}
client = httpx.Client(timeout=120)
def plat():
    t = time.time(); r = client.get(U + "/"); return r.status_code, round(time.time() - t, 3)
def state(n):
    a = subprocess.run(["docker", "inspect", n, "--format", "{{.State.OOMKilled}} {{.RestartCount}} {{.State.ExitCode}} {{.State.Status}}"], capture_output=True, text=True).stdout.split()
    return dict(zip(("oom_killed", "restarts", "exit_code", "status"), a))
def free():
    return next(int(l.split()[6]) for l in subprocess.run(["free", "-m"], capture_output=True, text=True).stdout.splitlines() if l.startswith("Mem"))
def alive(B):
    for _ in range(60):
        try:
            if client.get(B + "/ping", timeout=3).status_code == 200: return True
        except httpx.HTTPError: pass
        time.sleep(1)
    return False
def call(B, path):
    t = time.time()
    try:
        r = client.get(B + path, timeout=90)
        return {"status": r.status_code, "seconds": round(time.time() - t, 1), "body": r.json() if "json" in r.headers.get("content-type", "") else r.text[:120]}
    except httpx.HTTPError as e:
        return {"status": None, "seconds": round(time.time() - t, 1), "body": type(e).__name__}

tmp = pathlib.Path(tempfile.mkdtemp()); (tmp / "app.py").write_text(APP)
try:
    for n in ("s47a", "s47b"):
        d = deploy(tmp, n); assert d["ok"], d
    A = U + "/b/s47a"
    other = subprocess.run(["docker", "inspect", "d-s47b", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"], capture_output=True, text=True).stdout.strip()
    res["start"] = {"platform": plat(), "server_free_mb": free(), "disk_free_gb": round(shutil.disk_usage("/").free / 2**30, 2)}
    assert alive(A)
    res["look_inside"] = call(A, "/look")
    res["probe"] = call(A, f"/probe?other={other}")
    before = shutil.disk_usage("/").free
    res["disk_1gb"] = {**call(A, "/disk/1024"), "disk_used_more_mb": round((before - shutil.disk_usage("/").free) / 2**20), "platform": plat()}
    res["disk_delete"] = call(A, "/disk_delete")
    res["tmp_1gb"] = {**call(A, "/tmp/1024"), "after": state("d-s47a"), "platform": plat()}; alive(A)
    low = [free()]; stop = threading.Event()
    th = threading.Thread(target=lambda: [(low.append(free()), time.sleep(.2)) for _ in iter(lambda: stop.is_set(), True)]); th.start()
    res["memory_1500mb"] = {**call(A, "/memory"), "platform": plat()}; stop.set(); th.join()
    time.sleep(1); res["memory_1500mb"].update(after=state("d-s47a"), server_lowest_free_mb=min(low)); res["memory_1500mb"]["came_back"] = alive(A); res["memory_1500mb"]["after_restart"] = state("d-s47a")
    res["fork_300"] = {**call(A, "/fork"), "platform": plat()}
    quiet = [plat()[1] for _ in range(15)]; th = threading.Thread(target=call, args=(A, "/cpu")); th.start(); time.sleep(1); busy = [plat()[1] for _ in range(15)]; th.join()
    res["cpu_12s"] = {"platform_median_seconds_before": statistics.median(quiet), "platform_median_seconds_during": statistics.median(busy)}
    # too many requests, from this server's own address; a made-up id, so no Claude call
    codes = [client.post(U + "/api/builds/nosuchbuild/messages", json={"message": "hi"}).status_code for _ in range(31)]
    res["too_many_messages"] = {"first_30": sorted(set(codes[:30])), "number_31": codes[30]}
    res["faked_address_after_limit"] = client.post(U + "/api/builds/nosuchbuild/messages", json={"message": "hi"}, headers={"X-Forwarded-For": "1.2.3.4"}).status_code
    res["empty_request_is_free"] = client.post(U + "/api/builds", json={"request": "   "}).status_code
    # huge upload to the platform
    pid = subprocess.run("pgrep -f 'uvicorn web.app:app' | tail -1", shell=True, capture_output=True, text=True).stdout.strip()
    rss = lambda: int(subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True).stdout.strip() or 0) // 1024
    peak = [rss()]; stop = threading.Event(); start_mb = peak[0]
    th = threading.Thread(target=lambda: [(peak.append(rss()), time.sleep(.05)) for _ in iter(lambda: stop.is_set(), True)]); th.start()
    body = b'{"request":"' + b"x" * (200 * 2**20) + b'"}'
    t = time.time(); r = client.post(U + "/api/builds", content=body, headers={"content-type": "application/json"}, timeout=180); stop.set(); th.join()
    res["upload_200mb"] = {"status": r.status_code, "seconds": round(time.time() - t, 1), "platform_memory_before_mb": start_mb, "platform_memory_peak_mb": max(peak), "platform": plat()}
    res["end"] = {"platform": plat(), "server_free_mb": free(), "disk_free_gb": round(shutil.disk_usage("/").free / 2**30, 2)}
finally:
    print(json.dumps(res, indent=1, default=str))
    for n in ("s47a", "s47b"):
        undeploy(n)

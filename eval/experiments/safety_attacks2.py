"""S4.7, second pass, on the server from standard input like safety_attacks.py: (1) where memory goes when a backend is killed, (2) the platform's
memory during a 200 MB upload, (3) two ways to stop a backend filling the disk, same attacks: a limit on each file (ulimit) and a watchdog."""
import json, pathlib, subprocess, tempfile, threading, time
import httpx
from runtime import sandbox
from runtime.deploy import DEPLOY_ROOT, deploy, undeploy

U = "https://34-78-38-126.sslip.io"
APP = r'''
import glob, os
from fastapi import FastAPI
app = FastAPI()
@app.get("/ping")
def ping(): return {"ok": True}
@app.get("/memory")
def memory():
    keep = []
    for i in range(150): keep.append(bytearray(os.urandom(1024)) * 10240)
    return {"survived_mb": len(keep) * 10}
@app.get("/tmp/{mb}")
def tmp(mb: int):
    with open("/tmp/big.bin", "wb") as f:
        for i in range(mb): f.write(os.urandom(1048576))
    return {"wrote_mb": mb}
@app.get("/one/{mb}")
def one(mb: int):
    n = 0
    try:
        with open("/app/big.bin", "wb") as f:
            for i in range(mb): f.write(os.urandom(1048576)); f.flush(); n += 1
    except OSError as e: return {"wrote_mb": n, "error": str(e)}
    return {"wrote_mb": n}
@app.get("/many/{files}/{mb}")
def many(files: int, mb: int):
    n = 0
    try:
        for k in range(files):
            with open(f"/app/part{k}.bin", "wb") as f:
                for i in range(mb): f.write(os.urandom(1048576)); f.flush(); n += 1
    except OSError as e: return {"wrote_mb": n, "error": str(e)}
    return {"wrote_mb": n}
@app.get("/clear")
def clear():
    for f in glob.glob("/app/*.bin"): os.remove(f)
    return {"cleared": True}
'''
client = httpx.Client(timeout=180)
res = {}
def mem():
    m = dict(l.split(":") for l in open("/proc/meminfo").read().splitlines())
    g = lambda k: int(m[k].split()[0]) // 1024
    return {"available": g("MemAvailable"), "cached": g("Cached"), "shmem": g("Shmem")}
def alive(B):
    for _ in range(60):
        try:
            if client.get(B + "/ping", timeout=3).status_code == 200: return True
        except httpx.HTTPError: pass
        time.sleep(1)
    return False
def watch(sample):
    out, stop = [sample()], threading.Event()
    t = threading.Thread(target=lambda: [(out.append(sample()), time.sleep(.1)) for _ in iter(stop.is_set, True)]); t.start()
    def done(): stop.set(); t.join(); return out
    return done
def get(B, p):
    t = time.time()
    try:
        r = client.get(B + p); return {"status": r.status_code, "seconds": round(time.time() - t, 1), "body": r.json() if "json" in r.headers.get("content-type", "") else ""}
    except httpx.HTTPError as e: return {"status": None, "seconds": round(time.time() - t, 1), "body": type(e).__name__}
def size(name): return sum(f.stat().st_size for f in (DEPLOY_ROOT / name).glob("*.bin")) // 2**20

tmp = pathlib.Path(tempfile.mkdtemp()); (tmp / "app.py").write_text(APP)
names = []
def up(n):
    d = deploy(tmp, n); assert d["ok"], d; names.append(n); assert alive(f"{U}/b/{n}"); return f"{U}/b/{n}"
try:
    A = up("s47c")
    res["memory_at_rest"] = mem()
    for label, path in (("memory_1500mb", "/memory"), ("tmp_1gb", "/tmp/1024")):
        d = watch(mem); r = get(A, path); s = d(); time.sleep(4); alive(A); time.sleep(3)
        res[label] = {**r, "lowest_available": min(x["available"] for x in s), "highest_shmem": max(x["shmem"] for x in s), "available_6s_after": mem()["available"]}
    # the platform's memory during a big upload; the python process running uvicorn, not the shell
    pid = subprocess.run(["pgrep", "-u", "platform", "-f", r"python.* .*uvicorn web\.app:app"], capture_output=True, text=True).stdout.split()
    pid = max(pid, key=lambda p: int(subprocess.run(["ps", "-o", "rss=", "-p", p], capture_output=True, text=True).stdout or 0))
    rss = lambda: int(subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True).stdout or 0) // 1024
    before = rss(); d = watch(rss)
    body = b'{"request":"' + b"x" * (200 * 2**20) + b'"}'
    t = time.time(); r = client.post(U + "/api/builds", content=body, headers={"content-type": "application/json"}); s = d(); del body
    res["upload_200mb"] = {"status": r.status_code, "seconds": round(time.time() - t, 1), "platform_mb_before": before, "platform_mb_peak": max(s)}
    time.sleep(3); res["upload_200mb"]["platform_mb_after"] = rss()
    # disk, option 1: a limit on the size of each file
    keep = list(sandbox.LIMITS); sandbox.LIMITS[:] = keep + ["--ulimit", f"fsize={200 * 2**20}"]
    F = up("s47d"); sandbox.LIMITS[:] = keep
    res["file_limit"] = {"one_1gb_file": {**get(F, "/one/1024")}, "on_disk_mb": size("s47d")}
    get(F, "/clear"); res["file_limit"]["five_150mb_files"] = get(F, "/many/5/150"); res["file_limit"]["on_disk_mb_after_many"] = size("s47d"); get(F, "/clear")
    # disk, option 2: a watchdog that looks every 5 seconds and stops a backend holding more than 500 MB
    W = up("s47e"); hit = {}
    def dog():
        t0 = time.time()
        while time.time() - t0 < 60 and not hit:
            time.sleep(5)
            if size("s47e") > 500:
                subprocess.run(["docker", "stop", "-t", "0", "d-s47e"], capture_output=True); hit.update(at_seconds=round(time.time() - t0, 1), mb_when_stopped=size("s47e"))
    th = threading.Thread(target=dog); th.start(); r = get(W, "/many/20/150"); th.join()
    res["watchdog"] = {"attack_reply": r, **hit, "final_mb": size("s47e")}
    subprocess.run(["docker", "start", "d-s47e"], capture_output=True); alive(W); res["watchdog"]["cleared"] = get(W, "/clear")["status"]
    res["end"] = mem()
finally:
    print(json.dumps(res, indent=1, default=str))
    for n in names: undeploy(n)

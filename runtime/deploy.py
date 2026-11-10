"""Hosting: keep a built backend running at a public address, with its data kept (Lecture 8, hosted publicly).

    from runtime.deploy import deploy, undeploy
    deploy("projects/web/church", "church-1")
    # {"ok": True, "url": "https://HOST/b/church-1", "docs_url": "https://HOST/b/church-1/docs",
    #  "endpoints": ["GET /events", "POST /events"], "output": "Deployed ..."}

Same locks as the sandbox: a private network with no internet, 512 MB, 1 CPU, read-only system files. Only app.py is copied,
to its own folder under DEPLOY_ROOT, because the agent's checker deletes databases in the build folder. Deploying the same
name again replaces the code and keeps the data. Docker restarts everything after a reboot. Caddy gives each backend its
path on one HTTPS address. Runs on the server only: it needs Docker and Caddy, and writes one file per backend to CADDY_DIR.
"""

import os
import re
import shutil
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path

import httpx

from runtime import sandbox
from runtime.tools import fail, free_port, ok, start_server, stop_server

HOST = os.environ.get("PUBLIC_HOST", "34-78-38-126.sslip.io")
DEPLOY_ROOT = Path(os.environ.get("DEPLOY_ROOT", "/srv/deployed"))
CADDY_DIR = Path(os.environ.get("CADDY_DIR", "/etc/caddy/backends"))
CADDYFILE = "/etc/caddy/Caddyfile"
MAX_BACKEND_MB = 500
NAME = re.compile(r"[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?")  # goes into docker names, paths and Caddy's file: nothing else allowed


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout


def remove(name):
    subprocess.run(["docker", "rm", "-f", f"d-{name}", f"d-{name}-door"], capture_output=True)
    subprocess.run(["docker", "network", "rm", f"d-{name}"], capture_output=True)


def route(name, port):
    """Tell Caddy about this backend. handle_path takes /b/NAME off before the backend sees the request."""
    (CADDY_DIR / f"{name}.caddy").write_text(f"redir /b/{name} /b/{name}/docs\n"
                                             f"handle_path /b/{name}/* {{\n\treverse_proxy 127.0.0.1:{port}\n}}\n")
    subprocess.run(["caddy", "reload", "--config", CADDYFILE], capture_output=True, text=True, check=True)


def deploy(folder, name, timeout=20):
    """Run folder/app.py publicly as /b/NAME. Returns ok, url, docs_url, endpoints; or ok False and why."""
    if not NAME.fullmatch(name):
        return fail(f"Bad name {name!r}: use lowercase letters, numbers and hyphens, at most 40")
    app = Path(folder) / "app.py"
    if not app.exists():
        return fail(f"No app.py in {folder}")
    home = DEPLOY_ROOT / name
    home.mkdir(parents=True, exist_ok=True)
    shutil.copy(app, home / "app.py")
    remove(name)
    port = free_port()
    try:
        docker("network", "create", "--internal", f"d-{name}")
        docker("run", "-d", "--restart", "unless-stopped", "--pull", "never", "--name", f"d-{name}", "--network", f"d-{name}",
               *sandbox.LIMITS, *sandbox.LOCKS, "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{home.resolve()}:/app", "-w", "/app",
               sandbox.IMAGE, "python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000",
               "--root-path", f"/b/{name}")  # so /docs finds its openapi.json under /b/NAME
        docker("run", "-d", "--restart", "unless-stopped", "--name", f"d-{name}-door", "-p", f"127.0.0.1:{port}:8000",
               "--memory", "64m", "--cap-drop", "ALL", sandbox.DOOR_IMAGE, "TCP-LISTEN:8000,fork,reuseaddr", f"TCP:d-{name}:8000")
        docker("network", "connect", f"d-{name}", f"d-{name}-door")
    except subprocess.CalledProcessError as e:
        remove(name)
        return fail(f"Could not start the backend: {e.stderr}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            spec = httpx.get(f"http://127.0.0.1:{port}/openapi.json", timeout=httpx.Timeout(5, connect=0.2)).json()
            break
        except (httpx.HTTPError, ValueError):
            time.sleep(0.2)
    else:
        log = subprocess.run(["docker", "logs", "--tail", "30", f"d-{name}"], capture_output=True, text=True)
        remove(name)
        return fail(f"The backend did not start:\n{log.stdout}{log.stderr}")
    try:
        route(name, port)
    except subprocess.CalledProcessError as e:
        remove(name)
        return fail(f"Could not publish the backend: {e.stderr}")
    url = f"https://{HOST}/b/{name}"
    endpoints = [f"{m.upper()} {p}" for p, ops in spec.get("paths", {}).items() for m in ops]
    return {"ok": True, "url": url, "docs_url": f"{url}/docs", "endpoints": endpoints, "output": f"Deployed at {url}"}


def stop_oversized():
    """Stop every live backend holding more than MAX_BACKEND_MB on disk, so one backend cannot fill the server (decision 0057). Its data stays."""
    stopped = []
    for home in DEPLOY_ROOT.glob("*"):
        if sum(f.stat().st_size for f in home.rglob("*") if f.is_file()) > MAX_BACKEND_MB * 2**20:
            subprocess.run(["docker", "stop", "-t", "0", f"d-{home.name}"], capture_output=True)
            stopped.append(home.name)
    return stopped


def tables(db):
    """{table name: rows} in a SQLite file; {} if it is not one. Goes by the file's first bytes, not its name."""
    if db.read_bytes()[:16] != b"SQLite format 3\0":
        return {}
    with closing(sqlite3.connect(db)) as c:  # "with connect" alone leaves it open, and Windows cannot delete an open file
        names = [n for n, in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {n: c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def add_a_row(db, table):
    """Put one made-up row in a table, filling only the columns that must have a value. A table that refuses it is left as it was."""
    with closing(sqlite3.connect(db)) as c, c:  # the second c saves the row; closing alone would lose it
        columns = c.execute(f'PRAGMA table_info("{table}")').fetchall()  # (id, name, type, not null, default, primary key)
        needed = [(name, kind.upper()) for _, name, kind, required, default, key in columns
                  if (required or key) and default is None and not (key and "INT" in kind.upper())]
        values = [1 if "INT" in kind or "BOOL" in kind else 1.0 if kind in ("FLOAT", "REAL", "NUMERIC") else
                  "2000-01-01 00:00:00" if "DATE" in kind or "TIME" in kind else "x" for _, kind in needed]
        names = ", ".join(f'"{name}"' for name, _ in needed)
        insert = f'INSERT INTO "{table}" ({names}) VALUES ({", ".join("?" * len(values))})' if needed else f'INSERT INTO "{table}" DEFAULT VALUES'
        try:
            c.execute(insert, values)
        except sqlite3.Error:
            pass


def keeps_database(folder):
    """Would this app keep its data on the server? Start a copy of it: a SQLite file with tables must appear. Add a row to every
    table and start it again: no table may lose a row. Reads no code, so it does not matter how the app does it. Cannot see an
    app that has a database but also keeps some data in memory: eval/results/database_check.json measures how far this goes."""
    home = Path(folder) / "db_check"
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True)
    shutil.copy(Path(folder) / "app.py", home / "app.py")
    try:
        started = start_server(home)
        if not started["ok"]:
            return fail(f"It would not start: {started['output'][-300:]}")
        stop_server(home)
        found = [f for f in home.rglob("*") if f.is_file() and tables(f)]
        if not found:
            return fail("Starting the app creates no SQLite file with tables, so its data would be lost at every restart.")
        for db in found:
            for table in tables(db):
                add_a_row(db, table)
        before = {db: tables(db) for db in found}
        started = start_server(home)
        if not started["ok"]:
            return fail(f"With data in its database, it would not start again: {started['output'][-300:]}")
        stop_server(home)
        lost = [t for db, rows in before.items() for t, n in rows.items() if not db.exists() or tables(db).get(t, 0) < n]
        if lost:
            return fail(f"Starting the app wipes its data: rows disappeared from {', '.join(lost)}.")
        return ok(f"Keeps its data in {', '.join(db.name for db in found)}.")
    finally:
        stop_server(home)
        shutil.rmtree(home, ignore_errors=True)


def undeploy(name, delete_data=False):
    """Stop the backend and take it off the address. Its data stays unless delete_data."""
    if not NAME.fullmatch(name):
        return fail(f"Bad name {name!r}")
    remove(name)
    (CADDY_DIR / f"{name}.caddy").unlink(missing_ok=True)
    subprocess.run(["caddy", "reload", "--config", CADDYFILE], capture_output=True)
    if delete_data:
        shutil.rmtree(DEPLOY_ROOT / name, ignore_errors=True)
    return {"ok": True, "output": f"Removed {name}"}

"""The agent's tools (W2).

Every tool takes `root` first: the project folder the agent is building in. The agent program
chooses `root`; the LLM never does. The other arguments are the ones the LLM chose.
Every tool returns a dict {"ok": True or False, "output": "text for the LLM to read"}.
"""

import atexit
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

# Names the agent may never read, write or list, anywhere in the project.
BLOCKED = {".env", ".git"}
# Folders full of generated clutter that list_files leaves out.
CLUTTER = {".venv", "__pycache__", ".pytest_cache"}
LIMIT = 4000  # most characters of output the LLM gets back from one tool call
MAX_WRITE = 200_000  # most characters one write_file may write (a big source file is about 20,000)


def ok(output):
    return {"ok": True, "output": cut(output)}


def fail(reason):
    return {"ok": False, "output": cut(reason)}


def cut(text, limit=LIMIT):
    """Shorten long output: keep the start and the end, say how much was removed in the middle."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [{len(text) - limit} characters cut] ...\n" + text[-half:]


def safe_path(root, path):
    """Turn the path the LLM asked for into a real path inside root, or raise ValueError.

    The idea: let the operating system work out where the path really ends up
    (following "..", shortcuts and links), then check that place is still inside root.
    """
    if not path or len(path) > 255 or "\0" in path or ":" in path:
        # Empty, too long, a hidden zero character, or a colon (drive letters like C:, Windows streams like .env::$DATA)
        raise ValueError(f"Refused: {path[:80]!r} is not a valid project path")
    root = Path(root).resolve()
    try:
        full = (root / path).resolve()  # an absolute path replaces root here, and is caught below
    except OSError:
        raise ValueError(f"Refused: {path[:80]!r}... is not a valid path")
    if full == root or not full.is_relative_to(root):
        raise ValueError(f"Refused: {path!r} is outside the project folder")
    # Windows ignores case and trailing dots or spaces, so ".ENV" and ".env." are both ".env".
    parts = {part.lower().rstrip(". ") for part in full.relative_to(root).parts}
    if parts & BLOCKED:
        raise ValueError(f"Refused: {path!r} is a protected file")
    return full


def write_file(root, path, content):
    """Create or replace a file in the project. Makes missing folders."""
    try:
        full = safe_path(root, path)
    except ValueError as e:
        return fail(str(e))
    if len(content) > MAX_WRITE:
        return fail(f"Refused: {len(content)} characters is more than the {MAX_WRITE} allowed in one file")
    if full.is_dir():
        return fail(f"Refused: {path} is a folder, not a file")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8", newline="")  # newline="": write exactly what was sent
    return ok(f"Wrote {len(content)} characters to {path}")


def read_file(root, path):
    """Return the text of a file in the project (cut if long)."""
    try:
        full = safe_path(root, path)
    except ValueError as e:
        return fail(str(e))
    if not full.is_file():
        return fail(f"No such file: {path}")
    try:
        return ok(full.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return fail(f"Refused: {path} is not a text file")


def edit_file(root, path, old, new):
    """Replace one exact piece of text in a file, so the LLM need not resend the whole file."""
    try:
        full = safe_path(root, path)
        text = full.read_text(encoding="utf-8")
    except ValueError as e:  # refused by safe_path (UnicodeDecodeError is a kind of ValueError too)
        return fail(str(e))
    except OSError:
        return fail(f"No such file: {path}")
    count = text.count(old) if old else 0
    if count != 1:
        return fail(f"Not changed: the text to replace was found {count} times in {path}; it must be found exactly once")
    return write_file(root, path, text.replace(old, new))


def list_files(root):
    """List every file in the project, one path per line, leaving out protected files and clutter."""
    root = Path(root).resolve()
    names = []
    for p in sorted(root.rglob("*")):
        parts = {part.lower() for part in p.relative_to(root).parts}
        inside = p.resolve().is_relative_to(root)  # a folder link pointing outside is not followed
        if p.is_file() and inside and not parts & (BLOCKED | CLUTTER):
            names.append(p.relative_to(root).as_posix())
    return ok("\n".join(names) or "(no files yet)")


def clean_env():
    """The few settings a program needs to start. Keys such as LLM_API_KEY are left out on purpose."""
    keep = ["PATH", "SYSTEMROOT", "TEMP", "TMP"]  # SYSTEMROOT: Windows Python cannot start without it
    return {k: os.environ[k] for k in keep if k in os.environ} | {"PYTHONUTF8": "1"}


def run_tests(root, path="tests", timeout=60):
    """Run pytest on the project's own tests and return what it printed."""
    try:
        safe_path(root, path)
    except ValueError as e:
        return fail(str(e))
    command = [sys.executable, "-m", "pytest", path, "-q", "--tb=short", "-p", "no:cacheprovider"]
    try:
        result = subprocess.run(command, cwd=root, env=clean_env(), capture_output=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return fail(f"Tests stopped: still running after {timeout} seconds (something may be stuck in a loop or waiting)")
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return ok(output)
    if result.returncode == 5:  # pytest's code for "collected no tests"
        return fail(f"No tests found in {path}")
    return fail(output)


# The servers this program has started: project folder -> (process, base URL, log file).
SERVERS = {}


def free_port():
    """Ask the operating system for a port number nobody is using right now."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))  # port 0 means "any free port"
        return s.getsockname()[1]


def start_server(root, timeout=20):
    """Start the project's app.py (uvicorn app:app) on a free port and wait until it answers."""
    root = str(Path(root).resolve())
    stop_server(root)  # at most one server per project
    port = free_port()
    log_path = Path(tempfile.mkdtemp()) / "server.log"
    command = [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)]
    with open(log_path, "w") as log:
        process = subprocess.Popen(command, cwd=root, env=clean_env(), stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:  # the process ended by itself: the app crashed
            return fail("Server crashed while starting:\n" + log_path.read_text(errors="replace"))
        try:
            # Any answer means it is up. Give up connecting after 0.1 s and try again (log row 8).
            httpx.get(url + "/openapi.json", timeout=httpx.Timeout(5, connect=0.1))
            SERVERS[root] = (process, url, log_path)
            return ok(f"Server running at {url}")
        except httpx.HTTPError:
            time.sleep(0.1)
    process.kill()
    return fail(f"Server did not answer within {timeout} seconds:\n" + log_path.read_text(errors="replace"))


def stop_server(root):
    """Stop the project's server, if one is running."""
    root = str(Path(root).resolve())
    if root not in SERVERS:
        return fail("No server is running for this project")
    process, url, _ = SERVERS.pop(root)
    process.kill()
    process.wait()
    return ok(f"Stopped the server at {url}")


# Servers must not keep running after the agent program ends.
atexit.register(lambda: [stop_server(root) for root in list(SERVERS)])


def http_request(root, method, path, json=None, timeout=10):
    """Send one HTTP request to the project's running server. Returns the status code, then the body."""
    root = str(Path(root).resolve())
    if root not in SERVERS:
        return fail("No server is running: call start_server first")
    process, url, log_path = SERVERS[root]
    if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return fail(f"Refused: unknown method {method!r}")
    if not path.startswith("/"):
        return fail(f"Refused: {path!r} must start with /, for example /events (only our own server can be called)")
    try:
        response = httpx.request(method.upper(), url + path, json=json, timeout=timeout)
    except httpx.TimeoutException:
        return fail(f"No answer within {timeout} seconds")
    except httpx.HTTPError as e:
        try:
            process.wait(timeout=1)  # did the server die? If so, show the LLM why
        except subprocess.TimeoutExpired:
            return fail(f"Request failed: {e}")
        SERVERS.pop(root)
        return fail("The server has stopped. Its log:\n" + log_path.read_text(errors="replace"))
    return ok(f"{response.status_code}\n{response.text}")

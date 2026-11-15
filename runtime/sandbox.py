"""The sandbox (W2): where code written by the LLM runs. Only run_tests and start_server use it (decision 0027).

Every run is a fresh Docker container made from the w2-sandbox image (runtime/sandbox/Dockerfile). It sees only the
project folder, has no internet, at most 512 MB of memory, 1 CPU and 128 processes, runs as an ordinary user, and
cannot change its own system files. Keys such as LLM_API_KEY never reach it: docker passes none of our settings in.
"""

import os
import subprocess
import sys
import uuid

IMAGE = "w2-sandbox"
DOOR_IMAGE = "alpine/socat:1.8.0.3"  # a tiny program that only forwards connections
MAX_FILE_MB = 200  # no single file bigger than this. Many smaller files are the watchdog's job: runtime.deploy.stop_oversized
LIMITS = ["--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "128", "--ulimit", f"fsize={MAX_FILE_MB * 2**20}"]
LOCKS = ["--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
if sys.platform == "linux" and os.getuid() > 0:  # Linux: run as the folder's owner, or the code cannot write its database
    LOCKS += ["--user", f"{os.getuid()}:{os.getgid()}"]


def new_name():
    return "w2-" + uuid.uuid4().hex[:8]


def command(root, args, name, network="none"):
    """The docker command that runs args (e.g. python -m pytest) on the project folder, in a fresh locked container."""
    return ["docker", "run", "--rm", "--pull", "never", "--name", name, "--network", network, *LIMITS, *LOCKS,
            "-e", "PYTHONUTF8=1", "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{root}:/app", "-w", "/app", IMAGE, *args]


def server(root, name, port, log):
    """Start uvicorn on the project. This computer reaches it at 127.0.0.1:port. Returns the running process.

    A container with no network cannot be reached from outside either. So the server gets a private network with no
    internet, and a second "door" container joins that network and forwards port `port` on this computer to it. The
    door only passes connections in; the server still cannot reach the internet.
    """
    run = lambda *a: subprocess.run(["docker", *a], capture_output=True, text=True, check=True)  # noqa: E731
    run("network", "create", "--internal", name)
    args = ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
    process = subprocess.Popen(command(root, args, name, network=name), stdout=log, stderr=subprocess.STDOUT)
    run("run", "-d", "--rm", "--name", name + "-door", "-p", f"127.0.0.1:{port}:8000", "--memory", "64m",
        "--cap-drop", "ALL", DOOR_IMAGE, "TCP-LISTEN:8000,fork,reuseaddr", f"TCP:{name}:8000")
    run("network", "connect", name, name + "-door")
    return process


def remove(name):
    """Force-stop the container, its door and its network. Ones that do not exist are skipped."""
    subprocess.run(["docker", "rm", "-f", name, name + "-door"], capture_output=True)
    subprocess.run(["docker", "network", "rm", name], capture_output=True)

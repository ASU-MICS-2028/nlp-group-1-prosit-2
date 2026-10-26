"""The sandbox (W2, S1.2): where code written by the LLM runs. Only run_tests and start_server use it.

Choose with the SANDBOX setting (an environment variable):
- SANDBOX=docker (the default): every run is a fresh Docker container made from the w2-sandbox image.
  It sees only the project folder, has no internet, at most 512 MB of memory, 1 CPU and 128 processes,
  runs as an ordinary user, and cannot change its own system files.
- SANDBOX=subprocess: a normal program on this computer with a time limit and the cleaned settings.
  Faster, but NOT isolated: it can read other files and use the internet. Only for machines without Docker.
"""

import os
import subprocess
import sys
import uuid

MODE = os.environ.get("SANDBOX", "docker")
IMAGE = "w2-sandbox"  # built from runtime/sandbox/Dockerfile
DOOR_IMAGE = "alpine/socat:1.8.0.3"  # a tiny program that only forwards connections
LIMITS = ["--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "128"]
LOCKS = ["--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]


def clean_env():
    """The few settings a program needs to start. Keys such as LLM_API_KEY are left out on purpose."""
    keep = ["PATH", "SYSTEMROOT", "TEMP", "TMP"]  # SYSTEMROOT: Windows Python cannot start without it
    return {k: os.environ[k] for k in keep if k in os.environ} | {"PYTHONUTF8": "1"}


def host_env():
    """Settings for the program we start on this computer.
    Docker: the docker command needs our normal settings, but passes none of them into the container."""
    return dict(os.environ) if MODE == "docker" else clean_env()


def new_name():
    return "w2-" + uuid.uuid4().hex[:8]


def command(root, args, name, network="none"):
    """The command that runs args (always starting with "python") on the project folder, in the sandbox."""
    if MODE == "subprocess":
        return [sys.executable, *args[1:]]
    return ["docker", "run", "--rm", "--pull", "never", "--name", name, "--network", network, *LIMITS, *LOCKS,
            "-e", "PYTHONUTF8=1", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{root}:/app", "-w", "/app", IMAGE, *args]


def server(root, name, port, log):
    """Start uvicorn on the project. This computer reaches it at 127.0.0.1:port. Returns the running process.

    Docker: a container with no network cannot be reached from outside either. So the server gets a private
    network with no internet, and a second "door" container joins that network and forwards port `port` on
    this computer to it. The door only passes connections in; the server still cannot reach the internet.
    """
    if MODE == "subprocess":
        args = ["python", "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)]
        return subprocess.Popen(command(root, args, name), cwd=root, env=clean_env(), stdout=log, stderr=subprocess.STDOUT)
    run = lambda *a: subprocess.run(["docker", *a], capture_output=True, text=True, check=True)
    run("network", "create", "--internal", name)
    args = ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
    process = subprocess.Popen(command(root, args, name, network=name), stdout=log, stderr=subprocess.STDOUT)
    run("run", "-d", "--rm", "--name", name + "-door", "-p", f"127.0.0.1:{port}:8000", "--memory", "64m",
        "--cap-drop", "ALL", DOOR_IMAGE, "TCP-LISTEN:8000,fork,reuseaddr", f"TCP:{name}:8000")
    run("network", "connect", name, name + "-door")
    return process


def remove(name):
    """Docker: force-stop the container, its door and its network. Ones that do not exist are skipped."""
    if MODE == "docker":
        subprocess.run(["docker", "rm", "-f", name, name + "-door"], capture_output=True)
        subprocess.run(["docker", "network", "rm", name], capture_output=True)

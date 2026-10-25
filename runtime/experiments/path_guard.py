"""Experiment: which path guard is safer? Run: uv run python runtime/experiments/path_guard.py

A = check the text of the path. B = resolve the real path, then check it is inside (runtime/tools.py).
Both get the same 24 paths. We count attacks wrongly allowed and good paths wrongly refused.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runtime.tools import safe_path  # noqa: E402  (version B)


def text_check(root, path):
    """Version A: refuse anything whose text looks dangerous."""
    if not path or ".." in path or path.startswith(("/", "\\")) or ":" in path:
        raise ValueError("refused")
    if ".env" in path or ".git" in path:
        raise ValueError("refused")
    return Path(root) / path


# (path the LLM asks for, should it be allowed?)
CASES = [
    ("app.py", True),
    ("tests/test_app.py", True),
    ("tests\\test_app.py", True),
    ("my..notes.txt", True),
    ("envelope/.environment.txt", True),
    ("new_folder/models.py", True),
    ("../secret.txt", False),
    ("..\\secret.txt", False),
    ("tests/../../secret.txt", False),
    ("C:\\Windows\\win.ini", False),
    ("C:secret.txt", False),
    ("/etc/passwd", False),
    ("\\\\server\\share\\x", False),
    ("", False),
    (".", False),
    ("x" * 5000, False),
    ("app.py\0.txt", False),
    ("link/secret.txt", False),  # link = a folder link that points outside the project
    (".env", False),
    (".ENV", False),
    (".env.", False),
    (".env::$DATA", False),
    ("sub/.env", False),
    (".git/config", False),
]


def make_project():
    base = Path(tempfile.mkdtemp())
    project, outside = base / "project", base / "outside"
    (project / "tests").mkdir(parents=True)
    (project / "envelope").mkdir()
    (project / ".git").mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET")
    for name in ["app.py", "tests/test_app.py", "my..notes.txt", "envelope/.environment.txt", ".env", ".git/config"]:
        (project / name).write_text("x")
    # A folder link (Windows "junction" needs no admin rights; elsewhere a symlink).
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(project / "link"), str(outside)], capture_output=True)
    else:
        os.symlink(outside, project / "link")
    return project


def run(guard, project):
    wrongly_allowed, wrongly_refused, rows = [], [], []
    for path, should_allow in CASES:
        try:
            guard(project, path)
            allowed = True
        except ValueError:
            allowed = False
        if allowed and not should_allow:
            wrongly_allowed.append(path[:30])
        if should_allow and not allowed:
            wrongly_refused.append(path[:30])
        rows.append((path[:30].replace("\0", "\\0"), should_allow, allowed))
    return wrongly_allowed, wrongly_refused, rows


if __name__ == "__main__":
    project = make_project()
    print("link exists:", (project / "link" / "secret.txt").exists())
    results = {"A text check": run(text_check, project), "B resolve then compare": run(safe_path, project)}
    print(f"\n{'path':32} {'should':7} {'A':6} {'B':6}")
    for (path, should, a), (_, _, b) in zip(results["A text check"][2], results["B resolve then compare"][2]):
        show = lambda x: "allow" if x else "refuse"
        print(f"{path!r:32} {show(should):7} {show(a):6} {show(b):6}")
    for name, (bad_allow, bad_refuse, _) in results.items():
        print(f"\n{name}: {len(bad_allow)} attacks wrongly allowed {bad_allow}, "
              f"{len(bad_refuse)} good paths wrongly refused {bad_refuse}")

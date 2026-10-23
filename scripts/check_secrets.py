"""Block secrets and big files from being committed. The repo is public.

    python3 scripts/check_secrets.py --staged   # check what is about to be committed (pre-commit hook)
    python3 scripts/check_secrets.py --all      # check every tracked file (GitHub check)
"""

import re
import subprocess
import sys

KEY = re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|hf_[A-Za-z0-9]{30,}")
BAD_PATH = re.compile(r"(^|/)\.env$|\.gguf$|\.safetensors$|(^|/)models/")
MAX_MB = 5


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main():
    staged = "--staged" in sys.argv
    files = git("diff", "--cached", "--name-only", "--diff-filter=ACM") if staged else git("ls-files")
    problems = []
    for path in filter(None, files.splitlines()):
        if BAD_PATH.search(path):
            problems.append(f"{path}: this file must never be committed (secrets or a model file)")
            continue
        blob = git("show", f":{path}") if staged else open(path, errors="ignore").read()
        if len(blob.encode()) > MAX_MB * 1024 * 1024:
            problems.append(f"{path}: larger than {MAX_MB} MB; big files go on the Drive, not in git")
        for n, line in enumerate(blob.splitlines(), 1):
            if KEY.search(line):
                problems.append(f"{path}:{n}: looks like an API key or private key")
    if problems:
        sys.exit("Blocked, the repo is public:\n  " + "\n  ".join(problems) + "\nRemove these from the commit (git restore --staged <file>) and try again.")


if __name__ == "__main__":
    main()

"""The agent's tools (W2).

Every tool takes `root` first: the project folder the agent is building in. The agent program
chooses `root`; the LLM never does. The other arguments are the ones the LLM chose.
Every tool returns a dict {"ok": True or False, "output": "text for the LLM to read"}.
"""

from pathlib import Path

# Names the agent may never read, write or list, anywhere in the project.
BLOCKED = {".env", ".git"}


def ok(output):
    return {"ok": True, "output": output}


def fail(reason):
    return {"ok": False, "output": reason}


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

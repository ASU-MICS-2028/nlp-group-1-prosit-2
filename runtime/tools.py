"""The agent's tools (W2).

Every tool takes `root` first: the project folder the agent is building in. The agent program
chooses `root`; the LLM never does. The other arguments are the ones the LLM chose.
Every tool returns a dict {"ok": True or False, "output": "text for the LLM to read"}.
"""

from pathlib import Path

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

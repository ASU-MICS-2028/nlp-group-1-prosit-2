"""Experiment: how should the file tools present files? Run: uv run python runtime/experiments/file_tools.py

1. list_files: a flat list of paths vs an indented tree. Measure: characters.
2. Changing a file: write_file (resend the whole file) vs edit_file (send only the old and new piece).
   Measure: characters the LLM must write. Output tokens cost $20 per million on Opus 5.5.
3. Do real files fit in the 4,000-character output limit? If yes, read_file needs no line ranges.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "benchmark/church_signup/reference/app.py").read_text()

# A typical generated project (the layout a FastAPI + SQLModel backend usually has).
PROJECT = ["app.py", "database.py", "models.py", "ops.json", "requirements.txt", "README.md",
           "routers/__init__.py", "routers/events.py", "routers/signups.py",
           "tests/conftest.py", "tests/test_events.py", "tests/test_signups.py"]


def flat(paths):
    return "\n".join(paths)


def tree(paths):
    lines, seen = [], set()
    for p in paths:
        *folders, name = p.split("/")
        for depth, folder in enumerate(folders):
            if tuple(folders[: depth + 1]) not in seen:
                seen.add(tuple(folders[: depth + 1]))
                lines.append("  " * depth + folder + "/")
        lines.append("  " * len(folders) + name)
    return "\n".join(lines)


# Three small changes an agent typically makes after a failing test: (old piece, new piece).
EDITS = [
    ('raise HTTPException(409, "This event is full")', 'raise HTTPException(400, "This event is full")'),
    ("    max_people: int\n", "    max_people: int\n    location: str = \"\"\n"),
    ("def list_events():\n    return list(events.values())",
     "def list_events():\n    return sorted(events.values(), key=lambda e: e[\"date\"])"),
]

if __name__ == "__main__":
    print("1. list_files format (characters)")
    for name, paths in [("church reference (2 files)", ["app.py", "ops.json"]), ("typical project (12 files)", PROJECT)]:
        print(f"   {name}: flat {len(flat(paths))}, tree {len(tree(paths))}")
    print("\n   tree looks like:\n" + tree(PROJECT))

    print("\n2. characters the LLM writes for one change (tokens ~ characters / 4)")
    total_write = total_edit = 0
    for old, new in EDITS:
        assert APP.count(old) == 1
        whole, piece = len(APP.replace(old, new)), len(old) + len(new)
        total_write, total_edit = total_write + whole, total_edit + piece
        print(f"   write_file {whole:5}  edit_file {piece:4}  ({whole / piece:.0f}x fewer with edit)")
    for name, chars in [("write_file", total_write), ("edit_file", total_edit)]:
        print(f"   3 edits with {name}: {chars} characters, about {chars // 4} tokens, ${chars / 4 * 20 / 1e6:.4f}")

    print("\n3. file sizes vs the 4,000 limit")
    for p in sorted((ROOT / "benchmark").rglob("*.py")):
        print(f"   {p.relative_to(ROOT).as_posix()}: {len(p.read_text())} characters")

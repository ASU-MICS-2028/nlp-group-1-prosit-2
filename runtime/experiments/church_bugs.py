"""Seven realistic bugs planted in the church reference app, to get real failing test output.

make_broken(bug, folder) builds a project folder: the reference app.py with one bug, plus the
agent-style tests in church_tests/. Used by the output-limit and error-format experiments.
"""

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parents[1] / "benchmark" / "church_signup" / "reference" / "app.py"

# bug name: (text in the correct app.py, the broken text that replaces it)
BUGS = {
    "wrong_status": ('@app.post("/church-events", status_code=201)', '@app.post("/church-events")'),
    "off_by_one": ('>= event["max_people"]', '> event["max_people"]'),
    "syntax_error": ("def list_events():", "def list_events()"),
    "import_typo": ("from pydantic import BaseModel", "from pydantic import BaseModle"),
    "wrong_path": ('@app.get("/church-events/{event_id}")', '@app.get("/church-event/{event_id}")'),
    "renamed_field": ("    max_people: int", "    capacity: int"),
    # off_by_one plus a debug print of ~75,000 characters, which pytest shows for the failing test
    "noisy_debug": ('    event = find(event_id)\n    if len(signups[event_id]) >= event["max_people"]',
                    "    event = find(event_id)\n    print('debug: checking capacity ' * 3000)\n"
                    '    if len(signups[event_id]) > event["max_people"]'),
}


def make_broken(bug, folder):
    folder = Path(folder)
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(HERE / "church_tests", folder / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    good, bad = BUGS[bug] if bug else ("", "")
    text = REFERENCE.read_text()
    assert not bug or text.count(good) == 1, bug
    (folder / "app.py").write_text(text.replace(good, bad) if bug else text)
    return folder

"""Rewrite the README's Status section from docs/PLAN.md.

    python3 scripts/update_status.py           # update README.md
    python3 scripts/update_status.py --check   # exit 1 if README.md is out of date (used by CI)

A task is "ready" when every task in its Needs column is done, and "waiting" otherwise.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN, README = ROOT / "docs" / "PLAN.md", ROOT / "README.md"
START, END = "<!-- STATUS:START -->", "<!-- STATUS:END -->"


def rows(text):
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and not set(cells[0]) <= set("-: "):
            yield cells


def render(plan):
    owners = {c[0]: c[2] for c in rows(plan) if len(c) == 3 and c[0].startswith("W")}
    tasks = [c for c in rows(plan) if len(c) == 7 and c[0].startswith("P")]
    status = {t[0]: t[4] for t in tasks}
    who = lambda w: "Everyone" if w == "All" else f"{w} ({owners.get(w, 'TBD')})"
    needs = lambda t: [n.strip() for n in t[3].split(",") if n.strip() not in ("", "—")]

    doing = [t for t in tasks if t[4] == "doing"]
    todo = [t for t in tasks if t[4] == "todo"]
    ready = [t for t in todo if all(status.get(n) == "done" for n in needs(t))]
    waiting = [t for t in todo if t not in ready]
    done = sum(s == "done" for s in status.values())

    out = [START, "## Status", "",
           f"Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand. "
           f"**{done} of {len(tasks)} tasks done.**", ""]
    for title, items, extra in [("In progress", doing, False), ("Ready to start", ready, False),
                                ("Waiting on other tasks", waiting, True)]:
        out += [f"**{title}**", ""]
        if not items:
            out += ["None.", ""]
            continue
        out += ["| Task | Who | Target |" + (" Waiting on |" if extra else ""),
                "|---|---|---|" + ("---|" if extra else "")]
        for t in items:
            blockers = ", ".join(n for n in needs(t) if status.get(n) != "done")
            out.append(f"| {t[0]} {t[1]} | {who(t[2])} | {t[5]} |" + (f" {blockers} |" if extra else ""))
        out.append("")
    return "\n".join(out + [END])


def main():
    readme = README.read_text()
    if START not in readme or END not in readme:
        sys.exit(f"README.md needs {START} and {END} markers")
    head, rest = readme.split(START, 1)
    new = head + render(PLAN.read_text()) + rest.split(END, 1)[1]
    if "--check" in sys.argv:
        if new != readme:
            sys.exit("README.md Status is out of date: run python3 scripts/update_status.py")
        return
    README.write_text(new)


if __name__ == "__main__":
    main()

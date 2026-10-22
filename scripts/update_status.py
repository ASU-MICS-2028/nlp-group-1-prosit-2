"""Regenerate the plan views from the stage tables in docs/PLAN.md.

    python3 scripts/update_status.py           # rewrite the generated blocks
    python3 scripts/update_status.py --check   # exit 1 if any block is out of date (used by CI)

Only the stage tables and the "By person" owner table in docs/PLAN.md are edited by hand. This script
writes, between <!-- NAME:START --> / <!-- NAME:END --> markers:
  PLAN.md   BOARD     a grid of stages (columns) by person (rows)
  PLAN.md   FLOW      a Mermaid diagram of every task, its dependencies and its status
  PLAN.md   PEOPLE    each workstream's tasks in order
  PLAN.md   BLOCKERS  every task that waits on another person's task
  README.md STATUS    what is in progress, ready and waiting, per person
  docs/decisions/README.md DECISIONS  the index of decision records (one numbered file each)

A task is "ready" when everything in its Needs column is done, and "waiting" otherwise.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN, README = ROOT / "docs" / "PLAN.md", ROOT / "README.md"
DECISIONS = ROOT / "docs" / "decisions"
BLOCK = re.compile(r"(<!-- (\w+):START -->)(.*?)(<!-- \2:END -->)", re.S)
WHO = ["W1", "W2", "W3", "W4", "W5", "All"]


def parse(plan):
    plan = BLOCK.sub(r"\1\4", plan)  # never parse our own output
    stages, tasks, owners, stage = [], [], {}, None
    for line in plan.splitlines():
        if m := re.match(r"## (Stage \d+): (.*)", line):
            stage = (m[1], m[2])
            stages.append(stage)
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if re.fullmatch(r"S\d+\.\d+", c[0]) and len(c) == 7:
            tasks.append(dict(id=c[0], name=c[1], who=c[2], priority=c[4], status=c[5], stage=stage,
                              needs=[n.strip() for n in c[3].split(",") if n.strip() not in ("", "—")]))
        elif re.fullmatch(r"W\d", c[0]):
            owners[c[0]] = c[-1]
    return stages, tasks, owners


def state(t, by_id):
    if t["status"] in ("done", "doing"):
        return t["status"]
    return "ready" if all(by_id[n]["status"] == "done" for n in t["needs"]) else "waiting"


def render(plan):
    stages, tasks, owners = parse(plan)
    by_id = {t["id"]: t for t in tasks}
    bad = [f"{t['id']} needs unknown {n}" for t in tasks for n in t["needs"] if n not in by_id]
    bad += [f"{t['id']} has unknown owner {t['who']}" for t in tasks if t["who"] not in WHO]
    bad += [f"{t['id']} has unknown status {t['status']}" for t in tasks if t["status"] not in ("todo", "doing", "done")]
    if bad:
        sys.exit("docs/PLAN.md: " + "; ".join(bad))
    person = lambda w: "Everyone" if w == "All" else (f"{owners[w]} ({w})" if owners.get(w, "TBD") != "TBD" else f"{w} (no owner yet)")
    label = lambda t: f"{t['id']} {t['name']}".replace('"', "'").replace("`", "")
    blockers = lambda t: [n for n in t["needs"] if by_id[n]["status"] != "done"]

    flow = ["```mermaid", "flowchart LR"]
    for s in stages:
        flow.append(f'  subgraph {s[0].replace(" ", "")}["{s[0]}: {s[1]}"]')
        flow += [f'    {t["id"].replace(".", "_")}["{label(t)}<br/>{t["who"]} · {t["priority"]}"]:::{state(t, by_id)}'
                 for t in tasks if t["stage"] == s]
        flow.append("  end")
    def upstream(i, seen=None):  # every task that i depends on, directly or indirectly
        seen = set() if seen is None else seen
        for n in by_id[i]["needs"]:
            if n not in seen:
                seen.add(n)
                upstream(n, seen)
        return seen
    # draw only direct arrows: skip a need already implied through another need (keeps the diagram readable)
    flow += [f'  {n.replace(".", "_")} --> {t["id"].replace(".", "_")}' for t in tasks for n in t["needs"]
             if not any(n in upstream(m) for m in t["needs"] if m != n)]
    flow += ["  classDef done fill:#d3f9d8,stroke:#2b8a3e", "  classDef doing fill:#fff3bf,stroke:#e67700",
             "  classDef ready fill:#d0ebff,stroke:#1971c2", "  classDef waiting fill:#f1f3f5,stroke:#868e96", "```",
             "", "Green: done · yellow: in progress · blue: ready to start · grey: waiting on the tasks with arrows into it."]

    icon = {"done": "✅", "doing": "🟡", "ready": "🔵", "waiting": "⏳"}
    board = ["| Who | " + " | ".join(f"{s[0]}<br>{s[1]}" for s in stages) + " |", "|---|" + "---|" * len(stages)]
    for w in WHO:
        board.append(f"| {person(w)} | " + " | ".join("<br>".join(
            f"{icon[state(t, by_id)]} {t['id']} {t['name']}" for t in tasks if t["who"] == w and t["stage"] == s) or "—"
            for s in stages) + " |")
    board += ["", "✅ done · 🟡 in progress · 🔵 ready to start · ⏳ waiting on another task"]

    people = []
    for w in WHO:
        mine = [t for t in tasks if t["who"] == w]
        people += [f"**{person(w)}**", ""]
        people += [f"{i}. {t['id']} {t['name']} — {t['priority']}, {state(t, by_id)}"
                   + (f" (waiting on {', '.join(blockers(t))})" if state(t, by_id) == "waiting" else "")
                   for i, t in enumerate(mine, 1)]
        people.append("")

    waits = [f"- {t['id']} {t['name']} ({person(t['who'])}) waits on {n} {by_id[n]['name']} ({person(by_id[n]['who'])})"
             for t in tasks for n in blockers(t) if by_id[n]["who"] != t["who"] and t["status"] != "done"]
    waits = waits or ["- Nothing: no task is waiting on someone else's work."]

    done = sum(t["status"] == "done" for t in tasks)
    current = next((s for s in stages if any(t["stage"] == s and t["status"] != "done" for t in tasks)), None)
    status = ["## Status", "",
              f"Generated from [`docs/PLAN.md`](docs/PLAN.md) by `scripts/update_status.py`. Do not edit by hand. "
              f"**{done} of {len(tasks)} tasks done.**"
              + (f" Current stage: **{current[0]}: {current[1]}**." if current else ""), "",
              "| Who | In progress | Ready to start | Waiting (and on what) |", "|---|---|---|---|"]
    cell = lambda ts, extra=False: "<br>".join(
        f"{t['id']} {t['name']}" + (f" ← {', '.join(blockers(t))}" if extra else "") for t in ts) or "—"
    for w in WHO:
        mine = [t for t in tasks if t["who"] == w]
        status.append(f"| {person(w)} | {cell([t for t in mine if state(t, by_id) == 'doing'])} | "
                      f"{cell([t for t in mine if state(t, by_id) == 'ready'])} | "
                      f"{cell([t for t in mine if state(t, by_id) == 'waiting'], True)} |")
    status += ["", "The flow diagram, each person's full task list and who waits on whom are in [`docs/PLAN.md`](docs/PLAN.md)."]
    return {"BOARD": board, "FLOW": flow, "PEOPLE": people, "BLOCKERS": waits, "STATUS": status}


def decisions():
    rows, seen = [], {}
    for f in sorted(DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md")):
        n = f.name[:4]
        if n == "0000":
            continue  # the template
        if n in seen:
            sys.exit(f"docs/decisions: number {n} used twice ({seen[n]}, {f.name})")
        seen[n] = f.name
        text = f.read_text()
        title = re.search(r"^# \d{4}\. (.+)$", text, re.M)
        status = re.search(r"^- Status: (.+)$", text, re.M)
        date = re.search(r"^- Date: (.+)$", text, re.M)
        if not (title and status and date):
            sys.exit(f"docs/decisions/{f.name}: needs a '# NNNN. Title' line, '- Status:' and '- Date:'")
        rows.append(f"| [{n}]({f.name}) | {title[1]} | {status[1]} | {date[1]} |")
    return ["| # | Decision | Status | Date |", "|---|---|---|---|"] + rows


def fill(text, blocks):
    return BLOCK.sub(lambda m: m[1] + ("\n" + "\n".join(blocks[m[2]]).strip() + "\n" if m[2] in blocks else m[3]) + m[4], text)


def main():
    blocks = render(PLAN.read_text()) | {"DECISIONS": decisions()}
    stale = []
    for path in (PLAN, README, DECISIONS / "README.md"):
        old = path.read_text()
        new = fill(old, blocks)
        if new != old:
            stale.append(path.name)
            if "--check" not in sys.argv:
                path.write_text(new)
    if "--check" in sys.argv and stale:
        sys.exit(f"Out of date: {', '.join(stale)}. Run python3 scripts/update_status.py")


if __name__ == "__main__":
    main()

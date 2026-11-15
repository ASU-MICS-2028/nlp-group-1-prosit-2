"""Build benchmark tasks from the command line, the way the report's numbers were made.

    uv run --env-file .env --with anthropic python -m builder build church_signup [more tasks | all] [--ask 3] [--run NAME]
    uv run --env-file .env --with anthropic python -m builder change church_signup --what "add a phone number" [--run NAME]

--ask N first asks the client up to N questions. You type the answers, or --client answers lets a pretend client
answer them (builder/client.py). The answers are saved in questions.json and added to the request; later builds
and changes in the same folder reuse them. --search gives the agent Joseph's recipe search.

Reads ONLY benchmark/<task>/request.md (decision 0033) and builds in projects/<run>/<task>/, the layout the harness
scores: uv run --env-file .env --with anthropic python -m eval.harness all projects/<run> --repeat 3
"""

import argparse
import json
from pathlib import Path

import anthropic

from builder import client
from builder.agent import build, clarify, with_answers
from eval import bench

p = argparse.ArgumentParser()
p.add_argument("command", choices=["build", "change"])
p.add_argument("tasks", nargs="+")
p.add_argument("--model", default="claude-opus-5-5")
p.add_argument("--ask", type=int, default=0, help="build: ask the client up to N questions first")
p.add_argument("--client", default="person", choices=["person", "answers"], help="who answers: you, or the prepared answers")
p.add_argument("--search", action="store_true", help="give the agent Joseph's recipe search")
p.add_argument("--what", default="", help="change: the change the client wants, in their words")
p.add_argument("--run", default="cli")
a = p.parse_args()

for task in bench.task_names() if a.tasks == ["all"] else a.tasks:
    request = (bench.BENCH / task / "request.md").read_text().strip()
    root = Path("projects") / a.run / task
    saved = root / "questions.json"
    try:
        if a.ask and a.command == "build":
            questions, usd = clarify(request, a.ask, a.model)
            if a.client == "person":
                answers = [input(f"\n{q}\n> ").strip() or client.NONE for q in questions]
            else:
                answers, more = client.answer(task, questions)
                usd += more
            root.mkdir(parents=True, exist_ok=True)
            saved.write_text(json.dumps({"questions": questions, "answers": answers, "cost_usd": round(usd, 5)}, indent=2) + "\n")
        if saved.exists():
            q = json.loads(saved.read_text())
            request = with_answers(request, q["questions"], q["answers"])
    except (ValueError, KeyError, anthropic.AnthropicError) as e:
        print(f"{task:24} not built: {type(e).__name__}: {e}"[:300])
        continue
    r = build(request, root, a.model, search=a.search, change=a.what if a.command == "change" else None)
    tests = f"own tests {r['tests']['passed']} passed {r['tests']['failed']} failed" if r["tests"] else "own tests not run"
    print(f"{task:24} {r['stop']:9} {r['turns']:>2} turns {len(r['tool_calls']):>2} tools ${r['cost_usd']} {r['seconds']}s  {tests}", flush=True)

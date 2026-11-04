"""Plan and build backends from the command line.

    uv run --env-file .env --with anthropic python -m builder plan church_signup [more tasks | all] [--yes] [--run NAME]
    uv run --env-file .env --with anthropic python -m builder build church_signup [more tasks | all] [--plan] [--run NAME]

plan (S3.5) shows the plan and asks: y approves it (saved as plan.json), n stops, any other text is a change to make.
--yes approves without asking (for experiments). build --plan follows plan.json and refuses to build without one.
change --what "..." (S3.10) edits the app already in the folder.
--search (S3.7) adds Joseph's recipe search as a tool. --model qwen3.5-9b-local (S3.9) runs on llama.cpp.
--ask N (S3.8, plan or build) first asks the client up to N questions; --client person (you type, default), answers or
brief (pretend clients for benchmark tasks, builder/client.py). The answers are saved in questions.json and added to
the request; build --plan adds the answers saved when the plan was made.

Reads ONLY benchmark/<task>/request.md (decision 0033) and builds in projects/<run>/<task>/, the layout the
harness scores: uv run --env-file .env --with anthropic python -m eval.harness all projects/<run> --repeat 3
Each build leaves run.json (the totals) and trace.jsonl (every step) next to app.py.
"""

import argparse
import json
from pathlib import Path

import anthropic

from builder import client
from builder.agent import build, clarify, load_plan, make_plan, plan_text, with_answers
from eval import bench

p = argparse.ArgumentParser()
p.add_argument("command", choices=["plan", "build", "change"])
p.add_argument("tasks", nargs="+")
p.add_argument("--model", default="claude-opus-5-5")
p.add_argument("--effort", default="medium")
p.add_argument("--prompt", default="B", choices=["A", "B", "C", "D"])
p.add_argument("--repairs", type=int, default=0, help="most repair rounds after the independent check")
p.add_argument("--yes", action="store_true", help="plan: approve without asking")
p.add_argument("--planner", default="2", choices=["1", "2"], help="plan: v2 (default, decision 0041) or v1 (S3.5 row 4)")
p.add_argument("--plan", action="store_true", help="build: follow the approved plan.json")
p.add_argument("--ask", type=int, default=0, help="ask the client up to N questions first")
p.add_argument("--client", default="person", choices=["person", "answers", "brief"], help="who answers --ask questions")
p.add_argument("--search", action="store_true", help="build: give the agent Joseph's recipe search (S3.7)")
p.add_argument("--what", default="", help="change: the change the client wants, in their words")
p.add_argument("--max-turns", type=int, default=40, help="build: most replies before stopping")
p.add_argument("--run", default="agent_v1")
a = p.parse_args()


def clarified(task, request, root):
    """S3.8: the request plus the client's answers to up to --ask questions, also saved in questions.json."""
    questions, usd = clarify(request, a.ask, a.model)
    if a.client == "person":
        answers = [input(f"\n{q}\n> ").strip() or client.NONE for q in questions]
    else:
        answers, more = client.answer(task, questions, a.client)
        usd += more
    root.mkdir(parents=True, exist_ok=True)
    saved = {"questions": questions, "answers": answers, "client": a.client, "cost_usd": round(usd, 5)}
    (root / "questions.json").write_text(json.dumps(saved, indent=2) + "\n")
    return with_answers(request, questions, answers)


for task in bench.task_names() if a.tasks == ["all"] else a.tasks:
    request = (bench.BENCH / task / "request.md").read_text().strip()
    root = Path("projects") / a.run / task
    if a.command == "plan":
        try:
            request = clarified(task, request, root) if a.ask else request
            plan, usd = make_plan(request, a.model, planner=a.planner)
            while not a.yes:
                print(f"\n{task}\n\n{plan_text(plan)}\n")
                answer = input("Approve? y = yes, n = stop, or type the changes you want: ").strip()
                if answer.lower() in ("y", "n", ""):
                    plan = plan if answer.lower() == "y" else None
                    break
                plan, more = make_plan(request, a.model, plan, answer, a.planner)
                usd += more
        except (ValueError, RuntimeError, anthropic.AnthropicError) as e:  # empty request, budget, network, key
            print(f"{task:24} error: {type(e).__name__}: {e}"[:300])
            continue
        if plan:
            root.mkdir(parents=True, exist_ok=True)
            (root / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        else:
            (root / "plan.json").unlink(missing_ok=True)  # an older approval must not be built by mistake
        print(f"{task:24} {'approved' if plan else 'not approved'} ${round(usd, 4)}", flush=True)
        continue
    try:
        plan = load_plan(root) if a.plan else None
    except ValueError as e:
        print(f"{task:24} not built: {e}")
        continue
    try:
        if a.ask:
            request = clarified(task, request, root)
        elif (plan or a.command == "change") and (root / "questions.json").exists():  # the answers it was made with
            q = json.loads((root / "questions.json").read_text())
            request = with_answers(request, q["questions"], q["answers"])
    except (ValueError, KeyError, RuntimeError, anthropic.AnthropicError) as e:
        print(f"{task:24} not built: {type(e).__name__}: {e}"[:300])
        continue
    r = build(request, root, a.model, a.effort, a.prompt, a.max_turns, max_repairs=a.repairs, plan=plan, search=a.search,
              change=a.what if a.command == "change" else None)
    tests = f"own tests {r['tests']['passed']} passed {r['tests']['failed']} failed" if r["tests"] else "own tests not run"
    print(f"{task:24} {r['stop']:9} {r['turns']:>2} turns {len(r['tool_calls']):>2} tools ${r['cost_usd']} "
          f"{r['seconds']}s  {tests}  repairs {r['repairs']}  follows plan {r['follows_plan']}", flush=True)

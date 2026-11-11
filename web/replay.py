"""Play a saved session through the real page, free: no Claude, no Docker, nothing published (task S4.2).

    uv run --with anthropic python -m web.replay eval/results/sessions/bakery_through_the_page.jsonl
    then open http://127.0.0.1:8090 and click Start: the saved questions, plan, progress and link come back, whatever you type

The real web/app.py, builder/session.py and web/index.html run; only the paid or slow steps are swapped for what the
saved session.jsonl says they did. So you can change the page and see every screen without paying for a build.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

from builder import session


def fakes(saved, pace=1.0):
    """The stand-ins for the paid steps, read from one saved session. pace=0 plays at once (the test uses it)."""
    events = [json.loads(line) for line in Path(saved).read_text().splitlines()]
    questions = next((e["questions"] for e in events if e["event"] == "questions"), [])
    plan = next(e["plan"] for e in events if e["event"] == "plan")
    live = next(e for e in events if e["event"] == "live")
    agent = [e for e in events if e["event"] == "agent"]
    end = next(e["detail"] for e in agent if e["detail"]["event"] == "end")  # ponytail: only the first build; a later change plays it again

    def build(request, root, model, on_event, inbox, **k):
        for before, e in zip([agent[0]] + agent, agent):
            time.sleep(min(e["t"] - before["t"], 3) * pace)  # the saved gaps, at most 3 s each
            for text in inbox():  # a message typed now reaches the builder, as in a real build
                on_event({"event": "message", "text": text})
            on_event(e["detail"])
            if e["detail"] is end:
                break
        (root / "app.py").write_text("# replayed: the saved session's code is not copied here\n")
        return {"stop": end["stop"], "tests": end["tests"], "cost_usd": 0.0, "summary": live.get("summary", "")}

    return {"clarify": lambda *a, **k: (questions, 0.0), "make_plan": lambda *a, **k: (plan, 0.0), "build": build,
            "keeps_database": lambda root: {"ok": True, "output": ""},
            "deploy": lambda root, name: {"ok": True, "url": live["url"], "docs_url": live["docs_url"], "endpoints": live["endpoints"], "output": ""},
            "plain_summary": lambda *a, **k: (live.get("summary") or session.READY, 0.0), "undeploy": lambda name: None}


if __name__ == "__main__":
    import uvicorn
    from web.app import app

    for name, fake in fakes(sys.argv[1]).items():
        setattr(session, name, fake)
    session.BUILDS = Path(tempfile.mkdtemp())  # never the real builds folder
    print("Replaying", sys.argv[1], "at http://127.0.0.1:8090 (the link at the end points to the saved build, which may be offline)")
    uvicorn.run(app, host="127.0.0.1", port=8090)

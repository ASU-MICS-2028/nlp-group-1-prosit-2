"""The new web/index.html, every screen, free: the real web/app.py and builder/session.py with a pretend Claude and a pretend publish.
Real Chrome, at phone width and desktop width; screenshots next to this file.

    PYTHONPATH=. uv run --with anthropic --with playwright python eval/results/walkthrough/part6/new_page/check_page.py
"""
import json, pathlib, tempfile, threading, time

import uvicorn
from playwright.sync_api import sync_playwright

from builder import session
from web import app as web

OUT = pathlib.Path(__file__).parent
SAVED = pathlib.Path("eval/results/sessions/bakery_through_the_page.jsonl").read_text().splitlines()
# the real questions and plan of the bakery build made through the public page (W4 row 33)
QUESTIONS = next(json.loads(line)["questions"] for line in SAVED if '"event": "questions"' in line)
PLAN = next(json.loads(line)["plan"] for line in SAVED if '"event": "plan"' in line)


def fake_build(request, root, model, on_event, inbox, **k):
    for tool, tests in [("list_files", None), ("write_file", None), ("run_tests", {"passed": 4, "failed": 1}), ("edit_file", None), ("run_tests", {"passed": 5, "failed": 0})]:
        time.sleep(1.5)
        for text in inbox():
            on_event({"event": "message", "text": text})
        on_event({"event": "tool", "tool": tool, "ok": True, "tests": tests})
    (root / "app.py").write_text("x = 1\n")
    return {"stop": "end_turn", "tests": {"passed": 5, "failed": 0}, "cost_usd": 0.0, "summary": "Done"}


session.BUILDS = pathlib.Path(tempfile.mkdtemp())
session.clarify = lambda *a: (QUESTIONS, 0.0)
session.make_plan = lambda *a, **k: (PLAN, 0.0)
session.build = fake_build
session.keeps_database = lambda root: {"ok": True, "output": ""}
session.deploy = lambda root, name: {"ok": True, "url": f"https://example.test/b/{name}", "docs_url": f"https://example.test/b/{name}/docs",
                                     "endpoints": ["GET /events", "POST /events", "GET /events/{id}/signups"], "output": ""}
session.plain_summary = lambda request, notes, model: ("Your sign-up sheet is ready. Add events, and people can sign up for them.", 0.0)
session.undeploy = lambda name: None

server = uvicorn.Server(uvicorn.Config(web.app, host="127.0.0.1", port=8090, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.05)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    for name, size, scheme in [("phone", {"width": 390, "height": 800}, "light"), ("desktop", {"width": 1280, "height": 900}, "light"),
                               ("phone_dark", {"width": 390, "height": 800}, "dark")]:
        g = browser.new_context(viewport=size, color_scheme=scheme).new_page()
        errors = []
        g.on("pageerror", lambda e: errors.append(str(e)))
        g.on("dialog", lambda d: d.accept())  # "Take it offline?" asks first
        shot = lambda step: (g.wait_for_timeout(800), g.screenshot(path=OUT / f"{name}_{step}.png", full_page=True),  # 800 ms: the progress bar slides for 600
                             print(f"{name} {step}: sideways scroll {g.evaluate('document.documentElement.scrollWidth > innerWidth')}"))
        g.goto("http://127.0.0.1:8090/")
        g.click("button:has-text('Start')")
        print(f"{name} empty Start: {g.inner_text('#problem')!r}")
        g.click("button:has-text('Bakery orders')")
        print(f"{name} example click clears the message: {g.inner_text('#problem') == ''}")
        shot("1_describe")
        g.click("button:has-text('Start')")
        g.wait_for_selector("text=A few quick questions"); shot("2_questions")
        g.fill("#q0", "Always one cake per order")
        g.click("button:has-text('Continue')")
        g.wait_for_selector("text=Here is the plan"); shot("3_plan")
        g.reload(); g.wait_for_selector("text=Here is the plan"); print(f"{name} refresh keeps the build: yes")
        g.click("button:has-text('Looks good')")
        g.wait_for_selector("text=/Building/")
        g.fill("textarea", "orders also need a pickup date")
        g.click("button:has-text('Send')")
        g.wait_for_selector("text=Your message reached the builder", timeout=15000); shot("4_building")
        g.wait_for_selector("text=Your backend is live", timeout=20000); shot("5_live")
        g.click("button:has-text('Take it offline')")
        g.wait_for_selector("text=This backend was taken down"); shot("6_taken_down")
        print(f"{name} page errors: {errors}")
    browser.close()
server.should_exit = True

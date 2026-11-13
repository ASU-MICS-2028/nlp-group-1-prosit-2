"""S4.4, free: the page before decision 0060 (Joseph's, at 2735bfb), the page on Nov 11 (Michael's design on the same logic,
at 2dbf7a1), and the page now (live screen: developer details folded away, a named try-it link, "backend" explained).
The same saved bakery session plays through both (web/replay.py), in real Chrome at phone width. For each screen: how many
words the client reads, and which of them are technical words from a fixed list. A word count, not a user test (that is S4.5).

    PYTHONPATH=. uv run --with anthropic --with playwright python eval/experiments/page_compare.py
"""
import json, pathlib, re, subprocess, tempfile, threading, time

import uvicorn
from playwright.sync_api import sync_playwright

from builder import session
from web import app as web, replay

OUT = pathlib.Path("eval/results/page_compare")
SAVED = "eval/results/sessions/bakery_through_the_page.jsonl"
REQUEST = "I run a small bakery. I need to keep my cakes with a name and a price, see them all, and record orders for a cake with the customer's name."
TECH = {"api", "endpoint", "endpoints", "json", "swagger", "docs", "schema", "deploy", "deployed", "database", "field", "fields",
        "server", "http", "https", "sqlite", "url", "id"}
VERBS = {"GET", "POST", "PUT", "PATCH", "DELETE"}  # only in capitals: "get" and "delete" are plain words

def page_at(commit):
    f = pathlib.Path(tempfile.mkdtemp()) / "index.html"
    f.write_text(subprocess.run(["git", "show", f"{commit}:web/index.html"], capture_output=True, text=True, check=True).stdout)
    return f


VERSIONS = [("before", page_at("2735bfb")), ("nov11", page_at("2dbf7a1")), ("now", web.PAGE)]
for name, fake in replay.fakes(SAVED, pace=0.2).items():
    setattr(session, name, fake)
session.BUILDS = pathlib.Path(tempfile.mkdtemp())
server = uvicorn.Server(uvicorn.Config(web.app, host="127.0.0.1", port=8091, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.05)


def words(text):
    found = re.findall(r"[A-Za-z][A-Za-z'’-]*", text)
    return len(found), sorted({w for w in found if w in VERBS or w.lower() in TECH})


OUT.mkdir(exist_ok=True)
rows = {}
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    for version, page in VERSIONS:
        web.PAGE = page
        g = browser.new_context(viewport={"width": 390, "height": 800}).new_page()

        def screen(name):
            g.wait_for_timeout(800)
            g.screenshot(path=OUT / f"{version}_{name}.png", full_page=True)
            body = g.inner_text("body")
            summary = "".join(g.locator("pre").all_inner_texts())  # the agent's own summary, not the page's words
            rows.setdefault(name, {})[version] = words(body) + (words(body.replace(summary, ""))[1],)

        g.goto("http://127.0.0.1:8091/"); g.wait_for_selector("textarea"); screen("1_describe")
        g.fill("textarea", REQUEST); g.click("button:has-text('Start')")
        g.wait_for_selector("text=A few quick questions"); screen("2_questions")
        g.click("button:has-text('Continue')")
        g.wait_for_selector("text=Here is the plan"); screen("3_plan")
        g.click("button:has-text('Looks good')")
        g.wait_for_selector("text=/Building/"); g.wait_for_timeout(2000); screen("4_building")
        g.wait_for_selector("text=Your backend is live", timeout=30000); screen("5_live")
    browser.close()
server.should_exit = True

names = [v for v, _ in VERSIONS]
lines = ["screen        words " + " -> ".join(names) + "   technical words " + " | ".join(names) + "   ...not counting the agent's summary"]
for name, v in rows.items():
    lines.append(f"{name:13} " + " -> ".join(f"{v[n][0]:<4}" for n in names) + "   " + " | ".join(" ".join(v[n][1]) or "-" for n in names)
                 + "   " + " | ".join(" ".join(v[n][2]) or "-" for n in names))
print("\n".join(lines))
(OUT / "page_compare.txt").write_text("\n".join(lines) + "\n")
(OUT / "page_compare.json").write_text(json.dumps(rows, indent=1) + "\n")

"""The page's flow, free, through the playback, at phone width (W3 rows 12 and 13). Start the playback first:
    uv run --with anthropic python -m web.replay eval/results/sessions/bakery_through_the_page.jsonl
    uv run --with playwright python eval/experiments/flow_check.py
One line per check, then the build list each time it changes, with a message sent 4 s in (check 5 sends a second at 8 s)."""
import time
from playwright.sync_api import sync_playwright
U = "http://127.0.0.1:8090"
SLOW = "const f = fetch; fetch = async (u, o) => { const r = await f(u, o); if (o?.method !== 'POST') await new Promise(w => setTimeout(w, 800)); return r; }"  # every status reply 0.8 s late
ASK = "I run a small bakery. I need to keep my cakes with a name and a price, see them all, and record orders for a cake with the customer's name."

def to_plan(g):
    g.goto(U); g.fill("textarea", ASK); g.click("button:has-text('Start')")
    g.click("button:has-text('Continue')", timeout=30000); g.wait_for_selector("text=Looks good")

def build(g, sends=1, show=False):  # from the plan to live; returns the final list
    g.click("button:has-text('Looks good')"); g.wait_for_selector("text=/Building/"); start, seen, at = time.time(), None, [4, 8][:sends]
    while not g.is_visible("text=Your backend is live"):
        if at and time.time() - start > at[0]:
            g.fill("textarea", "Orders should also have a pickup date."); g.click("button:has-text('Send')"); at.pop(0)
            if show: print(f"{time.time() - start:4.1f} s  (message sent)")
        now = g.locator("#steps li").all_inner_texts() if g.is_visible("#steps") else seen
        if show and now != seen: print(f"{time.time() - start:4.1f} s ", now)
        seen = now; time.sleep(0.25)
    if show: print("live after", round(time.time() - start, 1), "s; the list's last line:", repr(g.evaluate("progress.at(-1)")))  # the playback publishes at once, so it is not seen
    return g.evaluate("progress")

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    def page():
        c = b.new_context(viewport={"width": 390, "height": 800}, extra_http_headers={"x-forwarded-for": str(time.time())})  # a new person each time: 5 starts a day each
        return c, c.new_page()

    c, g = page(); starts = []
    g.on("request", lambda r: r.method == "POST" and r.url.endswith("/api/builds") and starts.append(r.url))
    g.goto(U); g.fill("textarea", ASK); g.dblclick("button:has-text('Start')"); time.sleep(2)
    print("1. double click on Start, builds started:", len(starts)); c.close()

    c, g = page(); g.goto(U); short = g.locator("aside").bounding_box()["height"]; to_plan(g)
    print("2. phone, height of the dark bar: describe screen", short, "px, plan screen", g.locator("aside").bounding_box()["height"], "px")
    g.evaluate("scrollTo(0, document.body.scrollHeight)"); g.click("button:has-text('Looks good')"); g.wait_for_selector("text=/Building/"); time.sleep(0.5)
    print("3. after 'Looks good' at the bottom of the plan, scrolled down by", g.evaluate("scrollY"), "px"); c.close()

    c, g = page(); to_plan(g); g.click("button:has-text('Looks good')"); g.wait_for_selector("text=/Building/"); time.sleep(3)
    c.set_offline(True); time.sleep(4); gone = g.evaluate("location.search") == ""
    print("4. offline for 4 s mid-build: build forgotten:", gone, "| message:", repr(g.inner_text("#problem")))
    c.set_offline(False)
    try: g.wait_for_selector("text=Your backend is live", timeout=60000); print("   back online: reached live")
    except Exception: print("   back online: did not reach live")
    c.close()

    c, g = page(); g.goto(U); g.fill("textarea", ASK); g.click("button:has-text('Start')"); g.wait_for_selector("text=A few quick questions"); link = g.evaluate("location.href"); c.close()
    c, g = page(); g.route("**/api/builds/**", lambda r: r.abort()); g.goto(link); time.sleep(3)
    print("4b. a build's link opened while the server cannot be reached:", repr(g.inner_text("#view")[:60]), "|", repr(g.inner_text("#problem")))
    g.unroute("**/api/builds/**")
    try: g.wait_for_selector("text=A few quick questions", timeout=10000); print("    server back: shows the build's questions")
    except Exception: print("    server back: does not show the build")
    c.close()

    c, g = page(); to_plan(g); normal = build(g, sends=2); c.close()
    c, g = page(); g.add_init_script(SLOW); to_plan(g); slow = build(g, sends=2); c.close()
    print("5. two messages sent; lines in the build list with normal replies:", len(normal), "| with every reply 0.8 s slow:", len(slow))

    print("6. the build list over time:")
    c, g = page(); to_plan(g); build(g, show=True); c.close()
    b.close()

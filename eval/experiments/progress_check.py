"""What the building screen's progress list shows, free, through the playback (W3 row 12). Start the playback first:
    uv run --with anthropic python -m web.replay eval/results/sessions/bakery_through_the_page.jsonl
    uv run --with playwright python eval/experiments/progress_check.py
Prints the list each time it changes, from Building to live, with a message sent 4 s in (as browser_check.py does)."""
import time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    g = b.new_page(viewport={"width": 390, "height": 800})
    g.goto("http://127.0.0.1:8090"); g.fill("textarea", "I run a small bakery. I need to keep my cakes with a name and a price, see them all, and record orders for a cake with the customer's name.")
    g.click("button:has-text('Start')"); g.click("button:has-text('Continue')", timeout=30000)
    g.click("button:has-text('Looks good')", timeout=30000); g.wait_for_selector("text=/Building/")
    start, seen, sent = time.time(), None, False
    while not g.is_visible("text=Your backend is live"):
        if not sent and time.time() - start > 4:
            g.fill("textarea", "Orders should also have a pickup date."); g.click("button:has-text('Send')"); sent = True; print(f"{time.time() - start:4.1f} s  (message sent)")
        now = g.locator("#steps li").all_inner_texts() if g.is_visible("#steps") else seen
        if now != seen: print(f"{time.time() - start:4.1f} s ", now); seen = now
        time.sleep(0.25)
    print("live after", round(time.time() - start, 1), "s"); b.close()

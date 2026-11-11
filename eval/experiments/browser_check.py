"""The public page in real Chrome at phone width, one real build (about $0.20). Screenshots go to the folder given:
    uv run --with playwright python eval/experiments/browser_check.py eval/results/browser_check"""
import sys, time
from playwright.sync_api import sync_playwright
U = "https://34-78-38-126.sslip.io"; OUT = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    c = b.new_context(viewport={"width": 390, "height": 800})
    g = c.new_page(); errors = []
    g.on("pageerror", lambda e: errors.append(str(e)))
    g.goto(U); g.wait_for_selector("textarea"); g.screenshot(path=f"{OUT}/1_start.png")
    print("empty click:", end=" "); g.click("button:has-text('Start')"); time.sleep(1); print(repr(g.inner_text("#problem")), g.is_visible("textarea"))
    g.fill("textarea", "I run a small bakery. I need to keep my cakes with a name and a price, see them all, and record orders for a cake with the customer's name.")
    g.click("button:has-text('Start')")
    g.wait_for_selector("text=/quick questions|Here is the plan/", timeout=90000); g.screenshot(path=f"{OUT}/2_questions.png", full_page=True)
    if g.is_visible("text=A few quick questions"):
        print("questions:", g.locator("label").all_inner_texts())
        g.click("button:has-text('Continue')")
    g.wait_for_selector("text=Here is the plan", timeout=90000); g.screenshot(path=f"{OUT}/3_plan.png", full_page=True)
    print("url keeps the build:", g.url)
    g.reload(); g.wait_for_selector("text=Here is the plan", timeout=15000); print("survives a page refresh")
    g.click("button:has-text('Looks good')")
    g.wait_for_selector("text=/Building/", timeout=20000); time.sleep(4)
    g.fill("textarea", "Orders should also have a pickup date.")
    g.click("button:has-text('Send')"); time.sleep(6); g.screenshot(path=f"{OUT}/4_building.png", full_page=True)
    print("progress:", g.locator("#steps li").all_inner_texts())
    g.wait_for_selector("text=/Your backend is live|It is not online/", timeout=400000); g.screenshot(path=f"{OUT}/5_result.png", full_page=True)
    print("result:", g.inner_text("h2 >> nth=0"))
    print(g.inner_text("#view")[:900])
    wide = g.evaluate("document.documentElement.scrollWidth <= innerWidth"); print("no sideways scroll on a phone:", wide)
    link = g.locator("a").first.get_attribute("href"); print("docs link:", link)
    d = c.new_page(); d.goto(link); d.wait_for_selector(".opblock", timeout=20000); d.screenshot(path=f"{OUT}/6_docs.png"); print("docs operations:", d.locator(".opblock").count())
    print("page errors:", errors); b.close()

# Usability test kit (task S4.5)

For 4 to 5 people who do not write code (not on the team, not computing students). About 15 minutes each, so about an hour and a half for five, with two of us. Anyone on the team can run it (decision 0062). Bring a phone or laptop with the live page open, this sheet, and a timer. Nothing here is a result: the results go in `eval/results/usability/` once real people have used the page (decision 0051).

## Before

- **The live page must be the new one.** Joseph reruns `setup_server.sh` on the server first. Check that the start page says "the part of an app or website that keeps your records", and that a live build shows "Open the try-it page" and a folded "For the person who builds your website or app".
- **Cost.** Each person makes one real build: about $0.20, so about $1.00 for five. Tell Joseph before starting, so the day's $10 limit is not hit by other builds.
- **Privacy.** The repo is public. Write no names, phone numbers or emails: call people P1 to P5. Ask each person if you may write down what they say, and quote only their exact words.
- One person runs the test and says as little as possible; a second writes notes and keeps time. Do not help unless they are stuck for a minute; write down each time you help.

## What to say

First, consent: "We are a student group testing a website. It takes about 15 minutes. We will not write down your name. May we write down what you say, and quote it in our report without your name?" Only go on with a yes; if they say no to quotes, write no quotes for them.

Then: "We are testing the page, not you. Please say out loud what you are thinking as you go. There are no wrong answers."

## The tasks

Give one at a time. Write down: done without help, done with help, or not done; and any word they ask about or misread.

1. "Think of a small business you know. Ask this page for a system to keep its records." (If they cannot think of one, let them use an example button.)
2. "Answer its questions."
3. "Tell me in your own words what it is going to build. If that is what you want, approve it."
4. "While it builds, ask it for one more thing."
5. "When it is ready, find the link you would give to someone building your website."
6. "Now take it offline."

Time it from the click on Start to "Your backend is live", and the whole session.

## After: the SUS form (System Usability Scale)

Each from 1 (strongly disagree) to 5 (strongly agree). Read them in this order; do not change the wording.

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

Score: `uv run python eval/usability/sus.py 4 2 4 1 4 2 5 1 4 2` (the 10 answers in order). About 68 is average for software; above 80 is good.

Then ask: "What was the most confusing part?" and "What would you tell a friend about it?"

## The results sheet

Copy into `eval/results/usability/results.md` and fill in one row per person.

| Person | Tasks done without help (of 6) | Helped on | Start to live (min) | Whole session (min) | Words they did not understand | SUS | Their exact words (with permission) |
|---|---|---|---|---|---|---|---|
| P1 | | | | | | | |
| P2 | | | | | | | |
| P3 | | | | | | | |
| P4 | | | | | | | |
| P5 | | | | | | | |

Then: the average SUS, how many finished all 6 tasks, and every word that confused two or more people. Fix those words in `web/index.html`, and add a row to `learnings/W3-product-ui-and-usability.md`.

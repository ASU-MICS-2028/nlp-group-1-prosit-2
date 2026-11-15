# Usability test results (S4.5)

The kit is `eval/usability/README.md`. People are P1, P2, ... with no names.

## P1, Nov 15, on the public link

A non-developer (they said they "don't really even know what a backend is"). They talked aloud while they used the page and sent us their notes; this file summarizes them, and the raw notes are not committed. No SUS form was filled in, and nobody helped them.

**Their request:** a car dealership that cannot keep track of its cars: add new cars, log a sale with its profit (purchase, listing and sale price), cars sold over a time range, cars still in stock, and a record of every change.

| Task | Result | What happened |
|---|---|---|
| 1. Ask for a system | Done without help | Typed the request above and pressed Start |
| 2. Answer its questions | Done without help | Three questions (other costs in the profit? who may see what? which details per car?), then more questions inside the plan |
| 3. Explain and approve the plan | Done without help, but confused | Typed their answers in the box under the plan, then could not tell which button applies them: "Looks good, build it" or "Change the plan". They tried "Change the plan", and the plan did take in their answers ("So it's actually did update the plan. That's cool."). More questions came; tired of them, they pressed "Looks good, build it" |
| 4. Ask for one more thing mid-build | Not tried | Saw the box but felt the answers had already covered everything |
| 5. Find the link | Done without help | Opened the docs page, added two cars, saw a second car with the same VIN refused, listed all cars and cars in stock, read the change history |
| 6. Take it offline | Not done | Not asked to |

**Time:** about 10 minutes from typing the request to using the live backend, by their own estimate.

**Where they got stuck or unsure:**
- The plan screen: answers to the plan's questions go in "Tell us what to change", and the button that applies them is "Change the plan". They expected answering to be enough. "I think the UI needs to be worked on because that was confusing."
- Rounds of questions: three before the plan, then more in each new plan. "I hope it doesn't ask me any more questions cause I am tired."
- "Getting started" stayed on screen with nothing else for a while: "It's not really telling me what is happening."
- Words on the docs page: "Execute", "string", "changed by", "history". They worked out that "changed by" means the person's name.

**What they liked:** "Oh my God wait so when this is done, I'll actually have like my own backend and running that I can use for my store." "I have a full backend working. I mean I don't really even know what a backend is." "It only took me about ten minutes."

**What this shows (one person, so weak evidence):** a non-developer got from a sentence to a working backend with a real database alone, in about 10 minutes, and could use it through its docs page. The plan screen is the weak point: its questions read as a form to answer, but answering does nothing until "Change the plan" is pressed. Still to do: 3 to 4 more people, the SUS form, and tasks 4 and 6.

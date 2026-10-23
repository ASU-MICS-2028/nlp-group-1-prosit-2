# Lecture 7: Trusting Generative AI, Understanding Your Code, and a Prosit 2 Check-in

## In one paragraph
This was a short session with no new technical content. It opened with a clip, apparently a video. A narrator showed an old family photo that Gemini recoloured. The result looked convincing, but the model had invented details. The instructor drew the lesson: you must understand any AI-generated code you submit. He also gave advice on keeping code minimal. The rest of the class was a progress check with each group on Prosit 2. (The transcript writes "prosit" as "precedent" or "proceedings".) After the check-ins, about the last third of the recording is unrelated side chat and setup talk, unclear in the recording.

## Key ideas, explained simply
- **Generative AI fills gaps with likely content.** In the clip, a black-and-white Christmas photo was recoloured in about 10 seconds. But the model added bunting and a clock, and it put a whole new person into an empty gap in the centre. The narrator compared this to an LLM. When an LLM lacks an answer, it fills the gap with the most statistically likely words. Here the model filled empty space with statistically likely pixels. Even a simple, clear instruction can produce unexpected output, and the model answers confidently even when there is no real answer.
- **The "blind person" analogy.** The instructor said that using AI to write code in a language you cannot read is like a blind person using AI to recolour a photo. On good days nothing goes wrong. When the output is suboptimal, you have no way to tell. A sighted person can spot the extra person in the photo. A developer who can read the code can spot bad code. His email example: you can tell an AI "you are talking too much, keep it short" only because you can read English.
- **The goal is fluency, not avoiding AI.** You should use AI, but know enough to recognise when it is doing the right thing and when it is not. You can even use the AI to make the correction. You just need to know what it did and why it is not the best approach.
- **Code is liability.** Submit the most minimal code that does what your work needs to do. More code means more liability and a bigger attack surface.

## What the instructor said about assignments, deadlines, grading or expectations
- **Code understanding standard:** if code is in your submission, you must understand it. If he shows you any piece of it, you must be able to explain what it does. Build it, get it working, then go through every part of it.
- **Last year's viva (for context):** after presentations, students came one by one. He picked one of their code files at random and asked "what is this doing, why did you do this?" for about 5 minutes. He said he wants a better method than 5 minutes to judge whether you know the code. He did not say what the new method is.
- **Section C:** a student pointed out that the grading includes Section C, but the question has no Section C. The exchange is partly unclear in the recording.
- **Length:** a student said Prosit 2 seemed to need less writing than Prosit 1. The instructor said the total length is roughly the same. Prosit 1 gave paragraph counts per question. For Prosit 2 he put page counts at the top because he wants "a coherent story". What matters is that you address every question within the paragraph range he gave. Length itself is not the point. A student said Section A must be condensed into "three to five" paragraphs, then the speakers switched to talking about pages. Whether it is paragraphs or pages is unclear in the recording, so check the brief.
- **Timeline:** groups are behind. By this point they should be wrapping up Prosit 2, based on the original timeline. He told everyone to get working on it.
- **After the midterm break:** next week is the midterm break. In the week they return, there will be one lecture, and the other two periods will be used for prosit work. The class agreed to this.

## Relevance to Prosit 2
- **m Coding agents, l Human-in-the-loop:** this is the core risk of our platform. Our users are non-developers, so they are the "blind person" in the analogy. They cannot read the FastAPI code the agent writes. That makes the Tester agent, automatic checks and clear plain-language explanations essential. A user approving output they cannot read is a weak safeguard.
- **k Privacy and security:** "code is liability" and "attack surface" support keeping generated backends minimal and running them in the sandbox.
- **p Decomposition and self-reflection:** the model "confidently gives an answer when there isn't one". This argues for a self-check or reflection step before code is shown to the user.
- **Viva prep:** every team member must be able to explain any file in our repo, not just their own part.
- **Group process:** one group said assigning portions and having each member teach the others worked better than everyone learning everything.

## Likely quiz or viva questions
1. Why might a generative model add a person to a recoloured photo? It fills gaps with statistically likely pixels, just as an LLM fills knowledge gaps with likely words.
2. What does "code is liability" mean? Every extra line is something to maintain and secure. More code widens the attack surface.
3. Why does it matter that our users cannot read code? They cannot tell when the agent produced something suboptimal, so the system must test and explain for them.
4. What is the course standard for AI-generated code? You must understand and be able to explain any code in your submission.

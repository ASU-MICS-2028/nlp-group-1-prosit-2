# The assignment: Prosit 2

Summarized from the brief "PROSIT 2: Building a Non-Developer Friendly API Development Platform" (ICS554, 2026) and the course schedule. The PDF is on Canvas.

## The problem

Tools like Lovable and Replit let non-developers build web apps from a web page, with no coding, installing or deploying. Mesora, an AI research lab in Ghana that works on coding agents, believes coding agents should follow separation of concerns: **independent frontends and backends that talk only through a well-defined API.**

Mesora wants a platform that lets **non-developers build backend APIs** through an interface that is friendly to them. We build it as a team.

## Deliverables

| Deliverable | Who | Size | Notes |
|---|---|---|---|
| Code on GitHub | Team | — | This repo. The link must be on the **first page** of the slides and of the report |
| Technical report, Section A | Each person, in their own words | 3–5 pages | The 18 topics below, with justification, maths and visuals where appropriate |
| Technical report, Section B | Team, **identical text in every member's report** | 3–5 pages | How we built the platform (4 points below) |
| Team presentation | Team | 10 minutes | Summarizes Section B, in an engaging way. Slides uploaded to Canvas |
| Viva quiz | Each person | — | Questions on our own system |

Section A's goal is to help Mesora understand the journey from pre-trained LLMs to agents and how coding agents work. The question: *language models predict the next token, so how does that lead to AI that can do so much "magic"?* It must touch on all of these:

a. Instruction tuning · b. Preference-based learning · c. LLM alignment · d. Prompt engineering and chain-of-thought prompting · e. Retrieval augmented generation · f. Agentic AI · g. Multi-agent systems · h. Reasoning and planning · i. Memory mechanisms · j. Reinforcement learning from human feedback · k. Privacy and security of agentic AI · l. Human-in-the-loop · m. Coding agents · n. Perceive-Plan-Act loop and Thought-Action-Observation (ReAct) loop · o. Tool use · p. Decomposition and self-reflection · q. Model Context Protocol · r. Orchestration

Section B must cover:
1. How we went about solving the problem, and why we made those choices
2. The architecture of the solution
3. Implementation choices, justification and details
4. Evaluation of the solution

## Rubric

| Item | Weight | Graded on |
|---|---|---|
| Group presentation (10 min) | 20% | How educational it was; how well the examiners understand the work the group **and each member** did |
| Technical report | 45% | Section A 15%; Section B 15% implementation and results + 5% writing quality; "Section C" 15% + 5% (see below) |
| Viva quiz | 35% | Individual understanding of our system |

**There is no Section C.** An early version of the rubric listed one by mistake; the instructor confirmed and corrected it on Oct 22. The report is Section A (individual) and Section B (shared).

## Related learning outcomes (from the brief)

- Design, implement, train, evaluate and deploy LLM-based applications, using prompt engineering, fine-tuning and domain adaptation for real use cases.
- Critically read and implement NLP research papers, turning theory into reproducible experiments and applications.
- Explain NLP concepts clearly to technical and non-technical audiences, using visualization, documentation and presentation tools.

## Deadline

**We are working with no fixed deadline** (team decision, Oct 21; see `docs/DECISIONS.md`). For reference, the course schedule puts **Close Prosit 2 in Week 7 (Oct 19–23, 2026)**: technical presentations, technical report, viva quiz and Quiz 2. The exact days are not in the brief. Week 8 (Oct 26–30) is the mid-semester break.

For Prosit 1, the instructor said there would be no extensions, but late submissions would not be penalised. Do not assume the same applies to Prosit 2.

## What the instructor said in lectures

From the [lecture summaries](lectures/README.md). Recordings are imperfect, so confirm anything important with the instructor.

- **Lecture 4 (the Prosit 2 launch):** Section A is 3–5 pages **in total** and should be told as one story, from next-token prediction to agents, not as 18 separate answers. The instructor said projects will "most likely" use dense retrieval. If we use BM25, be ready to defend that with our comparison numbers.
- **Lecture 1:** each prosit is graded 20% presentation, 45% report, 35% viva. The repo must be public. Section A must be in your own words, and every member must understand the code.
- **Lecture 2:** the shared sections must be identical across the group, and each student submits their own document. The next prosit only unlocks once you submit.

## Report conventions the instructor asked for (Prosit 1, likely the same now)

- Each student submits their own report. Section A is personal; the shared sections are copied word for word across the group.
- A research-paper style format is encouraged.
- Course AI policy: AI tools are allowed, but you must be able to explain and defend everything you submit without AI. The viva tests this.

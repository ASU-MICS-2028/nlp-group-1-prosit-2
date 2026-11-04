# 0042. Ask the client up to 3 questions before planning or building

- Status: Proposed
- Date: 2026-11-04
- Decided by: Alice (to sign off)

## Context

S3.5 row 5 showed that what the request leaves out gets guessed or left out. S3.8 lets the agent ask first (`--ask N`): one Claude call writes up to N questions, the client answers (a person, or a pretend client from the task's prepared answers for the benchmark), and the answers are added to the request.

## Options considered

Measured in `learnings/W1-agent-core.md`, experiment log rows 6 and 7 (Opus, harness `--repeat 3`):

- No questions: 64.0% on the 3 vague tasks (3 builds each); 87.0% on all 15.
- Up to 3 questions, answered from prepared answers: 77.2% on the vague tasks; with "choose the simplest option when there is no preference" added, **95.8% on all 15** (school 3/12 to 12/12, restaurant 5/12 to 12/12, no task worse).
- Up to 3 questions, answered by a pretend client who knows the full brief: 68.4% on the vague tasks; it also answers in technical words a real client would not use.
- Without the "simplest option" line, a question about a PIN answered "you decide" got a PIN built in (momo 13/13 to 1/13).
- Cost: under 1 cent per task ($0.13 for 15).

## Decision

Before planning or building, the agent asks up to 3 questions (`--ask 3`; in Python `clarify` then `with_answers`). Where the client has no preference, the builder is told to choose the simplest option and add nothing. Benchmark runs answer with the prepared answers (`--client answers`). The command-line default stays `--ask 0`, so existing experiment commands do not start waiting for typed answers.

## Consequences

- The first agent version above the 89% baseline.
- 3 questions can miss what matters (shop never asked about categories). More questions, or questions after the plan, are untested.
- One build per task: 1 to 3 test differences on a task can be luck.
- Michael's page needs a step that shows the questions and collects the answers.

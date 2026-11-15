# 0063. Main holds only what the platform runs; the experiments live at a tag

- Status: Accepted
- Date: 2026-11-15
- Decided by: Joseph, for the team, before submission

## Context

The viva can ask about any code we submit (Lecture 7), and the instructor advised the smallest code that works. By submission, about half the code on `main` was there only to re-run experiments whose results are already saved: four builder prompts, the repair checker (off since decision 0040), the first planner, the local Qwen model, the subprocess sandbox, hybrid search, a session replayer, and about 50 experiment scripts.

## Options considered

- **Keep everything re-runnable from `main`.** Nothing to change, but every member must be able to explain code the live platform never runs.
- **Keep only what the live platform, the command line and the marker run, and tag the rest.** `builder/agent.py` went from 458 to 286 lines. The removed code is unchanged at the `report-experiments` tag, so every number in the report can still be traced to the exact code that made it.

## Decision

The second. Before the cleanup, `main` was tagged `report-experiments`. Removed:
- `builder/experiments/`, `runtime/experiments/` and `eval/experiments/`, except `audit_numbers.py`;
- `web/replay.py`, `eval/llm.py`, and the kb comparison scripts;
- from the agent: prompts A, C and D, the repair checker, planner v1, the local model and the plan-following check;
- `SANDBOX=subprocess`, and hybrid search.

The church test fixtures moved to `runtime/tests/`. Bernard's saved outputs moved from `runtime/experiments/results/` to `eval/results/runtime/`.

The prompts, tool definitions and schemas the platform sends are unchanged, word for word; this was checked against the tag. After the cleanup:
- 135 tests pass (the 19 removed tests covered only removed features);
- every reference backend still scores 100% (`eval/results/harness/cleanup_check.json`);
- every planted bug is still caught (`benchmark/validation.json` is unchanged).

## Consequences

The code to defend is smaller, and what is on `main` is what runs. Commands in `learnings/` that name a removed script work only after `git checkout report-experiments`; each learnings file says so at the top. Results, decision records and learnings are kept as they were.

# Decisions

Every decision is a numbered record (ADR), one file each. To add one: copy `0000-template.md` to the next number with a short name (e.g. `0017-retrieval-method.md`), fill it in, then run `python3 scripts/update_status.py` to update the index below. If a decision changes, write a new record and set the old one's status to `Superseded by NNNN`. Never edit an old decision away.

Statuses: `Proposed` (suggested, not yet signed off), `Accepted`, `Superseded by NNNN`.

<!-- DECISIONS:START -->
| # | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-two-team-rules.md) | Two team rules: explain simply, test every alternative | Accepted | 2026-10-18 |
| [0002](0002-fixed-backend-stack.md) | Generated backends always use FastAPI + SQLModel + SQLite + pytest | Proposed | 2026-10-18 |
| [0003](0003-hand-written-agent-loop.md) | Hand-written ReAct loop and a plain Python orchestrator | Proposed | 2026-10-18 |
| [0004](0004-spec-first.md) | Spec-first: the user approves the API contract before any code is written | Proposed | 2026-10-18 |
| [0005](0005-three-agents.md) | Planner, Builder and Tester agents, with a single agent as the baseline | Proposed | 2026-10-18 |
| [0006](0006-sandbox.md) | Generated code runs in a Docker sandbox, with a subprocess fallback | Proposed | 2026-10-18 |
| [0007](0007-benchmark-operations.md) | Benchmark tests call named operations, not fixed URLs | Proposed | 2026-10-18 |
| [0008](0008-repo-structure.md) | Three shared folders: docs, learnings, knowledge | Accepted | 2026-10-20 |
| [0009](0009-summarize-transcripts.md) | Transcripts are summarized before they go in the repo | Accepted | 2026-10-20 |
| [0010](0010-llms.md) | Claude Opus 5.5 as the main model, local Qwen 3.5 9B compared against it | Accepted | 2026-10-20 |
| [0011](0011-owners.md) | Each person owns a workstream outside their strengths | Accepted | 2026-10-20 |
| [0012](0012-assume-no-section-c.md) | Assume there is no Section C until the instructor replies | Superseded by 0014 | 2026-10-21 |
| [0013](0013-relay.md) | Work as a relay, one person at a time, with no fixed deadline | Accepted | 2026-10-21 |
| [0014](0014-no-section-c.md) | There is no Section C | Accepted | 2026-10-22 |
| [0015](0015-share-api-key.md) | Share the Claude API key with every member | Accepted | 2026-10-22 |
| [0016](0016-adrs.md) | Decisions are recorded as numbered ADRs, one file each | Accepted | 2026-10-22 |
| [0017](0017-drop-contracts-file.md) | Remove the interface suggestions file | Accepted | 2026-10-22 |
| [0018](0018-readme-current-stage.md) | The README shows only the current stage | Accepted | 2026-10-23 |
| [0019](0019-agent-instruction-files.md) | One set of agent instructions, with a pointer file for each assistant | Accepted | 2026-10-23 |
| [0020](0020-workflow-guides.md) | Step-by-step guides for the common workflows, usable by any assistant | Accepted | 2026-10-23 |
| [0021](0021-secret-guards.md) | Guards against leaking the API key | Accepted | 2026-10-23 |
| [0022](0022-path-guard.md) | File tools find the real path first, then check it is inside the project | Proposed | 2026-10-25 |
| [0023](0023-file-tools.md) | File tools: flat file list, whole-file reads, and an edit_file tool | Proposed | 2026-10-25 |
| [0024](0024-tool-output-size.md) | Tool output is cut to 4,000 characters, keeping the start and the end | Proposed | 2026-10-25 |
| [0025](0025-server-start.md) | start_server uses a free port and asks the server until it answers | Proposed | 2026-10-25 |
<!-- DECISIONS:END -->

## Open questions

- Product name: keep the working name "Mesora API Builder" or choose another?

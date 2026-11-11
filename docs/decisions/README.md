# Decisions

Every decision is a numbered record (ADR), one file each. To add one: copy `0000-template.md` to the next number with a short name (e.g. `0017-retrieval-method.md`), fill it in, then run `python3 scripts/update_status.py` to update the index below. If a decision changes, write a new record and set the old one's status to `Superseded by NNNN`. Never edit an old decision away.

Statuses: `Proposed` (suggested, not yet signed off), `Accepted`, `Superseded by NNNN`.

<!-- DECISIONS:START -->
| # | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-two-team-rules.md) | Two team rules: explain simply, test every alternative | Accepted | 2026-10-18 |
| [0002](0002-fixed-backend-stack.md) | Generated backends always use FastAPI + SQLModel + SQLite + pytest | Proposed | 2026-10-18 |
| [0003](0003-hand-written-agent-loop.md) | Hand-written ReAct loop and a plain Python orchestrator | Proposed | 2026-10-18 |
| [0004](0004-spec-first.md) | Spec-first: the user approves the API contract before any code is written | Superseded by 0041 | 2026-10-18 |
| [0005](0005-three-agents.md) | Planner, Builder and Tester agents, with a single agent as the baseline | Proposed | 2026-10-18 |
| [0006](0006-sandbox.md) | Generated code runs in a Docker sandbox, with a subprocess fallback | Superseded by 0027 | 2026-10-18 |
| [0007](0007-benchmark-operations.md) | Benchmark tests call named operations, not fixed URLs | Proposed | 2026-10-18 |
| [0008](0008-repo-structure.md) | Three shared folders: docs, learnings, knowledge | Accepted | 2026-10-20 |
| [0009](0009-summarize-transcripts.md) | Transcripts are summarized before they go in the repo | Accepted | 2026-10-20 |
| [0010](0010-llms.md) | Claude Opus 5.5 as the main model, local Qwen 3.5 9B compared against it | Accepted | 2026-10-20 |
| [0011](0011-owners.md) | Each person owns a workstream outside their strengths | Accepted | 2026-10-20 |
| [0012](0012-assume-no-section-c.md) | Assume there is no Section C until the instructor replies | Superseded by 0014 | 2026-10-21 |
| [0013](0013-relay.md) | Work as a relay, one person at a time, with no fixed deadline | Superseded by 0050 | 2026-10-21 |
| [0014](0014-no-section-c.md) | There is no Section C | Accepted | 2026-10-22 |
| [0015](0015-share-api-key.md) | Share the Claude API key with every member | Accepted | 2026-10-22 |
| [0016](0016-adrs.md) | Decisions are recorded as numbered ADRs, one file each | Accepted | 2026-10-22 |
| [0017](0017-drop-contracts-file.md) | Remove the interface suggestions file | Accepted | 2026-10-22 |
| [0018](0018-readme-current-stage.md) | The README shows only the current stage | Superseded by 0050 | 2026-10-23 |
| [0019](0019-agent-instruction-files.md) | One set of agent instructions, with a pointer file for each assistant | Accepted | 2026-10-23 |
| [0020](0020-workflow-guides.md) | Step-by-step guides for the common workflows, usable by any assistant | Accepted | 2026-10-23 |
| [0021](0021-secret-guards.md) | Guards against leaking the API key | Accepted | 2026-10-23 |
| [0022](0022-path-guard.md) | File tools find the real path first, then check it is inside the project | Proposed | 2026-10-25 |
| [0023](0023-file-tools.md) | File tools: flat file list, whole-file reads, and an edit_file tool | Proposed | 2026-10-25 |
| [0024](0024-tool-output-size.md) | Tool output is cut to 4,000 characters, keeping the start and the end | Proposed | 2026-10-25 |
| [0025](0025-server-start.md) | start_server uses a free port and asks the server until it answers | Proposed | 2026-10-25 |
| [0026](0026-error-format.md) | Failing tests are reported to the LLM as pytest prints them | Proposed | 2026-10-25 |
| [0027](0027-docker-sandbox.md) | Generated code runs in a locked Docker container; subprocess only when chosen on purpose | Proposed | 2026-10-25 |
| [0028](0028-test-time-limit.md) | run_tests stops tests after 60 seconds and removes their container | Proposed | 2026-10-25 |
| [0029](0029-safety-layers.md) | Safety comes from the tools and the sandbox, with no filter on the user's request | Proposed | 2026-10-26 |
| [0030](0030-harness-uses-docker-sandbox.md) | The evaluation harness runs every backend in the Docker sandbox, side by side, and cleans up first | Accepted | 2026-10-26 |
| [0031](0031-benchmark-format-and-checker.md) | Benchmark tasks are checked for being too weak, too strict and flaky before anything is measured | Accepted | 2026-10-27 |
| [0032](0032-opus-writes-ops-json.md) | The name map (ops.json) is always written by Opus, whichever model built the backend | Accepted | 2026-10-27 |
| [0033](0033-builder-never-sees-operations.md) | The agent that builds a backend never sees the task's operations list | Accepted | 2026-10-27 |
| [0034](0034-benchmark-translation-rules.md) | What the benchmark's name translation handles, and how a change to it is checked | Accepted | 2026-10-27 |
| [0035](0035-harness-defaults.md) | How the eval harness runs: 4 side by side, stop if Docker is off, flag incomplete maps | Accepted | 2026-10-28 |
| [0036](0036-recipes-never-use-benchmark-topics.md) | Recipes never use the benchmark's topics | Accepted | 2026-10-29 |
| [0037](0037-dense-minilm-search.md) | search_docs uses dense search (all-MiniLM-L6-v2) and returns the top 3 | Accepted | 2026-10-29 |
| [0038](0038-agent-prompt-b.md) | The agent's system prompt is version B (SQLite, write and run your own tests) | Proposed | 2026-11-03 |
| [0039](0039-run-record-and-trace.md) | Every build writes trace.jsonl as it happens and run.json at the end | Proposed | 2026-11-03 |
| [0040](0040-repairs-off-by-default.md) | The repair loop stays in the code but is off by default | Accepted | 2026-11-04 |
| [0041](0041-plan-v2-when-a-person-approves.md) | Plan first (planner v2) when a person approves; no plan in automatic benchmark runs | Accepted | 2026-11-04 |
| [0042](0042-ask-up-to-3-questions.md) | Ask the client up to 3 questions before planning or building | Proposed | 2026-11-04 |
| [0043](0043-search-off-for-opus.md) | Recipe search stays available but off for Opus | Proposed | 2026-11-04 |
| [0044](0044-one-agent-not-a-split.md) | One agent that asks questions, not a Planner / Builder / Tester split | Proposed | 2026-11-04 |
| [0045](0045-changes-edit-the-existing-app.md) | A requested change edits the existing app instead of rebuilding it | Proposed | 2026-11-04 |
| [0046](0046-opus-default-qwen-only-with-search.md) | Opus is the agent's default model; the local Qwen is used only with recipe search | Proposed | 2026-11-04 |
| [0047](0047-hosting-on-one-gcp-server.md) | Host everything on one GCP server, each backend at its own path | Accepted | 2026-11-05 |
| [0048](0048-agent-session.md) | One session object carries a client from request to live link | Accepted | 2026-11-06 |
| [0049](0049-small-live-platform-first.md) | Put a small platform online first; Michael improves it live | Accepted | 2026-11-06 |
| [0050](0050-everyone-works-at-once.md) | Everyone works at the same time; the README lists each person's tasks | Accepted | 2026-11-06 |
| [0051](0051-save-every-result.md) | Every test result is saved in the repo | Accepted | 2026-11-06 |
| [0052](0052-read-whole-files.md) | read_file returns up to 20,000 characters | Accepted | 2026-11-06 |
| [0053](0053-refuse-backends-that-lose-data.md) | Do not publish a backend that would lose its data | Accepted | 2026-11-06 |
| [0054](0054-plain-summary-after-the-build.md) | Rewrite the summary after the build; keep the wording of mid-build messages | Accepted | 2026-11-08 |
| [0055](0055-records-found-by-name-or-number.md) | Score backends that find a record by name or number; compare over repeated builds | Accepted | 2026-11-09 |
| [0056](0056-opus-stays-for-builds.md) | Opus stays as the model that builds backends | Accepted | 2026-11-09 |
| [0057](0057-stop-a-backend-filling-the-disk.md) | Stop a backend filling the disk with a file limit and a watchdog | Accepted | 2026-11-09 |
| [0058](0058-drop-the-mcp-server.md) | Drop S1.4, the MCP server | Accepted | 2026-11-10 |
| [0059](0059-take-a-build-down.md) | A client can take their build down | Proposed | 2026-11-10 |
| [0060](0060-michaels-design-on-the-live-page.md) | The live page uses Michael's design, in one plain file | Proposed | 2026-11-11 |
<!-- DECISIONS:END -->

## Open questions

- Product name: keep the working name "Mesora API Builder" or choose another?

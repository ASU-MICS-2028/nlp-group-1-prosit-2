# 0058. Drop S1.4, the MCP server

- Status: Accepted
- Date: 2026-11-10
- Decided by: Joseph

## Context

S1.4 was a `Could` task: let an MCP client such as Claude Desktop call the agent's tools. Bernard skipped it (section on S1.4 in `learnings/W2-runtime-tools-and-safety.md`) and is currently indisposed. It stayed in the plan as "ready", so it looked like unfinished work.

## Options considered

- Build it: nothing in the plan needs it, and the platform's agent calls the tools directly. It would add a dependency and more code to defend.
- Keep it listed as `todo`: costs nothing, but says work is left when nobody will do it.
- Drop it: remove the row from the plan and record why here.

## Decision

Drop it. The S1.4 row is removed from `docs/PLAN.md`. No other task depended on it.

## Consequences

The plan shows only work that will be done. Claude Desktop cannot call the tools. If someone wants that later, the tools in `runtime/tools.py` are plain functions and an MCP server could wrap them.

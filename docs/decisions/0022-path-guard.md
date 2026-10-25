# 0022. File tools find the real path first, then check it is inside the project

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

## Context

The file tools (`write_file`, `read_file`, `edit_file`) take a path chosen by the LLM. A wrong or tricked LLM could ask for `../.env` or `C:\Windows\...` and read secrets or damage the computer. The tools need one check that refuses every path outside the project folder.

## Options considered

- A: look at the text of the path and refuse anything containing `..`, a leading `/`, a `:`, `.env` or `.git`.
- B: let the operating system work out where the path really ends up (following `..` and folder links), then check that place is inside the project. Also refuse empty paths, paths over 255 letters, hidden zero characters, colons, and `.env` / `.git` in any capitals.

Measured on the same 24 paths (row 1 of the experiment log in `learnings/W2-runtime-tools-and-safety.md`): A let 5 attacks through and refused 2 good files; B let 0 through and refused 0.

## Decision

B, in `safe_path()` in `runtime/tools.py`. Every file tool calls it before touching anything.

## Consequences

- Links that point outside, `.ENV`, `.env.` and `.env::$DATA` are all refused, on Windows and on Linux.
- A colon is never allowed in a path, so a file name with a colon cannot be made (not needed for Python projects).
- It only protects the file tools. Code the agent writes and then runs (tests, the server) can still open any file; that is the sandbox's job (S1.2).

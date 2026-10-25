# 0023. File tools: flat file list, whole-file reads, and an edit_file tool

- Status: Proposed
- Date: 2026-10-25
- Decided by: Bernard (W2), awaiting his sign-off

## Context

The agent needs to see, read, create and change the files of the backend it is building. Each choice changes how many tokens it spends and how easily it makes mistakes.

## Options considered

Measured in `learnings/W2-runtime-tools-and-safety.md`, experiment log rows 2–4:

- File list as a flat list of paths (182 characters for 12 files) or an indented tree (168).
- Changing a file by resending all of it with `write_file` (4,271 characters for 3 fixes) or sending only the changed piece with `edit_file` (284).
- Reading whole files (every benchmark file is under the 4,000-character limit; the largest is 2,588) or adding line ranges.

## Decision

Four file tools in `runtime/tools.py`:
- `list_files`: flat list of paths;
- `read_file`: the whole file;
- `write_file`: new or replaced files, at most 200,000 characters;
- `edit_file`: the old text must appear exactly once, or nothing changes.

`list_files` never shows `.env`, `.git`, `__pycache__`, `.venv`, `.pytest_cache`, or links pointing outside the project.

## Consequences

- Small fixes cost 11–23 times fewer output tokens when the LLM uses `edit_file`.
- One more tool for the LLM to learn. Whether it uses `edit_file` well is measured later, when the agent loop exists (S3).
- A file over 4,000 characters is shown with its middle cut out.

# 0057. Stop a backend filling the disk with a file limit and a watchdog

- Status: Proposed
- Date: 2026-11-09
- Decided by: waiting for Joseph

## Context

S4.7 showed a backend could write 1 GB to its own folder with nothing stopping it. The server has one disk of 29 GB, so one backend could take down the platform and every other backend.

## Options considered

Measured on the live server, same attacks (`learnings/W4-evaluation-and-knowledge-base.md`, row 55):

- Limit on each file (`--ulimit fsize`, 200 MB): stopped a 1 GB file at exactly 200 MB, at once. Several smaller files got past it (750 MB).
- Watchdog every 5 seconds, 500 MB per backend: stopped many files in 7.5 s, at 996 MB. Covers total size, but only live backends.
- A true disk quota per backend: needs root on every deploy, or a reformatted disk. Not tried: too much for one server.

## Decision

Use both. The file limit applies in every container, including builds. The watchdog runs in the platform and stops any live backend holding more than 500 MB. Its data stays.

## Consequences

- One SQLite database cannot grow past 200 MB. That is far beyond what these clients need.
- A stopped backend gives a 502 until someone removes files. Nothing tells the client yet.
- The watchdog can overshoot by what a backend writes in 5 seconds, about 1 GB.

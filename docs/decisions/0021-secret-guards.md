# 0021. Guards against leaking the API key

- Status: Accepted
- Date: 2026-10-23
- Decided by: Joseph

## Context

The repo is public and all five members have the Claude API key. One commit of `.env`, or a key pasted into a file, would publish it and anyone could spend the credits.

## Options considered

- Rely on the written rules and `.gitignore`.
- Several layers that each catch what the others miss.

## Decision

Four layers:
1. Claude Code's `.claude/settings.json` blocks reading or editing `.env` and force-adding ignored files.
2. A pre-commit hook (`.githooks/pre-commit`, switched on once per clone with `git config core.hooksPath .githooks`) runs `scripts/check_secrets.py`: it blocks `.env`, anything that looks like an API or private key, model files and files over 5 MB. It also blocks a stale README status.
3. GitHub runs the same scan on every push, for anyone without the hook.
4. A pull request template with the handoff checklist.

## Consequences

- Tested Oct 23 on a copy with a fake key. A normal change and a doc that only mentions `sk-ant-` passed. A key pasted in markdown, a force-added `.env`, a model file, a stale README and a 7 MB file were all blocked. A key committed with `--no-verify` failed the GitHub scan. Claude Code refused to show the fake key, which appeared 0 times in its answer.
- Not airtight: a determined command can still read `.env` and the hook can be skipped. If a key is ever exposed, revoke it in the Anthropic console and make a new one.

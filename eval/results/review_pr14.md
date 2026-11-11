# Checking Eric's S6.1 results (PR #14, commit d1137c7)

Typed by hand from Joseph's review on Nov 10: a fresh clone of the branch on Joseph's Mac (uv 0.13.5, Docker). No Claude calls, $0.

| Claim in the PR | How it was checked | Result |
|---|---|---|
| Runtime 66 passed | `uv run pytest runtime -q` | 66 passed |
| Builder 75, web 6, marker 3 | `pytest builder`, `pytest web`, `pytest eval` | 75, 6, 3 passed |
| 96.0% against 84.0% recounts | Ran `part7/recompute.py`, compared with `recompute.txt` | Identical |
| `tables.md` and the audit | Regenerated tables, ran the audit, `git status` | No file changed; 105 of 105 |
| Harness on the references | Added up `harness_references.json` | 21 backends, 272 of 272 |
| Recipe search break test matches | Compared every value with `eval/results/replicated/break_search.json` | Only the `ms` timings differ |
| Hit rates match | 14 rows of `compare.txt` against `kb/compare.json` | 0 differ |
| Plain `uvicorn` fails, `python -m uvicorn` works | Started both | Fails with no `anthropic`; page 200 |
| Server is fine with plain `uvicorn` today | Read the running process on the server, checked its `anthropic` import | Works. The server has uv 0.13.7, the same version as Eric's Mac where it fails. Not explained |
| No personal data | Scanned added lines for home folders, emails, phone numbers, keys | None. "Eric" appears once, in `by_hand.txt` |

After merging `main` into the branch (no conflicts): 67 passed with Docker. With `SANDBOX=subprocess`: 57 passed, 10 skipped, the same with Docker unreachable. The branch's notes say 66, and 56 with 10 skipped.

Not re-run: the real church build ($0.14), Bernard's seven experiments apart from reading the saved `attacks.txt`, the recipe search itself. Not a fresh-machine test: the sandbox image was already on this Mac.

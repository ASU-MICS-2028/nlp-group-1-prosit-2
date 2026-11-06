# Audit: every learnings row against a saved file (Nov 6, 2026)

Every experiment row in every learnings file, checked. Michael's and Eric's files still hold only the template row. `eval/experiments/audit_numbers.py` checks 105 written numbers against the files automatically; all match. `eval/experiments/replicate_free.sh` re-runs everything free on a Mac, with the output in `replicated/`.

| Mark | Means |
|---|---|
| ✅ Re-run | Run again for free: same result |
| 🟰 File | The number matches a saved file. Not re-run, because it costs money or hours |
| ⏱️ Machine | Re-run on a Mac: same conclusion, different timings. The originals are from Bernard's Windows laptop or an earlier run |
| 🟡 | Partly backed: see the note |
| ⚪ | No numbers to check: reasoning or a lesson |

## Bernard (W2): 14 rows

| Row | Question | Mark | Evidence and notes |
|---|---|---|---|
| 1 | Path guard | ⏱️ | Method A: same, 5 attacks through. Method B: 0 on Windows; 2 on a Mac, both harmless (W4 row 6) |
| 2 | Flat list or tree | ✅ | Same: 15/15, 182/168 |
| 3 | Whole file or edit | ✅ | Same: 4,271 / 284 characters |
| 4 | Do files fit the 4,000 limit? | 🟡 **Out of date** | True then, for the church files only. **10 of 15 apps Opus built are over 4,000 characters** (largest 9,845). Tested: W4 row 36 |
| 5 | How much output to keep | ⏱️ | Start and end: 21/21 at every limit, same. Start only: 16–20/21 on a Mac, 14–20/21 on Windows |
| 6 | Pytest detail | ⏱️ | All 21/21. Sizes differ because file paths differ: `short` is about 40% smaller than `long` here, 35% there |
| 7 | Fixed or free port | ✅ | Same: one of two servers dies on a fixed port (which one varies), free ports both run |
| 8 | Knowing the server is ready | ⏱️ | All 10/10. On a Mac asking takes 0.23 s against 1.02 s for "sleep 1 s", so the choice holds more strongly |
| 9 | One-line reason first | 🟰 | `error_format.txt`: 21/21 each, $0.85 |
| 10 | Which Docker network | 🟡 | The winner is proved by a test that passes on re-run. Results for the other three options were not saved |
| 11 | Docker or subprocess | ⏱️ | Isolation the same, Docker blocks all four. A Mac is faster: Docker adds under 1 s, not 2–3 s |
| 12 | Test time limit | ⏱️ | Stops at 30.1/60.1/120.1 s with 0 containers left. Good runs 0.7 s on a Mac, 7.4 s on Windows |
| 13 | Attacks | ⏱️ | **Docker 14/16, identical.** Subprocess 4/16, not 5/16: on a Mac it can also see the Docker control socket |
| 14 | Prompt injection | 🟰 | `prompt_injection.txt`: canary leaked 0 of 9, $0.57 |

Files: `runtime/experiments/results/` (originals), `replicated/` (re-runs). Bernard's 51 tests: passed on Mac and server; subprocess mode 44 passed, 7 skipped.

## Alice (W1): 12 rows

Every score matches its file (`harness/s3*.json`). **Her cost and time figures are not in any file yet**: they are in each build's `run.json` on her laptop (requested, Nov 6).

| Row | Question | Mark | Scores checked | Still needs her `run.json` |
|---|---|---|---|---|
| 1 | Which prompt | 🟰 | A 87.5, B 87.0, C 88.5, D 86.5; 12/10/11/11 tasks | Cost, time, 109 requests in D |
| 2 | Run record | 🟡 | Free tests pass (76) | 11.5 KB trace, 7 lines |
| 3 | Repairs | 🟰 | 87.0 for all, 33/45 | Cost, 66 s, "0 repairs used" |
| 4 | Plan v1 | 🟰 | 74.5, 24/45 | Cost, time, follows plan |
| 5 | Plan v2 | 🟰 | 82.8, 24/45 | Cost, time |
| 6 | Questions, vague tasks | 🟰 | 64.0, 77.2, 68.4 | Cost; "momo 1/13" per task |
| 7 | Questions, all 15 | 🟰 | 95.8, 39/45 | Cost, 37 s |
| 8 | Recipe search | 🟰 | 92.7, 39/45 | "2 searches in 15 builds", cost |
| 9 | Edit or rebuild | 🟰 | 10, 11, 10, 13 | Cost, time, number of edits |
| 10 | **One agent or split (multi-agent)** | 🟰 | **95.8 vs 84.4**, 39 and 30 of 45 | Cost ($1.90 vs $4.06), 67 s, "0 repairs" |
| 11 | Opus or Qwen | 🟰 | 85.2 vs 0 on 5 easy tasks | Time, turns, crash reasons |
| 12 | Qwen with search | 🟰 | 59.0 | 155 min, what it searched for |

No build's score changed between its 3 repeats, in any of her files. Her 51 agent tests pass on re-run.

## Joseph (W4): 33 rows

| Row | Question | Mark | Evidence and notes |
|---|---|---|---|
| 1 | Handoff from a fresh copy | ✅ | 51 passed; 44 passed, 7 skipped |
| 2 | Docker trouble | ✅ | `handoff_checks.json`: never runs unprotected. Image-missing check uses a fake image name |
| 3 | Side by side | 🟡 **Corrected** | Both 10/10, nothing left. **The speed gain did not repeat**: 2.6 s against 2.9 s. Row 18 is the better evidence |
| 4 | Broken backends | ✅ | Same, 1.0–1.1 s |
| 5 | Left behind | ✅ | Same: 0, then 2 containers and 1 network; cleanup removed them |
| 6 | Path guard on a Mac | ✅ | Same |
| 7 | Tests are right | ✅ **Corrected** | 15/15, 75/75. "No flaky tests" was wrong: see row 35 |
| 8 | Tests per broken copy | ✅ | Median 1 |
| 9 | Fairness judge | 🟰 | `fairness.json`: 6 of 192. The "3 repeats" and "11 of 12 builds" figures have no file |
| 10 | Who writes the map | 🟰 | `mapping.json`: Opus 21, Haiku 10. Earlier Haiku 13 has no file |
| 11 | Builder sees operations | 🟰 ✅ | 89/79 and 99/100; all 66 builds re-scored identically, twice |
| 12 | Tool flaws | 🟡 **Corrected** | library, hostel, shared match. Restaurant was 5→12, not 2→12; tailoring 4→13, not 5→13. Interim 79% vs 78% has no file |
| 13 | Mapper prompt change | 🟡 | The 20/21 interim has no file; final 21/21 in `mapping.json` |
| 14 | Difficulty tiers | 🟰 | All 6 match |
| 15 | Real build mistakes | 🟰 | `baseline_failing.json` |
| 16 | Helper agents | ⚪ | Lessons only |
| 17 | Qwen in one call | 🟰 | 2/15, 2/192; 43 and 88 min match. Cause of the score change: possibly row 35, not confirmed |
| 18 | Workers | ⏱️ | Files match. Re-run 44, 19, 12, 12, 12 s; originals 51, 24, 13, 11 s; 272/272 every time |
| 19 | Stable scores | ✅ | 105 of 105 again |
| 20 | Bad backends | ✅ | Same scores. Killed run left 2 containers this time, 8 before: depends when it is killed |
| 21 | Harness vs baseline | ✅ | 66/66 identical |
| 22 | Recipes | ✅ | 18/18. First-try 17/18 has no file |
| 23 | Test questions | ✅ **Corrected** | 111. 6 written as no-answer, 10 in all with no right recipe |
| 24 | Search methods | ✅ **Corrected** | Identical on re-run. bge-small 90%, 89% with prefix; text-only wording fixed |
| 25 | "No recipe fits" | ✅ **Corrected** | 66 vs 62 is MiniLM only; BM25 54 vs 53 |
| 26 | What breaks search | ✅ | `break_search.json`: same. Timings vary: 26 ms and 4.8 s now, 175 ms and 7 s then |
| 27 | Recipes in builds | 🟰 | 2, 9, 7 start; 2, 35, 19 tests; $0.39 |
| 28 | Where to host | ⚪ | Reasoning |
| 29 | Hosting | ✅ | `hosting_check.json`: 24/24 twice |
| 30 | Crash | 🟡 | `crash_test.json`, typed by hand; church 30/30 re-scored |
| 31 | Mid-build messages | ⚪ | Reasoning |
| 32 | Whole journey | 🟰 | `sessions/animal_shelter.jsonl` |
| 33 | Through the page | 🟰 | `sessions/bakery_through_the_page.jsonl`, `browser_check/` |

## Repo setup: 7 rows

Behaviour checks of coding assistants and guides (`learnings/00-repo-setup.md`). No result files, and they are about how we work, not the platform. Not re-run: use them in the report only as a description.

## Open items

1. **Alice's `run.json` files** back every cost and time figure in her rows. Until they arrive, those numbers rest on her write-up alone.
2. **Files over the read limit: tested and fixed (W4 row 36, decision 0052).** Same results, about half the turns and 18% cheaper with no cut. `read_file` now returns up to 20,000 characters.
3. **No file:** the interim numbers listed above (rows 9, 10, 12, 13, 22). They are history, and re-running them would need old versions of the tool, so do not quote them in the report as measured results without saying so.

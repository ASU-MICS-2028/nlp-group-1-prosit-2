# Every test result, for the report and the slides

Rule (decision 0051): a result that is not saved here does not count. Details and explanations: `learnings/W4-*.md` and `learnings/W1-*.md`, section 3.

Each `harness/*.json` has one row per backend per repeat: `task`, `passed`, `total`, `started`, `failing` (test names), `error`, `seconds`. Score = sum of `passed` / sum of `total`.

## The agent

| Question | Files in `harness/` | Result | Decision |
|---|---|---|---|
| **One agent or several (multi-agent)?** | `s38_list_all` (one agent with questions) · `s36_split` (Planner / Builder / Tester) | **95.8%** vs **84.4%** | 0044 |
| Which system prompt? | `s32_A` `s32_B` `s32_C` `s32_D` | B: 87.0% | 0038 |
| Do repairs help? | `s34_r0` `s34_r1` `s34_r3` `s34_r5` | 87.0% for all: the loop never ran | 0040 |
| Plan first? | `s35` (v1) · `s35v2` (v2) | 74.5% · 82.8% | 0041 |
| Ask the client questions? | `s38_list_all`, `s38_none1`, `s38_list1-3`, `s38_brief1-3` | 95.8% with questions on all 15 | 0042 |
| Recipe search with Opus? | `s37_search` | 92.7%, searched only twice | 0043 |
| Local Qwen? | `s39_qwen` · `s39_qwen_search` (5 easy tasks ran; the rest count as 0) | 0% · 59.0% on those 5 | 0046 |
| Edit or rebuild on a change? | `s310_change` · `s310_rebuild` | see decision | 0045 |

## The baseline and the benchmark

| Question | Files | Result |
|---|---|---|
| One LLM call, no agent | `baseline_v2.json` (final) · `baseline.json` (before the tool fixes) · `baseline_failing.json` | Opus 89%, Haiku 79% |
| Local Qwen in one call, with and without recipes | `baseline_local_nothink.json` · `baseline_local_think.json` · `baseline_local_recipes_fixed.json` · `baseline_local_recipes_search.json` | 1% · 1% · 18% · 10% |
| Are the tests right? | `../../benchmark/validation.json` | all 15 tasks valid, 75 of 75 broken copies caught |
| Is the measuring fair? | `fairness.json` · `mapping.json` | W4 rows 9, 10, 12 |
| Recipe search methods | `../../kb/compare.json` | top 3: dense 95%, BM25 74%, random 17% |

## The harness and the live platform

| Question | Files | Result |
|---|---|---|
| Harness on bad backends | `harness_failures.json` | all handled safely |
| Is hosting working and locked in? | `hosting_check.json` | 24 of 24 |
| Tests on the Linux server | `server_tests.txt` · `harness/references_on_server.json` | 51 of 51 · 272/272 |
| A real agent build, live, on hidden tests | `harness/church_live_build.json` · `sessions/church_live_build_run.json` | 30/30 |
| Data after the server goes down | `crash_test.json` | normal reboot kept; plug pulled 5 s after a write lost |
| Whole journey with a message during the build | `sessions/animal_shelter.jsonl` | live; colour added but optional |
| Whole journey through the public page in Chrome | `sessions/bakery_through_the_page.jsonl` · `browser_check/*.png` | live, no page errors. Screenshots are from before three small page fixes |

## Not here

The apps themselves are in `projects/`, which git ignores. So is each build's `run.json` (its time and cost), and those live on the laptop that ran them.

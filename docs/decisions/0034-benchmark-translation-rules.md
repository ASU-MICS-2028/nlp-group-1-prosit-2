# 0034. What the benchmark's name translation handles, and how a change to it is checked

- Status: Accepted
- Date: 2026-10-27
- Decided by: Joseph

## Context

Hidden tests call operations by name and `benchmark/conftest.py` translates them to each backend's own paths and field names (decisions 0007, 0031). The baseline showed that the first version failed correct backends: library 3/13 and hostel 2/15 were correct builds. Each failure was traced to something the translation could not express.

## Options considered

- Keep the simple translation (one name map, used both ways) and accept lower scores for backends that make other valid choices.
- Extend the translation each time a correct backend is failed, and check every change on all saved results.

## Decision

The translation handles seven things, each found from a real build:
1. A field named differently going in and coming out (`request_fields`, `response_fields`).
2. A value the tests send in the path that the backend wants in the body, or in the query string for GET.
3. A placeholder in the backend's path filled from the body or the query string (a date filter in the path).
4. Nested vs flat fields (dotted names: `measurements.chest`).
5. A reply wrapped in another field (`response_key`).
6. One reply field that the tests read under two names (the table number is both `id` and `number`).
7. The reverse of 4, in replies: the backend nests what the test reads flat (money as `{"cedis": 5, "pesewas": 500}`; dotted backend name `balance.cedis`).

It also never changes the test's own data: values are moved on a copy. (Before that, tests that reuse one dict sent empty measurements from the second call on.)

Every change to the translation is checked by re-running `benchmark/validate.py` on all 15 tasks, then re-scoring every saved build with its saved map. Both are free. A change is kept only if no task breaks and no saved score drops.

## Consequences

- Scores now fail builds for behaviour, not for interface choices the request left open.
- Points 6 and 7 and the copy fix turned three "failed" Opus builds into full passes (restaurant 2→12/12, tailoring 5→13/13, shared expenses 1→13/13), which changed the result from "Haiku is as good as Opus" to Opus 89% vs Haiku 79%. A measuring tool's bugs can reverse a conclusion.
- Before point 6 was fixed, the same build with the same map scored 2/12 or 12/12 depending only on the order of two names in the map. Always re-score saved builds after a tool change: that is how this was found.
- A translation that can express more can also hide real mistakes. Each new rule only renames or moves values; it never changes a value or a status code.

# 0036. Recipes never use the benchmark's topics

- Status: Accepted
- Date: 2026-10-29
- Decided by: Joseph

## Context

The agent will search the recipe knowledge base (`kb/recipes/`) while it builds. If a recipe showed, say, a church event with a capacity, it would hand the agent the answers to that task's hidden tests: the same leak as showing it the operations list (decision 0033).

## Options considered

- Recipes written around the benchmark's own topics (closest to what the agent needs, but leaks the hidden tests).
- Recipes that teach the same techniques on unrelated made-up topics (notes, rooms, workshops, shirts).

## Decision

Every recipe teaches one technique on a topic that is not one of the 15 benchmark tasks. Each recipe's code and its check run inside the sandbox image (`kb/check_recipes.py`, 18/18 pass), so the examples work on exactly the library versions a build gets.

## Consequences

- Scores with recipes measure whether the agent can apply a technique, not whether it copied an answer.
- Anyone adding a recipe must check it against the task list in `benchmark/` and run `kb/check_recipes.py`.
- Ghanaian words (cedis, pesewas, susu) may appear when they explain a technique (money in pesewas), but never a benchmark task's rules.

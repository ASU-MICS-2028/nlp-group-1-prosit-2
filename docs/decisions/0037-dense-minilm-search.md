# 0037. search_docs uses dense search (all-MiniLM-L6-v2) and returns the top 3

- Status: Accepted
- Date: 2026-10-29
- Decided by: Joseph

## Context

`search_docs` (kb/search.py) finds recipes for the agent. The instructor expected dense retrieval and told us to defend BM25 if we chose it (lecture 4). We measured instead of assuming: 111 labelled questions (60 written by Haiku from the benchmark requests without seeing the recipes, 14 real crash messages, 37 hand-written hard cases), 13 methods (`kb/compare.py`, results in `kb/compare.json`).

## Options considered

| Method | Right recipe first | Right recipe in top 3 | ms per search |
|---|---|---|---|
| No search (random) | 5% | 17% | 0 |
| BM25 (keyword, our own 20 lines) | 58% | 74% | 0.03 |
| Dense all-MiniLM-L6-v2 (22M) | 68% | **95%** | 5 |
| Dense bge-small (33M), with its query prefix | 68% | 89% | 10 |
| Dense bge-base (110M) | 69% | 89% | 13 |
| Hybrid BM25 + MiniLM | **72%** | 87% | 6 |

BM25 is best on crash messages and Ghanaian words (exact words match); dense is best on reworded and planning questions.

## Decision

`search_docs(query, k=3)` uses dense search with all-MiniLM-L6-v2 by default: the agent reads 3 recipes, and that is where dense is clearly best (95% vs 74% for BM25). `method="bm25"` (no extra install) and `method="hybrid"` (best when only the first result is used) stay available.

## Consequences

- Needs `uv run --extra kb` (sentence-transformers, which pulls in PyTorch); a clear error says so if it is missing. The model (about 90 MB) downloads on first use; the first search takes about 7 s, later ones about 5 ms.
- No method can tell reliably that no recipe fits (a score cutoff is right 66% of the time vs 62% for always answering), so the agent must judge whether the recipes apply.
- 101 answerable questions: differences of 3–4 points are 3–4 questions and are not meaningful. The 95% vs 74% gap is.
- Twi questions return noise with every method; French and Pidgin mostly work with dense search.

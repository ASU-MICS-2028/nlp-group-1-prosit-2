"""search_docs: find the recipes (kb/recipes/*.md) that answer a question.

    from kb.search import search_docs
    search_docs("how do I stop double bookings?", k=3)   # -> [{"id": "15", "title": ..., "score": ..., "text": ...}, ...]

method="dense" (default) ranks by meaning with a small embedding model (all-MiniLM-L6-v2, about 90 MB, downloaded on first
use; needs `uv run --extra kb`). method="bm25" is keyword search, written out below, with no extra install.
method="hybrid" merges the two rankings. On 111 labelled questions (kb/compare.py): a right recipe is in the top 3 for
dense 95%, hybrid 87%, bm25 74% (decision 0037). No method can tell reliably that no recipe fits: judge the results.
"""

import math
import pathlib
import re
from collections import Counter
from functools import lru_cache

RECIPES = pathlib.Path(__file__).parent / "recipes"
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def recipes():
    out = []
    for p in sorted(RECIPES.glob("*.md")):
        text = p.read_text()
        out.append({"id": p.name[:2], "title": text.splitlines()[0].lstrip("# "), "text": text})
    return out


def words(text):
    """Lower-case words and numbers, in any alphabet (réservation, pɛ). Code names are split: check_same_thread ->
    check, same, thread."""
    return re.findall(r"[^\W_]+", text.lower())


class BM25:
    """Okapi BM25. A word counts more when it is frequent in this recipe (tf, with diminishing returns set by k1),
    rare across recipes (idf), and the recipe is not unusually long (b)."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [Counter(words(d)) for d in docs]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / len(self.docs)
        n = len(self.docs)
        df = Counter(w for d in self.docs for w in d)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = words(query)
        out = []
        for d, length in zip(self.docs, self.lengths):
            norm = self.k1 * (1 - self.b + self.b * length / self.avg)
            out.append(sum(self.idf.get(w, 0) * d[w] * (self.k1 + 1) / (d[w] + norm) for w in q if w in d))
        return out


@lru_cache
def _bm25():
    return BM25([r["text"] for r in recipes()])


@lru_cache
def _dense(model=DENSE_MODEL):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError("dense search needs sentence-transformers: uv run --extra kb ..., "
                          "or use method='bm25'") from None
    m = SentenceTransformer(model)
    return m, m.encode([r["text"] for r in recipes()], normalize_embeddings=True)


def dense_scores(query, model=DENSE_MODEL):
    m, docs = _dense(model)
    return (docs @ m.encode([query], normalize_embeddings=True)[0]).tolist()  # cosine similarity


def ranked(scores):
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def search_docs(query, k=3, method="dense"):
    """The k best recipes for the query, best first. An empty or wordless query returns []."""
    if not words(query):
        return []
    if method == "bm25":
        scores = _bm25().scores(query)
    elif method == "dense":
        scores = dense_scores(query)
    elif method == "hybrid":  # reciprocal rank fusion: add 1/(60 + rank) from each ranking
        scores = [0.0] * len(recipes())
        for s in (_bm25().scores(query), dense_scores(query)):
            for rank, i in enumerate(ranked(s)):
                scores[i] += 1 / (60 + rank)
    else:
        raise ValueError(f"unknown method {method!r}")
    return [{**recipes()[i], "score": round(scores[i], 4)} for i in ranked(scores)[:k] if scores[i] > 0]


if __name__ == "__main__":
    import sys

    for r in search_docs(" ".join(sys.argv[1:]) or "primary key"):
        print(r["id"], r["score"], r["title"])

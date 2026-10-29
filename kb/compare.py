"""Compare ways of finding recipes on the 111 labelled questions (kb/questions.json). Free: everything runs locally.

    uv run --extra kb python -m kb.compare
Writes kb/compare.json. Measures (on questions that have an answer):
  hit@1  the first result is a right recipe     hit@3  a right recipe is in the top 3
  mrr    1 / position of the first right recipe, averaged (1 = always first, 0.5 = usually second)
  refuse the best share of right "answer / no recipe fits" decisions, using a cutoff on the top score
"""

import json
import pathlib
import time

from kb import search

HERE = pathlib.Path(__file__).parent
QUESTIONS = json.loads((HERE / "questions.json").read_text())
BGE_PREFIX = "Represent this sentence for searching relevant passages: "  # what the bge authors advise for queries
SHORT = [r["text"].split("```")[0] for r in search.recipes()]  # title and explanation, without the code


def bm25(docs, **kw):
    index = search.BM25(docs, **kw)
    return lambda q: index.scores(q)


def dense(model, docs, prefix=""):
    from sentence_transformers import SentenceTransformer

    m = SentenceTransformer(model)
    d = m.encode(docs, normalize_embeddings=True)
    return lambda q: (d @ m.encode([prefix + q], normalize_embeddings=True)[0]).tolist()


def hybrid(a, b):
    def f(q):
        out = [0.0] * len(search.recipes())
        for s in (a(q), b(q)):
            for rank, i in enumerate(search.ranked(s)):
                out[i] += 1 / (60 + rank)
        return out
    return f


def evaluate(fn):
    ids = [r["id"] for r in search.recipes()]
    rows, start = [], time.time()
    for q in QUESTIONS:
        s = fn(q["q"])
        order = [ids[i] for i in search.ranked(s)]
        pos = next((n for n, i in enumerate(order, 1) if i in q["relevant"]), None)
        rows.append({**q, "top": order[:3], "top_score": max(s), "pos": pos})
    ms = (time.time() - start) / len(QUESTIONS) * 1000
    ans = [r for r in rows if r["relevant"]]
    res = {"hit@1": sum(r["pos"] == 1 for r in ans) / len(ans), "hit@3": sum(bool(r["pos"]) and r["pos"] <= 3 for r in ans) / len(ans),
           "mrr": sum(1 / r["pos"] for r in ans if r["pos"]) / len(ans), "ms_per_query": round(ms, 2)}
    best = (0, None)
    for t in sorted({r["top_score"] for r in rows}):  # cutoff: answer only when the top score is at least t
        right = sum((r["top_score"] >= t and r["pos"] == 1) if r["relevant"] else r["top_score"] < t for r in rows)
        best = max(best, (right / len(rows), t))
    res["refuse"], res["cutoff"] = best
    res["by_kind_hit@1"] = {k: round(sum(r["pos"] == 1 for r in ans if r["kind"] == k) / max(1, sum(r["kind"] == k for r in ans)), 2)
                            for k in sorted({r["kind"] for r in ans})}
    return res, rows


def main():
    import random

    random.seed(0)
    full = [r["text"] for r in search.recipes()]
    methods = {
        "random (no search)": lambda q: [random.random() for _ in full],
        "bm25 full recipe": bm25(full),
        "bm25 text only (no code)": bm25(SHORT),
        "bm25 k1=1.2 b=0.5": bm25(full, k1=1.2, b=0.5),
        "dense MiniLM-L6 (22M)": dense("sentence-transformers/all-MiniLM-L6-v2", full),
        "dense bge-small (33M)": dense("BAAI/bge-small-en-v1.5", full),
        "dense bge-small text only": dense("BAAI/bge-small-en-v1.5", SHORT),
        "dense bge-base (110M)": dense("BAAI/bge-base-en-v1.5", full),
        "dense bge-small + query prefix": dense("BAAI/bge-small-en-v1.5", full, BGE_PREFIX),
        "dense bge-base + query prefix": dense("BAAI/bge-base-en-v1.5", full, BGE_PREFIX),
    }
    methods["hybrid bm25 + bge-small"] = hybrid(methods["bm25 full recipe"], methods["dense bge-small (33M)"])
    methods["hybrid bm25 + bge-base"] = hybrid(methods["bm25 full recipe"], methods["dense bge-base (110M)"])
    methods["hybrid bm25 + MiniLM"] = hybrid(methods["bm25 full recipe"], methods["dense MiniLM-L6 (22M)"])
    methods["hybrid bm25 + bge-small prefix"] = hybrid(methods["bm25 full recipe"], methods["dense bge-small + query prefix"])
    out = {}
    for name, fn in methods.items():
        res, rows = evaluate(fn)
        out[name] = {"summary": res, "rows": rows}
        print(f"{name:32} hit@1 {res['hit@1']:.2f}  hit@3 {res['hit@3']:.2f}  mrr {res['mrr']:.2f}  refuse {res['refuse']:.2f}  "
              f"{res['ms_per_query']:>6} ms  {res['by_kind_hit@1']}", flush=True)
    (HERE / "compare.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()

"""S4.8: how plain is the summary the client reads? Same 15 builds for each rewrite. About $0.20 of Claude.
Writes eval/results/plain_summary.json.

    uv run --env-file .env --with anthropic python -m builder.experiments.plain_summary
"""

import json
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

from builder.agent import plain_summary

R = pathlib.Path("eval/results")
TECHNICAL = re.compile(r"`|(?<![a-zA-Z])/[a-z{]|\.py\b|\.db\b|\{\"|\b(?:GET|POST|PUT|PATCH|DELETE)\b|\b(?:4\d\d)\b|(?i:\b(?:endpoints?|api|sqlite|sqlmodel|"
                       r"fastapi|json|http|pytest|database|server|schema|field|query|parameters?|uuid|integer|boolean)\b)")


def words(text):
    return TECHNICAL.findall(text)


def new_numbers(text, notes):
    """Numbers in the rewrite that the notes do not have: the rewrite may have made them up."""
    return sorted(set(re.findall(r"\d+(?:[.:]\d+)?", text)) - set(re.findall(r"\d+(?:[.:]\d+)?", notes)))


def saved(folder):
    return {f.parent.name: json.loads(f.read_text()) for f in sorted(folder.glob("*/run.json"))}


fresh, prompt_e = saved(R / "fresh1"), saved(R / "runs/s48_all")
out = {"no rewrite (as live today)": {t: {"summary": r["summary"], "cost_usd": 0} for t, r in fresh.items()},
       "prompt change (Alice's s48_all, different builds)": {t: {"summary": r["summary"], "cost_usd": 0} for t, r in prompt_e.items()}}
for name, model in (("rewrite, Haiku", "claude-haiku-5-5"), ("rewrite, Opus", "claude-opus-5-5")):
    def one(item):
        task, r = item
        text, usd = plain_summary(r["request"], r["summary"], model)
        return task, {"summary": text, "cost_usd": usd}
    with ThreadPoolExecutor(5) as ex:
        out[name] = dict(ex.map(one, fresh.items()))
table = {name: {"summaries": len(rows), "with_technical_words": sum(bool(words(r["summary"])) for r in rows.values()),
                "technical_words": sum(len(words(r["summary"])) for r in rows.values()), "avg_characters": round(sum(len(r["summary"]) for r in rows.values()) / len(rows)),
                "numbers_not_in_notes": {t: n for t, r in rows.items() if name.startswith("rewrite") and (n := new_numbers(r["summary"], fresh[t]["summary"]))},
                "says_not_live": [t for t, r in rows.items() if re.search(r"not (?:yet )?(?:been )?(?:run|live)|live, running|Nobody has", r["summary"])],
                "cost_usd": round(sum(r["cost_usd"] for r in rows.values()), 3), "found": sorted({w.lower() for r in rows.values() for w in words(r["summary"])})[:25]}
         for name, rows in out.items()}
(R / "plain_summary.json").write_text(json.dumps({"table": table, "summaries": out}, indent=2) + "\n")
print(json.dumps(table, indent=1))

"""Questions an agent would really search for: Haiku reads each benchmark request (never the recipes) and writes the
how-to questions it would look up while building it. About $0.01. Writes kb/agent_questions.json (labelled by hand after).

    uv run --env-file .env --with anthropic python -m kb.agent_questions
"""

import json
import pathlib

from eval import bench
from eval.llm import SPENT, ask

SYSTEM = """You are about to build this client's backend as one FastAPI + SQLModel + SQLite file. Before writing code you
can search a how-to knowledge base of short coding recipes. Write the 4 searches you would type, each a short question
about HOW to implement something technical (not about the client's business). Reply in the field questions."""
SCHEMA = {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
          "required": ["questions"], "additionalProperties": False}

out = []
for name in bench.task_names():
    text, _ = ask("claude-haiku-5-5", SYSTEM, bench.load(name)["request"], schema=SCHEMA, effort="low", max_tokens=1000)
    out += [{"task": name, "question": q} for q in json.loads(text)["questions"]]
pathlib.Path(__file__).with_suffix(".json").write_text(json.dumps(out, indent=1) + "\n")
print(len(out), "questions", f"${SPENT['usd']:.4f}")

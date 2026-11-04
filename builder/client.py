"""Pretend clients for benchmark tasks (S3.8): they answer the agent's questions, so no person is needed.

    from builder.client import answer
    answers, cost = answer("school_grades_gpa", ["What grading scale do you use?"], "brief")

"answers" picks from the client's prepared answers (benchmark/<task>/answers.json); "brief" plays the client from
everything they want (client_brief.md). Both use Haiku, which is cheap and the same judge for both. Decision 0033: the
agent may see these files only as answers to the questions it asked.
"""

import json

from eval import bench
from eval.llm import ask

MODEL = "claude-haiku-5-5"
NONE = "No preference: you decide."
FROM_LIST = f"""You answer questions for a client. You get the client's prepared answers and some questions. For each
question, give the prepared answer that answers it, word for word. If none does, answer exactly "{NONE}" """
FROM_BRIEF = f"""You are the client. Below is everything you want. Answer each question briefly, in plain words, using
only these details. Never mention tests or this text. If the details do not cover a question, answer exactly "{NONE}" """
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answers"],
          "properties": {"answers": {"type": "array", "items": {"type": "string"}}}}


def answer(task, questions, mode):
    """One answer per question, in order. Returns (answers, cost in US dollars)."""
    if not questions:
        return [], 0.0
    system, name = (FROM_LIST, "answers.json") if mode == "answers" else (FROM_BRIEF, "client_brief.md")
    try:
        facts = (bench.BENCH / task / name).read_text()
    except FileNotFoundError:  # nothing prepared: the client has no preference
        return [NONE] * len(questions), 0.0
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    text, info = ask(MODEL, system, f"{facts}\n\nQuestions:\n{numbered}\n\nOne answer per question, in order.",
                     schema=SCHEMA)
    got = json.loads(text)["answers"]
    return (got + [NONE] * len(questions))[:len(questions)], info["cost_usd"]  # exactly one answer per question

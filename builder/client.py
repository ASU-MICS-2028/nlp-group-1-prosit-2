"""A pretend client for benchmark tasks: it answers the agent's questions, so no person is needed.

    from builder.client import answer
    answers, usd = answer("school_grades_gpa", ["What grading scale do you use?"])

Haiku picks, for each question, the matching answer the client prepared (benchmark/<task>/answers.json). Decision 0033:
the agent may see that file only as answers to the questions it asked.
"""

import json

from builder.llm import ask
from eval import bench

MODEL = "claude-haiku-5-5"
NONE = "No preference: you decide."
SYSTEM = f"""You answer questions for a client. You get the client's prepared answers and some questions. For each
question, give the prepared answer that answers it, word for word. If none does, answer exactly "{NONE}" """
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answers"],
          "properties": {"answers": {"type": "array", "items": {"type": "string"}}}}


def answer(task, questions):
    """One answer per question, in order. Returns (answers, cost in US dollars)."""
    if not questions:
        return [], 0.0
    try:
        prepared = (bench.BENCH / task / "answers.json").read_text()
    except FileNotFoundError:  # nothing prepared: the client has no preference
        return [NONE] * len(questions), 0.0
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    text, usd = ask(MODEL, SYSTEM, f"{prepared}\n\nQuestions:\n{numbered}\n\nOne answer per question, in order.", schema=SCHEMA)
    got = json.loads(text)["answers"]
    return (got + [NONE] * len(questions))[:len(questions)], usd  # exactly one answer per question

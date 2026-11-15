"""Calling Claude: one client, the prices, and ask() for single questions (questions, plans, summaries, the marker's name maps).

    from builder.llm import ask
    text, usd = ask("claude-opus-5-5", system, user, schema=None)

A schema (a JSON schema dict) turns on structured output: the reply is guaranteed to be JSON of that shape.
"""

import os

import anthropic

PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}  # US$ per million tokens in/out (Oct 2026)
_client = None


def create(model, **args):
    """One request to Claude. Opus gets the server-side fallback, so a refused reply is retried on another model."""
    global _client
    if not _client:
        if not os.environ.get("LLM_API_KEY"):  # the agent reports this as an error instead of crashing
            raise anthropic.AnthropicError("LLM_API_KEY is not set: run with --env-file .env")
        _client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], max_retries=4)
    if model.startswith("claude-opus"):
        return _client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", model=model, **args)
    return _client.messages.create(model=model, **args)


def cost(model, u):
    """US dollars for one reply: new input, cache writes (1.25x), cache reads (0.1x), output."""
    price_in, price_out = PRICES[model]
    written = getattr(u, "cache_creation_input_tokens", 0) or 0
    read = getattr(u, "cache_read_input_tokens", 0) or 0
    return (u.input_tokens * price_in + written * price_in * 1.25 + read * price_in * 0.1 + u.output_tokens * price_out) / 1e6


def ask(model, system, user, schema=None, effort="medium"):
    """One question, one answer. Returns (the reply's text, cost in US dollars)."""
    config = {"effort": effort}
    if schema:
        config["format"] = {"type": "json_schema", "schema": schema}
    r = create(model, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}], output_config=config)
    return "".join(b.text for b in r.content if b.type == "text"), cost(model, r.usage)

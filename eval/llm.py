"""One small helper for every W4 experiment that calls Claude.

    from eval.llm import ask
    text, info = ask("claude-opus-5-5", system, user, effort="medium", schema=None)

- Opus uses server-side refusal fallbacks ("default"); Haiku has none, so a refusal is just recorded.
- schema (a JSON schema dict) turns on structured output: the reply is guaranteed valid JSON.
- info holds tokens, cost in US dollars (from the API's own token counts) and stop_reason.
- "qwen3.5-9b-local" goes to the llama.cpp server on this laptop (knowledge/environment.md), free; LOCAL_THINKING=0 turns thinking off.
- Every call is added to SPENT; going over BUDGET_USD stops the experiment before the next call.
Run with: uv run --env-file .env --with anthropic python <script>
"""

import os

import anthropic
import httpx

PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-haiku-5-5": (0.10, 0.50), "qwen3.5-9b-local": (0, 0)}  # US$ per million tokens in/out (Oct 2026)
BUDGET_USD = float(os.environ.get("BUDGET_USD", "8"))
SPENT = {"usd": 0.0, "calls": 0}
_client = None


def ask(model, system, user, effort="medium", schema=None, max_tokens=16000):
    global _client
    if model.endswith("-local"):
        return _ask_local(system, user, schema, max_tokens)
    if SPENT["usd"] >= BUDGET_USD:
        raise RuntimeError(f"Budget of ${BUDGET_USD} reached after {SPENT['calls']} calls; stopping")
    _client = _client or anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], max_retries=4)
    args = dict(model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}], output_config={"effort": effort})
    if schema:
        args["output_config"]["format"] = {"type": "json_schema", "schema": schema}
    if model.startswith("claude-opus"):
        r = _client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **args)
    else:
        r = _client.messages.create(**args)
    u = r.usage
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    price_in, price_out = PRICES[model]
    cost = (u.input_tokens * price_in + cache_read * price_in * 0.1 + u.output_tokens * price_out) / 1e6
    SPENT["usd"] += cost
    SPENT["calls"] += 1
    text = "".join(b.text for b in r.content if b.type == "text")
    info = {"model": r.model, "stop_reason": r.stop_reason, "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens, "cost_usd": round(cost, 5)}
    return text, info


def _ask_local(system, user, schema, max_tokens):
    """The same call against llama.cpp's OpenAI-style API. A schema becomes a grammar, so the reply is valid JSON."""
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": os.environ.get("LOCAL_THINKING", "1") != "0"}}
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"schema": schema}}
    r = httpx.post(os.environ.get("LOCAL_URL", "http://localhost:8090/v1/chat/completions"), json=body, timeout=3600).json()
    choice, u = r["choices"][0], r["usage"]
    stop = {"stop": "end_turn", "length": "max_tokens"}.get(choice["finish_reason"], choice["finish_reason"])
    SPENT["calls"] += 1
    return choice["message"]["content"], {"model": "qwen3.5-9b-local", "stop_reason": stop, "input_tokens": u["prompt_tokens"],
                                          "output_tokens": u["completion_tokens"], "cost_usd": 0.0}

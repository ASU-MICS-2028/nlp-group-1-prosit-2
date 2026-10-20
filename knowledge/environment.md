# Environment and setup

## What you need

| Tool | Why | Check it works |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Installs Python and the dependencies (we used it in Prosit 1 too) | `uv --version` |
| Python 3.12 or newer | uv can install it for you | `uv run python --version` |
| Docker Desktop, running | The sandbox that runs generated code | `docker run --rm hello-world` |
| Git + GitHub access to `ASU-MICS-2028` | The repo | `git clone https://github.com/ASU-MICS-2028/nlp-group-1-prosit-2` |
| An LLM API key | The agent. Provider not chosen yet (see `docs/DECISIONS.md`) | — |

## Setup

```
git clone https://github.com/ASU-MICS-2028/nlp-group-1-prosit-2
cd nlp-group-1-prosit-2
uv sync
cp .env.example .env      # put the API key here; .env is git-ignored, never commit it
```

Check the setup by running the worked benchmark example against its reference backend:

```
uv run uvicorn --app-dir benchmark/church_signup/reference app:app --port 8001 &
BASE_URL=http://127.0.0.1:8001 OPS_FILE=benchmark/church_signup/reference/ops.json uv run pytest benchmark/church_signup
# expect: 10 passed
```

## Dependencies

Only `fastapi`, `uvicorn`, `sqlmodel`, `httpx` and `pytest` so far (`pyproject.toml`; exact versions in `uv.lock`). Add a dependency with `uv add <name>`, and record in your learnings file why you needed it and what else you tried.

## Notes

- The known setup is macOS on Apple Silicon (arm64). Windows and Linux should work, but nobody has checked yet. If you find a difference, write it here.
- The `NLP-GROUP-1/data/models/` folder on the Drive holds only the configs and tokenizers of Qwen2.5-0.5B and SmolLM2-135M from Prosit 1, without the weights. It cannot be used as a local LLM as it stands.

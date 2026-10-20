# Environment and setup

## What you need

| Tool | Why | Check it works |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Installs Python and the dependencies (we used it in Prosit 1 too) | `uv --version` |
| Python 3.12 or newer | uv can install it for you | `uv run python --version` |
| Docker Desktop, running | The sandbox that runs generated code | `docker run --rm hello-world` |
| Git + GitHub access to `ASU-MICS-2028` | The repo | `git clone https://github.com/ASU-MICS-2028/nlp-group-1-prosit-2` |
| Claude API key in `.env` | The agent's main model (see "The LLMs" below) | The check command below |
| llama.cpp + the Qwen model file (optional) | The local model we compare against | `llama-server --version` |

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

## The LLMs

We run two models and compare them (task P1.7 in `docs/PLAN.md`). The code reads both locations from `.env`, so everyone's setup looks the same.

### 1. Claude (hosted, main engine)

- Model `claude-opus-5-5` through the Anthropic API. Put the key in `.env` as `LLM_API_KEY` (see `.env.example`).
- Ask the team lead for the key. Never paste it in the group chat, in code or in a commit.
- Check it works: `uv run --with anthropic --env-file .env python -c "import os, anthropic; print(anthropic.Anthropic(api_key=os.environ['LLM_API_KEY']).models.retrieve('claude-opus-5-5').id)"`

### 2. Qwen 3.5 9B (local, for comparison)

- Model: [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) (Apache-2.0, supports tool calling). We use the 4-bit GGUF build `Qwen_Qwen3.5-9B-Q4_K_M.gguf` (6.2 GB) from [bartowski/Qwen_Qwen3.5-9B-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF).
- **It must sit at `models/Qwen_Qwen3.5-9B-Q4_K_M.gguf` inside the repo.** `models/` is git-ignored, so the file never goes to GitHub. Download it straight to that path from the repo root:

  ```
  uvx --from huggingface_hub hf download bartowski/Qwen_Qwen3.5-9B-GGUF Qwen_Qwen3.5-9B-Q4_K_M.gguf --local-dir models
  ```

  You only need the one `.gguf` file. The `mmproj` file on Hugging Face is for images, which we don't use.
- Run it with [llama.cpp](https://github.com/ggml-org/llama.cpp) (macOS: `brew install llama.cpp`; Windows/Linux: download a build from the [releases page](https://github.com/ggml-org/llama.cpp/releases)). It serves an OpenAI-compatible API on `http://localhost:8090/v1`:

  ```
  llama-server -m models/Qwen_Qwen3.5-9B-Q4_K_M.gguf --jinja -c 32768 --port 8090
  ```

  `--jinja` is required for tool calling. `-c` is the context window in tokens. More context needs more memory.
- Thinking is on by default. To turn it off for a request, send `"chat_template_kwargs": {"enable_thinking": false}`. The model card's recommended settings without thinking: temperature 0.7, top_p 0.8, top_k 20.
- **First measurement** (Oct 20, Apple M3, 24 GB): it made a correct `write_file` tool call that wrote a FastAPI hello-world. Speed was about 5 output tokens per second and 89 prompt tokens per second, so a reply of a few hundred tokens takes about a minute. It needs about 6–8 GB of free memory.

## Notes

- The known setup is macOS on Apple Silicon (arm64). Windows and Linux should work, but nobody has checked yet. If you find a difference, write it here.
- The `NLP-GROUP-1/data/models/` folder on the Drive holds only the configs and tokenizers of Prosit 1's Qwen2.5-0.5B and SmolLM2-135M, without the weights. It is not the local model above.

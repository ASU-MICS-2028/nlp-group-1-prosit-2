# Prosit 2: A Non-Developer Friendly API Builder

ICS554 Natural Language Processing, Ashesi University. NLP Group 1: Michael Boadi, Joseph Etse, Alice Kara-Acquah, Bernard Marfo, Eric Sunu.

A non-developer describes a backend in plain words ("I run a tailoring shop, I need to track customers, measurements and orders"). A coding agent turns that into a plan they approve, then into a tested, running API with an OpenAPI contract that any frontend can use. The full plan, schedule and roles are in the team doc on the Drive: `NLP-GROUP-1/prosit 2/Prosit 2 Plan - NLP Group 1`.

## The two rules (read these first)

**1. Explain everything as blatantly and simply as possible.** Nobody else is going to touch your part. The rest of the team will rely only on what you write in your `findings/` file to write the report, give the presentation and answer viva questions. Write it so someone who has never seen your code can explain it out loud. No unexplained jargon, show real examples, give real numbers. If it is not in your findings file, the team does not know it.

**2. Test out any and every possible scenario.** Never build just one version and move on. At every step, try the alternatives, measure them, and keep the one that works best. Log every comparison in your findings file: what you compared, how you tested it, the numbers, and why the winner won. "We picked X" is not acceptable without "because X beat Y and Z by this much on this test".

## Layout

| Path | Owner | What lives there |
|---|---|---|
| `findings/` | everyone | One file per workstream: the plain explanation and the log of everything tried. Start from `findings/TEMPLATE.md` |
| `docs/CONTRACTS.md` | everyone | The 5 interfaces we agree on day 1 so five people can build in parallel |
| `benchmark/` | everyone writes, W4 owns | The 15 plain-language requests and their hidden tests. See `benchmark/README.md` |
| `builder/` | W1 | Agent core: ReAct loop, Planner / Builder / Tester, orchestrator, memory, CLI (`python -m builder ...`) |
| `runtime/` | W2 | Tools, Docker sandbox, test runner, server launcher, MCP server |
| `ui/` | W3 | The web page |
| `eval/`, `kb/` | W4 | Test harness, ablation runs, results; the recipe knowledge base for RAG |
| `projects/` | generated | Backends the agent builds (git-ignored) |

The code folders are created by their owners. Nothing in them is pre-written.

## Running

```
uv sync                         # installs Python deps from pyproject.toml
cp .env.example .env            # then add the LLM API key (never commit .env)
uv run pytest benchmark         # runs the hidden tests against a running backend; see benchmark/README.md
```

Docker must be installed and running for the sandbox.

## Working together

- Branch per workstream (`w1-agent`, `w2-runtime`, ...), merge to `main` through a pull request once it runs.
- If you change anything in `docs/CONTRACTS.md`, say so in the group chat the same day.
- The GitHub link goes on page 1 of every report and on the first slide.

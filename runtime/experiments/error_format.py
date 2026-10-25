"""Experiment: does putting a one-line reason first help the LLM fix a failing test?
Run (costs about $1.30): uv run --env-file .env --with anthropic python runtime/experiments/error_format.py

A = run_tests output as pytest prints it (cut to 4,000 characters, start and end kept).
B = the same, but the failing-test lines and the summary line are copied to the top first.
For each of the 7 planted bugs and each format, 3 times: send app.py, the tests and the output to
Claude, ask for the fixed app.py, run the tests again. Success = all 8 tests pass.
"""

import os
import re
import sys
import tempfile
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from church_bugs import BUGS, make_broken  # noqa: E402
from runtime.tools import cut, run_tests  # noqa: E402

MODEL, REPEATS, MAX_DOLLARS = "claude-opus-5-5", 3, 3.0
PROMPT = """You are fixing a FastAPI backend. Its tests fail.

app.py:
```python
{app}
```

tests/test_app.py:
```python
{tests}
```

Output of the run_tests tool:
```
{output}
```

Reply with the complete corrected app.py in one ```python block and nothing else."""


def reason_first(output):
    """Format B: copy pytest's FAILED/ERROR lines and its last line to the top."""
    lines = output.strip().splitlines()
    reasons = [line for line in lines if line.startswith(("FAILED ", "ERROR "))] + lines[-1:]
    return "Why it failed: " + " | ".join(reasons) + "\n\nFull output:\n" + output


def ask(client, folder, output):
    prompt = PROMPT.format(app=(folder / "app.py").read_text(), tests=(folder / "tests/test_app.py").read_text(),
                           output=output)
    response = client.beta.messages.create(
        model=MODEL, max_tokens=16000, output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",  # if Opus declines, a fallback model answers
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    code = re.search(r"```python\n(.*?)```", text, flags=re.S)
    cost = (response.usage.input_tokens * 4 + response.usage.output_tokens * 20) / 1e6
    return (code.group(1) if code else ""), response.usage, cost


if __name__ == "__main__":
    client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"])
    folder = Path(tempfile.mkdtemp()) / "p"
    totals = {"A raw": [0, 0, 0, 0.0], "B reason first": [0, 0, 0, 0.0]}  # fixed, tries, output tokens, dollars
    spent = 0.0
    for bug in BUGS:
        for name in totals:
            for _ in range(REPEATS):
                make_broken(bug, folder)
                raw = run_tests(folder)["output"]  # already cut to 4,000 characters
                output = raw if name == "A raw" else cut(reason_first(raw))
                code, usage, cost = ask(client, folder, output)
                (folder / "app.py").write_text(code)
                fixed = run_tests(folder)["ok"]
                t = totals[name]
                t[0], t[1], t[2], t[3] = t[0] + fixed, t[1] + 1, t[2] + usage.output_tokens, t[3] + cost
                spent += cost
                print(f"{bug:14} {name:15} fixed={fixed}  in={usage.input_tokens} out={usage.output_tokens} "
                      f"${cost:.4f}  (total ${spent:.2f})", flush=True)
                if spent > MAX_DOLLARS:
                    sys.exit(f"Stopped: spent ${spent:.2f}, more than the ${MAX_DOLLARS} limit")
    print()
    for name, (fixed, tries, out_tokens, dollars) in totals.items():
        print(f"{name:15} fixed {fixed}/{tries}, average output tokens {out_tokens // tries}, cost ${dollars:.2f}")

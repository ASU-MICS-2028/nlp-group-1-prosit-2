"""Run every recipe's code and its check inside the sandbox image (the same library versions a build gets).

    uv run python kb/check_recipes.py
A recipe passes when its python blocks, run together, raise nothing. No network, nothing mounted.
"""

import pathlib
import re
import subprocess
import sys

RECIPES = pathlib.Path(__file__).parent / "recipes"


def code(recipe: pathlib.Path) -> str:
    return "\n".join(re.findall(r"```python[^\n]*\n(.*?)```", recipe.read_text(), re.S))


def main():
    bad = 0
    for r in sorted(RECIPES.glob("*.md")):
        p = subprocess.run(["docker", "run", "--rm", "-i", "--pull", "never", "--network", "none", "w2-sandbox", "python", "-"],
                           input=code(r), capture_output=True, text=True, timeout=120)
        ok = p.returncode == 0
        bad += not ok
        print(f"{'✅' if ok else '❌'} {r.stem}" + ("" if ok else "\n   " + p.stderr.strip().splitlines()[-1]))
    print(f"{len(list(RECIPES.glob('*.md'))) - bad}/{len(list(RECIPES.glob('*.md')))} recipes pass")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

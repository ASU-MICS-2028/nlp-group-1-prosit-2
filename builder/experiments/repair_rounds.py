"""S3.4: turn one set of builds made with --repairs 5 into what 0, 1, 3 and 5 repairs would have given.

    uv run --env-file .env --with anthropic python -m builder build all --repairs 5 --run s34
    uv run python builder/experiments/repair_rounds.py s34
    then score each: uv run --env-file .env --with anthropic python -m eval.harness all projects/s34_r1 --repeat 3 --name s34_r1

Each build saved app.py after every round as rounds/app_N.py. "At most K repairs" is the last copy with N <= K: a build
that passed the check after 1 repair is the same at 3 and 5.
"""

import shutil
import sys
from pathlib import Path

run = Path("projects") / sys.argv[1]
for k in (0, 1, 3, 5):
    for task in sorted(p for p in run.iterdir() if (p / "rounds").is_dir()):
        rounds = sorted(int(f.stem.split("_")[1]) for f in (task / "rounds").glob("app_*.py"))
        best = max(n for n in rounds if n <= k)
        out = Path(f"{run}_r{k}") / task.name
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(task / "rounds" / f"app_{best}.py", out / "app.py")
        (out / "ops.json").unlink(missing_ok=True)  # a stale name map from an earlier run would score the wrong app
    print(f"{run}_r{k}: done")

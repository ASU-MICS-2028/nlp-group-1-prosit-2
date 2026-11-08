"""Does one crash make the next test fail? (W4 row 34) Free, needs Docker. Writes eval/results/replicated/flaky_check.json.

    uv run python -m eval.experiments.flaky_check
The church broken copy missing_event_200 crashes on a missing event; the "no name" test must not suffer for it.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

from eval import bench
from runtime.tools import start_server, stop_server

T = bench.BENCH / "church_signup"
out = {}
for label, src in {"broken_copy": T / "mutants/missing_event_200.py", "correct_backend": T / "reference/app.py"}.items():
    wrongly_failed = 0
    for _ in range(20):
        d = pathlib.Path(tempfile.mkdtemp())
        shutil.copy(src, d / "app.py")
        url = start_server(d)["output"].split()[-1]
        env = {**os.environ, "BASE_URL": url, "OPS_FILE": str(T / "reference/ops.json")}
        p = subprocess.run([sys.executable, "-m", "pytest", str(T / "hidden_tests"), "-q", "-p", "no:cacheprovider", "-k", "without_name or missing_event"],
                           env=env, capture_output=True, text=True)
        stop_server(d)
        wrongly_failed += "::test_create_event_without_name_is_refused" in p.stdout
    out[label] = {"runs": 20, "no_name_test_wrongly_failed": wrongly_failed}
    print(label, out[label], flush=True)
path = bench.ROOT / "eval/results/replicated/flaky_check.json"
path.write_text(json.dumps(out, indent=2) + "\n")

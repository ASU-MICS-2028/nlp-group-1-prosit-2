"""Does the playback test catch a broken web/replay.py? Break it three ways, one at a time, run the test, put it back (free).

    uv run --with anthropic python eval/experiments/replay_breaks.py > eval/results/replay_breaks/output.txt
"""
import pathlib, subprocess
F = pathlib.Path("web/replay.py"); good = F.read_text()
BREAKS = {"wrong link": ('"url": live["url"]', '"url": "https://wrong.example"'),
          "events not sent": ('on_event(e["detail"])', 'pass'),
          "tests failing": ('"tests": end["tests"]', '"tests": {**end["tests"], "failed": 1}')}
def test():
    r = subprocess.run(["uv", "run", "--with", "anthropic", "python", "-m", "pytest", "-q", "web/test_web.py::test_replay_plays_a_saved_session"], capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1]
print("unbroken:", *test())
try:
    for name, (old, new) in BREAKS.items():
        assert good.count(old) == 1, name
        F.write_text(good.replace(old, new)); code, last = test()
        print(f"{name}: exit {code}, {last}, {'caught' if code else 'NOT CAUGHT'}")
finally:
    F.write_text(good)
print("put back:", *test())

"""The disk watchdog (S4.7), no Docker needed: only backends over the limit are stopped.

    uv run python -m pytest runtime/tests/test_disk_watchdog.py -q
"""

from runtime import deploy


def test_only_the_oversized_backend_is_stopped(monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, "DEPLOY_ROOT", tmp_path)
    ran = []
    monkeypatch.setattr(deploy.subprocess, "run", lambda args, **k: ran.append(args))
    for name, parts in (("small", 1), ("many", 6), ("nested", 6)):
        folder = tmp_path / name / ("sub" if name == "nested" else "")
        folder.mkdir(parents=True)
        for i in range(parts):
            with open(folder / f"{i}.bin", "wb") as f:
                f.truncate(100 * 2**20 if name != "small" else 2**20)  # empty files with a size, so the test writes nothing
    assert sorted(deploy.stop_oversized()) == ["many", "nested"]
    assert sorted(a[-1] for a in ran) == ["d-many", "d-nested"]


def test_exactly_at_the_limit_is_left_alone(monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, "DEPLOY_ROOT", tmp_path)
    (tmp_path / "edge").mkdir()
    with open(tmp_path / "edge" / "a.bin", "wb") as f:
        f.truncate(deploy.MAX_BACKEND_MB * 2**20)
    assert deploy.stop_oversized() == []

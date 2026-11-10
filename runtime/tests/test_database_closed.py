"""The check must close the database when it is done. Windows cannot delete a file that is still open, so an open one stays behind."""

import sqlite3

import pytest

from runtime import deploy


def test_the_database_is_closed_and_the_new_row_is_saved(tmp_path, monkeypatch):
    db, real, opened = tmp_path / "s.db", sqlite3.connect, []
    first = real(db)
    first.execute("CREATE TABLE a (x TEXT NOT NULL)")
    first.commit()
    first.close()
    monkeypatch.setattr(deploy.sqlite3, "connect", lambda path: opened.append(real(path)) or opened[-1])
    deploy.add_a_row(db, "a")
    assert deploy.tables(db) == {"a": 1}
    assert len(opened) == 2
    for c in opened:
        with pytest.raises(sqlite3.ProgrammingError):  # raised only by a closed connection
            c.execute("SELECT 1")

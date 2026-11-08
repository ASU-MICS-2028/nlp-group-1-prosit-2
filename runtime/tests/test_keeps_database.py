"""The check before publishing, on small apps whose answer is known (needs Docker, free).

    uv run python -m pytest runtime/tests/test_keeps_database.py -q
"""

import pytest

from runtime.deploy import keeps_database

SQLITE = """from fastapi import FastAPI
from sqlmodel import Field, SQLModel, create_engine
class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    price: float
    joined: str
engine = create_engine("{url}")
{start}
app = FastAPI()
"""
FILE, CREATE = "sqlite:///shop.db", "SQLModel.metadata.create_all(engine)"


@pytest.mark.parametrize("code, keeps", [
    (SQLITE.format(url=FILE, start=CREATE), True),
    (SQLITE.format(url="sqlite:///data/shop.db", start="import os; os.makedirs('data', exist_ok=True); " + CREATE), True),  # any folder
    ("from fastapi import FastAPI\nimport sqlite3\nc = sqlite3.connect('s.db'); c.execute('CREATE TABLE IF NOT EXISTS a (x TEXT NOT NULL)'); c.commit()\napp = FastAPI()\n", True),
    ("from fastapi import FastAPI\napp = FastAPI()\nITEMS = []\n", False),  # memory
    (SQLITE.format(url="sqlite://", start=CREATE), False),  # a database that lives in memory
    (SQLITE.format(url=FILE, start="SQLModel.metadata.drop_all(engine); " + CREATE), False),  # wiped at every start
    (SQLITE.format(url=FILE, start="import os\nif os.path.exists('shop.db'): os.remove('shop.db')\n" + CREATE), False),  # file deleted
    (SQLITE.format(url=FILE, start=""), False),  # the file never gets any tables
    ("this is not python\n", False),
])
def test_known_answers(tmp_path, code, keeps):
    (tmp_path / "app.py").write_text(code)
    got = keeps_database(tmp_path)
    assert got["ok"] is keeps, got["output"]
    assert not (tmp_path / "db_check").exists()  # leaves nothing behind

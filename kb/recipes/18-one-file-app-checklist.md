# Checklist for a complete one-file FastAPI app (app.py)

Use when: starting a new backend, or when the server will not start ("Attribute app not found in module app",
"NameError", "ImportError", "SyntaxError"). The harness runs `uvicorn app:app`, so the file must be named app.py and
must create a variable named `app`.
1. Imports first: `from sqlmodel import Field, Session, SQLModel, create_engine, select` (Field and Session come from
   sqlmodel; `Session` is a class, there is no `session` to import).
2. The engine (see the engine recipe), then the table classes, each with an id primary key.
3. `SQLModel.metadata.create_all(engine)` after the classes.
4. `app = FastAPI()` at the top level of the file, not inside a function or `if __name__ == "__main__"`.
5. Endpoints. Plain `def` is fine; do not mix async def with blocking database calls.
6. Run it once before handing over: `python -c "import app"` must print no error.

```python
from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.get("/items")
def items() -> list[Item]:
    with Session(engine) as s:
        return s.exec(select(Item)).all()
```

```python check
from fastapi.testclient import TestClient
assert TestClient(app).get("/items").json() == []
```

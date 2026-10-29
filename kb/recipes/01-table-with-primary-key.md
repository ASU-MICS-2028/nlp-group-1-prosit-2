# A database table with an id (primary key)

Use when: defining any table with SQLModel. Every table needs exactly one primary key column, or SQLAlchemy stops with
"could not assemble any primary key columns". Let the database number the rows: `id: int | None = Field(default=None, primary_key=True)`.
Import `Field` from sqlmodel (not pydantic). Keep separate classes for what the client sends (no id) and the table (with id).

```python
from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class NoteIn(SQLModel):  # what the client sends
    title: str
    body: str = ""


class Note(NoteIn, table=True):  # the table: the same fields plus the id
    id: int | None = Field(default=None, primary_key=True)


SQLModel.metadata.create_all(engine)  # after every table class is defined
app = FastAPI()


@app.post("/notes", status_code=201)
def create_note(note: NoteIn) -> Note:
    with Session(engine) as s:
        row = Note.model_validate(note)
        s.add(row)
        s.commit()
        s.refresh(row)  # fills in the id the database chose
        return row


@app.get("/notes")
def list_notes() -> list[Note]:
    with Session(engine) as s:
        return s.exec(select(Note)).all()
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
r = c.post("/notes", json={"title": "Shopping"})
assert r.status_code == 201 and r.json()["id"] == 1
assert [n["title"] for n in c.get("/notes").json()] == ["Shopping"]
```

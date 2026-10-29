# Setting up the SQLite database engine

Use when: creating the engine, or on errors like "SQLite objects created in a thread can only be used in that same thread",
"Invalid argument(s) 'check_same_thread'", "no such table", or "unable to open database file".
- In memory (data lost on restart, good for tests): `create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)`.
  `StaticPool` keeps one shared connection, so every request sees the same in-memory data.
- In a file next to app.py: `create_engine("sqlite:///data.db", connect_args={"check_same_thread": False})`. Three slashes
  means a relative path. Never copy placeholder paths such as `sqlite:////absolute/path/to/file.db`.
- `check_same_thread` goes inside `connect_args`, never as its own argument.
- Call `SQLModel.metadata.create_all(engine)` once, after all table classes are defined, or tables are missing ("no such table").

```python
from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Room(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/rooms", status_code=201)
def add_room(room: Room) -> Room:
    with Session(engine) as s:
        s.add(room)
        s.commit()
        s.refresh(room)
        return room


@app.get("/rooms")
def rooms() -> list[Room]:
    with Session(engine) as s:
        return s.exec(select(Room)).all()
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
c.post("/rooms", json={"name": "Blue"})
assert len(c.get("/rooms").json()) == 1  # a second request sees the same data: StaticPool works
```

# An action that changes a record's state (mark as done, collected, paid, cancelled)

Use when: the client "marks" something: an order is collected, a task is done, a loan is repaid, a booking is cancelled.
Keep a status field, change it with its own endpoint (POST /things/{id}/done), refuse doing it twice with 409, and leave
finished records out of lists that are meant for pending work.

```python
from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    done: bool = False


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/tasks", status_code=201)
def add(t: Task) -> Task:
    with Session(engine) as s:
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.post("/tasks/{tid}/done")
def mark_done(tid: int) -> Task:
    with Session(engine) as s:
        t = s.get(Task, tid)
        if t is None:
            raise HTTPException(404, "No such task")
        if t.done:
            raise HTTPException(409, "Already done")
        t.done = True
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.get("/tasks/pending")
def pending() -> list[Task]:
    with Session(engine) as s:
        return s.exec(select(Task).where(Task.done == False)).all()  # noqa: E712 (SQL needs ==)
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
t = c.post("/tasks", json={"title": "Sweep"}).json()
assert c.post(f"/tasks/{t['id']}/done").json()["done"] is True
assert c.post(f"/tasks/{t['id']}/done").status_code == 409
assert c.get("/tasks/pending").json() == []
```

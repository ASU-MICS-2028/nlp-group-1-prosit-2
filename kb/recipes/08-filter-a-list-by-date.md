# Filter a list by a date (on a day, before, after, between)

Use when: the client wants "everything on this day", "due on or before a date", "from one date to another".
Store dates with the `date` type (not text), take the filter from the query string (`GET /visits?on=2026-11-02`), and
let FastAPI parse it: a bad date gives 422 by itself. Optional filters default to None and are only applied when given.

```python
from datetime import date

from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Visit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    person: str
    day: date


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/visits", status_code=201)
def add(v: Visit) -> Visit:
    v.day = date.fromisoformat(str(v.day))  # model_validate is skipped for table models: make sure it is a date
    with Session(engine) as s:
        s.add(v)
        s.commit()
        s.refresh(v)
        return v


@app.get("/visits")
def visits(on: date | None = None, until: date | None = None, since: date | None = None) -> list[Visit]:
    q = select(Visit)
    if on:
        q = q.where(Visit.day == on)
    if until:
        q = q.where(Visit.day <= until)  # "on or before"
    if since:
        q = q.where(Visit.day >= since)
    with Session(engine) as s:
        return s.exec(q.order_by(Visit.day)).all()
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
for p, d in [("Ama", "2026-11-01"), ("Kojo", "2026-11-02"), ("Efua", "2026-11-05")]:
    assert c.post("/visits", json={"person": p, "day": d}).status_code == 201
assert [v["person"] for v in c.get("/visits", params={"on": "2026-11-02"}).json()] == ["Kojo"]
assert [v["person"] for v in c.get("/visits", params={"until": "2026-11-02"}).json()] == ["Ama", "Kojo"]
assert c.get("/visits", params={"on": "not-a-date"}).status_code == 422
```

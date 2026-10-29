# Refuse a request that breaks a rule (full, too much, not allowed)

Use when: the client says something "must not" happen: a room is full, a payment is more than what is owed, a limit is
reached, an action is not allowed in the current state. Check the rule before changing anything, and refuse with
`HTTPException`: 409 when it clashes with the current state (full, already done), 400 when the request itself is wrong.
Nothing is saved when the request is refused.

```python
from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, func, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Workshop(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    seats: int = Field(gt=0)


class Seat(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    workshop_id: int = Field(foreign_key="workshop.id")
    person: str


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/workshops", status_code=201)
def add_workshop(w: Workshop) -> Workshop:
    with Session(engine) as s:
        s.add(w)
        s.commit()
        s.refresh(w)
        return w


@app.post("/workshops/{wid}/seats", status_code=201)
def take_seat(wid: int, person: str) -> Seat:
    with Session(engine) as s:
        w = s.get(Workshop, wid)
        if w is None:
            raise HTTPException(404, "No such workshop")
        taken = s.exec(select(func.count()).select_from(Seat).where(Seat.workshop_id == wid)).one()
        if taken >= w.seats:  # check first; save nothing when refused
            raise HTTPException(409, "The workshop is full")
        seat = Seat(workshop_id=wid, person=person)
        s.add(seat)
        s.commit()
        s.refresh(seat)
        return seat
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
w = c.post("/workshops", json={"seats": 1}).json()
assert c.post(f"/workshops/{w['id']}/seats", params={"person": "Ama"}).status_code == 201
assert c.post(f"/workshops/{w['id']}/seats", params={"person": "Kofi"}).status_code == 409
assert c.post("/workshops/99/seats", params={"person": "Yaw"}).status_code == 404
```

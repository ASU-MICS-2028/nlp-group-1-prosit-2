# No double booking: one slot, one booking

Use when: something can only be booked once at a time: a court at a time, a bed for a date, a person for an hour.
Before saving, look for an existing booking with the same resource and the same slot (or an overlapping time range) and
refuse with 409. Different resources, or the same resource at another time, are allowed. Ranges overlap when
`start < other_end and other_start < end`.

```python
from datetime import date, time

from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Booking(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    court: int
    day: date
    start: time
    end: time


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/bookings", status_code=201)
def book(b: Booking) -> Booking:
    b = Booking.model_validate(b.model_dump())  # turn the text dates and times into real ones
    if b.start >= b.end:
        raise HTTPException(400, "Start must be before end")
    with Session(engine) as s:
        clash = s.exec(select(Booking).where(Booking.court == b.court, Booking.day == b.day,
                                             Booking.start < b.end, b.start < Booking.end)).first()
        if clash:
            raise HTTPException(409, f"Court {b.court} is already booked then")
        s.add(b)
        s.commit()
        s.refresh(b)
        return b
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
slot = {"court": 1, "day": "2026-11-02", "start": "10:00", "end": "11:00"}
assert c.post("/bookings", json=slot).status_code == 201
assert c.post("/bookings", json={**slot, "start": "10:30", "end": "11:30"}).status_code == 409  # overlaps
assert c.post("/bookings", json={**slot, "start": "11:00", "end": "12:00"}).status_code == 201  # right after
assert c.post("/bookings", json={**slot, "court": 2}).status_code == 201  # another court
assert c.post("/bookings", json={**slot, "day": "2026-11-03"}).status_code == 201  # another day
```

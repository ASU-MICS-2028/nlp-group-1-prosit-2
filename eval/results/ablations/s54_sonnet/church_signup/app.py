import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///church.db", connect_args={"check_same_thread": False})


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    date: datetime.date
    capacity: int


class Signup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    name: str
    phone: str


class EventIn(SQLModel):
    name: str
    date: datetime.date
    capacity: int

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("capacity")
    @classmethod
    def _cap(cls, v):
        if v < 1:
            raise ValueError("capacity must be at least 1")
        return v


class SignupIn(SQLModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def _nonempty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


app = FastAPI()


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


SQLModel.metadata.create_all(engine)


def event_dict(s, e):
    count = s.exec(select(func.count()).select_from(Signup).where(Signup.event_id == e.id)).one()
    return {
        "id": e.id,
        "name": e.name,
        "date": e.date.isoformat(),
        "capacity": e.capacity,
        "signed_up": count,
        "spots_left": max(e.capacity - count, 0),
    }


def get_event(s, event_id):
    e = s.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    return e


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    with Session(engine) as s:
        e = Event(name=data.name, date=data.date, capacity=data.capacity)
        s.add(e)
        s.commit()
        s.refresh(e)
        return event_dict(s, e)


@app.get("/events")
def list_events():
    with Session(engine) as s:
        return [event_dict(s, e) for e in s.exec(select(Event).order_by(Event.date, Event.id)).all()]


@app.get("/events/{event_id}")
def read_event(event_id: int):
    with Session(engine) as s:
        return event_dict(s, get_event(s, event_id))


@app.post("/events/{event_id}/signups", status_code=201)
def sign_up(event_id: int, data: SignupIn):
    with Session(engine) as s:
        e = get_event(s, event_id)
        existing = s.exec(select(Signup).where(Signup.event_id == event_id)).all()
        if any(x.phone == data.phone for x in existing):
            raise HTTPException(409, "This phone number is already signed up for this event")
        if len(existing) >= e.capacity:
            raise HTTPException(409, "Event is full")
        su = Signup(event_id=event_id, name=data.name, phone=data.phone)
        s.add(su)
        s.commit()
        s.refresh(su)
        return {"id": su.id, "event_id": su.event_id, "name": su.name, "phone": su.phone}


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with Session(engine) as s:
        get_event(s, event_id)
        rows = s.exec(select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)).all()
        return [{"id": r.id, "event_id": r.event_id, "name": r.name, "phone": r.phone} for r in rows]

from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///church_events.db", connect_args={"check_same_thread": False})


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    date: date
    capacity: int


class Signup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    name: str
    phone: str


class EventIn(BaseModel):
    name: str = PField(min_length=1)
    date: date
    capacity: int = PField(ge=1)

    @field_validator("name")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class SignupIn(BaseModel):
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Church Events", lifespan=lifespan)


def count_signups(session, event_id):
    return session.exec(select(func.count(Signup.id)).where(Signup.event_id == event_id)).one()


def event_out(session, ev):
    taken = count_signups(session, ev.id)
    return {
        "id": ev.id,
        "name": ev.name,
        "date": ev.date.isoformat(),
        "capacity": ev.capacity,
        "signed_up": taken,
        "spots_left": max(ev.capacity - taken, 0),
        "is_full": taken >= ev.capacity,
    }


def get_event_or_404(session, event_id):
    ev = session.get(Event, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    with Session(engine) as s:
        ev = Event(name=data.name, date=data.date, capacity=data.capacity)
        s.add(ev)
        s.commit()
        s.refresh(ev)
        return event_out(s, ev)


@app.get("/events")
def list_events():
    with Session(engine) as s:
        evs = s.exec(select(Event).order_by(Event.date, Event.id)).all()
        return [event_out(s, e) for e in evs]


@app.get("/events/{event_id}")
def get_event(event_id: int):
    with Session(engine) as s:
        return event_out(s, get_event_or_404(s, event_id))


@app.post("/events/{event_id}/signups", status_code=201)
def sign_up(event_id: int, data: SignupIn):
    with Session(engine) as s:
        ev = get_event_or_404(s, event_id)
        if count_signups(s, ev.id) >= ev.capacity:
            raise HTTPException(status_code=409, detail="Sorry, this event is full")
        su = Signup(event_id=ev.id, name=data.name, phone=data.phone)
        s.add(su)
        s.commit()
        s.refresh(su)
        return {"id": su.id, "event_id": su.event_id, "name": su.name, "phone": su.phone}


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with Session(engine) as s:
        get_event_or_404(s, event_id)
        sus = s.exec(select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)).all()
        return [{"id": x.id, "event_id": x.event_id, "name": x.name, "phone": x.phone} for x in sus]

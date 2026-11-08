import re
from contextlib import asynccontextmanager
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, StrictStr, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

engine = create_engine(
    "sqlite:///church_events.db", connect_args={"check_same_thread": False}
)


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    date: str
    place: str
    capacity: int


class Signup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    name: str
    phone: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    # Add the "place" column to a database file made before places existed.
    with engine.begin() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(event)")]
        if "place" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE event ADD COLUMN place VARCHAR NOT NULL DEFAULT ''"
            )
    yield


app = FastAPI(title="Church Events", lifespan=lifespan)


def _not_blank(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class EventIn(BaseModel):
    name: StrictStr
    date: StrictStr
    place: StrictStr
    capacity: StrictInt

    @field_validator("name", "place")
    @classmethod
    def check_name(cls, v):
        return _not_blank(v)

    @field_validator("date")
    @classmethod
    def check_date(cls, v):
        v = v.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("date must be a real date in the form YYYY-MM-DD")
        try:
            Date.fromisoformat(v)
        except ValueError:
            raise ValueError("date must be a real date in the form YYYY-MM-DD")
        return v

    @field_validator("capacity")
    @classmethod
    def check_capacity(cls, v):
        if v < 1:
            raise ValueError("capacity must be a whole number greater than zero")
        return v


class SignupIn(BaseModel):
    name: StrictStr
    phone: StrictStr

    @field_validator("name", "phone")
    @classmethod
    def check_text(cls, v):
        return _not_blank(v)


def _count(session: Session, event_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Signup).where(Signup.event_id == event_id)
    ).one()


def _event_out(session: Session, ev: Event) -> dict:
    taken = _count(session, ev.id)
    return {
        "id": ev.id,
        "name": ev.name,
        "date": ev.date,
        "place": ev.place,
        "capacity": ev.capacity,
        "places_left": max(ev.capacity - taken, 0),
    }


def _get_event(session: Session, event_id: int) -> Event:
    ev = session.get(Event, event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    with Session(engine) as session:
        ev = Event(
            name=data.name, date=data.date, place=data.place, capacity=data.capacity
        )
        session.add(ev)
        session.commit()
        session.refresh(ev)
        return _event_out(session, ev)


@app.get("/events")
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.id)).all()
        return [_event_out(session, ev) for ev in events]


@app.get("/events/{eventId}")
def get_event(eventId: int):
    with Session(engine) as session:
        return _event_out(session, _get_event(session, eventId))


@app.post("/events/{eventId}/signups", status_code=201)
def create_signup(eventId: int, data: SignupIn):
    with Session(engine) as session:
        ev = _get_event(session, eventId)
        if _count(session, ev.id) >= ev.capacity:
            raise HTTPException(
                status_code=409,
                detail="This event is full. No more sign-ups are possible.",
            )
        s = Signup(event_id=ev.id, name=data.name, phone=data.phone)
        session.add(s)
        session.commit()
        session.refresh(s)
        return {"id": s.id, "event_id": s.event_id, "name": s.name, "phone": s.phone}


@app.get("/events/{eventId}/signups")
def list_signups(eventId: int):
    with Session(engine) as session:
        ev = _get_event(session, eventId)
        rows = session.exec(
            select(Signup).where(Signup.event_id == ev.id).order_by(Signup.id)
        ).all()
        return [
            {"id": s.id, "event_id": s.event_id, "name": s.name, "phone": s.phone}
            for s in rows
        ]

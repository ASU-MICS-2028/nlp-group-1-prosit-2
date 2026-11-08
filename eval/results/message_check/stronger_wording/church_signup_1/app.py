import re
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

engine = create_engine(
    "sqlite:///./church_events.db", connect_args={"check_same_thread": False}
)
signup_lock = threading.Lock()


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    date: date
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
    # Older database files may lack the "place" column; add it if missing.
    with engine.begin() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(event)")]
        if "place" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE event ADD COLUMN place VARCHAR NOT NULL DEFAULT ''"
            )
    yield


app = FastAPI(title="Church Events", lifespan=lifespan)


def _required_text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty")
    return value.strip()


class EventIn(BaseModel):
    name: str
    date: str
    place: str
    capacity: StrictInt

    @field_validator("name", "place")
    @classmethod
    def check_name(cls, v):
        return _required_text(v)

    @field_validator("date")
    @classmethod
    def check_date(cls, v):
        v = v.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("must be a real date written as YYYY-MM-DD")
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("must be a real date written as YYYY-MM-DD")
        return v

    @field_validator("capacity")
    @classmethod
    def check_capacity(cls, v):
        if v <= 0:
            raise ValueError("must be a whole number greater than zero")
        return v


class SignupIn(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def check_text(cls, v):
        return _required_text(v)


def _count(session: Session, event_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Signup).where(Signup.event_id == event_id)
    ).one()


def _event_out(session: Session, event: Event) -> dict:
    taken = _count(session, event.id)
    return {
        "id": event.id,
        "name": event.name,
        "date": event.date.isoformat(),
        "place": event.place,
        "capacity": event.capacity,
        "places_left": max(event.capacity - taken, 0),
    }


def _get_event(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    with Session(engine) as session:
        event = Event(
            name=data.name,
            date=date.fromisoformat(data.date),
            place=data.place,
            capacity=data.capacity,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return _event_out(session, event)


@app.get("/events")
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.id)).all()
        return [_event_out(session, e) for e in events]


@app.get("/events/{event_id}")
def get_event(event_id: int):
    with Session(engine) as session:
        return _event_out(session, _get_event(session, event_id))


@app.post("/events/{event_id}/signups", status_code=201)
def create_signup(event_id: int, data: SignupIn):
    with signup_lock:
        with Session(engine) as session:
            event = _get_event(session, event_id)
            if _count(session, event_id) >= event.capacity:
                raise HTTPException(
                    status_code=409,
                    detail="Sorry, this event is full. No more sign-ups are accepted.",
                )
            signup = Signup(event_id=event_id, name=data.name, phone=data.phone)
            session.add(signup)
            session.commit()
            session.refresh(signup)
            return signup.model_dump()


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with Session(engine) as session:
        _get_event(session, event_id)
        signups = session.exec(
            select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)
        ).all()
        return [s.model_dump() for s in signups]

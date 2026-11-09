import threading
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

engine = create_engine("sqlite:///church_events.db", connect_args={"check_same_thread": False})
signup_lock = threading.Lock()  # so two people cannot take the last place at the same time


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    date: date
    capacity: int


class Signup(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    name: str
    phone: str


class EventIn(BaseModel):
    name: str = PField(min_length=1)
    date: date
    capacity: int = PField(gt=0)

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class SignupIn(BaseModel):
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


def count_signups(s: Session, event_id: int) -> int:
    return s.exec(select(func.count()).select_from(Signup).where(Signup.event_id == event_id)).one()


def event_out(s: Session, e: Event) -> dict:
    taken = count_signups(s, e.id)
    return {"id": e.id, "name": e.name, "date": e.date.isoformat(), "capacity": e.capacity,
            "signed_up": taken, "places_left": max(e.capacity - taken, 0)}


def get_event_or_404(s: Session, event_id: int) -> Event:
    e = s.get(Event, event_id)
    if e is None:
        raise HTTPException(404, "Event not found")
    return e


@app.post("/events", status_code=201)
def add_event(body: EventIn) -> dict:
    with Session(engine) as s:
        e = Event(name=body.name, date=body.date, capacity=body.capacity)
        s.add(e)
        s.commit()
        s.refresh(e)
        return event_out(s, e)


@app.get("/events")
def list_events() -> list[dict]:
    with Session(engine) as s:
        events = s.exec(select(Event).order_by(Event.date, Event.id)).all()
        return [event_out(s, e) for e in events]


@app.get("/events/{event_id}")
def get_event(event_id: int) -> dict:
    with Session(engine) as s:
        return event_out(s, get_event_or_404(s, event_id))


@app.post("/events/{event_id}/signups", status_code=201)
def sign_up(event_id: int, body: SignupIn) -> dict:
    with signup_lock:
        with Session(engine) as s:
            e = get_event_or_404(s, event_id)
            if count_signups(s, event_id) >= e.capacity:
                raise HTTPException(409, "Sorry, this event is full")
            su = Signup(event_id=event_id, name=body.name, phone=body.phone)
            s.add(su)
            s.commit()
            s.refresh(su)
            return su.model_dump()


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int) -> list[dict]:
    with Session(engine) as s:
        get_event_or_404(s, event_id)
        rows = s.exec(select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)).all()
        return [r.model_dump() for r in rows]

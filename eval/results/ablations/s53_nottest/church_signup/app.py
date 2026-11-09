import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

signup_lock = threading.Lock()
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


class EventCreate(SQLModel):
    name: str
    date: date
    capacity: int

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("capacity")
    @classmethod
    def capacity_positive(cls, v):
        if v < 1:
            raise ValueError("capacity must be at least 1")
        return v


class SignupCreate(SQLModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class EventOut(SQLModel):
    id: int
    name: str
    date: date
    capacity: int
    signed_up: int
    spots_left: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Church Events", lifespan=lifespan)


def count_signups(session: Session, event_id: int) -> int:
    return session.exec(select(func.count()).select_from(Signup).where(Signup.event_id == event_id)).one()


def to_out(session: Session, event: Event) -> EventOut:
    n = count_signups(session, event.id)
    return EventOut(id=event.id, name=event.name, date=event.date, capacity=event.capacity,
                    signed_up=n, spots_left=max(event.capacity - n, 0))


def get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", response_model=EventOut, status_code=201)
def create_event(data: EventCreate):
    with Session(engine) as session:
        event = Event(name=data.name, date=data.date, capacity=data.capacity)
        session.add(event)
        session.commit()
        session.refresh(event)
        return to_out(session, event)


@app.get("/events", response_model=List[EventOut])
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.date, Event.id)).all()
        return [to_out(session, e) for e in events]


@app.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: int):
    with Session(engine) as session:
        return to_out(session, get_event_or_404(session, event_id))


@app.post("/events/{event_id}/signups", response_model=Signup, status_code=201)
def sign_up(event_id: int, data: SignupCreate):
    # Lock so two people can't grab the last spot at the same time.
    with signup_lock, Session(engine) as session:
        event = get_event_or_404(session, event_id)
        if count_signups(session, event_id) >= event.capacity:
            raise HTTPException(status_code=409, detail="This event is full")
        signup = Signup(event_id=event_id, name=data.name, phone=data.phone)
        session.add(signup)
        session.commit()
        session.refresh(signup)
        return signup


@app.get("/events/{event_id}/signups", response_model=List[Signup])
def list_signups(event_id: int):
    with Session(engine) as session:
        get_event_or_404(session, event_id)
        return session.exec(select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)).all()

import threading
from contextlib import asynccontextmanager
from datetime import date as Date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictInt, field_validator
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, func, select

DATABASE_URL = "sqlite:///./church_events.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Serialises the "is it full?" check and the insert so two people can't take the last place.
signup_lock = threading.Lock()


class Event(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    date: Date
    capacity: int


class Signup(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    event_id: int = SQLField(foreign_key="event.id", index=True)
    name: str
    phone: str


class EventCreate(BaseModel):
    name: str
    date: Date
    capacity: StrictInt = Field(ge=1)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class SignupCreate(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class EventOut(BaseModel):
    id: int
    name: str
    date: Date
    capacity: int
    signed_up: int
    places_left: int


class SignupOut(BaseModel):
    id: int
    event_id: int
    name: str
    phone: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Church Event Sign-ups", lifespan=lifespan)


def count_signups(session: Session, event_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Signup).where(Signup.event_id == event_id)
    ).one()


def event_out(session: Session, event: Event) -> EventOut:
    taken = count_signups(session, event.id)
    return EventOut(
        id=event.id,
        name=event.name,
        date=event.date,
        capacity=event.capacity,
        signed_up=taken,
        places_left=max(event.capacity - taken, 0),
    )


def get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", response_model=EventOut, status_code=201)
def create_event(data: EventCreate):
    with Session(engine) as session:
        event = Event(name=data.name, date=data.date, capacity=data.capacity)
        session.add(event)
        session.commit()
        session.refresh(event)
        return event_out(session, event)


@app.get("/events", response_model=List[EventOut])
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.date, Event.id)).all()
        return [event_out(session, e) for e in events]


@app.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: int):
    with Session(engine) as session:
        return event_out(session, get_event_or_404(session, event_id))


@app.post("/events/{event_id}/signups", response_model=SignupOut, status_code=201)
def create_signup(event_id: int, data: SignupCreate):
    with signup_lock:
        with Session(engine) as session:
            event = get_event_or_404(session, event_id)
            if count_signups(session, event_id) >= event.capacity:
                raise HTTPException(status_code=409, detail="Sorry, this event is full")
            signup = Signup(event_id=event_id, name=data.name, phone=data.phone)
            session.add(signup)
            session.commit()
            session.refresh(signup)
            return SignupOut(**signup.model_dump())


@app.get("/events/{event_id}/signups", response_model=List[SignupOut])
def list_signups(event_id: int):
    with Session(engine) as session:
        get_event_or_404(session, event_id)
        signups = session.exec(
            select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)
        ).all()
        return [SignupOut(**s.model_dump()) for s in signups]

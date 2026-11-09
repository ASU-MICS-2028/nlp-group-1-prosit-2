import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select, func

DATABASE_URL = "sqlite:///./church_events.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
signup_lock = threading.Lock()


class Event(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    date: date
    capacity: int


class Signup(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    event_id: int = SQLField(foreign_key="event.id", index=True)
    name: str
    phone: str


class EventCreate(BaseModel):
    name: str
    date: date
    capacity: int = Field(..., ge=1, strict=True)

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
    date: date
    capacity: int
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


app = FastAPI(title="Church Events", lifespan=lifespan)


def count_signups(session: Session, event_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Signup).where(Signup.event_id == event_id)
    ).one()


def to_out(session: Session, event: Event) -> EventOut:
    taken = count_signups(session, event.id)
    return EventOut(
        id=event.id,
        name=event.name,
        date=event.date,
        capacity=event.capacity,
        places_left=max(event.capacity - taken, 0),
    )


def get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", status_code=201, response_model=EventOut)
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


@app.post("/events/{event_id}/signups", status_code=201, response_model=SignupOut)
def create_signup(event_id: int, data: SignupCreate):
    with signup_lock:
        with Session(engine) as session:
            event = get_event_or_404(session, event_id)
            if count_signups(session, event_id) >= event.capacity:
                raise HTTPException(status_code=409, detail="The event is full")
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

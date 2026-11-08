from contextlib import asynccontextmanager
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, StrictInt, StrictStr, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

DATABASE_URL = "sqlite:///./church_events.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


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
    yield


app = FastAPI(title="Church Events", lifespan=lifespan)


class EventIn(BaseModel):
    name: StrictStr
    date: StrictStr
    place: StrictStr
    capacity: StrictInt = PField(gt=0)

    @field_validator("name", "place")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("date")
    @classmethod
    def real_date(cls, v: str) -> str:
        v = v.strip()
        try:
            if len(v) != 10:
                raise ValueError
            return Date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("date must be a real date in the form YYYY-MM-DD")


class SignupIn(BaseModel):
    name: StrictStr
    phone: StrictStr

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


def count_signups(session: Session, event_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Signup).where(Signup.event_id == event_id)
    ).one()


def event_out(session: Session, event: Event) -> dict:
    taken = count_signups(session, event.id)
    return {
        "id": event.id,
        "name": event.name,
        "date": event.date,
        "place": event.place,
        "capacity": event.capacity,
        "places_left": max(event.capacity - taken, 0),
    }


def get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    with Session(engine) as session:
        event = Event(name=data.name, date=data.date, place=data.place, capacity=data.capacity)
        session.add(event)
        session.commit()
        session.refresh(event)
        return event_out(session, event)


@app.get("/events")
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.id)).all()
        return [event_out(session, e) for e in events]


@app.get("/events/{eventId}")
def get_event(eventId: int):
    with Session(engine) as session:
        return event_out(session, get_event_or_404(session, eventId))


@app.post("/events/{eventId}/signups", status_code=201)
def create_signup(eventId: int, data: SignupIn):
    with Session(engine) as session:
        event = get_event_or_404(session, eventId)
        if count_signups(session, eventId) >= event.capacity:
            raise HTTPException(
                status_code=409,
                detail="Sorry, this event is full. No more sign-ups are possible.",
            )
        signup = Signup(event_id=eventId, name=data.name, phone=data.phone)
        session.add(signup)
        session.commit()
        session.refresh(signup)
        return {"id": signup.id, "event_id": signup.event_id, "name": signup.name, "phone": signup.phone}


@app.get("/events/{eventId}/signups")
def list_signups(eventId: int):
    with Session(engine) as session:
        get_event_or_404(session, eventId)
        signups = session.exec(
            select(Signup).where(Signup.event_id == eventId).order_by(Signup.id)
        ).all()
        return [
            {"id": s.id, "event_id": s.event_id, "name": s.name, "phone": s.phone}
            for s in signups
        ]

import threading
from contextlib import asynccontextmanager
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

DATABASE_URL = "sqlite:///./church_events.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
signup_lock = threading.Lock()


# ---------- Database tables ----------
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


# ---------- Request bodies ----------
class EventIn(BaseModel):
    name: str
    date: str
    place: str
    capacity: StrictInt

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
            return Date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("date must be a real date in the form YYYY-MM-DD")

    @field_validator("capacity")
    @classmethod
    def positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("capacity must be a whole number greater than zero")
        return v


class SignupIn(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


# ---------- App ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    # Older database files may lack the "place" column; add it if needed.
    with engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(event)")]
        if "place" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE event ADD COLUMN place VARCHAR NOT NULL DEFAULT ''"
            )
    yield


app = FastAPI(title="Church Event Sign-ups", lifespan=lifespan)


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
        "signed_up": taken,
        "places_left": max(event.capacity - taken, 0),
    }


def get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", status_code=201)
def create_event(body: EventIn):
    with Session(engine) as session:
        event = Event(
            name=body.name, date=body.date, place=body.place, capacity=body.capacity
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event_out(session, event)


@app.get("/events")
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.id)).all()
        return [event_out(session, e) for e in events]


@app.get("/events/{event_id}")
def get_event(event_id: int):
    with Session(engine) as session:
        return event_out(session, get_event_or_404(session, event_id))


@app.post("/events/{event_id}/signups", status_code=201)
def create_signup(event_id: int, body: SignupIn):
    with signup_lock:
        with Session(engine) as session:
            event = get_event_or_404(session, event_id)
            if count_signups(session, event_id) >= event.capacity:
                raise HTTPException(
                    status_code=409,
                    detail="Sorry, this event is full. No more sign-ups are possible.",
                )
            signup = Signup(event_id=event_id, name=body.name, phone=body.phone)
            session.add(signup)
            session.commit()
            session.refresh(signup)
            return signup.model_dump()


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with Session(engine) as session:
        get_event_or_404(session, event_id)
        signups = session.exec(
            select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)
        ).all()
        return [s.model_dump() for s in signups]

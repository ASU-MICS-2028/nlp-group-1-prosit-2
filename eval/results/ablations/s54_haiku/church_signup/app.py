import datetime
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine(
    "sqlite:///./church_events.db",
    connect_args={"check_same_thread": False},
)

# Keeps the "check spaces left, then save" step from running twice at once.
signup_lock = threading.Lock()


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
    name: str = Field(min_length=1)
    date: datetime.date
    capacity: int = Field(ge=1)


class SignupIn(SQLModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Church Events", lifespan=lifespan)


def event_out(event: Event, session: Session) -> dict:
    signed_up = len(
        session.exec(select(Signup).where(Signup.event_id == event.id)).all()
    )
    return {
        "id": event.id,
        "name": event.name,
        "date": event.date.isoformat(),
        "capacity": event.capacity,
        "signed_up": signed_up,
        "spots_left": max(event.capacity - signed_up, 0),
    }


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Event name cannot be blank")
    with Session(engine) as session:
        event = Event(name=name, date=data.date, capacity=data.capacity)
        session.add(event)
        session.commit()
        session.refresh(event)
        return event_out(event, session)


@app.get("/events")
def list_events():
    with Session(engine) as session:
        events = session.exec(select(Event).order_by(Event.date, Event.id)).all()
        return [event_out(e, session) for e in events]


@app.get("/events/{event_id}")
def get_event(event_id: int):
    with Session(engine) as session:
        event = session.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event_out(event, session)


@app.post("/events/{event_id}/signups", status_code=201)
def sign_up(event_id: int, data: SignupIn):
    name = data.name.strip()
    phone = data.phone.strip()
    if not name or not phone:
        raise HTTPException(status_code=422, detail="Name and phone cannot be blank")
    with signup_lock, Session(engine) as session:
        event = session.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        taken = len(
            session.exec(select(Signup).where(Signup.event_id == event_id)).all()
        )
        if taken >= event.capacity:
            raise HTTPException(status_code=409, detail="This event is full")
        already = session.exec(
            select(Signup).where(Signup.event_id == event_id, Signup.phone == phone)
        ).first()
        if already is not None:
            raise HTTPException(
                status_code=409,
                detail="This phone number is already signed up for this event",
            )
        signup = Signup(event_id=event_id, name=name, phone=phone)
        session.add(signup)
        session.commit()
        session.refresh(signup)
        return {
            "id": signup.id,
            "event_id": signup.event_id,
            "name": signup.name,
            "phone": signup.phone,
        }


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with Session(engine) as session:
        if session.get(Event, event_id) is None:
            raise HTTPException(status_code=404, detail="Event not found")
        signups = session.exec(
            select(Signup).where(Signup.event_id == event_id).order_by(Signup.id)
        ).all()
        return [
            {"id": s.id, "event_id": s.event_id, "name": s.name, "phone": s.phone}
            for s in signups
        ]

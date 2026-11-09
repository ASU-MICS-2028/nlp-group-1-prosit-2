import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, StrictStr
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine(
    "sqlite:///hostel.db", connect_args={"check_same_thread": False}
)
booking_lock = threading.Lock()


class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    beds: int


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(index=True, foreign_key="room.id")
    student_name: str
    arrival: date
    leaving: date


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Legon Hostel Bed Booking", lifespan=lifespan)


class RoomIn(BaseModel):
    name: StrictStr
    beds: StrictInt


class BookingIn(BaseModel):
    student_name: StrictStr
    arrival: StrictStr
    leaving: StrictStr


def parse_date(value, label: str) -> date:
    if value is None or not isinstance(value, str) or not value.strip():
        raise HTTPException(422, f"The {label} date is required (YYYY-MM-DD).")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise HTTPException(422, f"The {label} date is not a real date (use YYYY-MM-DD).")


def parse_stay(arrival, leaving):
    a = parse_date(arrival, "arrival")
    l = parse_date(leaving, "leaving")
    if l <= a:
        raise HTTPException(422, "The leaving date must be after the arrival date.")
    return a, l


def max_beds_taken(session: Session, room_id: int, arrival: date, leaving: date) -> int:
    """Largest number of beds taken on any night from arrival to the night before leaving."""
    overlapping = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.arrival < leaving,
            Booking.leaving > arrival,
        )
    ).all()
    nights = {arrival} | {b.arrival for b in overlapping if b.arrival > arrival}
    best = 0
    for night in nights:
        count = sum(1 for b in overlapping if b.arrival <= night < b.leaving)
        best = max(best, count)
    return best


def room_out(room: Room) -> dict:
    return {"room_number": room.id, "name": room.name, "beds": room.beds}


def booking_out(b: Booking) -> dict:
    return {
        "booking_number": b.id,
        "room_number": b.room_id,
        "student_name": b.student_name,
        "arrival": b.arrival.isoformat(),
        "leaving": b.leaving.isoformat(),
    }


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "The room needs a name.")
    if data.beds < 1:
        raise HTTPException(422, "The number of beds must be a whole number of at least 1.")
    with Session(engine) as session:
        room = Room(name=name, beds=data.beds)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room_out(room)


@app.post("/rooms/{room_number}/bookings", status_code=201)
def book_bed(room_number: int, data: BookingIn):
    student = data.student_name.strip()
    if not student:
        raise HTTPException(422, "The student's name is required.")
    arrival, leaving = parse_stay(data.arrival, data.leaving)
    with booking_lock, Session(engine) as session:
        room = session.get(Room, room_number)
        if room is None:
            raise HTTPException(404, "That room does not exist.")
        if max_beds_taken(session, room.id, arrival, leaving) >= room.beds:
            raise HTTPException(
                409, "All beds in this room are taken on at least one night of that stay."
            )
        booking = Booking(
            room_id=room.id, student_name=student, arrival=arrival, leaving=leaving
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking_out(booking)


@app.delete("/bookings/{booking_number}")
def cancel_booking(booking_number: int):
    with booking_lock, Session(engine) as session:
        booking = session.get(Booking, booking_number)
        if booking is None:
            raise HTTPException(404, "No booking with that number (or it was already cancelled).")
        result = booking_out(booking)
        session.delete(booking)
        session.commit()
        return {"cancelled": True, "booking": result}


@app.get("/availability")
def availability(arrival: Optional[str] = None, leaving: Optional[str] = None):
    a, l = parse_stay(arrival, leaving)
    with Session(engine) as session:
        rooms = session.exec(select(Room).order_by(Room.id)).all()
        result = []
        for room in rooms:
            free = max(room.beds - max_beds_taken(session, room.id, a, l), 0)
            result.append({**room_out(room), "free_beds": free})
        return {"arrival": a.isoformat(), "leaving": l.isoformat(), "rooms": result}

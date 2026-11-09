import threading
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField
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
    room_id: int = Field(foreign_key="room.id", index=True)
    student_name: str
    arrival: date
    leaving: date


class RoomIn(BaseModel):
    name: str = PField(min_length=1)
    beds: int = PField(ge=1)


class BookingIn(BaseModel):
    room_id: int
    student_name: str = PField(min_length=1)
    arrival: date
    leaving: date


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


def check_dates(arrival: date, leaving: date):
    if leaving <= arrival:
        raise HTTPException(400, "The leaving date must be after the arrival date")


def max_beds_taken(session: Session, room_id: int, arrival: date, leaving: date) -> int:
    """Highest number of beds taken on any night from arrival to the night before leaving."""
    bookings = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.arrival < leaving,
            Booking.leaving > arrival,
        )
    ).all()
    highest = 0
    night = arrival
    while night < leaving:
        taken = sum(1 for b in bookings if b.arrival <= night < b.leaving)
        highest = max(highest, taken)
        night += timedelta(days=1)
    return highest


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with Session(engine) as session:
        room = Room(name=data.name, beds=data.beds)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room


@app.post("/bookings", status_code=201)
def book_bed(data: BookingIn):
    check_dates(data.arrival, data.leaving)
    with booking_lock, Session(engine) as session:
        room = session.get(Room, data.room_id)
        if room is None:
            raise HTTPException(404, "Room not found")
        if max_beds_taken(session, room.id, data.arrival, data.leaving) >= room.beds:
            raise HTTPException(409, "All beds in this room are taken on at least one night of this stay")
        booking = Booking(
            room_id=room.id,
            student_name=data.student_name,
            arrival=data.arrival,
            leaving=data.leaving,
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking


@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int):
    with booking_lock, Session(engine) as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            raise HTTPException(404, "Booking not found")
        session.delete(booking)
        session.commit()
        return {"cancelled": booking_id}


@app.get("/availability")
def availability(arrival: date, leaving: date):
    check_dates(arrival, leaving)
    with Session(engine) as session:
        rooms = session.exec(select(Room).order_by(Room.id)).all()
        return [
            {
                "room_id": r.id,
                "name": r.name,
                "beds": r.beds,
                "free_beds": r.beds - max_beds_taken(session, r.id, arrival, leaving),
            }
            for r in rooms
        ]

import threading
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///hostel.db", connect_args={"check_same_thread": False})
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
    departure: date


class RoomIn(SQLModel):
    name: str
    beds: int

    @field_validator("name")
    @classmethod
    def name_ok(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("beds")
    @classmethod
    def beds_ok(cls, v):
        if v < 1:
            raise ValueError("beds must be at least 1")
        return v


class BookingIn(SQLModel):
    room_id: int
    student_name: str
    arrival: date
    departure: date

    @field_validator("student_name")
    @classmethod
    def name_ok(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("student_name must not be empty")
        return v


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Hostel bed booking", lifespan=lifespan)


def check_dates(arrival: date, departure: date):
    if departure <= arrival:
        raise HTTPException(status_code=400, detail="Leaving date must be after the arrival date")


def free_beds(session: Session, room: Room, arrival: date, departure: date) -> int:
    """Beds free on every night from arrival up to the night before departure."""
    bookings = session.exec(
        select(Booking).where(
            Booking.room_id == room.id,
            Booking.arrival < departure,
            Booking.departure > arrival,
        )
    ).all()
    max_used = 0
    night = arrival
    while night < departure:
        used = sum(1 for b in bookings if b.arrival <= night < b.departure)
        max_used = max(max_used, used)
        night += timedelta(days=1)
    return max(room.beds - max_used, 0)


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with Session(engine) as session:
        room = Room(name=data.name, beds=data.beds)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room.model_dump()


@app.post("/bookings", status_code=201)
def book_bed(data: BookingIn):
    check_dates(data.arrival, data.departure)
    with booking_lock, Session(engine) as session:
        room = session.get(Room, data.room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="Room not found")
        if free_beds(session, room, data.arrival, data.departure) < 1:
            raise HTTPException(
                status_code=409,
                detail="All beds in this room are taken on at least one night of this stay",
            )
        booking = Booking(**data.model_dump())
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking.model_dump(mode="json")


@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int):
    with booking_lock, Session(engine) as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        session.delete(booking)
        session.commit()
        return {"cancelled": True, "id": booking_id}


@app.get("/availability")
def availability(arrival: date = Query(...), departure: date = Query(...)):
    check_dates(arrival, departure)
    with Session(engine) as session:
        rooms = session.exec(select(Room).order_by(Room.id)).all()
        return [
            {
                "room_id": r.id,
                "name": r.name,
                "beds": r.beds,
                "free_beds": free_beds(session, r, arrival, departure),
            }
            for r in rooms
        ]

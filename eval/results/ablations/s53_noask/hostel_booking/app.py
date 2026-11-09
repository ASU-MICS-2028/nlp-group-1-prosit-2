from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///hostel.db", connect_args={"check_same_thread": False})


class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    beds: int


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="room.id", index=True)
    student_name: str
    arrival: date
    departure: date
    cancelled: bool = Field(default=False)


class RoomIn(BaseModel):
    name: str = PField(min_length=1)
    beds: int = PField(ge=1)

    @field_validator("name")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()


class BookingIn(BaseModel):
    room_id: int
    student_name: str = PField(min_length=1)
    arrival: date
    departure: date

    @field_validator("student_name")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("student_name must not be blank")
        return v.strip()


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Hostel Bed Booking", lifespan=lifespan)


def max_beds_taken(session: Session, room_id: int, arrival: date, departure: date) -> int:
    """Largest number of beds taken on any single night from arrival up to the night before departure."""
    bookings = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.cancelled == False,  # noqa: E712
            Booking.arrival < departure,
            Booking.departure > arrival,
        )
    ).all()
    events = []
    for b in bookings:
        events.append((max(b.arrival, arrival), 1))
        events.append((min(b.departure, departure), -1))
    # on the same date, departures (-1) free the bed before arrivals (+1) take it
    events.sort(key=lambda e: (e[0], e[1]))
    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with Session(engine) as s:
        room = Room(name=data.name, beds=data.beds)
        s.add(room)
        s.commit()
        s.refresh(room)
        return room.model_dump()


@app.get("/rooms")
def list_rooms():
    with Session(engine) as s:
        return [r.model_dump() for r in s.exec(select(Room).order_by(Room.id)).all()]


@app.post("/bookings", status_code=201)
def book_bed(data: BookingIn):
    if data.departure <= data.arrival:
        raise HTTPException(400, "The leaving date must be after the arrival date")
    with Session(engine) as s:
        room = s.get(Room, data.room_id)
        if not room:
            raise HTTPException(404, "Room not found")
        if max_beds_taken(s, room.id, data.arrival, data.departure) >= room.beds:
            raise HTTPException(409, "All beds in this room are taken on at least one night of this stay")
        booking = Booking(
            room_id=room.id,
            student_name=data.student_name,
            arrival=data.arrival,
            departure=data.departure,
        )
        s.add(booking)
        s.commit()
        s.refresh(booking)
        return booking.model_dump(mode="json")


@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int):
    with Session(engine) as s:
        booking = s.get(Booking, booking_id)
        if not booking or booking.cancelled:
            raise HTTPException(404, "Booking not found")
        booking.cancelled = True
        s.add(booking)
        s.commit()
        return {"detail": "Booking cancelled", "id": booking_id}


@app.get("/availability")
def availability(arrival: date = Query(...), departure: date = Query(...)):
    if departure <= arrival:
        raise HTTPException(400, "The leaving date must be after the arrival date")
    with Session(engine) as s:
        result = []
        for room in s.exec(select(Room).order_by(Room.id)).all():
            taken = max_beds_taken(s, room.id, arrival, departure)
            result.append({
                "room_id": room.id,
                "name": room.name,
                "beds": room.beds,
                "free_beds": max(room.beds - taken, 0),
            })
        return result

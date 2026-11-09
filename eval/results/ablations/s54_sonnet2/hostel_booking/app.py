from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///hostel.db", connect_args={"check_same_thread": False})


class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    beds: int


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(index=True)
    student_name: str
    arrival: date
    departure: date


class RoomIn(BaseModel):
    name: str
    beds: int

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        if not v.strip():
            raise ValueError("name required")
        return v

    @field_validator("beds")
    @classmethod
    def _b(cls, v):
        if v < 1:
            raise ValueError("beds must be at least 1")
        return v


class BookingIn(BaseModel):
    student_name: str
    arrival: date
    departure: date

    @field_validator("student_name")
    @classmethod
    def _n(cls, v):
        if not v.strip():
            raise ValueError("name required")
        return v


app = FastAPI()
SQLModel.metadata.create_all(engine)


def max_used(session, room_id, start, end):
    """Max beds taken on any night in [start, end)."""
    bs = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.arrival < end,
            Booking.departure > start,
        )
    ).all()
    best = 0
    for n in {max(b.arrival, start) for b in bs}:
        c = sum(1 for b in bs if b.arrival <= n < b.departure)
        best = max(best, c)
    return best


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with Session(engine) as s:
        r = Room(name=data.name, beds=data.beds)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


@app.get("/rooms")
def list_rooms():
    with Session(engine) as s:
        return s.exec(select(Room)).all()


@app.get("/availability")
def availability(arrival: date, departure: date):
    if departure <= arrival:
        raise HTTPException(422, "departure must be after arrival")
    with Session(engine) as s:
        return [
            {
                "room_id": r.id,
                "name": r.name,
                "beds": r.beds,
                "free_beds": r.beds - max_used(s, r.id, arrival, departure),
            }
            for r in s.exec(select(Room)).all()
        ]


@app.post("/rooms/{room_id}/bookings", status_code=201)
def book(room_id: int, data: BookingIn):
    if data.departure <= data.arrival:
        raise HTTPException(422, "departure must be after arrival")
    with Session(engine) as s:
        room = s.get(Room, room_id)
        if not room:
            raise HTTPException(404, "room not found")
        if max_used(s, room_id, data.arrival, data.departure) >= room.beds:
            raise HTTPException(409, "no free bed for the whole stay")
        b = Booking(room_id=room_id, **data.model_dump())
        s.add(b)
        s.commit()
        s.refresh(b)
        return b


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: int):
    with Session(engine) as s:
        b = s.get(Booking, booking_id)
        if not b:
            raise HTTPException(404, "booking not found")
        return b


@app.delete("/bookings/{booking_id}")
def cancel(booking_id: int):
    with Session(engine) as s:
        b = s.get(Booking, booking_id)
        if not b:
            raise HTTPException(404, "booking not found")
        s.delete(b)
        s.commit()
        return {"cancelled": booking_id}

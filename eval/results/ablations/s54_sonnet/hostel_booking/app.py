from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select


class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    beds: int


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(index=True)
    student_name: str
    arrival: date
    leaving: date


class RoomIn(BaseModel):
    name: str
    beds: int

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v.strip():
            raise ValueError("name must not be empty")
        return v

    @field_validator("beds")
    @classmethod
    def _beds(cls, v):
        if v < 1:
            raise ValueError("beds must be at least 1")
        return v


class BookingIn(BaseModel):
    student_name: str
    arrival: date
    leaving: date

    @field_validator("student_name")
    @classmethod
    def _name(cls, v):
        if not v.strip():
            raise ValueError("student_name must not be empty")
        return v


engine = create_engine("sqlite:///hostel.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def check_dates(arrival: date, leaving: date):
    if leaving <= arrival:
        raise HTTPException(status_code=422, detail="leaving must be after arrival")


def max_occupied(session, room_id: int, arrival: date, leaving: date) -> int:
    bookings = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.arrival < leaving,
            Booking.leaving > arrival,
        )
    ).all()
    worst = 0
    night = arrival
    while night < leaving:
        n = sum(1 for b in bookings if b.arrival <= night < b.leaving)
        worst = max(worst, n)
        night += timedelta(days=1)
    return worst


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with Session(engine) as s:
        room = Room(name=data.name, beds=data.beds)
        s.add(room)
        s.commit()
        s.refresh(room)
        return room


@app.get("/rooms")
def list_rooms():
    with Session(engine) as s:
        return s.exec(select(Room)).all()


@app.post("/rooms/{room_id}/bookings", status_code=201)
def book(room_id: int, data: BookingIn):
    check_dates(data.arrival, data.leaving)
    with Session(engine) as s:
        room = s.get(Room, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="room not found")
        if max_occupied(s, room_id, data.arrival, data.leaving) >= room.beds:
            raise HTTPException(status_code=409, detail="no free bed for the whole stay")
        b = Booking(room_id=room_id, student_name=data.student_name,
                    arrival=data.arrival, leaving=data.leaving)
        s.add(b)
        s.commit()
        s.refresh(b)
        return b


@app.delete("/bookings/{booking_id}")
def cancel(booking_id: int):
    with Session(engine) as s:
        b = s.get(Booking, booking_id)
        if not b:
            raise HTTPException(status_code=404, detail="booking not found")
        s.delete(b)
        s.commit()
        return {"cancelled": booking_id}


@app.get("/availability")
def availability(arrival: date, leaving: date):
    check_dates(arrival, leaving)
    with Session(engine) as s:
        return [
            {"room_id": r.id, "name": r.name, "beds": r.beds,
             "free_beds": r.beds - max_occupied(s, r.id, arrival, leaving)}
            for r in s.exec(select(Room)).all()
        ]

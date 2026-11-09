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
    cancelled: bool = False


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


SQLModel.metadata.create_all(engine)
app = FastAPI()


def max_used(session, room_id, a, d):
    """Max beds in use on any night in [a, d)."""
    bks = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.cancelled == False,  # noqa
            Booking.arrival < d,
            Booking.departure > a,
        )
    ).all()
    best = 0
    for b in bks:
        # max occupancy occurs at some booking's arrival (clamped to a)
        night = max(b.arrival, a)
        n = sum(1 for o in bks if o.arrival <= night < o.departure)
        best = max(best, n)
    return best


def bk_out(b):
    return {
        "id": b.id,
        "room_id": b.room_id,
        "student_name": b.student_name,
        "arrival": b.arrival.isoformat(),
        "departure": b.departure.isoformat(),
        "cancelled": b.cancelled,
    }


@app.post("/rooms", status_code=201)
def add_room(r: RoomIn):
    with Session(engine) as s:
        room = Room(name=r.name, beds=r.beds)
        s.add(room)
        s.commit()
        s.refresh(room)
        return room.model_dump()


@app.get("/rooms")
def list_rooms():
    with Session(engine) as s:
        return [r.model_dump() for r in s.exec(select(Room)).all()]


@app.post("/rooms/{room_id}/bookings", status_code=201)
def book(room_id: int, b: BookingIn):
    if b.departure <= b.arrival:
        raise HTTPException(422, "departure must be after arrival")
    with Session(engine) as s:
        room = s.get(Room, room_id)
        if not room:
            raise HTTPException(404, "room not found")
        if max_used(s, room_id, b.arrival, b.departure) >= room.beds:
            raise HTTPException(409, "no free bed for the whole stay")
        bk = Booking(room_id=room_id, student_name=b.student_name,
                     arrival=b.arrival, departure=b.departure)
        s.add(bk)
        s.commit()
        s.refresh(bk)
        return bk_out(bk)


@app.delete("/bookings/{booking_id}")
def cancel(booking_id: int):
    with Session(engine) as s:
        bk = s.get(Booking, booking_id)
        if not bk:
            raise HTTPException(404, "booking not found")
        bk.cancelled = True
        s.add(bk)
        s.commit()
        s.refresh(bk)
        return bk_out(bk)


@app.get("/availability")
def availability(arrival: date, departure: date):
    if departure <= arrival:
        raise HTTPException(422, "departure must be after arrival")
    with Session(engine) as s:
        out = []
        for r in s.exec(select(Room)).all():
            free = r.beds - max_used(s, r.id, arrival, departure)
            out.append({"room_id": r.id, "name": r.name, "beds": r.beds,
                        "free_beds": max(free, 0)})
        return out

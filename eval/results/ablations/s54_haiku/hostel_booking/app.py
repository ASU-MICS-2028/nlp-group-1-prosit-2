import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

engine = create_engine(
    "sqlite:///./hostel.db", connect_args={"check_same_thread": False}
)


class Room(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    beds: int


class Booking(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    code: str = SQLField(index=True, unique=True)
    room_id: int = SQLField(foreign_key="room.id")
    student_name: str
    arrival: date
    leaving: date


class RoomIn(BaseModel):
    name: str
    beds: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


class BookingIn(BaseModel):
    room_id: int
    student_name: str
    arrival: date
    leaving: date

    @field_validator("student_name")
    @classmethod
    def student_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("student_name must not be empty")
        return value

    @model_validator(mode="after")
    def leaving_after_arrival(self):
        if self.leaving <= self.arrival:
            raise ValueError("leaving must be after arrival")
        return self


def free_beds_for_stay(session: Session, room: Room, arrival: date, leaving: date) -> int:
    """Beds free on every night from arrival up to (not including) leaving."""
    overlapping = session.exec(
        select(Booking).where(
            Booking.room_id == room.id,
            Booking.arrival < leaving,
            Booking.leaving > arrival,
        )
    ).all()
    worst_taken = 0
    night = arrival
    while night < leaving:
        taken = sum(1 for b in overlapping if b.arrival <= night < b.leaving)
        worst_taken = max(worst_taken, taken)
        night += timedelta(days=1)
    return room.beds - worst_taken


@asynccontextmanager
async def lifespan(_: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Legon Student Hostel Bed Booking", lifespan=lifespan)


@app.post("/rooms", status_code=201)
def add_room(body: RoomIn):
    with Session(engine) as session:
        room = Room(name=body.name, beds=body.beds)
        session.add(room)
        session.commit()
        session.refresh(room)
        return {"id": room.id, "name": room.name, "beds": room.beds}


@app.post("/bookings", status_code=201)
def book_bed(body: BookingIn):
    with Session(engine) as session:
        room = session.get(Room, body.room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="Room not found")
        if free_beds_for_stay(session, room, body.arrival, body.leaving) < 1:
            raise HTTPException(
                status_code=409,
                detail="No bed is free in this room for every night of the stay",
            )
        booking = Booking(
            code=secrets.token_urlsafe(9),
            room_id=room.id,
            student_name=body.student_name,
            arrival=body.arrival,
            leaving=body.leaving,
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return {
            "booking_code": booking.code,
            "room_id": booking.room_id,
            "student_name": booking.student_name,
            "arrival": booking.arrival,
            "leaving": booking.leaving,
        }


@app.delete("/bookings/{code}")
def cancel_booking(code: str):
    with Session(engine) as session:
        booking = session.exec(select(Booking).where(Booking.code == code)).first()
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        session.delete(booking)
        session.commit()
        return {"cancelled": True, "booking_code": code}


@app.get("/availability")
def availability(arrival: date, leaving: date):
    if leaving <= arrival:
        raise HTTPException(status_code=422, detail="leaving must be after arrival")
    with Session(engine) as session:
        rooms = session.exec(select(Room).order_by(Room.id)).all()
        return [
            {
                "room_id": room.id,
                "name": room.name,
                "beds": room.beds,
                "free_beds": free_beds_for_stay(session, room, arrival, leaving),
            }
            for room in rooms
        ]

import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt, field_validator
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///hostel.db", connect_args={"check_same_thread": False})
booking_lock = threading.Lock()


class Room(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    beds: int


class Booking(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = SQLField(default=None, primary_key=True)
    room_id: int = SQLField(foreign_key="room.id", index=True)
    student_name: str
    arrival: date
    leaving: date


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Legon Hostel Bed Booking", lifespan=lifespan)


class RoomIn(BaseModel):
    name: str
    beds: StrictInt = Field(ge=1)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Room name must not be empty")
        return v


class BookingIn(BaseModel):
    studentName: str
    arrival: date
    leaving: date

    @field_validator("studentName")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Student name must not be empty")
        return v


def room_out(room: Room) -> dict:
    return {"roomNumber": room.id, "name": room.name, "beds": room.beds}


def booking_out(b: Booking) -> dict:
    return {
        "bookingNumber": b.id,
        "roomNumber": b.room_id,
        "studentName": b.student_name,
        "arrival": b.arrival.isoformat(),
        "leaving": b.leaving.isoformat(),
    }


def max_beds_taken(session: Session, room_id: int, arrival: date, leaving: date) -> int:
    """Most beds taken on any single night from arrival up to the night before leaving."""
    bookings = session.exec(
        select(Booking).where(
            Booking.room_id == room_id,
            Booking.arrival < leaving,
            Booking.leaving > arrival,
        )
    ).all()
    events = []
    for b in bookings:
        start = max(b.arrival, arrival)
        end = min(b.leaving, leaving)
        events.append((start, 1))
        events.append((end, -1))
    # at the same date, a departure (-1) is processed before an arrival (+1)
    events.sort(key=lambda e: (e[0], e[1]))
    current = best = 0
    for _, delta in events:
        current += delta
        best = max(best, current)
    return best


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with Session(engine) as session:
        room = Room(name=data.name, beds=data.beds)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room_out(room)


@app.post("/rooms/{roomNumber}/bookings", status_code=201)
def book_bed(roomNumber: int, data: BookingIn):
    if data.leaving <= data.arrival:
        raise HTTPException(status_code=400, detail="The leaving date must be after the arrival date")
    with booking_lock:
        with Session(engine) as session:
            room = session.get(Room, roomNumber)
            if room is None:
                raise HTTPException(status_code=404, detail="Room not found")
            if max_beds_taken(session, room.id, data.arrival, data.leaving) >= room.beds:
                raise HTTPException(
                    status_code=409,
                    detail="All beds in this room are taken on at least one night of this stay",
                )
            booking = Booking(
                room_id=room.id,
                student_name=data.studentName,
                arrival=data.arrival,
                leaving=data.leaving,
            )
            session.add(booking)
            session.commit()
            session.refresh(booking)
            return booking_out(booking)


@app.delete("/bookings/{bookingNumber}")
def cancel_booking(bookingNumber: int):
    with booking_lock:
        with Session(engine) as session:
            booking = session.get(Booking, bookingNumber)
            if booking is None:
                raise HTTPException(status_code=404, detail="Booking not found")
            out = booking_out(booking)
            session.delete(booking)
            session.commit()
            return {"cancelled": True, "booking": out}


@app.get("/availability")
def availability(arrival: date = Query(...), leaving: date = Query(...)):
    if leaving <= arrival:
        raise HTTPException(status_code=400, detail="The leaving date must be after the arrival date")
    with Session(engine) as session:
        rooms = session.exec(select(Room).order_by(Room.id)).all()
        result = []
        for room in rooms:
            taken = max_beds_taken(session, room.id, arrival, leaving)
            result.append({**room_out(room), "freeBeds": max(room.beds - taken, 0)})
        return {"arrival": arrival.isoformat(), "leaving": leaving.isoformat(), "rooms": result}

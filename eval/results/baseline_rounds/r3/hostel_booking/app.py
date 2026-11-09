from datetime import date, timedelta
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

app = FastAPI(title="Legon Student Hostel Bed Booking")

_lock = Lock()
rooms: Dict[int, dict] = {}
bookings: Dict[int, dict] = {}
_counters = {"room": 0, "booking": 0}


class RoomIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str = Field(..., validation_alias=AliasChoices("name", "room_name"))
    beds: int = Field(..., validation_alias=AliasChoices("beds", "bed_count", "number_of_beds", "num_beds", "capacity"))

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Room name must not be empty")
        return v

    @field_validator("beds")
    @classmethod
    def _beds(cls, v: int) -> int:
        if v < 1:
            raise ValueError("A room must have at least one bed")
        return v


class BookingBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    student_name: str = Field(..., validation_alias=AliasChoices("student_name", "name", "student"))
    arrival_date: date = Field(..., validation_alias=AliasChoices("arrival_date", "arrival", "check_in", "start_date"))
    leaving_date: date = Field(..., validation_alias=AliasChoices("leaving_date", "leaving", "departure_date", "departure", "check_out", "end_date"))

    @field_validator("student_name")
    @classmethod
    def _sname(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Student name must not be empty")
        return v

    @model_validator(mode="after")
    def _dates(self):
        if self.leaving_date <= self.arrival_date:
            raise ValueError("The leaving date must be after the arrival date")
        return self


class BookingIn(BookingBase):
    room_id: int


def _nights(arrival: date, leaving: date):
    d = arrival
    while d < leaving:
        yield d
        d += timedelta(days=1)


def _max_used(room_id: int, arrival: date, leaving: date) -> int:
    active = [b for b in bookings.values() if b["room_id"] == room_id and b["status"] == "active"
              and b["arrival_date"] < leaving and b["leaving_date"] > arrival]
    worst = 0
    for night in _nights(arrival, leaving):
        used = sum(1 for b in active if b["arrival_date"] <= night < b["leaving_date"])
        worst = max(worst, used)
    return worst


def _room_out(r: dict) -> dict:
    return {"id": r["id"], "name": r["name"], "beds": r["beds"]}


def _booking_out(b: dict) -> dict:
    r = rooms.get(b["room_id"])
    return {
        "id": b["id"],
        "room_id": b["room_id"],
        "room_name": r["name"] if r else None,
        "student_name": b["student_name"],
        "arrival_date": b["arrival_date"].isoformat(),
        "leaving_date": b["leaving_date"].isoformat(),
        "nights": (b["leaving_date"] - b["arrival_date"]).days,
        "status": b["status"],
        "cancelled": b["status"] == "cancelled",
    }


@app.get("/")
def home():
    return {"message": "Legon student hostel bed booking. See /docs for help."}


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    with _lock:
        _counters["room"] += 1
        rid = _counters["room"]
        rooms[rid] = {"id": rid, "name": data.name, "beds": data.beds}
        return _room_out(rooms[rid])


@app.get("/rooms")
def list_rooms():
    with _lock:
        return [_room_out(r) for r in rooms.values()]


@app.get("/rooms/{room_id}")
def get_room(room_id: int):
    with _lock:
        r = rooms.get(room_id)
        if not r:
            raise HTTPException(404, "Room not found")
        return _room_out(r)


def _create_booking(room_id: int, data: BookingBase) -> dict:
    with _lock:
        r = rooms.get(room_id)
        if not r:
            raise HTTPException(404, "Room not found")
        if _max_used(room_id, data.arrival_date, data.leaving_date) >= r["beds"]:
            raise HTTPException(409, "All beds in this room are already taken on at least one night of this stay")
        _counters["booking"] += 1
        bid = _counters["booking"]
        bookings[bid] = {
            "id": bid,
            "room_id": room_id,
            "student_name": data.student_name,
            "arrival_date": data.arrival_date,
            "leaving_date": data.leaving_date,
            "status": "active",
        }
        return _booking_out(bookings[bid])


@app.post("/bookings", status_code=201)
def book_bed(data: BookingIn):
    return _create_booking(data.room_id, data)


@app.post("/rooms/{room_id}/bookings", status_code=201)
def book_bed_in_room(room_id: int, data: BookingBase):
    return _create_booking(room_id, data)


@app.get("/bookings")
def list_bookings(room_id: Optional[int] = None, include_cancelled: bool = True):
    with _lock:
        out = []
        for b in bookings.values():
            if room_id is not None and b["room_id"] != room_id:
                continue
            if not include_cancelled and b["status"] != "active":
                continue
            out.append(_booking_out(b))
        return out


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: int):
    with _lock:
        b = bookings.get(booking_id)
        if not b:
            raise HTTPException(404, "Booking not found")
        return _booking_out(b)


def _cancel(booking_id: int) -> dict:
    with _lock:
        b = bookings.get(booking_id)
        if not b:
            raise HTTPException(404, "Booking not found")
        if b["status"] == "cancelled":
            raise HTTPException(409, "This booking is already cancelled")
        b["status"] = "cancelled"
        return _booking_out(b)


@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int):
    return _cancel(booking_id)


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking_post(booking_id: int):
    return _cancel(booking_id)


@app.get("/availability")
def availability(
    arrival_date: date = Query(..., description="Arrival date YYYY-MM-DD"),
    leaving_date: date = Query(..., description="Leaving date YYYY-MM-DD"),
):
    if leaving_date <= arrival_date:
        raise HTTPException(422, "The leaving date must be after the arrival date")
    with _lock:
        result = []
        for r in rooms.values():
            free = max(0, r["beds"] - _max_used(r["id"], arrival_date, leaving_date))
            result.append({
                "room_id": r["id"],
                "id": r["id"],
                "name": r["name"],
                "room_name": r["name"],
                "beds": r["beds"],
                "free_beds": free,
            })
        return result

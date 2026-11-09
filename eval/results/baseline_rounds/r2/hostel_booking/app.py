from datetime import date
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

app = FastAPI(title="Legon Student Hostel Bed Booking")

_lock = Lock()
_rooms: Dict[int, dict] = {}
_bookings: Dict[int, dict] = {}
_next_room_id = 1
_next_booking_id = 1


class RoomIn(BaseModel):
    name: str = Field(..., min_length=1)
    beds: int = Field(..., ge=1)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class BookingIn(BaseModel):
    room_id: int
    student_name: str = Field(..., min_length=1)
    arrival_date: date
    departure_date: date

    @field_validator("student_name")
    @classmethod
    def strip_student(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("student_name must not be empty")
        return v

    @model_validator(mode="after")
    def check_dates(self):
        if self.departure_date <= self.arrival_date:
            raise ValueError("departure_date must be after arrival_date")
        return self


def _max_occupancy(room_id: int, start: date, end: date, exclude: Optional[int] = None) -> int:
    """Max number of beds taken on any night in [start, end)."""
    events = []
    for b in _bookings.values():
        if b["room_id"] != room_id or b["status"] != "active" or b["id"] == exclude:
            continue
        s = max(b["arrival_date"], start)
        e = min(b["departure_date"], end)
        if s < e:
            events.append((s, 1))
            events.append((e, -1))
    # departures (-1) processed before arrivals (+1) on the same date
    events.sort(key=lambda x: (x[0], x[1]))
    cur = 0
    best = 0
    for _, delta in events:
        cur += delta
        if cur > best:
            best = cur
    return best


def _room_out(r: dict) -> dict:
    return {"id": r["id"], "name": r["name"], "beds": r["beds"]}


def _booking_out(b: dict) -> dict:
    room = _rooms.get(b["room_id"])
    return {
        "id": b["id"],
        "room_id": b["room_id"],
        "room_name": room["name"] if room else None,
        "student_name": b["student_name"],
        "arrival_date": b["arrival_date"].isoformat(),
        "departure_date": b["departure_date"].isoformat(),
        "nights": (b["departure_date"] - b["arrival_date"]).days,
        "status": b["status"],
    }


@app.post("/rooms", status_code=201)
def add_room(room: RoomIn):
    global _next_room_id
    with _lock:
        for r in _rooms.values():
            if r["name"].lower() == room.name.lower():
                raise HTTPException(status_code=409, detail="A room with this name already exists")
        r = {"id": _next_room_id, "name": room.name, "beds": room.beds}
        _rooms[r["id"]] = r
        _next_room_id += 1
        return _room_out(r)


@app.get("/rooms")
def list_rooms():
    with _lock:
        return [_room_out(r) for r in _rooms.values()]


@app.get("/rooms/{room_id}")
def get_room(room_id: int):
    with _lock:
        r = _rooms.get(room_id)
        if not r:
            raise HTTPException(status_code=404, detail="Room not found")
        return _room_out(r)


@app.post("/bookings", status_code=201)
def create_booking(data: BookingIn):
    global _next_booking_id
    with _lock:
        room = _rooms.get(data.room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        taken = _max_occupancy(room["id"], data.arrival_date, data.departure_date)
        if taken >= room["beds"]:
            raise HTTPException(
                status_code=409,
                detail="All beds in this room are taken on at least one night of this stay",
            )
        b = {
            "id": _next_booking_id,
            "room_id": room["id"],
            "student_name": data.student_name,
            "arrival_date": data.arrival_date,
            "departure_date": data.departure_date,
            "status": "active",
        }
        _bookings[b["id"]] = b
        _next_booking_id += 1
        return _booking_out(b)


@app.get("/bookings")
def list_bookings(room_id: Optional[int] = None, include_cancelled: bool = False):
    with _lock:
        out = []
        for b in _bookings.values():
            if room_id is not None and b["room_id"] != room_id:
                continue
            if not include_cancelled and b["status"] != "active":
                continue
            out.append(_booking_out(b))
        return out


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: int):
    with _lock:
        b = _bookings.get(booking_id)
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        return _booking_out(b)


def _cancel(booking_id: int):
    with _lock:
        b = _bookings.get(booking_id)
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        if b["status"] == "cancelled":
            raise HTTPException(status_code=409, detail="Booking is already cancelled")
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
    arrival_date: date = Query(...),
    departure_date: date = Query(...),
):
    if departure_date <= arrival_date:
        raise HTTPException(status_code=422, detail="departure_date must be after arrival_date")
    with _lock:
        result: List[dict] = []
        for r in _rooms.values():
            taken = _max_occupancy(r["id"], arrival_date, departure_date)
            free = max(0, r["beds"] - taken)
            result.append({
                "room_id": r["id"],
                "room_name": r["name"],
                "beds": r["beds"],
                "free_beds": free,
            })
        return {
            "arrival_date": arrival_date.isoformat(),
            "departure_date": departure_date.isoformat(),
            "rooms": result,
        }

from datetime import date
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Legon Student Hostel Bed Booking")

_lock = Lock()
rooms: Dict[int, dict] = {}
bookings: Dict[int, dict] = {}
_ids = {"room": 0, "booking": 0}


class RoomIn(BaseModel):
    name: str = Field(..., min_length=1)
    beds: int = Field(..., ge=1)


class BookingIn(BaseModel):
    room_id: int
    student_name: str = Field(..., min_length=1)
    arrival_date: date
    leaving_date: date


def _next(kind: str) -> int:
    _ids[kind] += 1
    return _ids[kind]


def _max_used(room_id: int, start: date, end: date) -> int:
    """Largest number of beds taken on any night in [start, end)."""
    events = []
    for b in bookings.values():
        if b["room_id"] != room_id or b["status"] != "active":
            continue
        s = max(b["arrival_date"], start)
        e = min(b["leaving_date"], end)
        if s < e:
            events.append((s, 1))
            events.append((e, -1))
    events.sort(key=lambda x: (x[0], x[1]))
    cur = best = 0
    for _, delta in events:
        cur += delta
        best = max(best, cur)
    return best


def _check_dates(arrival: date, leaving: date):
    if leaving <= arrival:
        raise HTTPException(status_code=422, detail="The leaving date must be after the arrival date.")


@app.post("/rooms", status_code=201)
def add_room(data: RoomIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Room name cannot be empty.")
    with _lock:
        for r in rooms.values():
            if r["name"].lower() == name.lower():
                raise HTTPException(status_code=409, detail="A room with this name already exists.")
        rid = _next("room")
        room = {"id": rid, "name": name, "beds": data.beds}
        rooms[rid] = room
        return room


@app.get("/rooms")
def list_rooms():
    return list(rooms.values())


@app.get("/rooms/{room_id}")
def get_room(room_id: int):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")
    return room


@app.post("/bookings", status_code=201)
def book_bed(data: BookingIn):
    _check_dates(data.arrival_date, data.leaving_date)
    student = data.student_name.strip()
    if not student:
        raise HTTPException(status_code=422, detail="Student name cannot be empty.")
    with _lock:
        room = rooms.get(data.room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found.")
        used = _max_used(room["id"], data.arrival_date, data.leaving_date)
        if used >= room["beds"]:
            raise HTTPException(status_code=409, detail="All beds in this room are taken on at least one night of this stay.")
        bid = _next("booking")
        b = {
            "id": bid,
            "room_id": room["id"],
            "room_name": room["name"],
            "student_name": student,
            "arrival_date": data.arrival_date,
            "leaving_date": data.leaving_date,
            "status": "active",
        }
        bookings[bid] = b
        return b


@app.get("/bookings")
def list_bookings(room_id: Optional[int] = None, include_cancelled: bool = False):
    out = []
    for b in bookings.values():
        if room_id is not None and b["room_id"] != room_id:
            continue
        if not include_cancelled and b["status"] != "active":
            continue
        out.append(b)
    return out


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: int):
    b = bookings.get(booking_id)
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found.")
    return b


def _cancel(booking_id: int):
    with _lock:
        b = bookings.get(booking_id)
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found.")
        if b["status"] == "cancelled":
            raise HTTPException(status_code=409, detail="This booking is already cancelled.")
        b["status"] = "cancelled"
        return b


@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int):
    return _cancel(booking_id)


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking_post(booking_id: int):
    return _cancel(booking_id)


@app.get("/availability")
def availability(arrival_date: date = Query(...), leaving_date: date = Query(...)):
    _check_dates(arrival_date, leaving_date)
    with _lock:
        result = []
        for room in rooms.values():
            used = _max_used(room["id"], arrival_date, leaving_date)
            result.append({
                "room_id": room["id"],
                "room_name": room["name"],
                "total_beds": room["beds"],
                "free_beds": max(room["beds"] - used, 0),
            })
        return {"arrival_date": arrival_date, "leaving_date": leaving_date, "rooms": result}

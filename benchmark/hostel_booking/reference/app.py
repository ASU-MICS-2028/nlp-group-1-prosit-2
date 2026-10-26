# Reference backend for hostel_booking: proves the hidden tests are right.
# Deliberately uses different names (label, bed_count, guest, arrive, depart, /hostel/...) to exercise ops.json.
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
rooms, bookings = {}, {}


class RoomIn(BaseModel):
    label: str
    bed_count: int = Field(ge=1)


class BookingIn(BaseModel):
    guest: str
    arrive: date
    depart: date


def peak(room_id, arrive, depart):
    """Most bookings in the room on any single night from arrive up to the night before depart."""
    best, day = 0, arrive
    while day < depart:
        n = sum(1 for b in bookings.values()
                if b["room"] == room_id and b["status"] == "active" and b["arrive"] <= day < b["depart"])
        best = max(best, n)
        day += timedelta(days=1)
    return best


@app.post("/hostel/rooms", status_code=201)
def create_room(r: RoomIn):
    room = {"id": len(rooms) + 1, **r.model_dump()}
    rooms[room["id"]] = room
    return room


@app.post("/hostel/rooms/{rid}/bookings", status_code=201)
def book(rid: int, b: BookingIn):
    if rid not in rooms:
        raise HTTPException(404, "No such room")
    if b.depart <= b.arrive:
        raise HTTPException(400, "Leaving date must be after arrival date")
    if peak(rid, b.arrive, b.depart) >= rooms[rid]["bed_count"]:
        raise HTTPException(409, "No free bed in this room for those nights")
    booking = {"id": len(bookings) + 1, "room": rid, "status": "active", **b.model_dump()}
    bookings[booking["id"]] = booking
    return booking


@app.delete("/hostel/bookings/{bid}")
def cancel(bid: int):
    if bid not in bookings or bookings[bid]["status"] != "active":
        raise HTTPException(404, "No such active booking")
    bookings[bid]["status"] = "cancelled"
    return bookings[bid]


@app.get("/hostel/availability")
def availability(arrive: date, depart: date):
    if depart <= arrive:
        raise HTTPException(400, "Leaving date must be after arrival date")
    return [{"room": r["id"], "available": r["bed_count"] - peak(r["id"], arrive, depart)} for r in rooms.values()]

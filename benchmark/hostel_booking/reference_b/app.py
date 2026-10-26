# Second correct backend for hostel_booking, making other valid choices than reference/:
# text ids (uuid4 hex), 200 for creation, 422 for refusals, cancel by POST, other paths and names, per-night counting.
import uuid
from collections import Counter
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, PositiveInt

app = FastAPI()
rooms, reservations = {}, {}


class RoomIn(BaseModel):
    room_name: str
    bed_total: PositiveInt


class ReservationIn(BaseModel):
    occupant: str
    from_date: date
    to_date: date


def nights(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days)]


def busiest(room_id, start, end):
    taken = Counter(n for r in reservations.values() if r["room_id"] == room_id and not r["cancelled"]
                    for n in nights(r["from_date"], r["to_date"]))
    return max((taken[n] for n in nights(start, end)), default=0)


@app.post("/rooms")
def create_room(r: RoomIn):
    room = {"id": uuid.uuid4().hex, **r.model_dump()}
    rooms[room["id"]] = room
    return room


@app.post("/rooms/{room_id}/reservations")
def reserve(room_id: str, r: ReservationIn):
    if room_id not in rooms:
        raise HTTPException(404, "Room not found")
    if r.to_date <= r.from_date:
        raise HTTPException(422, "to_date must be after from_date")
    if busiest(room_id, r.from_date, r.to_date) >= rooms[room_id]["bed_total"]:
        raise HTTPException(422, "Room is full on at least one night")
    res = {"id": uuid.uuid4().hex, "room_id": room_id, "cancelled": False, **r.model_dump()}
    reservations[res["id"]] = res
    return res


@app.post("/reservations/{res_id}/cancel")
def cancel(res_id: str):
    res = reservations.get(res_id)
    if res is None or res["cancelled"]:
        raise HTTPException(422, "Nothing to cancel")
    res["cancelled"] = True
    return res


@app.get("/free-beds")
def free_beds(from_date: date, to_date: date):
    if to_date <= from_date:
        raise HTTPException(422, "to_date must be after from_date")
    return [{"room_id": r["id"], "beds_free": r["bed_total"] - busiest(r["id"], from_date, to_date)} for r in rooms.values()]

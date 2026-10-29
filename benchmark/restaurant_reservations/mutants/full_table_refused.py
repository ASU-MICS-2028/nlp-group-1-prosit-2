# MUTANT full_table_refused: 'b.guests >= capacity' instead of 'b.guests > capacity' (a party filling the table is refused)
# Reference backend for restaurant_reservations: proves the hidden tests are right.
# Deliberately uses different names (label, capacity, guest, contact, guests, day, hour, /spots, /bookings) to exercise ops.json.
from datetime import date
from itertools import count

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
spots, bookings = {}, {}
ids = count(1)


class SpotIn(BaseModel):
    label: int
    capacity: int


class BookingIn(BaseModel):
    guest: str
    contact: str
    guests: int
    day: date
    hour: str


@app.post("/spots", status_code=201)
def create_spot(s: SpotIn):
    spot = {"id": next(ids), **s.model_dump()}
    spots[spot["id"]] = spot
    return spot


@app.get("/spots")
def list_spots():
    return list(spots.values())


@app.post("/spots/{spot_id}/bookings", status_code=201)
def reserve(spot_id: int, b: BookingIn):
    if spot_id not in spots:
        raise HTTPException(404, "No such table")
    if b.guests >= spots[spot_id]["capacity"]:
        raise HTTPException(400, "Too many people for this table")
    for x in bookings.values():
        if x["spot_id"] == spot_id and x["day"] == b.day and x["hour"] == b.hour:
            raise HTTPException(409, "Table already reserved then")
    booking = {"id": next(ids), "spot_id": spot_id, **b.model_dump()}
    bookings[booking["id"]] = booking
    return booking


@app.get("/bookings")
def list_bookings(day: date):
    return [x for x in bookings.values() if x["day"] == day]

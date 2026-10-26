# Reference backend for clinic_appointments: proves the hidden tests are right.
# Deliberately uses different names (full_name, field, medic_id, patient, day, slot, /medics, /bookings) to exercise ops.json.
from datetime import date
from itertools import count

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
medics, bookings = {}, {}
ids = count(1)


class MedicIn(BaseModel):
    full_name: str
    field: str


class BookingIn(BaseModel):
    medic_id: int
    patient: str
    day: date
    slot: str


@app.post("/medics", status_code=201)
def create_medic(m: MedicIn):
    medic = {"id": next(ids), **m.model_dump()}
    medics[medic["id"]] = medic
    return medic


@app.get("/medics")
def list_medics():
    return list(medics.values())


@app.post("/bookings", status_code=201)
def book(b: BookingIn):
    if b.medic_id not in medics:
        raise HTTPException(404, "No such doctor")
    for x in bookings.values():
        if x["medic_id"] == b.medic_id and x["day"] == b.day and x["slot"] == b.slot:
            raise HTTPException(409, "That slot is already booked")
    booking = {"id": next(ids), **b.model_dump()}
    bookings[booking["id"]] = booking
    return booking


@app.get("/medics/{medic_id}/bookings")
def list_medic_bookings(medic_id: int, day: date):
    if medic_id not in medics:
        raise HTTPException(404, "No such doctor")
    return [x for x in bookings.values() if x["medic_id"] == medic_id and x["day"] == day]


@app.delete("/bookings/{booking_id}", status_code=204)
def cancel(booking_id: int):
    if booking_id not in bookings:
        raise HTTPException(404, "No such appointment")
    del bookings[booking_id]

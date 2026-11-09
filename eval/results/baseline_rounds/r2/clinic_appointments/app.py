from datetime import date as Date
import re
import threading
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Tamale Clinic Appointments")

_lock = threading.Lock()
_doctors = {}
_appointments = {}
_slots = {}
_next_doctor_id = 1
_next_appointment_id = 1

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class DoctorIn(BaseModel):
    name: str
    specialty: str


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_name: str
    date: str
    time_slot: str


class DoctorAppointmentIn(BaseModel):
    patient_name: str
    date: str
    time_slot: str


def _clean_text(value, field):
    if value is None or not str(value).strip():
        raise HTTPException(status_code=422, detail=f"{field} must not be empty")
    return str(value).strip()


def _parse_date(value):
    try:
        return Date.fromisoformat(str(value).strip()).isoformat()
    except Exception:
        raise HTTPException(status_code=422, detail="date must be a valid date in the form YYYY-MM-DD, e.g. 2024-05-17")


def _parse_time(value):
    m = _TIME_RE.match(str(value).strip())
    if not m:
        raise HTTPException(status_code=422, detail="time_slot must look like HH:MM, e.g. 09:00 or 14:30")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise HTTPException(status_code=422, detail="time_slot must be a real time between 00:00 and 23:59")
    return f"{h:02d}:{mi:02d}"


def _get_doctor(doctor_id):
    doc = _doctors.get(doctor_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doc


@app.post("/doctors", status_code=201)
def add_doctor(body: DoctorIn):
    global _next_doctor_id
    name = _clean_text(body.name, "name")
    specialty = _clean_text(body.specialty, "specialty")
    with _lock:
        doc = {"id": _next_doctor_id, "name": name, "specialty": specialty}
        _doctors[_next_doctor_id] = doc
        _next_doctor_id += 1
        return dict(doc)


@app.get("/doctors")
def list_doctors():
    with _lock:
        return [dict(d) for d in _doctors.values()]


@app.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: int):
    with _lock:
        return dict(_get_doctor(doctor_id))


def _book(doctor_id, patient_name, date_value, time_value):
    global _next_appointment_id
    patient = _clean_text(patient_name, "patient_name")
    d = _parse_date(date_value)
    t = _parse_time(time_value)
    with _lock:
        doc = _get_doctor(doctor_id)
        key = (doctor_id, d, t)
        if key in _slots:
            raise HTTPException(status_code=409, detail=f"Dr. {doc['name']} already has an appointment on {d} at {t}")
        appt = {
            "id": _next_appointment_id,
            "doctor_id": doctor_id,
            "doctor_name": doc["name"],
            "patient_name": patient,
            "date": d,
            "time_slot": t,
        }
        _appointments[_next_appointment_id] = appt
        _slots[key] = _next_appointment_id
        _next_appointment_id += 1
        return dict(appt)


@app.post("/appointments", status_code=201)
def book_appointment(body: AppointmentIn):
    return _book(body.doctor_id, body.patient_name, body.date, body.time_slot)


@app.post("/doctors/{doctor_id}/appointments", status_code=201)
def book_with_doctor(doctor_id: int, body: DoctorAppointmentIn):
    return _book(doctor_id, body.patient_name, body.date, body.time_slot)


@app.get("/doctors/{doctor_id}/appointments")
def doctor_appointments(doctor_id: int, date: Optional[str] = Query(None, description="YYYY-MM-DD")):
    d = _parse_date(date) if date is not None else None
    with _lock:
        _get_doctor(doctor_id)
        items = [dict(a) for a in _appointments.values()
                 if a["doctor_id"] == doctor_id and (d is None or a["date"] == d)]
    items.sort(key=lambda a: (a["date"], a["time_slot"]))
    return items


@app.get("/appointments")
def list_appointments():
    with _lock:
        items = [dict(a) for a in _appointments.values()]
    items.sort(key=lambda a: (a["date"], a["time_slot"], a["doctor_id"]))
    return items


@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: int):
    with _lock:
        appt = _appointments.get(appointment_id)
        if appt is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return dict(appt)


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    with _lock:
        appt = _appointments.pop(appointment_id, None)
        if appt is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        _slots.pop((appt["doctor_id"], appt["date"], appt["time_slot"]), None)
        return {"detail": "Appointment cancelled; the slot is free again", "appointment": dict(appt)}

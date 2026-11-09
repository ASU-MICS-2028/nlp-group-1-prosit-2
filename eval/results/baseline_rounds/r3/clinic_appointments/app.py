import threading
from datetime import date as date_cls, datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Tamale Clinic Appointments")

_lock = threading.Lock()
_doctors: Dict[int, dict] = {}
_appointments: Dict[int, dict] = {}
_next_doctor_id = 1
_next_appointment_id = 1


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


def _clean_text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"{field} must not be empty")
    return value.strip()


def _parse_date(value: str) -> str:
    try:
        d = datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="date must be a valid date in the form YYYY-MM-DD")
    return d.isoformat()


def _parse_time(value: str) -> str:
    s = str(value).strip()
    parts = s.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit() or len(parts[1]) != 2 or len(parts[0]) not in (1, 2):
        raise HTTPException(status_code=422, detail="time_slot must be in the form HH:MM, for example 09:00 or 14:30")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise HTTPException(status_code=422, detail="time_slot must be a valid time between 00:00 and 23:59")
    return f"{h:02d}:{m:02d}"


def _get_doctor(doctor_id: int) -> dict:
    doc = _doctors.get(doctor_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doc


def _book(doctor_id: int, patient_name: str, date: str, time_slot: str) -> dict:
    global _next_appointment_id
    name = _clean_text(patient_name, "patient_name")
    d = _parse_date(date)
    t = _parse_time(time_slot)
    with _lock:
        doc = _get_doctor(doctor_id)
        for a in _appointments.values():
            if a["doctor_id"] == doctor_id and a["date"] == d and a["time_slot"] == t:
                raise HTTPException(status_code=409, detail=f"Dr. {doc['name']} already has an appointment on {d} at {t}")
        appt = {
            "id": _next_appointment_id,
            "doctor_id": doctor_id,
            "doctor_name": doc["name"],
            "patient_name": name,
            "date": d,
            "time_slot": t,
        }
        _appointments[_next_appointment_id] = appt
        _next_appointment_id += 1
        return dict(appt)


@app.post("/doctors", status_code=201)
def add_doctor(body: DoctorIn):
    global _next_doctor_id
    name = _clean_text(body.name, "name")
    spec = _clean_text(body.specialty, "specialty")
    with _lock:
        doc = {"id": _next_doctor_id, "name": name, "specialty": spec}
        _doctors[_next_doctor_id] = doc
        _next_doctor_id += 1
        return dict(doc)


@app.get("/doctors")
def list_doctors():
    with _lock:
        return [dict(d) for d in sorted(_doctors.values(), key=lambda x: x["id"])]


@app.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: int):
    with _lock:
        return dict(_get_doctor(doctor_id))


@app.post("/appointments", status_code=201)
def book_appointment(body: AppointmentIn):
    return _book(body.doctor_id, body.patient_name, body.date, body.time_slot)


@app.post("/doctors/{doctor_id}/appointments", status_code=201)
def book_with_doctor(doctor_id: int, body: DoctorAppointmentIn):
    return _book(doctor_id, body.patient_name, body.date, body.time_slot)


@app.get("/doctors/{doctor_id}/appointments")
def doctor_appointments(doctor_id: int, date: str = Query(..., description="YYYY-MM-DD")):
    d = _parse_date(date)
    with _lock:
        _get_doctor(doctor_id)
        items = [dict(a) for a in _appointments.values() if a["doctor_id"] == doctor_id and a["date"] == d]
    items.sort(key=lambda a: a["time_slot"])
    return items


@app.get("/appointments")
def list_appointments(doctor_id: Optional[int] = None, date: Optional[str] = None):
    d = _parse_date(date) if date is not None else None
    with _lock:
        items = [dict(a) for a in _appointments.values()
                 if (doctor_id is None or a["doctor_id"] == doctor_id) and (d is None or a["date"] == d)]
    items.sort(key=lambda a: (a["date"], a["time_slot"], a["doctor_id"]))
    return items


@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: int):
    with _lock:
        a = _appointments.get(appointment_id)
        if a is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return dict(a)


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    with _lock:
        a = _appointments.pop(appointment_id, None)
        if a is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return {"message": "Appointment cancelled; the slot is free again", "appointment": a}

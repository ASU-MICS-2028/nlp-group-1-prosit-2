import re
import threading
from datetime import date as Date
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

app = FastAPI(title="Tamale Clinic Appointments")

_lock = threading.Lock()
_doctors: Dict[int, dict] = {}
_appointments: Dict[int, dict] = {}
_next_doctor_id = 1
_next_appointment_id = 1

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _normalize_slot(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("time slot must be text like 09:00 or 14:30")
    m = _TIME_RE.match(value.strip())
    if not m:
        raise ValueError("time slot must look like 09:00 or 14:30")
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError("time slot must be a valid time between 00:00 and 23:59")
    return f"{h:02d}:{mi:02d}"


def _clean_text(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must not be empty")
    return value.strip()


class DoctorIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    specialty: str = Field(
        validation_alias=AliasChoices("specialty", "speciality", "specialization", "specialisation", "specialises_in", "specializes_in")
    )

    @field_validator("name")
    @classmethod
    def _v_name(cls, v):
        return _clean_text(v, "name")

    @field_validator("specialty")
    @classmethod
    def _v_spec(cls, v):
        return _clean_text(v, "specialty")


class Doctor(BaseModel):
    id: int
    name: str
    specialty: str


class AppointmentBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    patient_name: str = Field(validation_alias=AliasChoices("patient_name", "patient", "name"))
    date: Date
    time_slot: str = Field(validation_alias=AliasChoices("time_slot", "time", "slot"))

    @field_validator("patient_name")
    @classmethod
    def _v_patient(cls, v):
        return _clean_text(v, "patient name")

    @field_validator("time_slot")
    @classmethod
    def _v_slot(cls, v):
        return _normalize_slot(v)


class AppointmentIn(AppointmentBase):
    doctor_id: int


class DoctorAppointmentIn(AppointmentBase):
    pass


class Appointment(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    patient_name: str
    date: str
    time_slot: str


def _get_doctor(doctor_id: int) -> dict:
    d = _doctors.get(doctor_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return d


def _book(doctor_id: int, patient_name: str, day: Date, slot: str) -> dict:
    global _next_appointment_id
    with _lock:
        doctor = _get_doctor(doctor_id)
        day_s = day.isoformat()
        for a in _appointments.values():
            if a["doctor_id"] == doctor_id and a["date"] == day_s and a["time_slot"] == slot:
                raise HTTPException(
                    status_code=409,
                    detail=f"Dr. {doctor['name']} already has an appointment on {day_s} at {slot}",
                )
        appt = {
            "id": _next_appointment_id,
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "patient_name": patient_name,
            "date": day_s,
            "time_slot": slot,
        }
        _appointments[_next_appointment_id] = appt
        _next_appointment_id += 1
        return appt


@app.get("/")
def root():
    return {"message": "Clinic appointment service is running"}


@app.post("/doctors", response_model=Doctor, status_code=201)
def add_doctor(body: DoctorIn):
    global _next_doctor_id
    with _lock:
        doc = {"id": _next_doctor_id, "name": body.name, "specialty": body.specialty}
        _doctors[_next_doctor_id] = doc
        _next_doctor_id += 1
        return doc


@app.get("/doctors", response_model=List[Doctor])
def list_doctors():
    with _lock:
        return sorted(_doctors.values(), key=lambda d: d["id"])


@app.get("/doctors/{doctor_id}", response_model=Doctor)
def get_doctor(doctor_id: int):
    with _lock:
        return _get_doctor(doctor_id)


@app.post("/appointments", response_model=Appointment, status_code=201)
def book_appointment(body: AppointmentIn):
    return _book(body.doctor_id, body.patient_name, body.date, body.time_slot)


@app.post("/doctors/{doctor_id}/appointments", response_model=Appointment, status_code=201)
def book_with_doctor(doctor_id: int, body: DoctorAppointmentIn):
    return _book(doctor_id, body.patient_name, body.date, body.time_slot)


@app.get("/doctors/{doctor_id}/appointments", response_model=List[Appointment])
def doctor_appointments(doctor_id: int, date: Optional[Date] = Query(None, description="Day in YYYY-MM-DD format")):
    with _lock:
        _get_doctor(doctor_id)
        result = [a for a in _appointments.values() if a["doctor_id"] == doctor_id]
        if date is not None:
            ds = date.isoformat()
            result = [a for a in result if a["date"] == ds]
        return sorted(result, key=lambda a: (a["date"], a["time_slot"]))


@app.get("/appointments", response_model=List[Appointment])
def list_appointments(doctor_id: Optional[int] = None, date: Optional[Date] = None):
    with _lock:
        result = list(_appointments.values())
        if doctor_id is not None:
            _get_doctor(doctor_id)
            result = [a for a in result if a["doctor_id"] == doctor_id]
        if date is not None:
            ds = date.isoformat()
            result = [a for a in result if a["date"] == ds]
        return sorted(result, key=lambda a: (a["date"], a["time_slot"], a["doctor_id"]))


@app.get("/appointments/{appointment_id}", response_model=Appointment)
def get_appointment(appointment_id: int):
    with _lock:
        a = _appointments.get(appointment_id)
        if a is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return a


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    with _lock:
        a = _appointments.pop(appointment_id, None)
        if a is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return {"message": "Appointment cancelled; the slot is now free", "appointment": a}

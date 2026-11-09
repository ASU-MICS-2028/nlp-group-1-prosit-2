import re
from datetime import date as date_type
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select, UniqueConstraint

engine = create_engine("sqlite:///clinic.db", connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id")
    patient_name: str
    date: str
    time: str


class DoctorIn(BaseModel):
    name: str
    specialty: str


class AppointmentIn(BaseModel):
    patient_name: str
    date: str
    time: str


SQLModel.metadata.create_all(engine)
app = FastAPI()

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@app.post("/doctors", status_code=201)
def add_doctor(d: DoctorIn):
    if not d.name.strip() or not d.specialty.strip():
        raise HTTPException(422, "name and specialty are required")
    doc = Doctor(name=d.name.strip(), specialty=d.specialty.strip())
    with Session(engine) as s:
        s.add(doc)
        s.commit()
        s.refresh(doc)
        return doc


@app.get("/doctors")
def list_doctors():
    with Session(engine) as s:
        return s.exec(select(Doctor)).all()


@app.post("/doctors/{doctor_id}/appointments", status_code=201)
def book(doctor_id: int, a: AppointmentIn):
    if not a.patient_name.strip():
        raise HTTPException(422, "patient_name is required")
    try:
        day = date_type.fromisoformat(a.date)
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")
    if not TIME_RE.match(a.time):
        raise HTTPException(422, "time must be HH:MM")
    with Session(engine) as s:
        if not s.get(Doctor, doctor_id):
            raise HTTPException(404, "doctor not found")
        exists = s.exec(select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.date == day.isoformat(),
            Appointment.time == a.time)).first()
        if exists:
            raise HTTPException(409, "slot already booked")
        ap = Appointment(doctor_id=doctor_id, patient_name=a.patient_name.strip(),
                         date=day.isoformat(), time=a.time)
        s.add(ap)
        s.commit()
        s.refresh(ap)
        return ap


@app.get("/doctors/{doctor_id}/appointments")
def list_appointments(doctor_id: int, date: str):
    try:
        day = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")
    with Session(engine) as s:
        if not s.get(Doctor, doctor_id):
            raise HTTPException(404, "doctor not found")
        return s.exec(select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.date == day.isoformat()).order_by(Appointment.time)).all()


@app.delete("/appointments/{appointment_id}")
def cancel(appointment_id: int):
    with Session(engine) as s:
        ap = s.get(Appointment, appointment_id)
        if not ap:
            raise HTTPException(404, "appointment not found")
        s.delete(ap)
        s.commit()
        return {"detail": "cancelled"}

import re
from datetime import date as date_type
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, UniqueConstraint

engine = create_engine("sqlite:///clinic.db", connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialisation: str


class Appointment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id")
    patient_name: str
    date: str
    time: str


class DoctorIn(BaseModel):
    name: str
    specialisation: str

    @field_validator("name", "specialisation")
    @classmethod
    def nonempty(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class AppointmentIn(BaseModel):
    patient_name: str
    date: str
    time: str

    @field_validator("patient_name")
    @classmethod
    def nonempty(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("date")
    @classmethod
    def valid_date(cls, v):
        date_type.fromisoformat(v)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("use YYYY-MM-DD")
        return v

    @field_validator("time")
    @classmethod
    def valid_time(cls, v):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("use HH:MM")
        return v


app = FastAPI()
SQLModel.metadata.create_all(engine)


@app.post("/doctors", status_code=201)
def add_doctor(d: DoctorIn):
    with Session(engine) as s:
        doc = Doctor(name=d.name, specialisation=d.specialisation)
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
    with Session(engine) as s:
        if not s.get(Doctor, doctor_id):
            raise HTTPException(404, "Doctor not found")
        exists = s.exec(select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.date == a.date,
            Appointment.time == a.time)).first()
        if exists:
            raise HTTPException(409, "Slot already booked")
        ap = Appointment(doctor_id=doctor_id, patient_name=a.patient_name,
                         date=a.date, time=a.time)
        s.add(ap)
        s.commit()
        s.refresh(ap)
        return ap


@app.get("/doctors/{doctor_id}/appointments")
def list_appointments(doctor_id: int, date: str):
    try:
        date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, "Invalid date, use YYYY-MM-DD")
    with Session(engine) as s:
        if not s.get(Doctor, doctor_id):
            raise HTTPException(404, "Doctor not found")
        return s.exec(select(Appointment).where(
            Appointment.doctor_id == doctor_id, Appointment.date == date)
            .order_by(Appointment.time)).all()


@app.delete("/appointments/{appointment_id}")
def cancel(appointment_id: int):
    with Session(engine) as s:
        ap = s.get(Appointment, appointment_id)
        if not ap:
            raise HTTPException(404, "Appointment not found")
        s.delete(ap)
        s.commit()
        return {"detail": "Appointment cancelled"}

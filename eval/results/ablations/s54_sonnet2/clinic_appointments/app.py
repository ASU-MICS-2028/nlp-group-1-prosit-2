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

    @field_validator("name", "specialty")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_name: str
    date: str
    time: str

    @field_validator("patient_name")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("date")
    @classmethod
    def valid_date(cls, v):
        return date_type.fromisoformat(v).isoformat()

    @field_validator("time")
    @classmethod
    def valid_time(cls, v):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("time must be HH:MM")
        return v


app = FastAPI()
SQLModel.metadata.create_all(engine)


@app.post("/doctors", status_code=201)
def add_doctor(body: DoctorIn):
    with Session(engine) as s:
        d = Doctor(name=body.name, specialty=body.specialty)
        s.add(d)
        s.commit()
        s.refresh(d)
        return d


@app.get("/doctors")
def list_doctors():
    with Session(engine) as s:
        return s.exec(select(Doctor)).all()


@app.post("/appointments", status_code=201)
def book(body: AppointmentIn):
    with Session(engine) as s:
        if not s.get(Doctor, body.doctor_id):
            raise HTTPException(404, "Doctor not found")
        taken = s.exec(select(Appointment).where(
            Appointment.doctor_id == body.doctor_id,
            Appointment.date == body.date,
            Appointment.time == body.time)).first()
        if taken:
            raise HTTPException(409, "Slot already booked")
        a = Appointment(**body.model_dump())
        s.add(a)
        s.commit()
        s.refresh(a)
        return a


@app.get("/doctors/{doctor_id}/appointments")
def doctor_appointments(doctor_id: int, date: str):
    try:
        date = date_type.fromisoformat(date).isoformat()
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")
    with Session(engine) as s:
        if not s.get(Doctor, doctor_id):
            raise HTTPException(404, "Doctor not found")
        return s.exec(select(Appointment).where(
            Appointment.doctor_id == doctor_id, Appointment.date == date
        ).order_by(Appointment.time)).all()


@app.delete("/appointments/{appointment_id}")
def cancel(appointment_id: int):
    with Session(engine) as s:
        a = s.get(Appointment, appointment_id)
        if not a:
            raise HTTPException(404, "Appointment not found")
        s.delete(a)
        s.commit()
        return {"detail": "Appointment cancelled"}

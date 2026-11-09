import re
from contextlib import asynccontextmanager
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Field, Session, create_engine, select, UniqueConstraint

import os

DB_FILE = os.environ.get("CLINIC_DB", "clinic.db")
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    __tablename__ = "doctors"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time_slot"), {"sqlite_autoincrement": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    patient_name: str
    date: str
    time_slot: str


class DoctorIn(BaseModel):
    name: str
    specialty: str

    @field_validator("name", "specialty")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_name: str
    date: Date
    time_slot: str

    @field_validator("patient_name")
    @classmethod
    def name_not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("time_slot")
    @classmethod
    def valid_slot(cls, v):
        v = v.strip()
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", v)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ValueError("time_slot must look like 09:00 or 14:30")
        return f"{int(m.group(1)):02d}:{m.group(2)}"


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tamale Clinic Appointments", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/doctors", status_code=201)
def add_doctor(data: DoctorIn, session: Session = Depends(get_session)):
    doctor = Doctor(name=data.name, specialty=data.specialty)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


@app.get("/doctors")
def list_doctors(session: Session = Depends(get_session)):
    return session.exec(select(Doctor).order_by(Doctor.id)).all()


@app.post("/appointments", status_code=201)
def book(data: AppointmentIn, session: Session = Depends(get_session)):
    if not session.get(Doctor, data.doctor_id):
        raise HTTPException(404, "Doctor not found")
    day = data.date.isoformat()
    taken = session.exec(
        select(Appointment).where(
            Appointment.doctor_id == data.doctor_id,
            Appointment.date == day,
            Appointment.time_slot == data.time_slot,
        )
    ).first()
    if taken:
        raise HTTPException(409, "This doctor already has an appointment at that date and time")
    appt = Appointment(doctor_id=data.doctor_id, patient_name=data.patient_name,
                       date=day, time_slot=data.time_slot)
    session.add(appt)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "This doctor already has an appointment at that date and time")
    session.refresh(appt)
    return appt


@app.get("/doctors/{doctor_id}/appointments")
def doctor_day(doctor_id: int, date: Date, session: Session = Depends(get_session)):
    if not session.get(Doctor, doctor_id):
        raise HTTPException(404, "Doctor not found")
    return session.exec(
        select(Appointment)
        .where(Appointment.doctor_id == doctor_id, Appointment.date == date.isoformat())
        .order_by(Appointment.time_slot)
    ).all()


@app.delete("/appointments/{appointment_id}")
def cancel(appointment_id: int, session: Session = Depends(get_session)):
    appt = session.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    session.delete(appt)
    session.commit()
    return {"detail": "Appointment cancelled", "id": appointment_id}

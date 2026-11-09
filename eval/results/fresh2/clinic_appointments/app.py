from contextlib import asynccontextmanager
from datetime import date as Date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

engine = create_engine("sqlite:///clinic_appointments.db", connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time"), {"sqlite_autoincrement": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    patient_name: str
    date: str
    time: str


class DoctorIn(BaseModel):
    name: str = PField(min_length=1)
    specialty: str = PField(min_length=1)


TIME_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_name: str = PField(min_length=1)
    date: Date
    time: str = PField(pattern=TIME_PATTERN, description="HH:MM, e.g. 09:00 or 14:30")


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Clinic Appointments", lifespan=lifespan)
SQLModel.metadata.create_all(engine)


@app.post("/doctors", status_code=201, response_model=Doctor)
def add_doctor(data: DoctorIn):
    name, specialty = data.name.strip(), data.specialty.strip()
    if not name or not specialty:
        raise HTTPException(422, "Name and specialty must not be empty")
    with Session(engine) as s:
        d = Doctor(name=name, specialty=specialty)
        s.add(d)
        s.commit()
        s.refresh(d)
        return d


@app.get("/doctors", response_model=List[Doctor])
def list_doctors():
    with Session(engine) as s:
        return s.exec(select(Doctor).order_by(Doctor.id)).all()


@app.post("/appointments", status_code=201, response_model=Appointment)
def book(data: AppointmentIn):
    patient = data.patient_name.strip()
    if not patient:
        raise HTTPException(422, "Patient name must not be empty")
    with Session(engine) as s:
        if not s.get(Doctor, data.doctor_id):
            raise HTTPException(404, "Doctor not found")
        d = data.date.isoformat()
        taken = s.exec(
            select(Appointment).where(
                Appointment.doctor_id == data.doctor_id,
                Appointment.date == d,
                Appointment.time == data.time,
            )
        ).first()
        if taken:
            raise HTTPException(409, "This doctor already has an appointment in that time slot")
        a = Appointment(doctor_id=data.doctor_id, patient_name=patient, date=d, time=data.time)
        s.add(a)
        try:
            s.commit()
        except Exception:
            s.rollback()
            raise HTTPException(409, "This doctor already has an appointment in that time slot")
        s.refresh(a)
        return a


@app.get("/doctors/{doctor_id}/appointments", response_model=List[Appointment])
def doctor_day(doctor_id: int, date: Date = Query(...)):
    with Session(engine) as s:
        if not s.get(Doctor, doctor_id):
            raise HTTPException(404, "Doctor not found")
        return s.exec(
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id, Appointment.date == date.isoformat())
            .order_by(Appointment.time)
        ).all()


@app.delete("/appointments/{appointment_id}")
def cancel(appointment_id: int):
    with Session(engine) as s:
        a = s.get(Appointment, appointment_id)
        if not a:
            raise HTTPException(404, "Appointment not found")
        s.delete(a)
        s.commit()
        return {"detail": "Appointment cancelled", "id": appointment_id}

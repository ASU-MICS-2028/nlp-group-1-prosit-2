from contextlib import asynccontextmanager
from datetime import date as Date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField, field_validator
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///clinic.db", connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    patient_name: str
    date: str
    time: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Clinic Appointments", lifespan=lifespan)


class DoctorIn(BaseModel):
    name: str = PField(min_length=1)
    specialty: str = PField(min_length=1)

    @field_validator("name", "specialty")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_name: str
    date: Date
    time: str = PField(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="HH:MM, e.g. 09:00 or 14:30")

    @field_validator("patient_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


@app.post("/doctors", status_code=201, response_model=Doctor)
def add_doctor(data: DoctorIn):
    with Session(engine) as s:
        d = Doctor(name=data.name, specialty=data.specialty)
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
    with Session(engine) as s:
        if not s.get(Doctor, data.doctor_id):
            raise HTTPException(404, "Doctor not found")
        a = Appointment(
            doctor_id=data.doctor_id,
            patient_name=data.patient_name,
            date=data.date.isoformat(),
            time=data.time,
        )
        s.add(a)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "This doctor already has an appointment at that date and time")
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
        return {"ok": True, "deleted_id": appointment_id}

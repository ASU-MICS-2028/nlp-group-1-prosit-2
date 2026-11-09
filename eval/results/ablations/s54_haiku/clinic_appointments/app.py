import re
from contextlib import asynccontextmanager
from datetime import date as Date

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./clinic.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class Doctor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time"),)

    id: int | None = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id")
    patient_name: str
    date: str  # stored as YYYY-MM-DD
    time: str  # stored as HH:MM


class DoctorIn(BaseModel):
    name: str
    specialty: str

    @field_validator("name", "specialty")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class BookingIn(BaseModel):
    doctor_id: int
    patient_name: str
    date: str
    time: str

    @field_validator("patient_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("patient name must not be empty")
        return v.strip()

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        try:
            return Date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("date must be in the form YYYY-MM-DD")

    @field_validator("time")
    @classmethod
    def valid_time(cls, v: str) -> str:
        if not TIME_PATTERN.match(v):
            raise ValueError("time must be in the form HH:MM, e.g. 09:00 or 14:30")
        return v


@asynccontextmanager
async def lifespan(_: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Clinic Appointments", lifespan=lifespan)


@app.post("/doctors", status_code=201)
def add_doctor(data: DoctorIn):
    with Session(engine) as session:
        doctor = Doctor(name=data.name, specialty=data.specialty)
        session.add(doctor)
        session.commit()
        session.refresh(doctor)
        return doctor


@app.get("/doctors")
def list_doctors():
    with Session(engine) as session:
        return session.exec(select(Doctor).order_by(Doctor.id)).all()


@app.post("/appointments", status_code=201)
def book_appointment(data: BookingIn):
    with Session(engine) as session:
        if session.get(Doctor, data.doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found")
        taken = session.exec(
            select(Appointment).where(
                Appointment.doctor_id == data.doctor_id,
                Appointment.date == data.date,
                Appointment.time == data.time,
            )
        ).first()
        if taken is not None:
            raise HTTPException(
                status_code=409,
                detail="This doctor already has an appointment at that date and time",
            )
        appointment = Appointment(
            doctor_id=data.doctor_id,
            patient_name=data.patient_name,
            date=data.date,
            time=data.time,
        )
        session.add(appointment)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="This doctor already has an appointment at that date and time",
            )
        session.refresh(appointment)
        return appointment


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    with Session(engine) as session:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        session.delete(appointment)
        session.commit()
        return {"cancelled": appointment_id}


@app.get("/doctors/{doctor_id}/appointments")
def doctor_appointments_for_day(doctor_id: int, date: str = Query(...)):
    try:
        day = Date.fromisoformat(date).isoformat()
    except ValueError:
        raise HTTPException(status_code=422, detail="date must be in the form YYYY-MM-DD")
    with Session(engine) as session:
        if session.get(Doctor, doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found")
        return session.exec(
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id, Appointment.date == day)
            .order_by(Appointment.time)
        ).all()

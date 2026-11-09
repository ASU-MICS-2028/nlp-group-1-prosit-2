import re
from contextlib import asynccontextmanager
from datetime import date as date_type
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

DATABASE_URL = "sqlite:///./clinic.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("doctor_id", "date", "time", name="uq_doctor_slot"),
        {"sqlite_autoincrement": True},
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    patient_name: str
    date: str = Field(index=True)
    time: str


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_date(value: str) -> str:
    value = value.strip()
    if not DATE_RE.match(value):
        raise ValueError("date must be a real date written as YYYY-MM-DD, for example 2025-03-14")
    try:
        return date_type.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError("date must be a real date written as YYYY-MM-DD, for example 2025-03-14")


def parse_time(value: str) -> str:
    value = value.strip()
    m = TIME_RE.match(value)
    if not m:
        raise ValueError("time must be hours and minutes, for example 09:00 or 14:30")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ValueError("time must be a real time, for example 09:00 or 14:30")
    return f"{h:02d}:{mi:02d}"


def not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


class DoctorCreate(BaseModel):
    name: str
    specialty: str

    _check = field_validator("name", "specialty")(classmethod(lambda cls, v: not_blank(v)))


class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_name: str
    date: str
    time: str

    @field_validator("patient_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return not_blank(v)

    @field_validator("date")
    @classmethod
    def _date(cls, v: str) -> str:
        return parse_date(v)

    @field_validator("time")
    @classmethod
    def _time(cls, v: str) -> str:
        return parse_time(v)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tamale Clinic Appointments", lifespan=lifespan)
SQLModel.metadata.create_all(engine)


@app.post("/doctors", status_code=201, response_model=Doctor)
def add_doctor(data: DoctorCreate):
    with Session(engine) as session:
        doctor = Doctor(name=data.name, specialty=data.specialty)
        session.add(doctor)
        session.commit()
        session.refresh(doctor)
        return doctor


@app.get("/doctors", response_model=List[Doctor])
def list_doctors():
    with Session(engine) as session:
        return session.exec(select(Doctor).order_by(Doctor.id)).all()


@app.post("/appointments", status_code=201, response_model=Appointment)
def book_appointment(data: AppointmentCreate):
    with Session(engine) as session:
        if session.get(Doctor, data.doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found")
        clash = session.exec(
            select(Appointment).where(
                Appointment.doctor_id == data.doctor_id,
                Appointment.date == data.date,
                Appointment.time == data.time,
            )
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="This doctor already has an appointment at that date and time")
        appt = Appointment(
            doctor_id=data.doctor_id, patient_name=data.patient_name, date=data.date, time=data.time
        )
        session.add(appt)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=409, detail="This doctor already has an appointment at that date and time")
        session.refresh(appt)
        return appt


@app.get("/doctors/{doctor_id}/appointments", response_model=List[Appointment])
def doctor_appointments(doctor_id: int, date: str = Query(...)):
    try:
        day = parse_date(date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    with Session(engine) as session:
        if session.get(Doctor, doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found")
        return session.exec(
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id, Appointment.date == day)
            .order_by(Appointment.time)
        ).all()


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    with Session(engine) as session:
        appt = session.get(Appointment, appointment_id)
        if appt is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        session.delete(appt)
        session.commit()
        return {"detail": "Appointment cancelled", "id": appointment_id}

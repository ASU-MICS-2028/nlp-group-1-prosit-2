import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./clinic.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# ---------- Database tables ----------

class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("doctor_id", "date", "time_slot", name="uq_doctor_date_slot"),
        {"sqlite_autoincrement": True},  # never reuse a cancelled appointment's number
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    patient_name: str
    date: str  # YYYY-MM-DD
    time_slot: str  # HH:MM (24-hour)


# ---------- Validation helpers ----------

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_date(value: str) -> str:
    value = (value or "").strip()
    if not DATE_RE.match(value):
        raise ValueError("date must be a real calendar date written as YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("date must be a real calendar date written as YYYY-MM-DD")
    return value


def parse_time_slot(value: str) -> str:
    value = (value or "").strip()
    m = TIME_RE.match(value)
    if not m:
        raise ValueError("time_slot must be hours and minutes on a 24-hour clock, e.g. 09:00 or 14:30")
    hours, minutes = int(m.group(1)), int(m.group(2))
    if hours > 23 or minutes > 59:
        raise ValueError("time_slot must be between 00:00 and 23:59")
    return f"{hours:02d}:{minutes:02d}"


def not_blank(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    return value


# ---------- Request bodies ----------

class DoctorCreate(BaseModel):
    name: str
    specialty: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return not_blank(v, "name")

    @field_validator("specialty")
    @classmethod
    def _specialty(cls, v: str) -> str:
        return not_blank(v, "specialty")


class AppointmentCreate(BaseModel):
    patient_name: str
    date: str
    time_slot: str

    @field_validator("patient_name")
    @classmethod
    def _patient(cls, v: str) -> str:
        return not_blank(v, "patient_name")

    @field_validator("date")
    @classmethod
    def _date(cls, v: str) -> str:
        return parse_date(v)

    @field_validator("time_slot")
    @classmethod
    def _slot(cls, v: str) -> str:
        return parse_time_slot(v)


# ---------- App ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tamale Clinic Appointments", lifespan=lifespan)


def get_doctor_or_404(session: Session, doctor_id: int) -> Doctor:
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@app.post("/doctors", status_code=201, response_model=Doctor)
def add_doctor(body: DoctorCreate):
    with Session(engine) as session:
        doctor = Doctor(name=body.name, specialty=body.specialty)
        session.add(doctor)
        session.commit()
        session.refresh(doctor)
        return doctor


@app.get("/doctors", response_model=List[Doctor])
def list_doctors():
    with Session(engine) as session:
        return session.exec(select(Doctor).order_by(Doctor.id)).all()


@app.post("/doctors/{doctor_id}/appointments", status_code=201, response_model=Appointment)
def book_appointment(doctor_id: int, body: AppointmentCreate):
    with Session(engine) as session:
        get_doctor_or_404(session, doctor_id)
        existing = session.exec(
            select(Appointment).where(
                Appointment.doctor_id == doctor_id,
                Appointment.date == body.date,
                Appointment.time_slot == body.time_slot,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="This doctor already has an appointment on that date in that time slot",
            )
        appt = Appointment(
            doctor_id=doctor_id,
            patient_name=body.patient_name,
            date=body.date,
            time_slot=body.time_slot,
        )
        session.add(appt)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="This doctor already has an appointment on that date in that time slot",
            )
        session.refresh(appt)
        return appt


@app.get("/doctors/{doctor_id}/appointments", response_model=List[Appointment])
def doctor_appointments(doctor_id: int, date: str = Query(...)):
    try:
        day = parse_date(date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    with Session(engine) as session:
        get_doctor_or_404(session, doctor_id)
        return session.exec(
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id, Appointment.date == day)
            .order_by(Appointment.time_slot)
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

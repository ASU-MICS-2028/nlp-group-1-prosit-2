from contextlib import asynccontextmanager
from datetime import date as Date, datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

engine = create_engine("sqlite:///clinic.db", connect_args={"check_same_thread": False})


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialty: str


class Appointment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time", name="uq_doctor_slot"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    patient_name: str
    date: str
    time: str


def _non_empty(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class DoctorIn(BaseModel):
    name: str
    specialty: str

    _check = field_validator("name", "specialty")(_non_empty)


class AppointmentIn(BaseModel):
    doctor_id: int
    patient_name: str
    date: Date
    time: str

    _check = field_validator("patient_name")(_non_empty)

    @field_validator("time")
    @classmethod
    def check_time(cls, v: str) -> str:
        try:
            return datetime.strptime(v.strip(), "%H:%M").strftime("%H:%M")
        except ValueError:
            raise ValueError("time must be HH:MM, for example 09:00 or 14:30")


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Clinic appointments", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/doctors", response_model=Doctor, status_code=201)
def add_doctor(data: DoctorIn, session: Session = Depends(get_session)):
    doctor = Doctor(name=data.name, specialty=data.specialty)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


@app.get("/doctors", response_model=List[Doctor])
def list_doctors(session: Session = Depends(get_session)):
    return session.exec(select(Doctor).order_by(Doctor.id)).all()


@app.post("/appointments", response_model=Appointment, status_code=201)
def book(data: AppointmentIn, session: Session = Depends(get_session)):
    if session.get(Doctor, data.doctor_id) is None:
        raise HTTPException(404, "Doctor not found")
    appt = Appointment(
        doctor_id=data.doctor_id,
        patient_name=data.patient_name,
        date=data.date.isoformat(),
        time=data.time,
    )
    session.add(appt)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "This doctor already has an appointment in that time slot")
    session.refresh(appt)
    return appt


@app.get("/doctors/{doctor_id}/appointments", response_model=List[Appointment])
def doctor_day(doctor_id: int, date: Date = Query(...), session: Session = Depends(get_session)):
    if session.get(Doctor, doctor_id) is None:
        raise HTTPException(404, "Doctor not found")
    stmt = (
        select(Appointment)
        .where(Appointment.doctor_id == doctor_id, Appointment.date == date.isoformat())
        .order_by(Appointment.time)
    )
    return session.exec(stmt).all()


@app.delete("/appointments/{appointment_id}")
def cancel(appointment_id: int, session: Session = Depends(get_session)):
    appt = session.get(Appointment, appointment_id)
    if appt is None:
        raise HTTPException(404, "Appointment not found")
    session.delete(appt)
    session.commit()
    return {"ok": True, "deleted_id": appointment_id}

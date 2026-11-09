import datetime as dt
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

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
    date: dt.date
    time: str


class DoctorIn(BaseModel):
    name: str
    specialty: str

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
    date: dt.date
    time: str

    @field_validator("patient_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("time")
    @classmethod
    def valid_time(cls, v: str) -> str:
        v = v.strip()
        try:
            parsed = dt.datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("time must be in HH:MM format, e.g. 09:00 or 14:30")
        return parsed.strftime("%H:%M")


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Clinic Appointments", lifespan=lifespan)


@app.post("/doctors", response_model=Doctor, status_code=201)
def add_doctor(data: DoctorIn):
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


@app.post("/appointments", response_model=Appointment, status_code=201)
def book_appointment(data: AppointmentIn):
    with Session(engine) as session:
        if session.get(Doctor, data.doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found")
        appt = Appointment(
            doctor_id=data.doctor_id,
            patient_name=data.patient_name,
            date=data.date,
            time=data.time,
        )
        session.add(appt)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="This doctor already has an appointment on that date and time slot",
            )
        session.refresh(appt)
        return appt


@app.get("/doctors/{doctor_id}/appointments", response_model=List[Appointment])
def doctor_appointments(doctor_id: int, date: dt.date):
    with Session(engine) as session:
        if session.get(Doctor, doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found")
        stmt = (
            select(Appointment)
            .where(Appointment.doctor_id == doctor_id, Appointment.date == date)
            .order_by(Appointment.time)
        )
        return session.exec(stmt).all()


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    with Session(engine) as session:
        appt = session.get(Appointment, appointment_id)
        if appt is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        session.delete(appt)
        session.commit()
        return {"detail": "Appointment cancelled", "id": appointment_id}

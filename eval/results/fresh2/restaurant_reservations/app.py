from contextlib import asynccontextmanager
from datetime import date as Date, time as Time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///chopbar.db", connect_args={"check_same_thread": False})


class DiningTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(index=True, unique=True)
    seats: int


class Reservation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(index=True)
    name: str
    phone: str
    people: int
    date: str = Field(index=True)
    time: str


class TableIn(BaseModel):
    number: int
    seats: int = PField(gt=0)


class ReservationIn(BaseModel):
    table_number: int
    name: str
    phone: str
    people: int = PField(gt=0)
    date: Date
    time: Time

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Chop Bar Reservations", lifespan=lifespan)


@app.post("/tables", status_code=201)
def add_table(data: TableIn):
    with Session(engine) as s:
        if s.exec(select(DiningTable).where(DiningTable.number == data.number)).first():
            raise HTTPException(409, f"Table {data.number} already exists")
        t = DiningTable(number=data.number, seats=data.seats)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.get("/tables")
def list_tables():
    with Session(engine) as s:
        return s.exec(select(DiningTable).order_by(DiningTable.number)).all()


@app.post("/reservations", status_code=201)
def make_reservation(data: ReservationIn):
    day = data.date.isoformat()
    at = data.time.strftime("%H:%M")
    with Session(engine) as s:
        table = s.exec(select(DiningTable).where(DiningTable.number == data.table_number)).first()
        if not table:
            raise HTTPException(404, f"Table {data.table_number} does not exist")
        if data.people > table.seats:
            raise HTTPException(
                400, f"Table {table.number} has only {table.seats} seats, but {data.people} people are coming"
            )
        clash = s.exec(
            select(Reservation).where(
                Reservation.table_number == table.number,
                Reservation.date == day,
                Reservation.time == at,
            )
        ).first()
        if clash:
            raise HTTPException(409, f"Table {table.number} is already reserved on {day} at {at}")
        r = Reservation(
            table_number=table.number, name=data.name, phone=data.phone,
            people=data.people, date=day, time=at,
        )
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


@app.get("/reservations")
def reservations_for_date(date: Date):
    with Session(engine) as s:
        return s.exec(
            select(Reservation)
            .where(Reservation.date == date.isoformat())
            .order_by(Reservation.time, Reservation.table_number)
        ).all()

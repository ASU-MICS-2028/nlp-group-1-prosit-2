from datetime import date as Date, time as Time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./chopbar.db", connect_args={"check_same_thread": False})


class DiningTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(index=True, unique=True)
    seats: int


class Reservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("table_number", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(index=True)
    name: str
    phone: str
    party_size: int
    date: str = Field(index=True)  # YYYY-MM-DD
    time: str  # HH:MM


class TableIn(BaseModel):
    number: int = PField(ge=1)
    seats: int = PField(ge=1)


class ReservationIn(BaseModel):
    table_number: int
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)
    party_size: int = PField(ge=1)
    date: Date
    time: Time


app = FastAPI(title="Chop Bar Reservations")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


SQLModel.metadata.create_all(engine)


@app.post("/tables", status_code=201)
def add_table(data: TableIn):
    with Session(engine) as s:
        if s.exec(select(DiningTable).where(DiningTable.number == data.number)).first():
            raise HTTPException(409, f"Table {data.number} already exists")
        t = DiningTable(number=data.number, seats=data.seats)
        s.add(t)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, f"Table {data.number} already exists")
        s.refresh(t)
        return t


@app.get("/tables")
def list_tables() -> List[DiningTable]:
    with Session(engine) as s:
        return s.exec(select(DiningTable).order_by(DiningTable.number)).all()


@app.post("/reservations", status_code=201)
def make_reservation(data: ReservationIn):
    d = data.date.isoformat()
    tm = data.time.strftime("%H:%M")
    with Session(engine) as s:
        table = s.exec(select(DiningTable).where(DiningTable.number == data.table_number)).first()
        if not table:
            raise HTTPException(404, f"Table {data.table_number} does not exist")
        if data.party_size > table.seats:
            raise HTTPException(
                400, f"Table {table.number} has only {table.seats} seats, but {data.party_size} people are coming"
            )
        clash = s.exec(
            select(Reservation).where(
                Reservation.table_number == table.number, Reservation.date == d, Reservation.time == tm
            )
        ).first()
        if clash:
            raise HTTPException(409, f"Table {table.number} is already reserved on {d} at {tm}")
        r = Reservation(
            table_number=table.number, name=data.name, phone=data.phone,
            party_size=data.party_size, date=d, time=tm,
        )
        s.add(r)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, f"Table {table.number} is already reserved on {d} at {tm}")
        s.refresh(r)
        return r


@app.get("/reservations")
def reservations_for_date(date: Date = Query(...)) -> List[Reservation]:
    with Session(engine) as s:
        return s.exec(
            select(Reservation)
            .where(Reservation.date == date.isoformat())
            .order_by(Reservation.time, Reservation.table_number)
        ).all()

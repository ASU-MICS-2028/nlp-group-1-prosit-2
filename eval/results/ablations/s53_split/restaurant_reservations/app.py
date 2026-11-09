from contextlib import asynccontextmanager
from datetime import date as Date, time as Time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///chopbar.db", connect_args={"check_same_thread": False})


class Table(SQLModel, table=True):
    table_number: int = Field(primary_key=True)
    seats: int


class Reservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("table_number", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(foreign_key="table.table_number", index=True)
    customer_name: str
    phone: str
    party_size: int
    date: Date = Field(index=True)
    time: Time


class TableIn(SQLModel):
    table_number: int = Field(ge=1)
    seats: int = Field(ge=1)


class ReservationIn(SQLModel):
    table_number: int
    customer_name: str
    phone: str
    party_size: int = Field(ge=1)
    date: Date
    time: Time

    @field_validator("customer_name", "phone")
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


@app.post("/tables", status_code=201, response_model=Table)
def add_table(data: TableIn):
    with Session(engine) as s:
        if s.get(Table, data.table_number):
            raise HTTPException(409, "A table with this number already exists.")
        t = Table(table_number=data.table_number, seats=data.seats)
        s.add(t)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "A table with this number already exists.")
        s.refresh(t)
        return t


@app.get("/tables", response_model=List[Table])
def list_tables():
    with Session(engine) as s:
        return s.exec(select(Table).order_by(Table.table_number)).all()


@app.post("/reservations", status_code=201, response_model=Reservation)
def make_reservation(data: ReservationIn):
    with Session(engine) as s:
        t = s.get(Table, data.table_number)
        if not t:
            raise HTTPException(404, "That table number does not exist.")
        if data.party_size > t.seats:
            raise HTTPException(
                422, f"Table {t.table_number} has only {t.seats} seats; the group is too big."
            )
        clash = s.exec(
            select(Reservation).where(
                Reservation.table_number == data.table_number,
                Reservation.date == data.date,
                Reservation.time == data.time,
            )
        ).first()
        if clash:
            raise HTTPException(409, "That table is already reserved for this date and time.")
        r = Reservation(**data.model_dump())
        s.add(r)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "That table is already reserved for this date and time.")
        s.refresh(r)
        return r


@app.get("/reservations", response_model=List[Reservation])
def reservations_for_date(date: Date = Query(...)):
    with Session(engine) as s:
        return s.exec(
            select(Reservation)
            .where(Reservation.date == date)
            .order_by(Reservation.time, Reservation.table_number)
        ).all()

from contextlib import asynccontextmanager
from datetime import date as Date, time as Time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, StrictInt, field_validator
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./chopbar.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Table(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(index=True, unique=True)
    seats: int


class Reservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("table_number", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(index=True)
    customer_name: str
    phone: str
    people: int
    date: str = Field(index=True)  # YYYY-MM-DD
    time: str  # HH:MM:SS


class TableIn(BaseModel):
    table_number: StrictInt
    seats: StrictInt

    @field_validator("seats")
    @classmethod
    def seats_positive(cls, v):
        if v < 1:
            raise ValueError("seats must be a whole number of at least 1")
        return v


class TableOut(BaseModel):
    table_number: int
    seats: int


class ReservationIn(BaseModel):
    table_number: StrictInt
    customer_name: str
    phone: str
    people: StrictInt
    date: Date
    time: Time

    @field_validator("customer_name", "phone")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("people")
    @classmethod
    def people_positive(cls, v):
        if v < 1:
            raise ValueError("people must be a whole number of at least 1")
        return v


class ReservationOut(BaseModel):
    id: int
    table_number: int
    customer_name: str
    phone: str
    people: int
    date: str
    time: str


def get_engine():
    return engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(get_engine())
    yield


app = FastAPI(title="Chop Bar Reservations", lifespan=lifespan)


def norm_time(t: Time) -> str:
    return t.replace(microsecond=0, tzinfo=None).strftime("%H:%M:%S")


@app.post("/tables", response_model=TableOut, status_code=201)
def add_table(data: TableIn):
    with Session(get_engine()) as s:
        if s.exec(select(Table).where(Table.table_number == data.table_number)).first():
            raise HTTPException(409, "A table with that number already exists")
        t = Table(table_number=data.table_number, seats=data.seats)
        s.add(t)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "A table with that number already exists")
        s.refresh(t)
        return TableOut(table_number=t.table_number, seats=t.seats)


@app.get("/tables", response_model=List[TableOut])
def list_tables():
    with Session(get_engine()) as s:
        rows = s.exec(select(Table).order_by(Table.table_number)).all()
        return [TableOut(table_number=t.table_number, seats=t.seats) for t in rows]


@app.post("/reservations", response_model=ReservationOut, status_code=201)
def make_reservation(data: ReservationIn):
    d = data.date.isoformat()
    tm = norm_time(data.time)
    with Session(get_engine()) as s:
        table = s.exec(select(Table).where(Table.table_number == data.table_number)).first()
        if not table:
            raise HTTPException(404, "That table does not exist")
        if data.people > table.seats:
            raise HTTPException(
                400, f"The group of {data.people} is bigger than the {table.seats} seats at this table"
            )
        clash = s.exec(
            select(Reservation).where(
                Reservation.table_number == data.table_number,
                Reservation.date == d,
                Reservation.time == tm,
            )
        ).first()
        if clash:
            raise HTTPException(409, "That table is already reserved for this date and time")
        r = Reservation(
            table_number=data.table_number,
            customer_name=data.customer_name,
            phone=data.phone,
            people=data.people,
            date=d,
            time=tm,
        )
        s.add(r)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "That table is already reserved for this date and time")
        s.refresh(r)
        return ReservationOut(**r.model_dump())


@app.get("/reservations", response_model=List[ReservationOut])
def list_reservations(date: Date = Query(...)):
    with Session(get_engine()) as s:
        rows = s.exec(
            select(Reservation)
            .where(Reservation.date == date.isoformat())
            .order_by(Reservation.time, Reservation.table_number)
        ).all()
        return [ReservationOut(**r.model_dump()) for r in rows]

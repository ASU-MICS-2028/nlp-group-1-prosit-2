from contextlib import asynccontextmanager
from datetime import date as Date, time as Time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///chopbar.db", connect_args={"check_same_thread": False})


class Table(SQLModel, table=True):
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
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)
    people: int = PField(gt=0)
    date: Date
    time: Time


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Chop Bar Reservations", lifespan=lifespan)


@app.post("/tables", status_code=201)
def add_table(data: TableIn) -> Table:
    with Session(engine) as s:
        if s.exec(select(Table).where(Table.number == data.number)).first():
            raise HTTPException(409, "A table with this number already exists")
        t = Table(number=data.number, seats=data.seats)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.get("/tables")
def list_tables() -> List[Table]:
    with Session(engine) as s:
        return s.exec(select(Table).order_by(Table.number)).all()


@app.post("/reservations", status_code=201)
def make_reservation(data: ReservationIn) -> Reservation:
    d = data.date.isoformat()
    t = data.time.strftime("%H:%M")
    with Session(engine) as s:
        table = s.exec(select(Table).where(Table.number == data.table_number)).first()
        if not table:
            raise HTTPException(404, "Table not found")
        if data.people > table.seats:
            raise HTTPException(400, f"Table {table.number} only has {table.seats} seats")
        clash = s.exec(
            select(Reservation).where(
                Reservation.table_number == data.table_number,
                Reservation.date == d,
                Reservation.time == t,
            )
        ).first()
        if clash:
            raise HTTPException(409, "This table is already reserved for that date and time")
        r = Reservation(
            table_number=data.table_number, name=data.name, phone=data.phone,
            people=data.people, date=d, time=t,
        )
        s.add(r)
        s.commit()
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

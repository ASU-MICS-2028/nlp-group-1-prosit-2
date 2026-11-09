from datetime import date as date_type, time as time_type
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as F, Session, SQLModel, create_engine, select


class Table(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    number: int = F(unique=True)
    seats: int


class Reservation(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    table_id: int = F(foreign_key="table.id")
    name: str
    phone: str
    party_size: int
    date: date_type
    time: time_type


class TableIn(BaseModel):
    number: int
    seats: int = Field(gt=0)


class ReservationIn(BaseModel):
    table_id: int
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    party_size: int = Field(gt=0)
    date: date_type
    time: time_type


engine = create_engine("sqlite:///app.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/tables", status_code=201)
def add_table(t: TableIn):
    with Session(engine) as s:
        if s.exec(select(Table).where(Table.number == t.number)).first():
            raise HTTPException(409, "Table number already exists")
        row = Table(number=t.number, seats=t.seats)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


@app.get("/tables")
def list_tables():
    with Session(engine) as s:
        return s.exec(select(Table).order_by(Table.number)).all()


@app.post("/reservations", status_code=201)
def reserve(r: ReservationIn):
    with Session(engine) as s:
        t = s.get(Table, r.table_id)
        if not t:
            raise HTTPException(404, "Table not found")
        if r.party_size > t.seats:
            raise HTTPException(400, "Group is bigger than the seats at this table")
        clash = s.exec(select(Reservation).where(
            Reservation.table_id == r.table_id,
            Reservation.date == r.date,
            Reservation.time == r.time)).first()
        if clash:
            raise HTTPException(409, "Table already reserved for that date and time")
        row = Reservation(**r.model_dump())
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


@app.get("/reservations")
def list_reservations(date: date_type):
    with Session(engine) as s:
        return s.exec(select(Reservation).where(Reservation.date == date)
                      .order_by(Reservation.time)).all()

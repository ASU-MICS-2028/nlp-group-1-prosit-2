from datetime import date as date_type, time as time_type
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SField, Session, create_engine, select


class Table(SQLModel, table=True):
    id: Optional[int] = SField(default=None, primary_key=True)
    number: int = SField(unique=True, index=True)
    seats: int


class Reservation(SQLModel, table=True):
    id: Optional[int] = SField(default=None, primary_key=True)
    table_id: int = SField(index=True)
    name: str
    phone: str
    party_size: int
    date: date_type
    time: time_type


class TableIn(BaseModel):
    number: int = Field(gt=0)
    seats: int = Field(gt=0)


class ReservationIn(BaseModel):
    table_id: int
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    party_size: int = Field(gt=0)
    date: date_type
    time: time_type


engine = create_engine("sqlite:///reservations.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


@app.post("/tables", status_code=201)
def add_table(data: TableIn):
    with Session(engine) as s:
        if s.exec(select(Table).where(Table.number == data.number)).first():
            raise HTTPException(409, "Table number already exists")
        t = Table(number=data.number, seats=data.seats)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.get("/tables")
def list_tables():
    with Session(engine) as s:
        return s.exec(select(Table).order_by(Table.number)).all()


@app.post("/reservations", status_code=201)
def reserve(data: ReservationIn):
    with Session(engine) as s:
        t = s.get(Table, data.table_id)
        if not t:
            raise HTTPException(404, "Table not found")
        if data.party_size > t.seats:
            raise HTTPException(400, "Group is bigger than the seats at this table")
        clash = s.exec(select(Reservation).where(
            Reservation.table_id == data.table_id,
            Reservation.date == data.date,
            Reservation.time == data.time)).first()
        if clash:
            raise HTTPException(409, "Table already reserved for that date and time")
        r = Reservation(**data.model_dump())
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


@app.get("/reservations")
def reservations_for_date(date: date_type):
    with Session(engine) as s:
        return s.exec(select(Reservation).where(Reservation.date == date)
                      .order_by(Reservation.time)).all()

from datetime import date as Date, time as Time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

engine = create_engine("sqlite:///chopbar.db", connect_args={"check_same_thread": False})


class DiningTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(index=True, unique=True)
    seats: int


class Reservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("table_number", "date", "time"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    table_number: int = Field(index=True)
    name: str
    phone: str
    party_size: int
    date: str = Field(index=True)
    time: str


class TableIn(BaseModel):
    table_number: int = PField(gt=0)
    seats: int = PField(gt=0)


class ReservationIn(BaseModel):
    table_number: int
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)
    party_size: int = PField(gt=0)
    date: Date
    time: Time


app = FastAPI(title="Chop Bar Reservations")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


@app.post("/tables", status_code=201)
def add_table(data: TableIn):
    with Session(engine) as s:
        if s.exec(select(DiningTable).where(DiningTable.table_number == data.table_number)).first():
            raise HTTPException(409, "A table with this number already exists")
        t = DiningTable(table_number=data.table_number, seats=data.seats)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.get("/tables")
def list_tables() -> List[DiningTable]:
    with Session(engine) as s:
        return s.exec(select(DiningTable).order_by(DiningTable.table_number)).all()


@app.post("/reservations", status_code=201)
def make_reservation(data: ReservationIn):
    name, phone = data.name.strip(), data.phone.strip()
    if not name or not phone:
        raise HTTPException(422, "Name and phone number are required")
    d = data.date.isoformat()
    t = data.time.replace(tzinfo=None).isoformat(timespec="minutes" if data.time.second == 0 and data.time.microsecond == 0 else "auto")
    with Session(engine) as s:
        table = s.exec(select(DiningTable).where(DiningTable.table_number == data.table_number)).first()
        if not table:
            raise HTTPException(404, "Table not found")
        if data.party_size > table.seats:
            raise HTTPException(400, f"Group of {data.party_size} is too big for table {table.table_number} ({table.seats} seats)")
        clash = s.exec(
            select(Reservation).where(
                Reservation.table_number == data.table_number,
                Reservation.date == d,
                Reservation.time == t,
            )
        ).first()
        if clash:
            raise HTTPException(409, "This table is already reserved for that date and time")
        r = Reservation(table_number=data.table_number, name=name, phone=phone,
                        party_size=data.party_size, date=d, time=t)
        s.add(r)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "This table is already reserved for that date and time")
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

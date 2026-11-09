from contextlib import asynccontextmanager
from datetime import date as Date, time as Time
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field as PField
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Field, Session, create_engine, select, UniqueConstraint

engine = create_engine("sqlite:///chopbar.db", connect_args={"check_same_thread": False})


class DiningTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(unique=True, index=True)
    seats: int


class Reservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("table_number", "date", "time", name="uq_table_slot"),)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Chop Bar Reservations", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/tables", status_code=201)
def add_table(data: TableIn, session: Session = Depends(get_session)):
    table = DiningTable(number=data.number, seats=data.seats)
    session.add(table)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Table {data.number} already exists")
    session.refresh(table)
    return table


@app.get("/tables")
def list_tables(session: Session = Depends(get_session)):
    return session.exec(select(DiningTable).order_by(DiningTable.number)).all()


@app.post("/reservations", status_code=201)
def make_reservation(data: ReservationIn, session: Session = Depends(get_session)):
    name, phone = data.name.strip(), data.phone.strip()
    if not name or not phone:
        raise HTTPException(422, "Name and phone number are required")
    table = session.exec(select(DiningTable).where(DiningTable.number == data.table_number)).first()
    if table is None:
        raise HTTPException(404, f"Table {data.table_number} does not exist")
    if data.party_size > table.seats:
        raise HTTPException(
            400, f"Table {table.number} has only {table.seats} seats but {data.party_size} people are coming"
        )
    date_s = data.date.isoformat()
    time_s = data.time.strftime("%H:%M")
    res = Reservation(
        table_number=table.number, name=name, phone=phone,
        party_size=data.party_size, date=date_s, time=time_s,
    )
    session.add(res)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Table {table.number} is already reserved on {date_s} at {time_s}")
    session.refresh(res)
    return res


@app.get("/reservations")
def reservations_for_date(date: Date, session: Session = Depends(get_session)):
    stmt = (
        select(Reservation)
        .where(Reservation.date == date.isoformat())
        .order_by(Reservation.time, Reservation.table_number)
    )
    return session.exec(stmt).all()

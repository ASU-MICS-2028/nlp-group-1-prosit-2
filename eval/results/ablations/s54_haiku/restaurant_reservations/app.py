import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, SQLModel, create_engine, select
import sqlmodel

DATABASE_URL = "sqlite:///./reservations.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class RestaurantTable(SQLModel, table=True):
    id: Optional[int] = sqlmodel.Field(default=None, primary_key=True)
    number: int = sqlmodel.Field(unique=True, index=True)
    seats: int


class Reservation(SQLModel, table=True):
    id: Optional[int] = sqlmodel.Field(default=None, primary_key=True)
    table_number: int = sqlmodel.Field(index=True)
    name: str
    phone: str
    party_size: int
    date: datetime.date = sqlmodel.Field(index=True)
    time: datetime.time


class TableIn(BaseModel):
    number: int = Field(ge=1)
    seats: int = Field(ge=1)


class ReservationIn(BaseModel):
    table_number: int
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    party_size: int = Field(ge=1)
    date: datetime.date
    time: datetime.time


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Chop Bar Table Reservations", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/tables", status_code=201)
def add_table(data: TableIn, session: Session = Depends(get_session)):
    existing = session.exec(
        select(RestaurantTable).where(RestaurantTable.number == data.number)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A table with this number already exists")
    table = RestaurantTable(number=data.number, seats=data.seats)
    session.add(table)
    session.commit()
    session.refresh(table)
    return table


@app.get("/tables")
def list_tables(session: Session = Depends(get_session)):
    return session.exec(select(RestaurantTable).order_by(RestaurantTable.number)).all()


@app.post("/reservations", status_code=201)
def make_reservation(data: ReservationIn, session: Session = Depends(get_session)):
    table = session.exec(
        select(RestaurantTable).where(RestaurantTable.number == data.table_number)
    ).first()
    if table is None:
        raise HTTPException(status_code=404, detail="No table with this number")
    if data.party_size > table.seats:
        raise HTTPException(
            status_code=422,
            detail=f"Party of {data.party_size} is bigger than table {table.number} ({table.seats} seats)",
        )
    clash = session.exec(
        select(Reservation).where(
            Reservation.table_number == data.table_number,
            Reservation.date == data.date,
            Reservation.time == data.time,
        )
    ).first()
    if clash:
        raise HTTPException(
            status_code=409,
            detail="This table is already reserved for that date and time",
        )
    reservation = Reservation(
        table_number=data.table_number,
        name=data.name,
        phone=data.phone,
        party_size=data.party_size,
        date=data.date,
        time=data.time,
    )
    session.add(reservation)
    session.commit()
    session.refresh(reservation)
    return reservation


@app.get("/reservations")
def list_reservations(
    date: datetime.date = Query(...),
    session: Session = Depends(get_session),
):
    return session.exec(
        select(Reservation)
        .where(Reservation.date == date)
        .order_by(Reservation.time, Reservation.table_number)
    ).all()

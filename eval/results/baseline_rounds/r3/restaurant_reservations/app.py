from datetime import date as Date, time as Time
from threading import Lock
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Chop Bar Table Reservations")

_lock = Lock()
_tables = {}  # table_number -> dict
_reservations = []  # list of dicts
_next_id = 1


class TableIn(BaseModel):
    table_number: int = Field(..., ge=1, description="The table's number")
    seats: int = Field(..., ge=1, description="How many seats the table has")


class TableOut(BaseModel):
    table_number: int
    seats: int


class ReservationIn(BaseModel):
    table_number: int = Field(..., ge=1)
    customer_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    party_size: int = Field(..., ge=1, description="How many people are coming")
    date: Date = Field(..., description="YYYY-MM-DD")
    time: Time = Field(..., description="HH:MM")

    @field_validator("customer_name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class ReservationOut(BaseModel):
    id: int
    table_number: int
    customer_name: str
    phone: str
    party_size: int
    date: Date
    time: str


def _norm_time(t: Time) -> str:
    return t.strftime("%H:%M")


@app.post("/tables", response_model=TableOut, status_code=201)
def add_table(body: TableIn):
    with _lock:
        if body.table_number in _tables:
            raise HTTPException(status_code=409, detail=f"Table {body.table_number} already exists")
        rec = {"table_number": body.table_number, "seats": body.seats}
        _tables[body.table_number] = rec
        return rec


@app.get("/tables", response_model=List[TableOut])
def list_tables():
    with _lock:
        return [_tables[k] for k in sorted(_tables)]


@app.post("/reservations", response_model=ReservationOut, status_code=201)
def make_reservation(body: ReservationIn):
    global _next_id
    t = _norm_time(body.time)
    with _lock:
        table = _tables.get(body.table_number)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table {body.table_number} does not exist")
        if body.party_size > table["seats"]:
            raise HTTPException(
                status_code=400,
                detail=f"Group of {body.party_size} is too big for table {body.table_number}, which has {table['seats']} seats",
            )
        for r in _reservations:
            if r["table_number"] == body.table_number and r["date"] == body.date and r["time"] == t:
                raise HTTPException(
                    status_code=409,
                    detail=f"Table {body.table_number} is already reserved on {body.date.isoformat()} at {t}",
                )
        rec = {
            "id": _next_id,
            "table_number": body.table_number,
            "customer_name": body.customer_name,
            "phone": body.phone,
            "party_size": body.party_size,
            "date": body.date,
            "time": t,
        }
        _next_id += 1
        _reservations.append(rec)
        return rec


@app.get("/reservations", response_model=List[ReservationOut])
def list_reservations(date: Optional[Date] = Query(None, description="YYYY-MM-DD")):
    with _lock:
        items = [r for r in _reservations if date is None or r["date"] == date]
        return sorted(items, key=lambda r: (r["date"], r["time"], r["table_number"]))


@app.get("/reservations/date/{day}", response_model=List[ReservationOut])
def reservations_for_date(day: Date):
    return list_reservations(date=day)

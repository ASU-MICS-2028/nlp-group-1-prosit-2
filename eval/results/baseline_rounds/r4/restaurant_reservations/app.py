from datetime import date as Date, time as Time
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Chop Bar Table Reservations")

_lock = Lock()
tables: Dict[int, dict] = {}
reservations: List[dict] = []
_next_reservation_id = 1


class TableIn(BaseModel):
    table_number: int = Field(..., ge=1, description="Table number")
    seats: int = Field(..., ge=1, description="Number of seats at the table")


class TableOut(BaseModel):
    table_number: int
    seats: int


class ReservationIn(BaseModel):
    table_number: int = Field(..., ge=1)
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    party_size: int = Field(..., ge=1, description="How many people are coming")
    date: Date = Field(..., description="YYYY-MM-DD")
    time: Time = Field(..., description="HH:MM")

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ReservationOut(BaseModel):
    id: int
    table_number: int
    name: str
    phone: str
    party_size: int
    date: Date
    time: Time


@app.get("/")
def home():
    return {"message": "Welcome to the chop bar reservation system"}


@app.post("/tables", response_model=TableOut, status_code=201)
def add_table(table: TableIn):
    with _lock:
        if table.table_number in tables:
            raise HTTPException(status_code=409, detail=f"Table {table.table_number} already exists")
        record = {"table_number": table.table_number, "seats": table.seats}
        tables[table.table_number] = record
        return record


@app.get("/tables", response_model=List[TableOut])
def list_tables():
    with _lock:
        return [tables[k] for k in sorted(tables)]


@app.post("/reservations", response_model=ReservationOut, status_code=201)
def make_reservation(res: ReservationIn):
    global _next_reservation_id
    with _lock:
        table = tables.get(res.table_number)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table {res.table_number} does not exist")
        if res.party_size > table["seats"]:
            raise HTTPException(
                status_code=400,
                detail=f"Table {res.table_number} has only {table['seats']} seats but the group has {res.party_size} people",
            )
        t = res.time.replace(microsecond=0, tzinfo=None)
        for r in reservations:
            if r["table_number"] == res.table_number and r["date"] == res.date and r["time"] == t:
                raise HTTPException(
                    status_code=409,
                    detail=f"Table {res.table_number} is already reserved on {res.date.isoformat()} at {t.strftime('%H:%M')}",
                )
        record = {
            "id": _next_reservation_id,
            "table_number": res.table_number,
            "name": res.name,
            "phone": res.phone,
            "party_size": res.party_size,
            "date": res.date,
            "time": t,
        }
        _next_reservation_id += 1
        reservations.append(record)
        return record


def _for_date(d: Date):
    with _lock:
        found = [r for r in reservations if r["date"] == d]
    return sorted(found, key=lambda r: (r["time"], r["table_number"]))


@app.get("/reservations", response_model=List[ReservationOut])
def list_reservations(date: Optional[Date] = Query(None, description="YYYY-MM-DD")):
    if date is None:
        with _lock:
            return sorted(reservations, key=lambda r: (r["date"], r["time"], r["table_number"]))
    return _for_date(date)


@app.get("/reservations/date/{day}", response_model=List[ReservationOut])
def reservations_for_date(day: Date):
    return _for_date(day)

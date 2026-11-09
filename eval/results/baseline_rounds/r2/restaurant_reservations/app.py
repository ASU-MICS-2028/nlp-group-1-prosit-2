from datetime import date as Date, time as Time
from threading import Lock
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Chop Bar Table Reservations")

_lock = Lock()
_tables = {}  # table_number -> dict
_reservations = []  # list of dicts
_next_id = 1


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


class ReservationOut(BaseModel):
    id: int
    table_number: int
    name: str
    phone: str
    party_size: int
    date: Date
    time: Time


def _norm_time(t: Time) -> Time:
    return t.replace(second=0, microsecond=0, tzinfo=None)


@app.get("/")
def home():
    return {"message": "Welcome to the chop bar reservation system"}


@app.post("/tables", response_model=TableOut, status_code=201)
def add_table(table: TableIn):
    with _lock:
        if table.table_number in _tables:
            raise HTTPException(status_code=409, detail=f"Table {table.table_number} already exists")
        rec = {"table_number": table.table_number, "seats": table.seats}
        _tables[table.table_number] = rec
        return rec


@app.get("/tables", response_model=List[TableOut])
def list_tables():
    with _lock:
        return sorted(_tables.values(), key=lambda t: t["table_number"])


@app.get("/tables/{table_number}", response_model=TableOut)
def get_table(table_number: int):
    with _lock:
        t = _tables.get(table_number)
        if not t:
            raise HTTPException(status_code=404, detail="Table not found")
        return t


@app.post("/reservations", response_model=ReservationOut, status_code=201)
def make_reservation(r: ReservationIn):
    global _next_id
    name = r.name.strip()
    phone = r.phone.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    if not phone:
        raise HTTPException(status_code=422, detail="Phone number is required")
    t_norm = _norm_time(r.time)
    with _lock:
        table = _tables.get(r.table_number)
        if not table:
            raise HTTPException(status_code=404, detail=f"Table {r.table_number} does not exist")
        if r.party_size > table["seats"]:
            raise HTTPException(
                status_code=400,
                detail=f"Group of {r.party_size} is too big for table {r.table_number} which has {table['seats']} seats",
            )
        for existing in _reservations:
            if (existing["table_number"] == r.table_number and existing["date"] == r.date
                    and existing["time"] == t_norm):
                raise HTTPException(
                    status_code=409,
                    detail=f"Table {r.table_number} is already reserved on {r.date.isoformat()} at {t_norm.strftime('%H:%M')}",
                )
        rec = {
            "id": _next_id,
            "table_number": r.table_number,
            "name": name,
            "phone": phone,
            "party_size": r.party_size,
            "date": r.date,
            "time": t_norm,
        }
        _next_id += 1
        _reservations.append(rec)
        return rec


@app.get("/reservations", response_model=List[ReservationOut])
def list_reservations(date: Optional[Date] = Query(None, description="YYYY-MM-DD")):
    with _lock:
        items = [x for x in _reservations if date is None or x["date"] == date]
        return sorted(items, key=lambda x: (x["date"], x["time"], x["table_number"]))


@app.get("/reservations/date/{date}", response_model=List[ReservationOut])
def reservations_for_date(date: Date):
    with _lock:
        items = [x for x in _reservations if x["date"] == date]
        return sorted(items, key=lambda x: (x["time"], x["table_number"]))


@app.get("/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int):
    with _lock:
        for x in _reservations:
            if x["id"] == reservation_id:
                return x
    raise HTTPException(status_code=404, detail="Reservation not found")

from datetime import date, datetime
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

app = FastAPI(title="Kumasi Tailoring Shop Orders")

_lock = Lock()
_customers: Dict[int, dict] = {}
_orders: Dict[int, dict] = {}
_next_customer_id = 1
_next_order_id = 1


class CustomerIn(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    chest: float = Field(..., gt=0, description="inches")
    waist: float = Field(..., gt=0, description="inches")
    hip: float = Field(..., gt=0, description="inches")
    length: float = Field(..., gt=0, description="inches")

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class OrderIn(BaseModel):
    garment: str = Field(..., min_length=1)
    due_date: date
    price: float = Field(..., ge=0, description="cedis")
    deposit: float = Field(0, ge=0, description="cedis")

    @field_validator("garment")
    @classmethod
    def garment_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def deposit_not_more_than_price(self):
        if round(self.deposit, 2) > round(self.price, 2):
            raise ValueError("deposit can never be more than the price")
        return self


def _order_out(o: dict) -> dict:
    out = dict(o)
    out["balance"] = round(o["price"] - o["deposit"], 2)
    c = _customers.get(o["customer_id"])
    out["customer_name"] = c["name"] if c else None
    out["customer_phone"] = c["phone"] if c else None
    return out


def _get_customer(customer_id: int) -> dict:
    c = _customers.get(customer_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


def _get_order(order_id: int) -> dict:
    o = _orders.get(order_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return o


@app.get("/")
def root():
    return {"message": "Tailoring shop orders API. See /docs for all endpoints."}


@app.post("/customers", status_code=201)
def create_customer(data: CustomerIn):
    global _next_customer_id
    with _lock:
        cid = _next_customer_id
        _next_customer_id += 1
        c = {"id": cid, **data.model_dump(), "created_at": datetime.now().isoformat()}
        _customers[cid] = c
        return c


@app.get("/customers")
def list_customers():
    return list(_customers.values())


@app.get("/customers/{customer_id}")
def get_customer(customer_id: int):
    return _get_customer(customer_id)


@app.post("/customers/{customer_id}/orders", status_code=201)
def create_order(customer_id: int, data: OrderIn):
    global _next_order_id
    with _lock:
        _get_customer(customer_id)
        oid = _next_order_id
        _next_order_id += 1
        o = {
            "id": oid,
            "customer_id": customer_id,
            "garment": data.garment,
            "due_date": data.due_date.isoformat(),
            "price": round(data.price, 2),
            "deposit": round(data.deposit, 2),
            "collected": False,
            "collected_at": None,
            "created_at": datetime.now().isoformat(),
        }
        _orders[oid] = o
        return _order_out(o)


@app.get("/customers/{customer_id}/orders")
def list_customer_orders(customer_id: int):
    _get_customer(customer_id)
    orders = [o for o in _orders.values() if o["customer_id"] == customer_id]
    orders.sort(key=lambda o: (o["due_date"], o["id"]))
    return [_order_out(o) for o in orders]


@app.get("/orders")
def list_orders():
    return [_order_out(o) for o in sorted(_orders.values(), key=lambda o: o["id"])]


@app.get("/orders/due")
def orders_due(
    on_or_before: Optional[date] = Query(None, description="Show uncollected orders due on or before this date (YYYY-MM-DD)"),
    date_: Optional[date] = Query(None, alias="date"),
    before: Optional[date] = Query(None),
):
    cutoff = on_or_before or date_ or before
    if cutoff is None:
        raise HTTPException(status_code=400, detail="Please give a date, e.g. ?on_or_before=2024-12-31")
    cut = cutoff.isoformat()
    orders = [o for o in _orders.values() if not o["collected"] and o["due_date"] <= cut]
    orders.sort(key=lambda o: (o["due_date"], o["id"]))
    return [_order_out(o) for o in orders]


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    return _order_out(_get_order(order_id))


@app.post("/orders/{order_id}/collect")
def collect_order(order_id: int):
    with _lock:
        o = _get_order(order_id)
        if not o["collected"]:
            o["collected"] = True
            o["collected_at"] = datetime.now().isoformat()
        return _order_out(o)


@app.put("/orders/{order_id}/collect")
def collect_order_put(order_id: int):
    return collect_order(order_id)


@app.patch("/orders/{order_id}/collect")
def collect_order_patch(order_id: int):
    return collect_order(order_id)

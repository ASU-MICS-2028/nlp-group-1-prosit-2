from datetime import date, datetime, timezone
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
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=50)
    chest: float = Field(..., gt=0, le=200, allow_inf_nan=False, description="inches")
    waist: float = Field(..., gt=0, le=200, allow_inf_nan=False, description="inches")
    hip: float = Field(..., gt=0, le=200, allow_inf_nan=False, description="inches")
    length: float = Field(..., gt=0, le=200, allow_inf_nan=False, description="inches")

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class OrderIn(BaseModel):
    garment: str = Field(..., min_length=1, max_length=200)
    due_date: date
    price: float = Field(..., ge=0, allow_inf_nan=False, description="cedis")
    deposit: float = Field(0, ge=0, allow_inf_nan=False, description="cedis")

    @field_validator("garment")
    @classmethod
    def garment_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("price", "deposit")
    @classmethod
    def round_money(cls, v: float) -> float:
        return round(v, 2)

    @model_validator(mode="after")
    def deposit_not_more_than_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit can never be more than the price")
        return self


def _order_out(o: dict) -> dict:
    out = dict(o)
    out["due_date"] = o["due_date"].isoformat()
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


@app.post("/customers", status_code=201)
def create_customer(data: CustomerIn):
    global _next_customer_id
    with _lock:
        cid = _next_customer_id
        _next_customer_id += 1
        c = {"id": cid, **data.model_dump()}
        _customers[cid] = c
        return dict(c)


@app.get("/customers")
def list_customers():
    with _lock:
        return [dict(c) for c in _customers.values()]


@app.get("/customers/{customer_id}")
def get_customer(customer_id: int):
    with _lock:
        return dict(_get_customer(customer_id))


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
            "due_date": data.due_date,
            "price": data.price,
            "deposit": data.deposit,
            "collected": False,
            "collected_at": None,
        }
        _orders[oid] = o
        return _order_out(o)


@app.get("/customers/{customer_id}/orders")
def list_customer_orders(customer_id: int):
    with _lock:
        _get_customer(customer_id)
        items = [o for o in _orders.values() if o["customer_id"] == customer_id]
        items.sort(key=lambda o: (o["due_date"], o["id"]))
        return [_order_out(o) for o in items]


@app.get("/orders/due")
def orders_due(on_or_before: date = Query(..., alias="date", description="YYYY-MM-DD")):
    with _lock:
        items = [
            o for o in _orders.values()
            if not o["collected"] and o["due_date"] <= on_or_before
        ]
        items.sort(key=lambda o: (o["due_date"], o["id"]))
        return [_order_out(o) for o in items]


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    with _lock:
        return _order_out(_get_order(order_id))


@app.post("/orders/{order_id}/collect")
def collect_order(order_id: int):
    with _lock:
        o = _get_order(order_id)
        if o["collected"]:
            raise HTTPException(status_code=409, detail="Order has already been collected")
        o["collected"] = True
        o["collected_at"] = datetime.now(timezone.utc).isoformat()
        return _order_out(o)

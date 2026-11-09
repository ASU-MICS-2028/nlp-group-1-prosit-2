from datetime import date
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
    chest: float = Field(..., gt=0, le=200, description="inches")
    waist: float = Field(..., gt=0, le=200, description="inches")
    hip: float = Field(..., gt=0, le=200, description="inches")
    length: float = Field(..., gt=0, le=200, description="inches")

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class Customer(CustomerIn):
    id: int


class OrderIn(BaseModel):
    garment: str = Field(..., min_length=1, max_length=200)
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

    @field_validator("price", "deposit")
    @classmethod
    def two_decimals(cls, v: float) -> float:
        return round(v, 2)

    @model_validator(mode="after")
    def deposit_not_more_than_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit can never be more than the price")
        return self


class Order(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_phone: str
    garment: str
    due_date: date
    price: float
    deposit: float
    balance: float
    collected: bool
    collected_on: Optional[date] = None


def _order_out(o: dict) -> Order:
    c = _customers[o["customer_id"]]
    return Order(
        id=o["id"],
        customer_id=o["customer_id"],
        customer_name=c["name"],
        customer_phone=c["phone"],
        garment=o["garment"],
        due_date=o["due_date"],
        price=o["price"],
        deposit=o["deposit"],
        balance=round(o["price"] - o["deposit"], 2),
        collected=o["collected"],
        collected_on=o["collected_on"],
    )


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


@app.post("/customers", response_model=Customer, status_code=201)
def create_customer(data: CustomerIn):
    global _next_customer_id
    with _lock:
        cid = _next_customer_id
        _next_customer_id += 1
        rec = {"id": cid, **data.model_dump()}
        _customers[cid] = rec
        return Customer(**rec)


@app.get("/customers", response_model=List[Customer])
def list_customers():
    with _lock:
        return [Customer(**c) for c in _customers.values()]


@app.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: int):
    with _lock:
        return Customer(**_get_customer(customer_id))


@app.put("/customers/{customer_id}", response_model=Customer)
def update_customer(customer_id: int, data: CustomerIn):
    with _lock:
        _get_customer(customer_id)
        rec = {"id": customer_id, **data.model_dump()}
        _customers[customer_id] = rec
        return Customer(**rec)


@app.post("/customers/{customer_id}/orders", response_model=Order, status_code=201)
def create_order(customer_id: int, data: OrderIn):
    global _next_order_id
    with _lock:
        _get_customer(customer_id)
        oid = _next_order_id
        _next_order_id += 1
        rec = {
            "id": oid,
            "customer_id": customer_id,
            **data.model_dump(),
            "collected": False,
            "collected_on": None,
        }
        _orders[oid] = rec
        return _order_out(rec)


@app.get("/customers/{customer_id}/orders", response_model=List[Order])
def list_customer_orders(customer_id: int):
    with _lock:
        _get_customer(customer_id)
        items = [o for o in _orders.values() if o["customer_id"] == customer_id]
        items.sort(key=lambda o: (o["due_date"], o["id"]))
        return [_order_out(o) for o in items]


@app.get("/orders/due", response_model=List[Order])
def orders_due(on_or_before: date = Query(..., description="YYYY-MM-DD")):
    with _lock:
        items = [
            o for o in _orders.values()
            if not o["collected"] and o["due_date"] <= on_or_before
        ]
        items.sort(key=lambda o: (o["due_date"], o["id"]))
        return [_order_out(o) for o in items]


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: int):
    with _lock:
        return _order_out(_get_order(order_id))


@app.post("/orders/{order_id}/collect", response_model=Order)
def collect_order(order_id: int):
    with _lock:
        o = _get_order(order_id)
        if o["collected"]:
            raise HTTPException(status_code=409, detail="Order already collected")
        o["collected"] = True
        o["collected_on"] = date.today()
        return _order_out(o)

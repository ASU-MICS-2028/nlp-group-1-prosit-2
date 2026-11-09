from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Field as F, Session, SQLModel, create_engine, select


class Customer(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str
    phone: str
    chest: float
    waist: float
    hip: float
    length: float


class Order(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    customer_id: int = F(foreign_key="customer.id", index=True)
    garment: str
    due_date: date
    price: float
    deposit: float
    collected: bool = False


class CustomerIn(BaseModel):
    name: str
    phone: str
    chest: float = Field(gt=0)
    waist: float = Field(gt=0)
    hip: float = Field(gt=0)
    length: float = Field(gt=0)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class OrderIn(BaseModel):
    garment: str
    due_date: date
    price: float = Field(ge=0)
    deposit: float = Field(ge=0)

    @field_validator("garment")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @model_validator(mode="after")
    def deposit_ok(self):
        if self.deposit > self.price:
            raise ValueError("deposit cannot be more than the price")
        return self


engine = create_engine("sqlite:///tailor.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def get_customer_or_404(s, cid):
    c = s.get(Customer, cid)
    if not c:
        raise HTTPException(404, "Customer not found")
    return c


@app.post("/customers", status_code=201)
def create_customer(data: CustomerIn):
    with Session(engine) as s:
        c = Customer(**data.model_dump())
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/customers/{cid}")
def read_customer(cid: int):
    with Session(engine) as s:
        return get_customer_or_404(s, cid)


@app.post("/customers/{cid}/orders", status_code=201)
def create_order(cid: int, data: OrderIn):
    with Session(engine) as s:
        get_customer_or_404(s, cid)
        o = Order(customer_id=cid, **data.model_dump())
        s.add(o)
        s.commit()
        s.refresh(o)
        return o


@app.get("/customers/{cid}/orders")
def customer_orders(cid: int):
    with Session(engine) as s:
        get_customer_or_404(s, cid)
        return s.exec(select(Order).where(Order.customer_id == cid).order_by(Order.id)).all()


@app.get("/orders")
def due_orders(due_on_or_before: date):
    with Session(engine) as s:
        return s.exec(
            select(Order)
            .where(Order.due_date <= due_on_or_before, Order.collected == False)  # noqa: E712
            .order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/{oid}")
def read_order(oid: int):
    with Session(engine) as s:
        o = s.get(Order, oid)
        if not o:
            raise HTTPException(404, "Order not found")
        return o


@app.post("/orders/{oid}/collect")
def collect_order(oid: int):
    with Session(engine) as s:
        o = s.get(Order, oid)
        if not o:
            raise HTTPException(404, "Order not found")
        o.collected = True
        s.add(o)
        s.commit()
        s.refresh(o)
        return o

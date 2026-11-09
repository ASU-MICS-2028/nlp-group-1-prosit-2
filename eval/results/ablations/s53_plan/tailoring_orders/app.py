from contextlib import asynccontextmanager
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField, field_validator, model_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///tailoring.db", connect_args={"check_same_thread": False})


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    chest: float
    waist: float
    hip: float
    length: float


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    garment: str
    due_date: Date = Field(index=True)
    price: float
    deposit: float
    collected: bool = False


class CustomerIn(BaseModel):
    name: str
    phone: str
    chest: float = PField(gt=0)
    waist: float = PField(gt=0)
    hip: float = PField(gt=0)
    length: float = PField(gt=0)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class OrderIn(BaseModel):
    garment: str
    due_date: Date
    price: float = PField(ge=0)
    deposit: float = PField(ge=0)

    @field_validator("garment")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @model_validator(mode="after")
    def deposit_not_over_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit cannot be more than the price")
        return self


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tailoring Shop", lifespan=lifespan)
SQLModel.metadata.create_all(engine)


def _get_customer(session: Session, customer_number: int) -> Customer:
    c = session.get(Customer, customer_number)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


def _get_order(session: Session, order_number: int) -> Order:
    o = session.get(Order, order_number)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return o


@app.post("/customers", status_code=201)
def create_customer(data: CustomerIn) -> Customer:
    with Session(engine) as s:
        c = Customer(**data.model_dump())
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/customers/{customerNumber}")
def get_customer(customerNumber: int) -> Customer:
    with Session(engine) as s:
        return _get_customer(s, customerNumber)


@app.post("/customers/{customerNumber}/orders", status_code=201)
def create_order(customerNumber: int, data: OrderIn) -> Order:
    with Session(engine) as s:
        _get_customer(s, customerNumber)
        o = Order(customer_id=customerNumber, **data.model_dump())
        s.add(o)
        s.commit()
        s.refresh(o)
        return o


@app.get("/customers/{customerNumber}/orders")
def list_customer_orders(customerNumber: int) -> list[Order]:
    with Session(engine) as s:
        _get_customer(s, customerNumber)
        return list(s.exec(select(Order).where(Order.customer_id == customerNumber).order_by(Order.id)).all())


@app.get("/orders/due")
def orders_due(date: Date = Query(...)) -> list[Order]:
    with Session(engine) as s:
        stmt = (
            select(Order)
            .where(Order.collected == False)  # noqa: E712
            .where(Order.due_date <= date)
            .order_by(Order.due_date, Order.id)
        )
        return list(s.exec(stmt).all())


@app.get("/orders/{orderNumber}")
def get_order(orderNumber: int) -> Order:
    with Session(engine) as s:
        return _get_order(s, orderNumber)


@app.post("/orders/{orderNumber}/collected")
def mark_collected(orderNumber: int) -> Order:
    with Session(engine) as s:
        o = _get_order(s, orderNumber)
        o.collected = True
        s.add(o)
        s.commit()
        s.refresh(o)
        return o

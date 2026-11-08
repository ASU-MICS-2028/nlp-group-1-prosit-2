from datetime import date as Date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import text
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
    __tablename__ = "orders"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    garment: str
    tailor: str
    due_date: Date
    price: float
    deposit: float
    collected: bool = False


class CustomerIn(BaseModel):
    name: str
    phone: str
    chest: float
    waist: float
    hip: float
    length: float


class OrderIn(BaseModel):
    garment: str
    tailor: str
    due_date: Date
    price: float
    deposit: float

    @field_validator("tailor")
    @classmethod
    def tailor_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("The tailor's name must be given")
        return v


app = FastAPI(title="Tailoring Shop Orders")


def init_db():
    SQLModel.metadata.create_all(engine)
    # Older database files may lack the tailor column; add it if missing.
    with engine.begin() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(orders)"))]
        if "tailor" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN tailor VARCHAR NOT NULL DEFAULT ''"))


@app.on_event("startup")
def on_startup():
    init_db()


init_db()


@app.post("/customers", status_code=201, response_model=Customer)
def create_customer(data: CustomerIn):
    with Session(engine) as s:
        c = Customer(**data.model_dump())
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.post("/customers/{customerId}/orders", status_code=201, response_model=Order)
def create_order(customerId: int, data: OrderIn):
    with Session(engine) as s:
        if not s.get(Customer, customerId):
            raise HTTPException(404, "Customer not found")
        if data.deposit > data.price:
            raise HTTPException(422, "Deposit cannot be more than the price")
        o = Order(customer_id=customerId, collected=False, **data.model_dump())
        s.add(o)
        s.commit()
        s.refresh(o)
        return o


@app.get("/customers/{customerId}/orders", response_model=List[Order])
def customer_orders(customerId: int):
    with Session(engine) as s:
        if not s.get(Customer, customerId):
            raise HTTPException(404, "Customer not found")
        return s.exec(select(Order).where(Order.customer_id == customerId).order_by(Order.id)).all()


@app.get("/orders/due", response_model=List[Order])
def orders_due(date: Date = Query(...)):
    with Session(engine) as s:
        return s.exec(
            select(Order)
            .where(Order.due_date <= date, Order.collected == False)  # noqa: E712
            .order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/{orderId}", response_model=Order)
def get_order(orderId: int):
    with Session(engine) as s:
        o = s.get(Order, orderId)
        if not o:
            raise HTTPException(404, "Order not found")
        return o


@app.patch("/orders/{orderId}/collected", response_model=Order)
def mark_collected(orderId: int):
    with Session(engine) as s:
        o = s.get(Order, orderId)
        if not o:
            raise HTTPException(404, "Order not found")
        o.collected = True
        s.add(o)
        s.commit()
        s.refresh(o)
        return o

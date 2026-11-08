from contextlib import asynccontextmanager
from datetime import date
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
    due_date: date
    price: float
    deposit: float
    collected: bool = False


class CustomerIn(BaseModel):
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)
    chest: float = PField(gt=0)
    waist: float = PField(gt=0)
    hip: float = PField(gt=0)
    length: float = PField(gt=0)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class OrderIn(BaseModel):
    garment: str = PField(min_length=1)
    due_date: date
    price: float = PField(ge=0)
    deposit: float = PField(default=0, ge=0)

    @field_validator("garment")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def deposit_le_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit cannot be more than the price")
        return self


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tailoring Shop Orders", lifespan=lifespan)


def _customer_or_404(session: Session, customer_id: int) -> Customer:
    c = session.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@app.post("/customers", status_code=201, response_model=Customer)
def create_customer(data: CustomerIn):
    with Session(engine) as s:
        c = Customer(**data.model_dump())
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: int):
    with Session(engine) as s:
        return _customer_or_404(s, customer_id)


@app.post("/customers/{customer_id}/orders", status_code=201, response_model=Order)
def create_order(customer_id: int, data: OrderIn):
    with Session(engine) as s:
        _customer_or_404(s, customer_id)
        o = Order(customer_id=customer_id, **data.model_dump())
        s.add(o)
        s.commit()
        s.refresh(o)
        return o


@app.get("/customers/{customer_id}/orders", response_model=list[Order])
def customer_orders(customer_id: int):
    with Session(engine) as s:
        _customer_or_404(s, customer_id)
        return s.exec(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/due", response_model=list[Order])
def due_orders(on_or_before: date = Query(..., description="YYYY-MM-DD")):
    with Session(engine) as s:
        return s.exec(
            select(Order)
            .where(Order.due_date <= on_or_before, Order.collected == False)  # noqa: E712
            .order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: int):
    with Session(engine) as s:
        o = s.get(Order, order_id)
        if not o:
            raise HTTPException(status_code=404, detail="Order not found")
        return o


@app.post("/orders/{order_id}/collect", response_model=Order)
def collect_order(order_id: int):
    with Session(engine) as s:
        o = s.get(Order, order_id)
        if not o:
            raise HTTPException(status_code=404, detail="Order not found")
        if o.collected:
            raise HTTPException(status_code=409, detail="Order already collected")
        o.collected = True
        s.add(o)
        s.commit()
        s.refresh(o)
        return o

from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import field_validator, model_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///tailor.db", connect_args={"check_same_thread": False})


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
    due_date: date = Field(index=True)
    price: float
    deposit: float
    collected: bool = False


class CustomerCreate(SQLModel):
    name: str
    phone: str
    chest: float = Field(gt=0)
    waist: float = Field(gt=0)
    hip: float = Field(gt=0)
    length: float = Field(gt=0)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class MeasurementsUpdate(SQLModel):
    chest: Optional[float] = Field(default=None, gt=0)
    waist: Optional[float] = Field(default=None, gt=0)
    hip: Optional[float] = Field(default=None, gt=0)
    length: Optional[float] = Field(default=None, gt=0)


class OrderCreate(SQLModel):
    garment: str
    due_date: date
    price: float = Field(ge=0)
    deposit: float = Field(default=0, ge=0)

    @field_validator("garment")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @model_validator(mode="after")
    def deposit_not_more_than_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit cannot be more than the price")
        return self


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tailoring Shop Orders", lifespan=lifespan)


@app.post("/customers", response_model=Customer, status_code=201)
def create_customer(data: CustomerCreate):
    with Session(engine) as s:
        c = Customer(**data.model_dump())
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.patch("/customers/{customerId}", response_model=Customer)
def update_measurements(customerId: int, data: MeasurementsUpdate):
    with Session(engine) as s:
        c = s.get(Customer, customerId)
        if not c:
            raise HTTPException(404, "Customer not found")
        for k, v in data.model_dump(exclude_unset=True).items():
            if v is None:
                raise HTTPException(422, f"{k} cannot be empty")
            setattr(c, k, v)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.post("/customers/{customerId}/orders", response_model=Order, status_code=201)
def create_order(customerId: int, data: OrderCreate):
    with Session(engine) as s:
        if not s.get(Customer, customerId):
            raise HTTPException(404, "Customer not found")
        o = Order(customer_id=customerId, **data.model_dump())
        s.add(o)
        s.commit()
        s.refresh(o)
        return o


@app.get("/customers/{customerId}/orders", response_model=List[Order])
def customer_orders(customerId: int):
    with Session(engine) as s:
        if not s.get(Customer, customerId):
            raise HTTPException(404, "Customer not found")
        return s.exec(
            select(Order).where(Order.customer_id == customerId).order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/due", response_model=List[Order])
def orders_due(date_: date = Query(..., alias="date")):
    with Session(engine) as s:
        return s.exec(
            select(Order)
            .where(Order.due_date <= date_, Order.collected == False)  # noqa: E712
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

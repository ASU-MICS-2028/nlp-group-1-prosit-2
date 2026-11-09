from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import field_validator, model_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///tailoring.db", connect_args={"check_same_thread": False})


class CustomerIn(SQLModel):
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


class Customer(CustomerIn, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class OrderIn(SQLModel):
    garment: str
    due_date: date
    price: float = Field(ge=0)
    deposit: float = Field(ge=0)

    @field_validator("garment")
    @classmethod
    def garment_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @model_validator(mode="after")
    def deposit_not_more_than_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit can not be more than the price")
        return self


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    garment: str
    due_date: date = Field(index=True)
    price: float
    deposit: float
    collected: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tailoring Shop", lifespan=lifespan)


def get_customer_or_404(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.post("/customers", response_model=Customer, status_code=201)
def create_customer(data: CustomerIn):
    with Session(engine) as session:
        customer = Customer.model_validate(data)
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return customer


@app.get("/customers/{customer_id}", response_model=Customer)
def read_customer(customer_id: int):
    with Session(engine) as session:
        return get_customer_or_404(session, customer_id)


@app.put("/customers/{customer_id}", response_model=Customer)
def update_customer(customer_id: int, data: CustomerIn):
    with Session(engine) as session:
        customer = get_customer_or_404(session, customer_id)
        for key, value in data.model_dump().items():
            setattr(customer, key, value)
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return customer


@app.post("/customers/{customer_id}/orders", response_model=Order, status_code=201)
def create_order(customer_id: int, data: OrderIn):
    with Session(engine) as session:
        get_customer_or_404(session, customer_id)
        order = Order(customer_id=customer_id, **data.model_dump())
        session.add(order)
        session.commit()
        session.refresh(order)
        return order


@app.get("/customers/{customer_id}/orders", response_model=List[Order])
def list_customer_orders(customer_id: int):
    with Session(engine) as session:
        get_customer_or_404(session, customer_id)
        return session.exec(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/due", response_model=List[Order])
def orders_due(on_or_before: date = Query(..., description="YYYY-MM-DD")):
    with Session(engine) as session:
        return session.exec(
            select(Order)
            .where(Order.due_date <= on_or_before, Order.collected == False)  # noqa: E712
            .order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/{order_id}", response_model=Order)
def read_order(order_id: int):
    with Session(engine) as session:
        order = session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order


@app.post("/orders/{order_id}/collect", response_model=Order)
def collect_order(order_id: int):
    with Session(engine) as session:
        order = session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.collected:
            raise HTTPException(status_code=409, detail="Order already collected")
        order.collected = True
        session.add(order)
        session.commit()
        session.refresh(order)
        return order

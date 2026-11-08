from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field as PField, field_validator, model_validator
from sqlmodel import SQLModel, Field, Session, create_engine, select

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
    due_date: date
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
    def deposit_not_more_than_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit cannot be more than the price")
        return self


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Tailoring Shop Orders", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


def find_customer(session: Session, customer_id: int) -> Customer:
    c = session.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@app.post("/customers", response_model=Customer, status_code=201)
def create_customer(data: CustomerIn, session: Session = Depends(get_session)):
    c = Customer(**data.model_dump())
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@app.get("/customers", response_model=List[Customer])
def list_customers(session: Session = Depends(get_session)):
    return session.exec(select(Customer).order_by(Customer.name)).all()


@app.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: int, session: Session = Depends(get_session)):
    return find_customer(session, customer_id)


@app.post("/customers/{customer_id}/orders", response_model=Order, status_code=201)
def create_order(customer_id: int, data: OrderIn, session: Session = Depends(get_session)):
    find_customer(session, customer_id)
    o = Order(customer_id=customer_id, **data.model_dump())
    session.add(o)
    session.commit()
    session.refresh(o)
    return o


@app.get("/customers/{customer_id}/orders", response_model=List[Order])
def customer_orders(customer_id: int, session: Session = Depends(get_session)):
    find_customer(session, customer_id)
    return session.exec(
        select(Order).where(Order.customer_id == customer_id).order_by(Order.due_date, Order.id)
    ).all()


@app.get("/orders/due", response_model=List[Order])
def orders_due(on_or_before: date, session: Session = Depends(get_session)):
    return session.exec(
        select(Order)
        .where(Order.due_date <= on_or_before, Order.collected == False)  # noqa: E712
        .order_by(Order.due_date, Order.id)
    ).all()


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: int, session: Session = Depends(get_session)):
    o = session.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return o


@app.post("/orders/{order_id}/collect", response_model=Order)
def collect_order(order_id: int, session: Session = Depends(get_session)):
    o = session.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.collected:
        raise HTTPException(status_code=409, detail="Order already collected")
    o.collected = True
    session.add(o)
    session.commit()
    session.refresh(o)
    return o

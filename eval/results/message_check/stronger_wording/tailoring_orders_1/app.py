from datetime import date as Date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
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


app = FastAPI(title="Tailoring Shop Orders")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def get_customer_or_404(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.post("/customers", status_code=201, response_model=Customer)
def create_customer(data: CustomerIn):
    with Session(engine) as session:
        customer = Customer(**data.model_dump())
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return customer


@app.post("/customers/{customerId}/orders", status_code=201, response_model=Order)
def create_order(customerId: int, data: OrderIn):
    with Session(engine) as session:
        get_customer_or_404(session, customerId)
        if not data.tailor.strip():
            raise HTTPException(status_code=422, detail="The tailor's name is required")
        if data.deposit > data.price:
            raise HTTPException(status_code=400, detail="Deposit cannot be more than the price")
        order = Order(customer_id=customerId, **data.model_dump(), collected=False)
        session.add(order)
        session.commit()
        session.refresh(order)
        return order


@app.get("/customers/{customerId}/orders", response_model=List[Order])
def list_customer_orders(customerId: int):
    with Session(engine) as session:
        get_customer_or_404(session, customerId)
        return session.exec(
            select(Order).where(Order.customer_id == customerId).order_by(Order.id)
        ).all()


@app.get("/orders/due", response_model=List[Order])
def orders_due(date: Date = Query(...)):
    with Session(engine) as session:
        return session.exec(
            select(Order)
            .where(Order.due_date <= date, Order.collected == False)  # noqa: E712
            .order_by(Order.due_date, Order.id)
        ).all()


@app.get("/orders/{orderId}", response_model=Order)
def get_order(orderId: int):
    with Session(engine) as session:
        order = session.get(Order, orderId)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order


@app.patch("/orders/{orderId}/collected", response_model=Order)
def mark_collected(orderId: int):
    with Session(engine) as session:
        order = session.get(Order, orderId)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        order.collected = True
        session.add(order)
        session.commit()
        session.refresh(order)
        return order

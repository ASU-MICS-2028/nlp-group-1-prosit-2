from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import model_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///tailoring.db", connect_args={"check_same_thread": False})


# ---------- Customers ----------
class CustomerIn(SQLModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    chest: float = Field(gt=0, description="inches")
    waist: float = Field(gt=0, description="inches")
    hip: float = Field(gt=0, description="inches")
    length: float = Field(gt=0, description="inches")


class Customer(CustomerIn, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


# ---------- Orders ----------
class OrderIn(SQLModel):
    garment: str = Field(min_length=1)
    due_date: date
    price: float = Field(ge=0, description="cedis")
    deposit: float = Field(default=0, ge=0, description="cedis")

    @model_validator(mode="after")
    def deposit_not_more_than_price(self):
        if self.deposit > self.price:
            raise ValueError("The deposit cannot be more than the price")
        return self


class Order(SQLModel, table=True):
    __tablename__ = "orders"
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


def _get_customer(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _get_order(session: Session, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/customers", response_model=Customer, status_code=201)
def create_customer(data: CustomerIn):
    with Session(engine) as session:
        customer = Customer.model_validate(data)
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return customer


@app.get("/customers", response_model=List[Customer])
def list_customers():
    with Session(engine) as session:
        return session.exec(select(Customer).order_by(Customer.id)).all()


@app.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: int):
    with Session(engine) as session:
        return _get_customer(session, customer_id)


@app.post("/customers/{customer_id}/orders", response_model=Order, status_code=201)
def create_order(customer_id: int, data: OrderIn):
    with Session(engine) as session:
        _get_customer(session, customer_id)
        order = Order(customer_id=customer_id, **data.model_dump())
        session.add(order)
        session.commit()
        session.refresh(order)
        return order


@app.get("/customers/{customer_id}/orders", response_model=List[Order])
def list_customer_orders(customer_id: int):
    with Session(engine) as session:
        _get_customer(session, customer_id)
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
def get_order(order_id: int):
    with Session(engine) as session:
        return _get_order(session, order_id)


@app.post("/orders/{order_id}/collect", response_model=Order)
def collect_order(order_id: int):
    with Session(engine) as session:
        order = _get_order(session, order_id)
        order.collected = True
        session.add(order)
        session.commit()
        session.refresh(order)
        return order

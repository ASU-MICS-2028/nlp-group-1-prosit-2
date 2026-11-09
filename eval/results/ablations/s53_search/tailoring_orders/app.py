from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import model_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///tailoring.db", connect_args={"check_same_thread": False})


class CustomerIn(SQLModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    chest: float = Field(ge=0)
    waist: float = Field(ge=0)
    hip: float = Field(ge=0)
    length: float = Field(ge=0)


class Customer(CustomerIn, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class OrderIn(SQLModel):
    garment: str = Field(min_length=1)
    due_date: date
    price: float = Field(ge=0)
    deposit: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def deposit_not_above_price(self):
        if self.deposit > self.price:
            raise ValueError("deposit cannot be more than the price")
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
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


def get_session():
    with Session(engine) as s:
        yield s


def get_customer_or_404(s, customer_id):
    c = s.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    return c


@app.post("/customers", status_code=201, response_model=Customer)
def create_customer(data: CustomerIn, s: Session = Depends(get_session)):
    c = Customer.model_validate(data)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


@app.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: int, s: Session = Depends(get_session)):
    return get_customer_or_404(s, customer_id)


@app.post("/customers/{customer_id}/orders", status_code=201, response_model=Order)
def create_order(customer_id: int, data: OrderIn, s: Session = Depends(get_session)):
    get_customer_or_404(s, customer_id)
    o = Order(customer_id=customer_id, **data.model_dump())
    s.add(o)
    s.commit()
    s.refresh(o)
    return o


@app.get("/customers/{customer_id}/orders", response_model=list[Order])
def customer_orders(customer_id: int, s: Session = Depends(get_session)):
    get_customer_or_404(s, customer_id)
    return s.exec(select(Order).where(Order.customer_id == customer_id).order_by(Order.due_date, Order.id)).all()


@app.get("/orders/due", response_model=list[Order])
def orders_due(by: date, s: Session = Depends(get_session)):
    return s.exec(
        select(Order).where(Order.due_date <= by, Order.collected == False).order_by(Order.due_date, Order.id)  # noqa: E712
    ).all()


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: int, s: Session = Depends(get_session)):
    o = s.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@app.post("/orders/{order_id}/collect", response_model=Order)
def collect_order(order_id: int, s: Session = Depends(get_session)):
    o = s.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Order not found")
    o.collected = True
    s.add(o)
    s.commit()
    s.refresh(o)
    return o

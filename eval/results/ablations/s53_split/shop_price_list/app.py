import math
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float


def check_price(v: Any) -> float:
    if v is None:
        raise ValueError("price is required")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("price must be a number")
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        raise ValueError("price must be a number")
    if v < 0:
        raise ValueError("price must not be less than zero")
    return v


class ItemCreate(BaseModel):
    model_config = ConfigDict(validate_default=True)
    name: Any = None
    price: Any = None

    @field_validator("name", mode="before")
    @classmethod
    def name_ok(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("name is required")
        return v.strip()

    @field_validator("price", mode="before")
    @classmethod
    def price_ok(cls, v):
        return check_price(v)


class PriceChange(BaseModel):
    model_config = ConfigDict(validate_default=True)
    price: Any = None

    @field_validator("price", mode="before")
    @classmethod
    def price_ok(cls, v):
        return check_price(v)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shop price list", lifespan=lifespan)
SQLModel.metadata.create_all(engine)


def get_or_404(session: Session, number: int) -> Item:
    item = session.get(Item, number)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", status_code=201, response_model=Item)
def add_item(data: ItemCreate):
    with Session(engine) as session:
        item = Item(name=data.name, price=data.price)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/{number}", response_model=Item)
def get_item(number: int):
    with Session(engine) as session:
        return get_or_404(session, number)


@app.patch("/items/{number}", response_model=Item)
def change_price(number: int, data: PriceChange):
    with Session(engine) as session:
        item = get_or_404(session, number)
        item.price = data.price
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.delete("/items/{number}")
def remove_item(number: int):
    with Session(engine) as session:
        item = get_or_404(session, number)
        session.delete(item)
        session.commit()
        return {"detail": "Item removed", "id": number}

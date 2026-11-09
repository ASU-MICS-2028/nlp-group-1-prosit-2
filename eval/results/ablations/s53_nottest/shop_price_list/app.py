from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    price: float


class ItemIn(BaseModel):
    name: str
    price: float

    @field_validator("name")
    @classmethod
    def name_ok(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("price")
    @classmethod
    def price_ok(cls, v):
        if v < 0:
            raise ValueError("price must not be negative")
        return v


class PriceIn(BaseModel):
    price: float

    @field_validator("price")
    @classmethod
    def price_ok(cls, v):
        if v < 0:
            raise ValueError("price must not be negative")
        return v


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


def name_taken(session, name, exclude_id=None):
    for it in session.exec(select(Item)).all():
        if it.name.lower() == name.lower() and it.id != exclude_id:
            return True
    return False


@app.post("/items", status_code=201)
def add_item(data: ItemIn):
    with Session(engine) as s:
        if name_taken(s, data.name):
            raise HTTPException(409, "An item with this name is already on the list")
        item = Item(name=data.name, price=data.price)
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.get("/items")
def list_items():
    with Session(engine) as s:
        return s.exec(select(Item).order_by(Item.name)).all()


@app.get("/items/{item_id}")
def get_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item


@app.patch("/items/{item_id}")
def change_price(item_id: int, data: PriceIn):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        item.price = data.price
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.delete("/items/{item_id}")
def remove_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        s.delete(item)
        s.commit()
        return {"deleted": item_id}

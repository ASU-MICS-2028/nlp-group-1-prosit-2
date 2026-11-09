from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
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
        if v != v or v in (float("inf"), float("-inf")) or v < 0:
            raise ValueError("price must be zero or more")
        return v


SQLModel.metadata.create_all(engine)

app = FastAPI()


@app.post("/items", status_code=201)
def add_item(data: ItemIn):
    with Session(engine) as s:
        item = Item(name=data.name, price=data.price)
        s.add(item)
        s.commit()
        s.refresh(item)
        return item.model_dump()


@app.get("/items")
def list_items():
    with Session(engine) as s:
        return [i.model_dump() for i in s.exec(select(Item).order_by(Item.id)).all()]


@app.get("/items/{item_id}")
def get_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item.model_dump()


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        s.delete(item)
        s.commit()
        return {"detail": "Item removed"}

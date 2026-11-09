from typing import Optional
from fastapi import FastAPI, HTTPException
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
            raise ValueError("name required")
        return v

    @field_validator("price")
    @classmethod
    def price_ok(cls, v):
        if v != v or v < 0 or v == float("inf"):
            raise ValueError("price must be zero or more")
        return v


class PriceIn(BaseModel):
    price: float

    @field_validator("price")
    @classmethod
    def price_ok(cls, v):
        if v != v or v < 0 or v == float("inf"):
            raise ValueError("price must be zero or more")
        return v


SQLModel.metadata.create_all(engine)
app = FastAPI()


def get_or_404(s, item_id):
    item = s.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return item


@app.post("/items", status_code=201)
def add_item(body: ItemIn):
    with Session(engine) as s:
        item = Item(name=body.name, price=body.price)
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.get("/items")
def list_items():
    with Session(engine) as s:
        return s.exec(select(Item)).all()


@app.get("/items/{item_id}")
def get_item(item_id: int):
    with Session(engine) as s:
        return get_or_404(s, item_id)


@app.put("/items/{item_id}")
def update_price(item_id: int, body: PriceIn):
    with Session(engine) as s:
        item = get_or_404(s, item_id)
        item.price = body.price
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    with Session(engine) as s:
        item = get_or_404(s, item_id)
        s.delete(item)
        s.commit()
        return {"detail": "Item removed"}

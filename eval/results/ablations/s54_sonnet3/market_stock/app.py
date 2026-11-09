from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SField, Session, SQLModel, create_engine, select


class Item(SQLModel, table=True):
    id: Optional[int] = SField(default=None, primary_key=True)
    name: str
    quantity: int
    low_level: int


class ItemIn(BaseModel):
    name: str
    quantity: int = Field(ge=0)
    low_level: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class Amount(BaseModel):
    amount: int = Field(gt=0)


engine = create_engine("sqlite:///stock.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def get_or_404(session, item_id):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", status_code=201)
def create_item(data: ItemIn):
    with Session(engine) as s:
        item = Item(**data.model_dump())
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.get("/items")
def list_items():
    with Session(engine) as s:
        return s.exec(select(Item)).all()


@app.get("/items/low")
def low_items():
    with Session(engine) as s:
        return s.exec(select(Item).where(Item.quantity <= Item.low_level)).all()


@app.get("/items/{item_id}")
def get_item(item_id: int):
    with Session(engine) as s:
        return get_or_404(s, item_id)


@app.post("/items/{item_id}/sell")
def sell(item_id: int, data: Amount):
    with Session(engine) as s:
        item = get_or_404(s, item_id)
        if data.amount > item.quantity:
            raise HTTPException(status_code=400, detail="Not enough stock to sell")
        item.quantity -= data.amount
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.post("/items/{item_id}/restock")
def restock(item_id: int, data: Amount):
    with Session(engine) as s:
        item = get_or_404(s, item_id)
        item.quantity += data.amount
        s.add(item)
        s.commit()
        s.refresh(item)
        return item

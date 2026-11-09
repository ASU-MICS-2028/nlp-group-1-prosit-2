from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as F, Session, SQLModel, create_engine, select, update

engine = create_engine("sqlite:///stock.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str
    quantity: int
    low_level: int


class ItemIn(BaseModel):
    name: str = Field(min_length=1, pattern=r".*\S.*")
    quantity: int = Field(ge=0)
    low_level: int = Field(ge=0)


class Amount(BaseModel):
    amount: int = Field(gt=0)


SQLModel.metadata.create_all(engine)
app = FastAPI()


def get_or_404(s: Session, item_id: int) -> Item:
    item = s.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
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


@app.get("/items/low-stock")
def low_stock():
    with Session(engine) as s:
        return s.exec(select(Item).where(Item.quantity <= Item.low_level)).all()


@app.get("/items/{item_id}")
def read_item(item_id: int):
    with Session(engine) as s:
        return get_or_404(s, item_id)


@app.post("/items/{item_id}/sell")
def sell(item_id: int, data: Amount):
    with Session(engine) as s:
        get_or_404(s, item_id)
        # atomic conditional update so we never go below zero
        res = s.exec(
            update(Item)
            .where(Item.id == item_id, Item.quantity >= data.amount)
            .values(quantity=Item.quantity - data.amount)
        )
        s.commit()
        if res.rowcount == 0:
            raise HTTPException(409, "Not enough stock to sell that amount")
        return s.get(Item, item_id)


@app.post("/items/{item_id}/restock")
def restock(item_id: int, data: Amount):
    with Session(engine) as s:
        get_or_404(s, item_id)
        s.exec(
            update(Item)
            .where(Item.id == item_id)
            .values(quantity=Item.quantity + data.amount)
        )
        s.commit()
        return s.get(Item, item_id)

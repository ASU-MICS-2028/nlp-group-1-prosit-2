from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, StrictStr
from sqlmodel import Field, Session, SQLModel, create_engine, select, update

engine = create_engine("sqlite:///stock.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    quantity: int
    low_level: int


class ItemCreate(BaseModel):
    name: StrictStr
    quantity: StrictInt
    low_level: StrictInt


class Amount(BaseModel):
    amount: StrictInt


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


def get_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", status_code=201)
def create_item(data: ItemCreate) -> Item:
    with Session(engine) as session:
        item = Item(name=data.name, quantity=data.quantity, low_level=data.low_level)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items")
def list_items() -> list[Item]:
    with Session(engine) as session:
        return list(session.exec(select(Item).order_by(Item.id)))


@app.get("/items/low")
def low_items() -> list[Item]:
    with Session(engine) as session:
        return list(session.exec(select(Item).where(Item.quantity <= Item.low_level).order_by(Item.id)))


@app.get("/items/{item_id}")
def get_item(item_id: int) -> Item:
    with Session(engine) as session:
        return get_or_404(session, item_id)


@app.post("/items/{item_id}/sell")
def sell_item(item_id: int, data: Amount) -> Item:
    if data.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be more than zero")
    with Session(engine) as session:
        get_or_404(session, item_id)
        result = session.exec(
            update(Item)
            .where(Item.id == item_id, Item.quantity >= data.amount)
            .values(quantity=Item.quantity - data.amount)
        )
        if result.rowcount == 0:
            session.rollback()
            raise HTTPException(status_code=409, detail="Cannot sell more than you have")
        session.commit()
        session.expire_all()
        return get_or_404(session, item_id)


@app.post("/items/{item_id}/restock")
def restock_item(item_id: int, data: Amount) -> Item:
    if data.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be more than zero")
    with Session(engine) as session:
        get_or_404(session, item_id)
        session.exec(
            update(Item).where(Item.id == item_id).values(quantity=Item.quantity + data.amount)
        )
        session.commit()
        session.expire_all()
        return get_or_404(session, item_id)
